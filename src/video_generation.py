import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.parse
from typing import Any, Callable, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from gtts import gTTS
from langchain_openai import ChatOpenAI

load_dotenv()

OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "xiaomi/mimo-v2-flash:free")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

POLLINATIONS_MODEL = os.getenv("POLLINATIONS_MODEL", "")
POLLINATIONS_TOKEN = os.getenv("POLLINATIONS_TOKEN", "")
CLOUDINARY_CLOUD = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", None)

IMAGE_GEN_MAX_RETRIES = int(os.getenv("IMAGE_GEN_MAX_RETRIES", "5"))
IMAGE_GEN_RETRY_DELAY_SEC = float(os.getenv("IMAGE_GEN_RETRY_DELAY_SEC", "2"))
VIDEO_SHOT_COUNT = int(os.getenv("VIDEO_SHOT_COUNT", "8"))
VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "1080"))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1920"))
TTS_LANG = os.getenv("TTS_LANG", "en")


def _extract_json_block(text: str) -> Any:
    if "```" in text:
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    match = re.search(r"\[.*\]|\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON found in response")
    return json.loads(match.group(0))


def _fetch_pollinations_bytes(prompt: str) -> bytes:
    if not POLLINATIONS_TOKEN:
        raise RuntimeError("POLLINATIONS_TOKEN missing")
    if not POLLINATIONS_MODEL:
        raise RuntimeError("POLLINATIONS_MODEL missing")
    safe_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?nologo=true&model={POLLINATIONS_MODEL}"
    headers = {"Authorization": f"Bearer {POLLINATIONS_TOKEN}"}
    resp = requests.get(url, headers=headers, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Pollinations failed: {resp.status_code} {resp.text[:200]}")
    return resp.content


def _sign_cloudinary(params: dict, api_secret: str) -> str:
    sorted_items = sorted((k, v) for k, v in params.items() if v is not None)
    to_sign = "&".join([f"{k}={v}" for k, v in sorted_items]) + api_secret
    return hashlib.sha1(to_sign.encode("utf-8")).hexdigest()


def _upload_video_cloudinary(video_path: str) -> str:
    if not (CLOUDINARY_CLOUD and CLOUDINARY_KEY and CLOUDINARY_SECRET):
        raise RuntimeError("Cloudinary credentials missing")
    timestamp = int(time.time())
    params = {"timestamp": timestamp}
    if CLOUDINARY_FOLDER:
        params["folder"] = CLOUDINARY_FOLDER
    signature = _sign_cloudinary(params, CLOUDINARY_SECRET)
    upload_url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD}/video/upload"
    with open(video_path, "rb") as f:
        files = {"file": f}
        data = {"timestamp": timestamp, "api_key": CLOUDINARY_KEY, "signature": signature}
        if CLOUDINARY_FOLDER:
            data["folder"] = CLOUDINARY_FOLDER
        resp = requests.post(upload_url, data=data, files=files, timeout=120)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Cloudinary video upload failed: {resp.status_code} {resp.text[:200]}")
    secure_url = resp.json().get("secure_url")
    if not secure_url:
        raise RuntimeError(f"Unexpected Cloudinary response: {resp.text[:200]}")
    return secure_url


def _generate_tts_mp3(text: str, mp3_path: str) -> None:
    tts = gTTS(text=text, lang=TTS_LANG, slow=False)
    tts.save(mp3_path)


def _audio_duration_seconds(audio_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="ignore")[:200])
    return float(result.stdout.decode("utf-8").strip())


def _run_ffmpeg(cmd: List[str]) -> None:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="ignore")[:500])


def _format_srt_time(seconds: float) -> str:
    millis = int(seconds * 1000)
    hours = millis // 3600000
    minutes = (millis % 3600000) // 60000
    secs = (millis % 60000) // 1000
    ms = millis % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _write_srt(entries: List[Tuple[float, float, str]], srt_path: str) -> None:
    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, (start, end, text) in enumerate(entries, start=1):
            f.write(f"{idx}\n")
            f.write(f"{_format_srt_time(start)} --> {_format_srt_time(end)}\n")
            f.write(text.strip() + "\n\n")


def _escape_ffmpeg_path(path: str) -> str:
    return path.replace("\\", "\\\\").replace(":", "\\:")


def _build_drawtext_filter(entries: List[Tuple[float, float, str]], tmpdir: str) -> str:
    filters = []
    for i, (start, end, text) in enumerate(entries):
        textfile = os.path.join(tmpdir, f"caption_{i + 1}.txt")
        with open(textfile, "w", encoding="utf-8") as f:
            f.write(text.strip())
        tf = _escape_ffmpeg_path(textfile)
        filters.append(
            "drawtext="
            f"textfile={tf}:"
            "fontcolor=white:fontsize=42:borderw=3:bordercolor=black@0.9:"
            "box=1:boxcolor=black@0.35:boxborderw=16:"
            "x=(w-text_w)/2:y=h-360:"
            "line_spacing=8:wrap=1:"
            f"enable='between(t,{start:.2f},{end:.2f})'"
        )
    return ",".join(filters)


