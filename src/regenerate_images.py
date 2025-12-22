from langchain_openai import ChatOpenAI
import requests 
import json
import os
import time
import hashlib
import urllib.parse

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

def upload_image_to_linkedin(image_url, access_token, person_urn):
        """Download image from URL and upload to LinkedIn"""
        try:
            print(f"Uploading image: {image_url}")
            response = requests.get(image_url, timeout=30)
            if response.status_code != 200:
                raise Exception(f"Failed to download image: {response.status_code}")
                
            image_data = response.content
            
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
            
        except Exception as e:
            raise Exception(f"Upload failed for {image_url}: {e}")

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


def generate_images_direct(topics):
    """Direct function to generate images via Pollinations -> Cloudinary."""
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
                filename = f"pollinations_regen_{int(time.time())}_{i}.jpg"
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


def regenerate(client_info,access_token,linkedin_urn):
    """Generate content and images - returns data to post"""
    llm = ChatOpenAI(
        temperature=0.5,
        model=OPENROUTER_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
    )
    content_goals = client_info.get('contentRequirements', 'Professional')
    industry = client_info.get('targetAudience', 'Technology')
    postTone = client_info.get('postTone', '')
    website_content = client_info.get('website', '')
    
    content_prompt = f"""
    You are creating image instructions for a Image model to further forward to a LinkedIn post for a professional in {industry}.

    CONTEXT:
    - Industry: {industry}
    - Content Goal: {content_goals}
    - Target audience: {industry}
    
    INSTRUCTIONS:
    Create engaging LinkedIn content that:
    1. Reflects their professional expertise and background
    2. Uses an authentic, professional tone suitable for their industry
    3. Includes relevant industry insights or personal experiences
    4. Encourages meaningful engagement from their network
    5. Aligns with current trends in {industry}
    6. Image instructions must be realistic/photorealistic, natural lighting, no CGI look, no watermarks, no obvious AI artifacts.

    OUTPUT FORMAT (JSON only, no markdown or extra text):
    {{
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
    print("Generating images for carousel...")
    
    # Call the direct function instead
    try:
        image_urls = generate_images_direct(content_data['image_instructions'])
    except Exception as e:
        print(f"Image generation failed: {e}")
        image_urls = []
    
    media_urns = []
    for i, url in enumerate(image_urls[:6]):  # LinkedIn max 6 slides
        try:
            asset_urn = upload_image_to_linkedin(url, access_token, f"urn:li:person:{linkedin_urn}")
            media_urns.append({"status": "READY", "media": asset_urn})
            print(f"Successfully uploaded image {i+1}/{len(image_urls)}")
        except Exception as e:
            print(f"Failed to upload image {i+1}: {e}")
    return {
        "urns":media_urns,
        "urls":image_urls,
        "image_instructions":content_data['image_instructions']
    }
