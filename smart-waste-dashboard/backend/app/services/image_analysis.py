import os
import base64
import json
import re
import logging
from dataclasses import dataclass, asdict
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

# ── Configuration (from environment variables) ────────────────
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.2-90b-vision-instruct")

CONFIDENCE_THRESHOLD = 0.3
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
API_TIMEOUT = 60.0

@dataclass
class AnalysisResult:
    severity: Optional[str]
    confidence: Optional[float]
    reason: Optional[str]
    analysis_status: str
    analysis_provider: Optional[str]
    analysis_model: Optional[str]
    needs_review: bool
    error: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)

SEVERITY_DEFINITIONS = """
Severity categories for waste assessment:
- LOW: Small or localized waste accumulation. Minor issue, no overflow.
- MEDIUM: Noticeable waste accumulation requiring scheduled attention. Partially full bins or moderate litter.
- HIGH: Substantial waste accumulation requiring timely collection. Bins near capacity or significant litter spread.
- CRITICAL: Severe overflow, large accumulation, or hazardous conditions requiring urgent collection. Overflowing bins, waste spilling into surroundings.
"""

ANALYSIS_PROMPT = f"""You are a waste management image analysis system. Analyze the provided image of a waste collection point or area.

Based ONLY on what you can see in the image, assess the waste severity.

{SEVERITY_DEFINITIONS}

You MUST respond with ONLY a valid JSON object (no markdown, no code fences, no extra text):

{{"severity": "LOW|MEDIUM|HIGH|CRITICAL", "confidence": 0.0-1.0, "reason": "Brief explanation of what you observe"}}

Rules:
1. severity MUST be exactly one of: LOW, MEDIUM, HIGH, CRITICAL
2. confidence MUST be a number between 0.0 and 1.0, reflecting how certain you are
3. reason MUST be a short sentence describing the visible waste condition
4. Do NOT invent information not visible in the image
5. Do NOT estimate weight or volume unless visually obvious
6. If the image is unclear, use a lower confidence value
7. If you cannot determine waste severity at all, use LOW severity with confidence below 0.2
"""

def _check_api_configured() -> Optional[str]:
    if not NVIDIA_API_KEY:
        return "NVIDIA_API_KEY not configured. Set it in backend/.env"
    if not NVIDIA_BASE_URL:
        return "NVIDIA_BASE_URL not configured"
    if not NVIDIA_MODEL:
        return "NVIDIA_MODEL not configured"
    return None

def _parse_ai_response(raw_content: str) -> dict:
    if not raw_content or not raw_content.strip():
        raise ValueError("Empty response from AI model")

    content = raw_content.strip()
    content = re.sub(r'^```(?:json)?\s*', '', content, flags=re.MULTILINE)
    content = re.sub(r'\s*```\s*$', '', content, flags=re.MULTILINE)
    content = content.strip()

    json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
    if json_match:
        content = json_match.group()

    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Cannot parse AI response as JSON: {e}. Raw: {raw_content[:200]}")

    if "severity" not in result:
        raise ValueError(f"AI response missing 'severity' field.")
    if "confidence" not in result:
        raise ValueError(f"AI response missing 'confidence' field.")
    if "reason" not in result:
        raise ValueError(f"AI response missing 'reason' field.")

    return result

def _validate_analysis(parsed: dict) -> tuple[str, float, str]:
    severity = str(parsed["severity"]).upper().strip()
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"Invalid severity '{severity}'")

    try:
        confidence = float(parsed["confidence"])
    except (TypeError, ValueError):
        raise ValueError(f"Invalid confidence value: {parsed['confidence']}")

    if confidence < 0.0 or confidence > 1.0:
        raise ValueError(f"Confidence {confidence} out of range")

    reason = str(parsed.get("reason", "")).strip()
    if not reason:
        raise ValueError("Empty analysis reason")
    if len(reason) > 1000:
        reason = reason[:1000]

    return severity, confidence, reason

def analyze_image(image_url: str) -> AnalysisResult:
    config_error = _check_api_configured()
    if config_error:
        logger.warning(f"AI analysis skipped: {config_error}")
        return AnalysisResult(
            severity=None, confidence=None, reason=None,
            analysis_status="failed", analysis_provider=None,
            analysis_model=None, needs_review=False, error=config_error,
        )

    payload = {
        "model": NVIDIA_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ANALYSIS_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                ],
            }
        ],
        "max_tokens": 512,
        "temperature": 0.2,
        "top_p": 0.9,
    }

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=API_TIMEOUT) as client:
            response = client.post(
                f"{NVIDIA_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )

        if response.status_code != 200:
            return AnalysisResult(
                severity=None, confidence=None, reason=None,
                analysis_status="failed", analysis_provider="nvidia_nim",
                analysis_model=NVIDIA_MODEL, needs_review=False,
                error=f"NVIDIA API returned status {response.status_code}",
            )

        response_data = response.json()
    except Exception as e:
        return AnalysisResult(
            severity=None, confidence=None, reason=None,
            analysis_status="failed", analysis_provider="nvidia_nim",
            analysis_model=NVIDIA_MODEL, needs_review=False,
            error=f"Unexpected error: {type(e).__name__}: {e}",
        )

    try:
        choices = response_data.get("choices", [])
        if not choices:
            raise ValueError("No choices in API response")
        raw_content = choices[0].get("message", {}).get("content", "")
        if not raw_content:
            raise ValueError("Empty content in API response")
    except Exception as e:
        return AnalysisResult(
            severity=None, confidence=None, reason=None,
            analysis_status="failed", analysis_provider="nvidia_nim",
            analysis_model=NVIDIA_MODEL, needs_review=False,
            error=f"Malformed API response: {e}",
        )

    try:
        parsed = _parse_ai_response(raw_content)
        severity, confidence, reason = _validate_analysis(parsed)
    except ValueError as e:
        return AnalysisResult(
            severity=None, confidence=None, reason=None,
            analysis_status="failed", analysis_provider="nvidia_nim",
            analysis_model=NVIDIA_MODEL, needs_review=False,
            error=f"AI response validation failed: {e}",
        )

    needs_review = confidence < CONFIDENCE_THRESHOLD

    return AnalysisResult(
        severity=severity,
        confidence=round(confidence, 2),
        reason=reason,
        analysis_status="analyzed",
        analysis_provider="nvidia_nim",
        analysis_model=NVIDIA_MODEL,
        needs_review=needs_review,
        error=None,
    )
