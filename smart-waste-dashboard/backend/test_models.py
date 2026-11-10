import os
import httpx
import asyncio

NVIDIA_API_KEY = os.environ.get('NVIDIA_API_KEY', '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')
NVIDIA_BASE_URL = 'https://integrate.api.nvidia.com/v1'

async def test_model(model):
    headers = {
        'Authorization': f'Bearer {NVIDIA_API_KEY}',
        'Accept': 'application/json',
    }
    
    b64_img = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
    
    payload = {
        'model': model,
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': 'Describe this image'},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{b64_img}'}}
                ]
            }
        ],
        'max_tokens': 50
    }
    
    print(f'Testing {model}...')
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f'{NVIDIA_BASE_URL}/chat/completions', headers=headers, json=payload)
            print('Status:', resp.status_code)
            print('Response:', resp.text[:100])
    except Exception as e:
        print('Error:', type(e).__name__)

async def run():
    await test_model('meta/llama-3.2-11b-vision-instruct')
    await test_model('microsoft/phi-3-vision-128k-instruct')

asyncio.run(run())
