import json
import requests
from langchain.agents import initialize_agent, AgentType
from langchain_cohere import ChatCohere
from dotenv import load_dotenv
from langchain_core.tools import tool
import os
load_dotenv()  


@tool
def generate_images(topics):
  """Generate images based on post"""
  images = []
  for i in range(len(topics)):
    url = "https://subnp.com//api/free/generate"  
    headers = {
        "Content-Type": "application/json",
    }
    data = {
        "prompt": topics[i],
        "model": "turbo"
    }

    response = requests.post(url, headers=headers, json=data)
    print("HERE")
    print(response)
    images.append(json.loads(response.content.decode().strip().split("\n")[-1][6:])['imageUrl'])
    return images
  
def run_agent():
    access_token = os.getenv('access_token')
    urn = os.getenv('urn')
    print(access_token)
    # Simple LinkedIn upload function
    def upload_image_to_linkedin(image_url, access_token, person_urn):
        """Download image from URL and upload to LinkedIn - SIMPLE VERSION"""
        try:
            response = requests.get(image_url, timeout=30)
            image_data = response.content
            
            register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
            register_payload = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": person_urn,
                    "serviceRelationships": [{"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}]
                }
            }
            register_response = requests.post(register_url, json=register_payload, headers={'Authorization': f'Bearer {access_token}'})
            register_data = register_response.json()
            
            upload_url = register_data['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
            requests.post(upload_url, data=image_data, headers={'Content-Type': 'application/octet-stream'})
            
            return register_data['value']['asset']
        except Exception as e:
            raise Exception(f"Upload failed: {e}")

    # Simple agent setup
    llm = ChatCohere(temperature=0.5)
    agent = initialize_agent(tools=[generate_images], llm=llm, handle_parsing_errors=True)

    def create_and_post_linkedin_content(client_info, post_type, target_industry, content_goals, linkedin_urn, access_token):
        prompt = f"""
        Generate LinkedIn {post_type} content for {client_info['name']} in {target_industry}.
        Goals: {content_goals}
        
        Return ONLY this JSON format:
        {{
            "content_draft": "post text here",
            "hashtag_suggestions": ["#hashtag1", "#hashtag2", "#hashtag3"],
            "image_instructions": ["prompt 1", "prompt 2", "prompt 3"]
        }}
        """
        
        content_result = agent.run(prompt)
        
        try:
            start = content_result.find('{')
            end = content_result.rfind('}') + 1
            json_str = content_result[start:end]
            content_data = json.loads(json_str)
        except:
            print("JSON failed, using fallback")
            return

        media_urns = []
        if post_type.lower() == "carousel":
            print("Generating images...")
            
            image_result = agent.run(f"Use generate_images with prompts: {content_data['image_instructions']}")
            
            import re
            urls = re.findall(r'https://[^\s\"\'\]\)\,]+', image_result)
            image_urls = [url.rstrip('\'"]),') for url in urls]
            print(f"Found URLs: {image_urls}")
            
            for i, url in enumerate(image_urls[:6]):  # Max 6 slides
                try:
                    print(url)
                    asset_urn = upload_image_to_linkedin(url, access_token, f"urn:li:person:{linkedin_urn}")
                    media_urns.append({"status": "READY", "media": asset_urn})
                    print(f"Uploaded image {i+1}")
                except Exception as e:
                    print(f"Failed image {i+1}: {e}")
        
        # Step 4: Create post
        full_text = content_data["content_draft"] + " " + " ".join(content_data["hashtag_suggestions"])
        
        payload = {
            "author": f"urn:li:person:{linkedin_urn}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": full_text},
                    "shareMediaCategory": "IMAGE" if media_urns else "NONE"
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "CONNECTIONS"}
        }
        
        if media_urns:
            payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = media_urns
        
        # Step 5: Post to LinkedIn
        try:
            response = requests.post(
                "https://api.linkedin.com/v2/ugcPosts",
                json=payload,
                headers={'Authorization': f'Bearer {access_token}'}
            )
            
            if response.status_code == 201:
                return {"success": True, "post_id": response.json().get("id"), "images_uploaded": len(media_urns)}
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    # SIMPLE USAGE
    result = create_and_post_linkedin_content(
        client_info={'name': 'John Doe', 'industry': 'Tech'},
        post_type="article",
        target_industry="Tech",
        content_goals="AI boom post",
        linkedin_urn=urn,
        access_token=access_token
    )

    return result