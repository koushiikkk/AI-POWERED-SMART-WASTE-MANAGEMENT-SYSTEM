import os
import json
import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Default configuration from environment
def _get_config():
    api_key = (os.getenv("NVIDIA_API_KEY") or "").strip()
    base_url = (os.getenv("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1").strip().rstrip("/")
    model = (os.getenv("NVIDIA_MODEL") or "nvidia/nemotron-3.5-super-vl-120b-a12b").strip()
    return api_key, base_url, model

SYSTEM_PROMPT = """You are an AI assistant analyzing a municipal waste collection image.
CRITICAL INSTRUCTION: Assess ONLY what is visibly supported by the image.
Do not invent hidden facts. Do not assume hazardous materials, exact weight, exact volume, municipal regulations, or hidden waste behind objects unless clearly visible.
If the image is unclear, blurry, or does not depict waste, state so clearly and return LOW severity with low confidence.

Determine:
1. Is waste clearly visible? (If no waste is visible, return LOW severity, confidence < 0.5, and explain why).
2. Approximate visible accumulation severity based ONLY on the visual footprint.
3. Whether overflow is visibly occurring outside intended containers.
4. Whether waste appears to be blocking public space/access.
5. Whether immediate attention appears warranted based ONLY on visible conditions.
6. Confidence in the assessment (0.0 to 1.0). If you are unsure, provide a low score.
7. A concise explanation based ONLY on visible evidence. Do NOT guess what might be hidden.

Output ONLY valid JSON in this exact structure:
{
  "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "confidence": <float>,
  "reason": "<explanation based only on visible evidence>"
}

Severity Guidelines:
- LOW: Small amount of waste, not overflowing. Or image is not of waste.
- MEDIUM: Noticeable accumulation requiring attention, but contained.
- HIGH: Substantial accumulation, possibly some overflow or blocking access.
- CRITICAL: Severe overflow, blocking public spaces, requiring immediate urgent collection.
"""

import re

def _parse_json_response(text: str) -> Dict[str, Any]:
    text = text.strip()
    # 1. Try standard JSON extraction
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # 2. Robust regex fallback: extracts fields even if model omitted quotes or used markdown
    severity_match = re.search(
        r'(?:"severity"|\*?\*?Severity:?\*?\*?)\s*[:=]\s*["\']?(LOW|MEDIUM|HIGH|CRITICAL)["\']?',
        text,
        re.IGNORECASE
    )
    confidence_match = re.search(
        r'(?:"confidence"|\*?\*?Confidence:?\*?\*?)\s*[:=]\s*([0-9.]+)',
        text,
        re.IGNORECASE
    )
    reason_match = re.search(
        r'(?:"reason"|\*?\*?Reason:?\*?\*?)\s*[:=]\s*["\']?([^"}\r\n]+(?:"[^}]*)?)',
        text,
        re.IGNORECASE
    )

    if severity_match:
        severity = severity_match.group(1).upper()
        confidence = 0.8
        if confidence_match:
            try:
                confidence = float(confidence_match.group(1))
            except ValueError:
                confidence = 0.8
        reason = reason_match.group(1).strip().rstrip('"}') if reason_match else "Waste condition assessed by AI."
        return {
            "severity": severity,
            "confidence": confidence,
            "reason": reason
        }

    logger.error(f"No JSON block found and fallback failed. Raw output: {text}")
    raise ValueError(f"AI response did not contain JSON or recognizable fields. Raw output: {text}")

async def analyze_waste_image(image_url: str) -> Dict[str, Any]:
    api_key, base_url, model = _get_config()
    if not api_key:
        raise ValueError("NVIDIA_API_KEY environment variable is missing.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Analyze this waste image. Output JSON directly."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "PLACEHOLDER_FOR_BASE64"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 2048,
        "temperature": 0.0,
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 1. Download image and convert to base64
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            
            import base64
            b64_str = base64.b64encode(img_resp.content).decode('utf-8')
            mime_type = img_resp.headers.get('content-type', 'image/jpeg')
            b64_data_uri = f"data:{mime_type};base64,{b64_str}"
            
            # Update payload
            payload["messages"][1]["content"][1]["image_url"]["url"] = b64_data_uri

            # 2. Send to NVIDIA
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            choice = data['choices'][0]
            message = choice['message']
            raw_content = message.get('content')
            if not raw_content:
                if choice.get('finish_reason') == 'length':
                    raise ValueError("AI model reached token limit before generating response. Increase max_tokens.")
                raise ValueError("AI provider returned empty content.")
            
            result = _parse_json_response(raw_content)
            
            severity = result.get("severity")
            if severity not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
                raise ValueError(f"Invalid severity returned: {severity}")
                
            confidence = float(result.get("confidence", 0.0))
            if not (0.0 <= confidence <= 1.0):
                raise ValueError(f"Confidence out of range: {confidence}")
                
            reason = result.get("reason", "No reason provided")
            
            return {
                "severity": severity,
                "confidence": confidence,
                "reason": reason,
                "analysis_provider": "NVIDIA NIM",
                "analysis_model": model,
            }
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {raw_content if 'raw_content' in locals() else 'No content'}")
        raise ValueError(f"Malformed response from AI provider: {e}")
    except httpx.RequestError as e:
        err_msg = f"{type(e).__name__}: {str(e) or 'Request timed out or connection error'}"
        logger.error(f"HTTP Request failed: {err_msg}")
        raise Exception(f"AI provider communication error: {err_msg}")
    except httpx.HTTPStatusError as e:
        err_msg = f"Status {e.response.status_code}: {e.response.text}"
        logger.error(f"HTTP Status Error: {err_msg}")
        raise Exception(f"AI provider returned error status {e.response.status_code}: {e.response.text}")
    except Exception as e:
        logger.error(f"Unexpected error in AI analysis: {type(e).__name__}: {e}")
        raise
