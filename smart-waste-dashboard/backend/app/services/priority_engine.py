"""
Smart Priority Engine — Explainable waste collection prioritization.

Formula (from project specification):
    Priority Score = 0.5 * Fill Ratio Score
                   + 0.3 * Status Weight Score
                   + 0.2 * Waiting Time Score

All components normalized to 0–100 scale.
Final score: 0–100.

Priority Levels:
    0–30:   LOW
    31–60:  MEDIUM
    61–80:  HIGH
    81–100: CRITICAL

Status Weights:
    LOW      = 25
    MEDIUM   = 50
    HIGH     = 75
    CRITICAL = 100

Waiting Time:
    Normalized based on hours since oldest pending collection.
    Max cap at 48 hours (score 100). No pending = 0.

Tie-breaker: older pending collection first, then higher fill ratio.

Future extension: additional signals (image AI severity, citizen reports)
can be added as extra weighted factors without rewriting the engine.
"""

from datetime import datetime, timezone
from app.services.waste_logic import calculate_waste_status

# ── Component Weights ──────────────────────────
WEIGHT_FILL_RATIO = 0.5
WEIGHT_STATUS = 0.3
WEIGHT_WAITING_TIME = 0.2

# ── Status Weight Map ──────────────────────────
STATUS_WEIGHTS = {
    "LOW": 25,
    "MEDIUM": 50,
    "HIGH": 75,
    "CRITICAL": 100,
}

# ── Priority Level Thresholds ──────────────────
PRIORITY_THRESHOLDS = [
    (81, "CRITICAL"),
    (61, "HIGH"),
    (31, "MEDIUM"),
    (0, "LOW"),
]

# ── Waiting Time Cap (hours) ───────────────────
MAX_WAITING_HOURS = 48.0


def _get_priority_level(score: float) -> str:
    """Map a 0–100 priority score to a priority level string."""
    for threshold, level in PRIORITY_THRESHOLDS:
        if score >= threshold:
            return level
    return "LOW"


def _build_reason(fill_ratio: float, status: str, waiting_hours: float) -> str:
    """Generate a human-readable explanation for the priority score."""
    parts = []
    if fill_ratio >= 0.91:
        parts.append("critically full")
    elif fill_ratio >= 0.76:
        parts.append("high fill level")
    elif fill_ratio >= 0.51:
        parts.append("moderate fill level")
    else:
        parts.append("low fill level")

    if status == "CRITICAL":
        parts.append("critical waste status")
    elif status == "HIGH":
        parts.append("high waste status")

    if waiting_hours >= 24:
        parts.append(f"waiting {waiting_hours:.0f}h for collection")
    elif waiting_hours >= 6:
        parts.append(f"pending collection for {waiting_hours:.0f}h")

    return ". ".join(parts).capitalize() if parts else "Normal priority"


def calculate_priority_score(
    current_level: float,
    capacity: float,
    status: str,
    pending_created_at: datetime = None,
    now: datetime = None,
) -> dict:
    """
    Calculate an explainable priority score for a location.

    Args:
        current_level: Current waste fill amount.
        capacity: Maximum capacity.
        status: Derived waste status (LOW/MEDIUM/HIGH/CRITICAL).
        pending_created_at: Earliest pending collection created_at (or None).
        now: Current time for waiting calculation (defaults to utcnow).

    Returns:
        Dictionary with all scoring components for explainability.
    """
    if now is None:
        now = datetime.now()

    # ── Fill Ratio Score (0–100) ──────────────
    fill_ratio = min(current_level / capacity, 1.0) if capacity > 0 else 1.0
    fill_ratio_score = fill_ratio * 100

    # ── Status Weight Score (0–100) ───────────
    status_weight = STATUS_WEIGHTS.get(status, 25)

    # ── Waiting Time Score (0–100) ────────────
    waiting_hours = 0.0
    if pending_created_at is not None:
        # Make both datetimes naive for safe subtraction
        if hasattr(pending_created_at, 'tzinfo') and pending_created_at.tzinfo:
            pending_created_at = pending_created_at.replace(tzinfo=None)
        if hasattr(now, 'tzinfo') and now.tzinfo:
            now = now.replace(tzinfo=None)
        delta = now - pending_created_at
        waiting_hours = max(delta.total_seconds() / 3600, 0)
    waiting_time_score = min(waiting_hours / MAX_WAITING_HOURS, 1.0) * 100

    # ── Final Weighted Score ──────────────────
    priority_score = round(
        WEIGHT_FILL_RATIO * fill_ratio_score
        + WEIGHT_STATUS * status_weight
        + WEIGHT_WAITING_TIME * waiting_time_score,
        1,
    )
    priority_score = min(priority_score, 100.0)

    priority_level = _get_priority_level(priority_score)
    reason = _build_reason(fill_ratio, status, waiting_hours)

    return {
        "fill_ratio": round(fill_ratio, 4),
        "fill_ratio_score": round(fill_ratio_score, 1),
        "status": status,
        "status_weight": status_weight,
        "waiting_hours": round(waiting_hours, 1),
        "waiting_time_score": round(waiting_time_score, 1),
        "priority_score": priority_score,
        "priority_level": priority_level,
        "reason": reason,
    }


