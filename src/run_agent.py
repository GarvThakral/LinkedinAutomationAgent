import json
import requests
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_core.tools import tool
import os
load_dotenv()  

OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "xiaomi/mimo-v2-flash:free")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

def generate_images_direct(topics):
    """Direct function to generate images without tool wrapper"""
    print(f"Generating images for topics: {topics}")
    
    # Handle input
    if isinstance(topics, str):
        try:
            topics = json.loads(topics)
        except:
            topics = topics.split(',') if ',' in topics else [topics]
    elif not isinstance(topics, list):
        topics = [str(topics)]
    
    # Limit to 3 images max
    topics = topics[:3]
    
    images = []
    for i, topic in enumerate(topics):
        print(f"Generating image {i+1}/{len(topics)}: {topic}")
        
        url = "https://subnp.com/api/free/generate"  
        headers = {"Content-Type": "application/json"}
        data = {"prompt": str(topic).strip(), "model": "magic"}
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            data_raw = response.content.decode().strip()

            try:
                data = json.loads(data_raw)
            except json.JSONDecodeError:
                try:
                    data = json.loads(data_raw.split("\n")[-1][6:])
                except:
                    print(f"Failed to parse response for topic {topic}: {data_raw}")
                    continue

            if 'imageUrl' in data:
                print(f"Generated: {data['imageUrl']}")
                images.append(data['imageUrl'])
            else:
                print(f"No imageUrl found in response for topic {topic}: {data}")
                
        except Exception as e:
            print(f"Error generating image for topic {topic}: {e}")
            
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
        print(f"Generating image {i+1}/{len(topics)}: {topic}")
        
        url = "https://subnp.com/api/free/generate"  
        headers = {"Content-Type": "application/json"}
        data = {"prompt": str(topic).strip(), "model": "magic"}
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            data_raw = response.content.decode().strip()

            try:
                data = json.loads(data_raw)
            except json.JSONDecodeError:
                try:
                    data = json.loads(data_raw.split("\n")[-1][6:])
                except:
                    print(f"Failed to parse response for topic {topic}: {data_raw}")
                    continue

            if 'imageUrl' in data:
                print(f"Generated: {data['imageUrl']}")
                images.append(data['imageUrl'])
            else:
                print(f"No imageUrl found in response for topic {topic}: {data}")
                
        except Exception as e:
            print(f"Error generating image for topic {topic}: {e}")
            
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
    You are a storytelling marketer. Market through narrative, emotion, and user journeys; never through ad copy or feature lists.

    Core structure (must follow):
    - Hook (scroll-stopping opening): bold, relatable, or emotionally charged; feels like a personal realization, not a pitch.
    - Context & struggle (0 → 30): real-world problem the audience relates to, framed as lived experience or observation.
    - Market awareness (research-driven, subtle): show awareness of similar solutions or patterns; refer indirectly ("other platforms", "existing women-first products") unless explicitly told; avoid naming competitors unless instructed.
    - User journey (30 → 80): move from confusion → clarity → progress; focus on emotional shifts, not features.
    - Achievements & outcomes (80 → 95): progress/wins/impact, authentic and grounded, not boastful.
    - Feedback or validation: include reactions, realizations, or lessons learned (emotion, confidence, relief, etc.).
    - Closing line (95 → 100): strong, reflective, or empowering statement; ending feels complete and memorable.
    - Make the product appear naturally inside the story; never lead with features, pricing, or CTAs.
    - Cover where the user started, what they experienced, and what changed (emotionally/practically).
    - Highlight wins/milestones authentically; include user reactions or lessons.

    Style rules:
    - Do NOT sound like an ad. Avoid buzzwords, feature lists, and sales language.
    - Write like a real human sharing a journey. Short paragraphs, social-media readable.
    - Research behavior: use general market understanding and common patterns; do NOT invent specific statistics or claims; if unsure, keep insights high-level and experience-based.
    - Do not dump everything in one paragraph. Use spacing and flow with short, distinct paragraphs that read easily in-feed.
    - This is marketing through storytelling, not advertising. Avoid hard sells. Write like a thoughtful founder/user/builder.
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
    8. Image instructions must be realistic/photorealistic, natural lighting, no CGI look, no watermarks, no obvious AI artifacts.

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
            if not image_urls:
                image_urls = [
                    "https://free-cdn.mitraai.xyz/b4f006e7-f485-4785-a008-3236c284e2d8.jpg",
                    "https://free-cdn.mitraai.xyz/3adcd7be-ede2-4cc8-8e89-4298bf6cbbf8.jpg",
                    "https://free-cdn.mitraai.xyz/8329263a-fdcc-4429-964d-de61a90e0f23.jpg"
                ]
        except Exception as e:
            print(f"Image generation failed: {e}")
            image_urls = []
    
    return {
        "content_data": content_data,
        "image_urls": image_urls
    }

def create_and_post_linkedin_content(content_data, image_urls, post_type, linkedin_urn, access_token):
    """Takes generated content and posts to LinkedIn"""

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

        try:
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
    
    media_urns = []
    
    # Upload images for carousel
    if post_type.lower() == "carousel" and image_urls:
        print(f"Uploading {len(image_urls)} images...")
        
        for i, url in enumerate(image_urls[:6]):  # LinkedIn max 6 slides
            try:
                asset_urn = upload_image_to_linkedin(url, access_token, f"urn:li:person:{linkedin_urn}")
                media_urns.append({"status": "READY", "media": asset_urn})
                print(f"Successfully uploaded image {i+1}/{len(image_urls)}")
            except Exception as e:
                print(f"Failed to upload image {i+1}: {e}")
    
    # Create LinkedIn post
    full_text = content_data.get('text')
    if content_data.get('hashtags'):
        full_text += "\n\n" + " ".join(content_data["hashtag_suggestions"])
    
    payload = {
        "author": f"urn:li:person:{linkedin_urn}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": full_text},
                "shareMediaCategory": "IMAGE" if media_urns else "NONE"
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
                "images_uploaded": len(media_urns)
            }
        else:
            return {
                "success": False, 
                "error": f"LinkedIn API error: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        return {"success": False, "error": f"Request failed: {str(e)}"}
