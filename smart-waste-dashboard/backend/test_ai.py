import os
import httpx
import asyncio

NVIDIA_API_KEY = os.environ.get('NVIDIA_API_KEY', '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')
NVIDIA_BASE_URL = 'https://integrate.api.nvidia.com/v1'
NVIDIA_MODEL = 'meta/llama-3.2-90b-vision-instruct'

async def test_base64():
    headers = {
        'Authorization': f'Bearer {NVIDIA_API_KEY}',
        'Accept': 'application/json',
    }
    
    b64_img = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
    
    payload_openai = {
        'model': NVIDIA_MODEL,
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': 'What is this image?'},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{b64_img}'}}
                ]
            }
        ],
        'max_tokens': 50
    }
    
    print('Testing base64 image...')
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f'{NVIDIA_BASE_URL}/chat/completions', headers=headers, json=payload_openai)
            print('Status:', resp.status_code)
            print('Response:', resp.text)
    except Exception as e:
        print('Error:', e)

asyncio.run(test_base64())
