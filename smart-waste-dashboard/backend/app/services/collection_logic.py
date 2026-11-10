"""
Business logic for collection lifecycle state machine.
Single source of truth for allowed transitions — NOT duplicated elsewhere.
"""

# Allowed lifecycle transitions: current_status → set of valid next statuses
VALID_TRANSITIONS = {
    "pending": {"assigned", "in_progress"},
    "assigned": {"in_progress", "completed"},
    "in_progress": {"completed"},
    "completed": {"completed"},  # terminal state — allow idempotent re-transition
}

VALID_STATUSES = set(VALID_TRANSITIONS.keys())


def validate_collection_transition(current_status: str, new_status: str) -> tuple[bool, str]:
    """
    Validate whether a collection status transition is allowed.

    Args:
        current_status: The current lifecycle status.
        new_status: The requested next status.

    Returns:
        Tuple of (is_valid, error_message).
        If valid, error_message is empty string.
    """
    if new_status not in VALID_STATUSES:
        return False, f"Invalid status '{new_status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"

    if current_status not in VALID_STATUSES:
        return False, f"Current status '{current_status}' is not recognized"

    # Same status transition is always allowed (idempotent)
    if current_status == new_status:
        return True, ""

    allowed = VALID_TRANSITIONS[current_status]
    if new_status not in allowed:
        if not allowed:
            return False, f"Collection is '{current_status}' and cannot transition further (terminal state)"
        return False, (
            f"Invalid transition: '{current_status}' → '{new_status}'. "
            f"Allowed transitions from '{current_status}': {', '.join(sorted(allowed))}"
        )

    return True, ""
