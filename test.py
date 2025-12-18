import argparse
import base64
import os
import textwrap
import requests
import json

"""
Image generator using Gemini's native API.
- Uses the native Google Generative Language API (not OpenAI-compatible endpoint)
- Supports gemini-2.5-flash-image and other image generation models
"""

# Use the native API endpoint
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.5-flash-image"


def build_prompt(subject: str, aspect: str) -> str:
    """Build an enhanced prompt for image generation."""
    return textwrap.dedent(
        f"""
        Create a realistic, non-AI-looking photograph of {subject}.
        - Cinematic lighting, ultra sharp, 8k resolution feel.
        - No text, no watermarks, no artifacts.
        - Frame and composition must honor a {aspect} aspect ratio.
        """
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an image with Gemini image model.")
    parser.add_argument(
        "--subject",
        default="a modern desk setup with laptop, coffee mug, and soft daylight",
        help="What to depict in the image.",
    )
    parser.add_argument(
        "--aspect",
        default="16:9",
        help="Aspect ratio hint to bake into the prompt (e.g., 16:9 or 9:16).",
    )
    parser.add_argument(
        "--output",
        default="gemini_image.png",
        help="Where to write the generated image.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Model to use (e.g., gemini-2.5-flash-image, gemini-3-pro-image-preview)",
    )
    args = parser.parse_args()

    # Read API key from environment variable
    api_key = "AIzaSyB43unoPREdYj455hr3TIGoy1YULTL69rs"
    if not api_key:
        raise SystemExit("Missing GOOGLE_API_KEY in environment. Set it with: export GOOGLE_API_KEY='your-key-here'")

    prompt = build_prompt(args.subject, args.aspect)
    
    # Build the API URL with the model and API key
    url = f"{API_BASE}/{args.model}:generateContent?key={api_key}"
    
    # Payload for native Gemini API
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 1.0,
            "topP": 0.95,
            "topK": 64,
            "maxOutputTokens": 8192,
        }
    }

    headers = {
        "Content-Type": "application/json",
    }

    print(f"Using model: {args.model}")
    print(f"Generating image with prompt: {prompt[:100]}...")
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        
        # Extract the image from the response
        # Gemini image models return inline data in the response
        if "candidates" in data and len(data["candidates"]) > 0:
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    if "inlineData" in part:
                        # Found the image data
                        mime_type = part["inlineData"]["mimeType"]
                        image_b64 = part["inlineData"]["data"]
                        
                        # Decode and save
                        image_bytes = base64.b64decode(image_b64)
                        
                        # Determine file extension from mime type
                        ext = args.output.split('.')[-1]
                        if 'png' in mime_type.lower():
                            ext = 'png'
                        elif 'jpeg' in mime_type.lower() or 'jpg' in mime_type.lower():
                            ext = 'jpg'
                        
                        output_file = args.output if '.' in args.output else f"{args.output}.{ext}"
                        
                        with open(output_file, "wb") as f:
                            f.write(image_bytes)
                        
                        print(f"✓ Image saved to {output_file}")
                        print(f"  MIME type: {mime_type}")
                        print(f"  Size: {len(image_bytes):,} bytes")
                        return
        
        # If we got here, the response format was unexpected
        print(f"Unexpected response format. Full response:")
        print(json.dumps(data, indent=2))
        
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response: {resp.text}")
        raise SystemExit(1)
    except Exception as e:
        print(f"Error: {e}")
        if 'resp' in locals():
            print(f"Response: {resp.text}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()