# LoanMVP/services/vip_ai_pilot.py
"""Lightweight NL intent parser for the Ravlo copilot.

Turns a natural-language voice/text command into a structured intent that the
VIP blueprint can dispatch — adding listings, logging expenses, drafting
flyers, or just saving a free-form suggestion.
"""

import re


WAKE_WORDS = ("ravlo", "hey ravlo", "okay ravlo", "ok ravlo")


def _strip_wake_word(text: str) -> str:
    lower = text.lower().strip()
    for word in WAKE_WORDS:
        if lower.startswith(word):
            return text[len(word):].lstrip(" ,.:;-")
    return text


def _extract_amount(text: str):
    m = re.search(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)", text)
    if not m:
        return None
    try:
        return int(round(float(m.group(1).replace(",", ""))))
    except (TypeError, ValueError):
        return None


def _extract_address(text: str):
    m = re.search(
        r"(?:at|on|for)\s+(\d+\s+[A-Za-z0-9 '.,-]{2,80})",
        text, flags=re.IGNORECASE,
    )
    if m:
        return m.group(1).strip().rstrip(".")
    m = re.search(r"(\d+\s+[A-Za-z][A-Za-z0-9 '.,-]{2,80})", text)
    if m:
        return m.group(1).strip().rstrip(".")
    return None


def parse_vip_command(command: str) -> dict:
    raw = (command or "").strip()
    if not raw:
        return {
            "intent":          "empty",
            "suggestion_type": "note",
            "title":           "Empty command",
            "body":            "",
            "executed":        False,
        }

    body = _strip_wake_word(raw)
    text = body.lower()

    if any(k in text for k in ("add listing", "new listing", "list my", "list a property", "add my listing", "create listing")):
        return {
            "intent":          "add_listing",
            "suggestion_type": "listing",
            "title":           "Add Listing",
            "body":            body,
            "address":         _extract_address(body),
            "price":           _extract_amount(body),
        }

    if any(k in text for k in ("flyer", "make a flyer", "design flyer", "create flyer")):
        return {
            "intent":          "make_flyer",
            "suggestion_type": "flyer",
            "title":           "Make Flyer",
            "body":            body,
            "address":         _extract_address(body),
        }

    if any(k in text for k in ("commission", "closing", "received", "got paid", "income", "earned")):
        return {
            "intent":          "add_income",
            "suggestion_type": "income",
            "title":           "Log Income",
            "body":            body,
            "amount":          _extract_amount(body),
        }

    if any(k in text for k in ("expense", "paid for", "i paid", "toll", "mile", "gas", "lunch", "meal", "receipt")):
        return {
            "intent":          "add_expense",
            "suggestion_type": "expense",
            "title":           "Log Expense",
            "body":            body,
            "amount":          _extract_amount(body),
        }

    if "follow up" in text or "remind me" in text or "reminder" in text:
        return {
            "intent":          "follow_up",
            "suggestion_type": "follow_up",
            "title":           "Create Follow-Up",
            "body":            body,
        }

    if "email" in text:
        return {
            "intent":          "draft_email",
            "suggestion_type": "email",
            "title":           "Draft Email",
            "body":            body,
        }

    if "text" in text or "sms" in text or "message" in text:
        return {
            "intent":          "draft_text",
            "suggestion_type": "text",
            "title":           "Draft Text Message",
            "body":            body,
        }

    if "tax" in text or "save for tax" in text:
        return {
            "intent":          "tax_suggestion",
            "suggestion_type": "tax",
            "title":           "Tax Set-Aside",
            "body":            body,
        }

    return {
        "intent":          "note",
        "suggestion_type": "note",
        "title":           "Save Note",
        "body":            body,
    }
