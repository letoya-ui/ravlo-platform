from datetime import datetime


BLOCK_REASONS = {
    "non_payment": "Non-Payment",
    "manual_review": "Manual Review",
    "compliance_hold": "Compliance Hold",
    "chargeback": "Chargeback",
    "fraud_review": "Fraud Review",
}


def normalize_text(value):
    return (value or "").strip().lower()


def get_block_reason_display(reason: str) -> str:
    key = normalize_text(reason)
    return BLOCK_REASONS.get(key, key.replace("_", " ").title() if key else "Blocked")


def is_user_blocked(user) -> bool:
    if not user:
        return False

    if getattr(user, "is_blocked", False):
        return True

    company = getattr(user, "company", None)
    if company and getattr(company, "is_blocked", False):
        return True

    return False


def get_user_block_message(user) -> str:
    company = getattr(user, "company", None)

    if company and getattr(company, "is_blocked", False):
        reason = get_block_reason_display(getattr(company, "blocked_reason", None))
        return f"Your company account is currently blocked. Reason: {reason}."

    if getattr(user, "is_blocked", False):
        reason = get_block_reason_display(getattr(user, "blocked_reason", None))
        return f"Your account is currently blocked. Reason: {reason}."

    return "Your account is currently unavailable."