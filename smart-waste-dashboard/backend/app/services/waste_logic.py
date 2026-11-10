"""
Business logic for waste status calculation.
Single source of truth for status derivation — NOT duplicated elsewhere.
"""


def calculate_waste_status(current_level: float, capacity: float) -> str:
    """
    Derive waste status from fill percentage.

    Recommended default bands:
        0–50%   → LOW
        51–75%  → MEDIUM
        76–90%  → HIGH
        91–100% → CRITICAL

    Args:
        current_level: Current fill amount.
        capacity: Maximum capacity of the container.

    Returns:
        Status string: 'LOW', 'MEDIUM', 'HIGH', or 'CRITICAL'.
    """
    if capacity <= 0:
        return "CRITICAL"

    percentage = (current_level / capacity) * 100

    if percentage <= 50:
        return "LOW"
    elif percentage <= 75:
        return "MEDIUM"
    elif percentage <= 90:
        return "HIGH"
    else:
        return "CRITICAL"