def generate_collection_recommendations(locations_data: list) -> list:
    """
    Generate ranked collection recommendations from location/collection data.

    Args:
        locations_data: List of dicts with location + pending collection info.
            Each dict must have: location_id, location_name, area, waste_type,
            capacity, current_level, status, pending_created_at (or None).

    Returns:
        List of recommendation dicts sorted by priority_score descending.
        Tie-breaker: older pending first, then higher fill ratio.
    """
    recommendations = []
    now = datetime.now()

    for loc in locations_data:
        status = calculate_waste_status(
            float(loc["current_level"]), float(loc["capacity"])
        )
        scoring = calculate_priority_score(
            current_level=float(loc["current_level"]),
            capacity=float(loc["capacity"]),
            status=status,
            pending_created_at=loc.get("pending_created_at"),
            now=now,
        )

        recommendations.append({
            "location_id": loc["location_id"],
            "location_name": loc["location_name"],
            "area": loc["area"],
            "waste_type": loc["waste_type"],
            "capacity": float(loc["capacity"]),
            "current_level": float(loc["current_level"]),
            **scoring,
        })

    # Sort: highest priority first; tie-break by waiting_hours desc, fill_ratio desc
    recommendations.sort(
        key=lambda r: (r["priority_score"], r["waiting_hours"], r["fill_ratio"]),
        reverse=True,
    )

    return recommendations


# ── Module 7: Report-level Priority from AI Analysis ──────────
# Uses the same STATUS_WEIGHTS and PRIORITY_THRESHOLDS as location
# priority, but adapted for waste reports where severity comes
# from AI image analysis rather than fill-ratio sensors.
#
# Confidence adjustment: the AI severity weight is multiplied by
# the model's confidence. A HIGH severity at 0.5 confidence gets
# an effective score of 75 * 0.5 = 37.5, not 75. This prevents
# low-confidence AI results from triggering false urgency.

# Threshold below which confidence reduces effective severity
REPORT_CONFIDENCE_REDUCTION_THRESHOLD = 0.7


def calculate_report_priority(
    severity: str,
    confidence: float,
) -> dict:
    """
    Calculate priority score for a waste report based on AI analysis.

    This function integrates Module 7 (AI image analysis) with the
    existing Module 5 priority engine. It uses the same STATUS_WEIGHTS
    and PRIORITY_THRESHOLDS to maintain consistency.

    Args:
        severity: AI-determined severity (LOW/MEDIUM/HIGH/CRITICAL).
        confidence: AI confidence score (0.0–1.0).

    Returns:
        Dictionary with priority_score, priority_level, reason,
        and confidence_adjusted flag.
    """
    # Get base status weight from existing Module 5 weights
    base_weight = STATUS_WEIGHTS.get(severity, 25)

    # Apply confidence adjustment: if confidence is below the reduction
    # threshold, scale down the effective weight proportionally.
    # Above the threshold, full weight is used.
    confidence_adjusted = False
    if confidence < REPORT_CONFIDENCE_REDUCTION_THRESHOLD:
        effective_weight = base_weight * confidence
        confidence_adjusted = True
    else:
        effective_weight = float(base_weight)

    # Priority score for reports is based purely on severity weight
    # (no fill-ratio or waiting-time signals available for citizen reports)
    priority_score = round(min(effective_weight, 100.0), 1)
    priority_level = _get_priority_level(priority_score)

    # Build explanation
    parts = [f"AI severity: {severity}"]
    if confidence_adjusted:
        parts.append(
            f"confidence-adjusted ({confidence:.2f} < {REPORT_CONFIDENCE_REDUCTION_THRESHOLD})"
        )
    else:
        parts.append(f"confidence: {confidence:.2f}")
    reason = ". ".join(parts)

    return {
        "priority_score": priority_score,
        "priority_level": priority_level,
        "reason": reason,
        "confidence_adjusted": confidence_adjusted,
        "effective_weight": round(effective_weight, 1),
        "base_weight": base_weight,
    }
