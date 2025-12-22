import json
import requests
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_core.tools import tool
import os
import time
import hashlib
import urllib.parse
from typing import Sequence
import re

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


def _upload_cloudinary(img_bytes: bytes, filename: str) -> str:
    if not (CLOUDINARY_CLOUD and CLOUDINARY_KEY and CLOUDINARY_SECRET):
        raise RuntimeError("Cloudinary credentials missing")
    timestamp = int(time.time())
    params = {"timestamp": timestamp}
    if CLOUDINARY_FOLDER:
        params["folder"] = CLOUDINARY_FOLDER
    signature = _sign_cloudinary(params, CLOUDINARY_SECRET)
    upload_url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD}/image/upload"
    files = {"file": (filename, img_bytes, "application/octet-stream")}
    data = {
        "timestamp": timestamp,
        "api_key": CLOUDINARY_KEY,
        "signature": signature,
    }
    if CLOUDINARY_FOLDER:
        data["folder"] = CLOUDINARY_FOLDER
    resp = requests.post(upload_url, data=data, files=files, timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Cloudinary upload failed: {resp.status_code} {resp.text[:200]}")
    secure_url = resp.json().get("secure_url")
    if not secure_url:
        raise RuntimeError(f"Unexpected Cloudinary response: {resp.text[:200]}")
    return secure_url

def _extract_json_block(text: str) -> dict:
    """Best-effort JSON extraction from LLM output."""
    # Strip code fences
    if "```" in text:
        parts = text.split("```")
        # take the middle part if present
        text = parts[1] if len(parts) > 1 else text
    # Remove control chars
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    # Find first { ... } block
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in response")
    json_str = match.group(0)
    return json.loads(json_str)


def generate_images_direct(topics):
    """Generate images via Pollinations -> Cloudinary and return public URLs."""
    print(f"Generating images for topics: {topics}")
    
    if isinstance(topics, str):
        try:
            topics = json.loads(topics)
        except:
            topics = topics.split(',') if ',' in topics else [topics]
    elif not isinstance(topics, list):
        topics = [str(topics)]
    
    topics = topics[:3]
    images = []
    for i, topic in enumerate(topics):
        attempt = 0
        while True:
            attempt += 1
            print(
                f"Generating image {i+1}/{len(topics)} (attempt {attempt}/{IMAGE_GEN_MAX_RETRIES}): {topic} "
                f"(model={POLLINATIONS_MODEL})"
            )
            try:
                img_bytes = _fetch_pollinations_bytes(str(topic).strip())
                filename = f"pollinations_{int(time.time())}_{i}.jpg"
                secure_url = _upload_cloudinary(img_bytes, filename)
                print(f"Generated and uploaded: {secure_url}")
                images.append(secure_url)
                break
            except Exception as e:
                print(f"Error generating image for topic {topic}: {e}")
                if attempt >= IMAGE_GEN_MAX_RETRIES:
                    print(f"Giving up after {IMAGE_GEN_MAX_RETRIES} attempts for topic: {topic}")
                    break
                time.sleep(IMAGE_GEN_RETRY_DELAY_SEC)
            
    print(f"Total images generated: {len(images)}")
    return images

@tool
def generate_images(topics: str):
    """Given a list of image prompts as a JSON string, generate and return a list of direct image URLs."""
    print(f"Generating images for topics: {topics}")
    
    # Parse topics if it's a string
    if isinstance(topics, str):
        try:
            topics = json.loads(topics)
        except:
            topics = topics.split(',') if ',' in topics else [topics]
    elif isinstance(topics, list):
        # Already a list, use as is
        pass
    else:
        topics = [str(topics)]
    
    # Limit to 3 images max to prevent spam
    topics = topics[:3]
    
    images = []
    for i, topic in enumerate(topics):
        attempt = 0
        while True:
            attempt += 1
            print(
                f"Generating image {i+1}/{len(topics)} (attempt {attempt}/{IMAGE_GEN_MAX_RETRIES}): {topic} "
                f"(model={POLLINATIONS_MODEL})"
            )
            try:
                img_bytes = _fetch_pollinations_bytes(str(topic).strip())
                filename = f"pollinations_tool_{int(time.time())}_{i}.jpg"
                secure_url = _upload_cloudinary(img_bytes, filename)
                images.append(secure_url)
                print(f"Generated and uploaded: {secure_url}")
                break
            except Exception as e:
                print(f"Error generating image for topic {topic}: {e}")
                if attempt >= IMAGE_GEN_MAX_RETRIES:
                    print(f"Giving up after {IMAGE_GEN_MAX_RETRIES} attempts for topic: {topic}")
                    break
                time.sleep(IMAGE_GEN_RETRY_DELAY_SEC)
            
    print(f"Total images generated: {len(images)}")
    return images

def run_agent(client_info, post_type, target_industry, content_goals, context: str = ""):
    """Generate content and images - returns data to post"""
    llm = ChatOpenAI(
        temperature=0.5,
        model=OPENROUTER_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
    )
    name = client_info.get('name', 'Professional')
    industry = client_info.get('industry', 'Technology')
    about = client_info.get('about', '')
    website_content = client_info.get('website', '')
    
    content_prompt = f"""
    You are creating a LinkedIn {post_type} for {name}, a professional in {industry}.

    CONTEXT:
    - Name: {name}
    - Industry: {industry}
    - Content Goal: {content_goals}
    - Target audience: {target_industry}
    - Additional context (use verbatim where relevant): {context}
    - About/summary: {about}
    - Website notes: {website_content}
    
    ROLE & STYLE (must obey):
    You are a social media storyteller, not a marketer.
    Your task is to edit or generate a social media post for a product in a way that feels human, story-driven, and emotionally engaging — not like an advertisement.

    Core structure (must follow):
    - Hook (scroll-stopping opening): bold, relatable, or emotionally charged; feels like a personal realization, not a pitch.
    - Context & struggle (0 → 30): real-world problem the audience relates to, framed as lived experience or observation.
    - Market awareness (research-driven, subtle): show awareness of similar solutions or patterns; refer indirectly ("other platforms", "existing women-first products") unless explicitly told; avoid naming competitors unless instructed.
    - User journey (30 → 80): move from confusion → clarity → progress; focus on emotional shifts, not features.
    - Achievements & outcomes (80 → 95): progress/wins/impact, authentic and grounded, not boastful.
    - Feedback or validation: include reactions, realizations, or lessons learned (emotion, confidence, relief, etc.).
    - Closing line (95 → 100): strong, reflective, or empowering statement; ending feels complete and memorable.

    Style rules:
    - Do NOT sound like an ad. Avoid buzzwords, feature lists, and sales language.
    - Write like a real human sharing a journey. Short paragraphs, social-media readable.
    - Research behavior: use general market understanding and common patterns; do NOT invent specific statistics or claims; if unsure, keep insights high-level and experience-based.
    - Rewrite or generate the post following all these rules.

    INSTRUCTIONS:
    Create engaging LinkedIn content that:
    1. Reflects their professional expertise and background
    2. Uses an authentic, professional tone suitable for their industry
    3. Includes relevant industry insights or personal experiences
    4. Encourages meaningful engagement from their network
    5. Aligns with current trends in {industry}
    6. Respect the provided context; do not invent facts.
    7. Keep copy concise and scannable.
    8. Image Instructions:
    Any image used must contain readable text within the image itself, not just be a plain or decorative visual. The image should visually communicate information using embedded text (for example: quotes, headlines, captions, tips, or call-to-action text).

    OUTPUT FORMAT (JSON only, no markdown or extra text):
    {{
        "content_draft": "Write a compelling post that sounds authentic to {name}'s voice and expertise. Include relevant insights, personal touch, and clear value for their network. End with an engaging question or call-to-action.",
        "hashtag_suggestions": ["#relevant", "#industry", "#specific"],
        "image_instructions": ["Professional visual concept 1", "Supporting visual concept 2", "Engaging visual concept 3"]
    }}"""


    
    try:
        # Use LLM directly for content generation instead of agent
        response = llm.invoke(content_prompt)
        content_output = response.content if hasattr(response, 'content') else str(response)
        
        # Extract JSON from response
        start = content_output.find('{')
        end = content_output.rfind('}') + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in response")
            
        json_str = content_output[start:end]
        content_data = json.loads(json_str)
        
    except Exception as e:
        print(f"Content generation failed: {e}")
        return None
    
    # Step 2: Generate images only if carousel and we have instructions
    image_urls = []
    if post_type.lower() == "carousel" and content_data.get('image_instructions'):
        print("Generating images for carousel...")
        
        # Call the direct function instead
        try:
            image_urls = generate_images_direct(content_data['image_instructions'])
        except Exception as e:
            print(f"Image generation failed: {e}")
            image_urls = []
    
    return {
        "content_data": content_data,
        "image_urls": image_urls
    }


def run_automated_agent(
    project_name: str,
    project_description: str,
    target_audience: str,
    content_tone: str = "Professional",
    page: str = "",
    post_type: str = "carousel",
    image_type: str = "normal",  # normal | text
    instagram_post_type: str = "posts",  # posts | stories
):
    """Generate content for automated sheet-driven posts (LinkedIn/Instagram/Reddit)."""
    # If Instagram stories, skip text generation and craft image instructions directly
    if instagram_post_type.lower() == "stories":
        story_prompt = "Vertical 9:16 Instagram story, 1080x1920, high-contrast, legible typography on simple background."
        if image_type == "text":
            story_prompt += " Text-forward design, minimal illustration, brand-like quote card."
        content_data = {
            "content_draft": "",
            "hashtag_suggestions": [],
            "image_instructions": [story_prompt],
        }
    else:
        llm = ChatOpenAI(
            temperature=0.5,
            model=OPENROUTER_MODEL,
            base_url=OPENROUTER_BASE_URL,
            api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
        )

        image_style = "photorealistic product/people visual"
        if image_type == "text":
            image_style = "text-forward graphic on clean background, quote-card style, readable typography"

        content_prompt = f"""
    You are a storytelling marketer.
    Your goal is to create high-engagement social media posts that market a product through narrative, emotion, and user journeys, not through ads or feature lists.

    INPUTS:
    - Product/Project: {project_name}
    - Description: {project_description}
    - Target audience: {target_audience}
    - Tone: {content_tone}
    - Target page/channel name (may be Instagram/LinkedIn/Reddit): {page}
    - Desired image style: {image_style}

    Core principles (must follow):
    1) Hook first: bold, relatable, or emotionally charged opening; feels like a lived insight.
    2) Emotional journey (0→100): start with tension/problem, build through discovery/learning, end with clarity/confidence/impact.
    3) Story before product: product appears naturally inside the story; never lead with features/pricing/CTAs; feels like a journey someone lived.
    4) Market awareness (subtle): show understanding of the broader market and similar solutions; refer indirectly ("other platforms", "existing women-first tools", "what we've seen work in India"); do NOT name competitors unless explicitly instructed.
    5) User journey: where the user started, what they experienced, what changed (emotionally/practically).
    6) Achievements & progress: highlight wins/milestones/outcomes authentically, not boastfully.
    7) Feedback & validation: include reactions, reflections, or lessons learned (emotional or observational).
    8) Strong ending: memorable, reflective, or empowering closing line; complete, not promotional.

    Style rules:
    - This is marketing through storytelling, not advertising.
    - Avoid buzzwords, hard sells, feature lists.
    - Write like a thoughtful founder/user/builder.
    - Short paragraphs, social-media friendly.
    - Do NOT put everything in one paragraph; use spacing and flow with concise paragraphs.
    - Use general market understanding; avoid specific stats or unverifiable claims; keep insights experience-based if unsure.

    CHANNEL NOTE:
    - Copy should be channel-agnostic but suitable for LinkedIn/Instagram/Reddit feed posts.
    - Provide hashtag suggestions that fit the audience and platform tone.

    OUTPUT FORMAT (JSON only, no markdown):
    {{
        "content_draft": "Full post text following all rules and formatting guidance.",
        "hashtag_suggestions": ["#...", "#...", "#..."],
        "image_instructions": ["Visual concept 1", "Visual concept 2", "Visual concept 3. Include: {image_style}."]
    }}
    """

        try:
            response = llm.invoke(content_prompt)
            content_output = response.content if hasattr(response, "content") else str(response)
            content_data = _extract_json_block(content_output)
        except Exception as e:
            print(f"Automated content generation failed: {e}")
            return None

    image_urls = []
    if post_type.lower() == "carousel" and content_data.get("image_instructions"):
        print("Generating images for automated carousel...")
        try:
            image_urls = generate_images_direct(content_data["image_instructions"])
        except Exception as e:
            print(f"Automated image generation failed: {e}")
            image_urls = []

    return {
        "content_data": content_data,
        "image_urls": image_urls,
    }


def create_and_post_linkedin_content(
    content_data, 
    image_urls, 
    post_type, 
    linkedin_urn, 
    access_token
):
    """
    Post to LinkedIn with images.
    """

    def upload_image_to_linkedin(image_url, access_token, person_urn):
        """Download image from URL and upload to LinkedIn"""
        def try_download(url: str):
            resp = requests.get(url, timeout=30)
            if resp.status_code != 200:
                raise Exception(f"Failed to download image: {resp.status_code}")
            return resp.content

        try:
            print(f"Uploading image: {image_url}")
            image_data = try_download(image_url)
        except Exception as e:
            print(f"Primary download failed, retrying once for {image_url}: {e}")
            try:
                image_data = try_download(image_url)
            except Exception as e2:
                raise Exception(f"Upload failed for {image_url}: {e2}")

        register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": person_urn,
                "serviceRelationships": [
                    {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
                ]
            }
        }

        register_response = requests.post(
            register_url,
            json=register_payload,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=30
        )

        if register_response.status_code != 200:
            raise Exception(f"Registration failed: {register_response.status_code} - {register_response.text}")

        register_data = register_response.json()
        upload_url = register_data['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']

        upload_response = requests.post(
            upload_url,
            data=image_data,
            headers={'Content-Type': 'application/octet-stream'},
            timeout=30
        )

        if upload_response.status_code not in [200, 201]:
            raise Exception(f"Upload failed: {upload_response.status_code}")

        return register_data['value']['asset']
    
    media_urns = []
    media_category = "NONE"
    
    # Handle carousel (images only)
    if post_type.lower() == "carousel" and image_urls:
        print(f"Uploading {len(image_urls)} images...")
        for i, url in enumerate(image_urls[:6]):  # LinkedIn max 6
            try:
                asset_urn = upload_image_to_linkedin(url, access_token, f"urn:li:person:{linkedin_urn}")
                media_urns.append({"status": "READY", "media": asset_urn})
                print(f"✓ Uploaded image {i+1}/{len(image_urls)}")
            except Exception as e:
                print(f"✗ Failed image {i+1}: {e}")
        
        if media_urns:
            media_category = "IMAGE"
    
    # Build post text
    full_text = content_data.get('content_draft') or content_data.get('text', '')
    if content_data.get('hashtag_suggestions'):
        full_text += "\n\n" + " ".join(content_data["hashtag_suggestions"])
    
    # Create payload
    payload = {
        "author": f"urn:li:person:{linkedin_urn}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": full_text},
                "shareMediaCategory": media_category
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
    }
    
    if media_urns:
        payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = media_urns
    
    # Post to LinkedIn
    try:
        response = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            json=payload,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )
        
        if response.status_code == 201:
            return {
                "success": True, 
                "post_id": response.json().get("id"), 
                "media_uploaded": len(media_urns),
                "media_type": "PDF" if media_category == "ARTICLE" else "Images"
            }
        else:
            return {
                "success": False, 
                "error": f"LinkedIn API error: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        return {"success": False, "error": f"Request failed: {str(e)}"}
