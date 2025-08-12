from langchain_core.tools import tool
import requests
import json
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
    images.append(json.loads(response.content.decode().strip().split("\n")[-1][6:])['imageUrl'])
    return images