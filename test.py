import argparse
import hashlib
import os
import time
import urllib.parse
import requests
from dotenv import load_dotenv
load_dotenv()
"""
Test script: pull an image from Pollinations (bytes) and upload to Cloudinary.
Env required:
  POLLINATIONS_TOKEN
  CLOUDINARY_CLOUD_NAME
  CLOUDINARY_API_KEY
  CLOUDINARY_API_SECRET
"""


def fetch_pollinations_image(prompt: str, model: str, token: str) -> tuple[bytes, str]:
    safe_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?nologo=true&model={model}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    mime = resp.headers.get("Content-Type", "application/octet-stream")
    return resp.content, mime


def sign_cloudinary(params: dict, api_secret: str) -> str:
    # Cloudinary signature: sha1 of sorted params joined with '&' plus api_secret
    sorted_items = sorted((k, v) for k, v in params.items() if v is not None)
    to_sign = "&".join([f"{k}={v}" for k, v in sorted_items]) + api_secret
    return hashlib.sha1(to_sign.encode("utf-8")).hexdigest()


def upload_to_cloudinary(
    img_bytes: bytes,
    filename: str,
    cloud_name: str,
    api_key: str,
    api_secret: str,
    folder: str | None = None,
) -> str:
    timestamp = int(time.time())
    params = {"timestamp": timestamp, "folder": folder} if folder else {"timestamp": timestamp}
    signature = sign_cloudinary(params, api_secret)

    upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    files = {"file": (filename, img_bytes, "application/octet-stream")}
    data = {
        "timestamp": timestamp,
        "api_key": api_key,
        "signature": signature,
    }
    if folder:
        data["folder"] = folder

    resp = requests.post(upload_url, data=data, files=files, timeout=60)
    resp.raise_for_status()
    secure_url = resp.json().get("secure_url")
    if not secure_url:
        raise RuntimeError(f"Unexpected Cloudinary response: {resp.text}")
    return secure_url


def build_prompt(base: str, style: str) -> str:
    if style == "text":
        return f"{base}. Text-forward graphic on clean background, readable typography, quote-card feel."
    if style == "story":
        return f"{base}. Vertical 9:16 story, 1080x1920, high-contrast, legible typography on simple background."
    return base


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Fetch Pollinations image and upload to Cloudinary.")
    parser.add_argument("--prompt", default="people fighting", help="Prompt to send to Pollinations.")
    parser.add_argument("--model", default=None, help="Ignored; model is always read from POLLINATIONS_MODEL env.")
    parser.add_argument("--folder", default=None, help="Optional Cloudinary folder.")
    parser.add_argument("--filename", default="pollinations.jpg", help="Filename to upload.")
    parser.add_argument("--count", type=int, default=1, help="How many images to generate/upload.")
    parser.add_argument("--style", choices=["normal", "text", "story"], default="normal", help="Prompt style variant.")
    args = parser.parse_args()

    poll_token = os.getenv("POLLINATIONS_TOKEN")
    poll_model = os.getenv("POLLINATIONS_MODEL")
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    cloud_key = os.getenv("CLOUDINARY_API_KEY")
    cloud_secret = os.getenv("CLOUDINARY_API_SECRET")

    if not poll_token:
        raise SystemExit("Missing POLLINATIONS_TOKEN in environment.")
    if not poll_model:
        raise SystemExit("Missing POLLINATIONS_MODEL in environment.")
    if not (cloud_name and cloud_key and cloud_secret):
        raise SystemExit("Missing Cloudinary envs (CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET).")

    urls = []
    for i in range(max(1, args.count)):
        prompt = build_prompt(args.prompt, args.style)
        fname = args.filename
        if args.count > 1:
            name, ext = os.path.splitext(args.filename)
            fname = f"{name}_{i+1}{ext or '.jpg'}"

        print(f"[{i+1}/{args.count}] Fetching image from Pollinations model={poll_model} style={args.style} prompt='{prompt}'...")
        try:
            img_bytes, mime = fetch_pollinations_image(prompt, poll_model, poll_token)
        except requests.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            body = e.response.text if getattr(e, "response", None) else ""
            if status == 403:
                raise SystemExit(f"Pollinations 403 Unauthorized. Check POLLINATIONS_TOKEN (set, no quotes/spaces) and restart. Body: {body[:200]}")
            raise

        print(f"Fetched {len(img_bytes):,} bytes (mime={mime}). Uploading to Cloudinary as {fname}...")
        secure_url = upload_to_cloudinary(
            img_bytes=img_bytes,
            filename=fname,
            cloud_name=cloud_name,
            api_key=cloud_key,
            api_secret=cloud_secret,
            folder=args.folder,
        )
        print(f"✅ Uploaded: {secure_url}")
        urls.append(secure_url)

    print("\nAll uploaded URLs:")
    for u in urls:
        print(u)


if __name__ == "__main__":
    main()