def generate_trending_script(prompt: str, shot_count: int) -> List[dict]:
    llm = ChatOpenAI(
        temperature=0.7,
        model=OPENROUTER_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
    )
    system = (
        "You are an expert short-form video editor for high-retention content. "
        "Create a viral, fast-paced script for a trending social video. "
        "Avoid anything about flags; focus on the user's topic, hooks, and punchy pacing."
    )
    prompt_text = f"""
Generate exactly {shot_count} shots for a 9:16 trending short-form video about:
{prompt}

Rules:
- Each shot has a short narration (1 sentence max).
- Each visualPrompt is a single-frame description with cinematic camera cues.
- Duration approx 3-5 seconds.

Return JSON array only with objects:
{{"narration": "...", "visualPrompt": "...", "durationApprox": 4}}
"""
    response = llm.invoke(f"{system}\n\n{prompt_text}")
    output = response.content if hasattr(response, "content") else str(response)
    data = _extract_json_block(output)
    if not isinstance(data, list):
        raise RuntimeError("Script generation did not return an array")
    return data


def generate_video_from_prompt(
    prompt: str,
    shot_count: int | None = None,
    progress_cb: Optional[Callable[[dict], None]] = None,
) -> dict:
    shots = shot_count or VIDEO_SHOT_COUNT
    if progress_cb:
        progress_cb({"status": "scripting", "script_ready": 0, "script_total": shots, "frames_ready": 0, "frames_total": shots})
    scenes = generate_trending_script(prompt, shots)
    if not scenes:
        raise RuntimeError("No scenes generated")
    if progress_cb:
        progress_cb({"status": "script_ready", "script_ready": shots, "script_total": shots, "frames_ready": 0, "frames_total": shots})

    with tempfile.TemporaryDirectory() as tmpdir:
        segment_paths: List[str] = []
        caption_entries: List[Tuple[float, float, str]] = []
        current_time = 0.0

        for idx, scene in enumerate(scenes):
            narration = scene.get("narration", "").strip()
            visual_prompt = scene.get("visualPrompt", "").strip()
            if not narration or not visual_prompt:
                raise RuntimeError("Scene missing narration or visualPrompt")

            # Pollinations image with retries
            attempt = 0
            while True:
                attempt += 1
                try:
                    img_prompt = (
                        f"{visual_prompt}. Vertical 9:16 (1080x1920), full-frame, no borders or padding, "
                        "cinematic, high contrast, trending short-form style."
                    )
                    img_bytes = _fetch_pollinations_bytes(img_prompt)
                    break
                except Exception as e:
                    if attempt >= IMAGE_GEN_MAX_RETRIES:
                        raise RuntimeError(f"Image generation failed for scene {idx + 1}: {e}")
                    time.sleep(IMAGE_GEN_RETRY_DELAY_SEC)

            image_path = os.path.join(tmpdir, f"scene_{idx + 1}.jpg")
            with open(image_path, "wb") as f:
                f.write(img_bytes)

            audio_path = os.path.join(tmpdir, f"scene_{idx + 1}.mp3")
            _generate_tts_mp3(narration, audio_path)
            duration = _audio_duration_seconds(audio_path)
            caption_entries.append((current_time, current_time + duration, narration))
            current_time += duration

            segment_path = os.path.join(tmpdir, f"segment_{idx + 1}.mp4")
            vf = (
                f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}"
            )
            cmd = [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                image_path,
                "-i",
                audio_path,
                "-t",
                f"{max(duration, 0.5):.2f}",
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                segment_path,
            ]
            _run_ffmpeg(cmd)
            segment_paths.append(segment_path)
            if progress_cb:
                progress_cb({"status": "rendering", "frames_ready": idx + 1, "frames_total": shots})

        concat_list = os.path.join(tmpdir, "concat.txt")
        with open(concat_list, "w") as f:
            for seg in segment_paths:
                f.write(f"file '{seg}'\n")

        output_path = os.path.join(tmpdir, "final.mp4")
        concat_cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_list,
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            output_path,
        ]
        _run_ffmpeg(concat_cmd)

        # Add captions (best-effort)
        captioned_path = output_path
        captions_applied = False
        try:
            srt_path = os.path.join(tmpdir, "captions.srt")
            _write_srt(caption_entries, srt_path)
            escaped = _escape_ffmpeg_path(srt_path)
            vf = (
                f"subtitles={escaped}:force_style="
                "FontName=Arial,FontSize=42,OutlineColour=&H000000&,BorderStyle=3,Outline=2,Shadow=0,"
                "Alignment=2,MarginV=240"
            )
            captioned_path = os.path.join(tmpdir, "final_captioned.mp4")
            caption_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                output_path,
                "-vf",
                vf,
                "-c:a",
                "copy",
                captioned_path,
            ]
            _run_ffmpeg(caption_cmd)
            captions_applied = True
        except Exception as e:
            print(f"SRT captions failed, trying drawtext: {e}")
            try:
                drawtext_filter = _build_drawtext_filter(caption_entries, tmpdir)
                captioned_path = os.path.join(tmpdir, "final_captioned_drawtext.mp4")
                caption_cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    output_path,
                    "-vf",
                    drawtext_filter,
                    "-c:a",
                    "copy",
                    captioned_path,
                ]
                _run_ffmpeg(caption_cmd)
                captions_applied = True
            except Exception as e2:
                print(f"Caption rendering failed, using original video: {e2}")
                captioned_path = output_path

        if progress_cb:
            progress_cb({"status": "uploading"})
        video_url = _upload_video_cloudinary(captioned_path)
        if progress_cb:
            progress_cb({"status": "ready", "video_url": video_url, "captions_applied": captions_applied})

    return {"video_url": video_url, "scenes": scenes, "captions_applied": captions_applied}
