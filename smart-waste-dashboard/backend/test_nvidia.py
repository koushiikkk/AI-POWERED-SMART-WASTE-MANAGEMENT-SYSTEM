import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def test_nvidia():
    api_key = os.getenv("NVIDIA_API_KEY")
    base_url = os.getenv("NVIDIA_BASE_URL")
    model = os.getenv("NVIDIA_MODEL")
    
    print(f"API Key present: {bool(api_key)}")
    print(f"Base URL: {base_url}")
    print(f"Model: {model}")
    
    # Just a simple text request to see if the API key is valid for this model
    # Note: meta/llama-3.2-90b-vision-instruct is a vision model, but it might support text-only too.
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Hello, respond with exactly the word 'OK'."}
        ],
        "max_tokens": 10
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=15.0)
            print(f"Status Code: {resp.status_code}")
            print(resp.text)
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_nvidia())
