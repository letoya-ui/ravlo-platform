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


_MONEY_RE          = re.compile(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)")
_AMOUNT_KEYWORD_RE = re.compile(
    r"(?:for|price(?:\s+of)?|at|worth|amount|total|of)\s+\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
    flags=re.IGNORECASE,
)
_BARE_NUMBER_RE    = re.compile(r"(?<![\w-])([0-9][0-9,]*(?:\.[0-9]+)?)(?![\w-])")


def _extract_amount(text: str):
    """Prefer $-prefixed or keyword-prefixed amounts; fall back to a bare
    number only when nothing that *looks* like money is present. This stops
    street numbers like ``123 Main St for $425,000`` from being interpreted
    as the price."""
    if not text:
        return None

    for regex in (_MONEY_RE, _AMOUNT_KEYWORD_RE):
        m = regex.search(text)
        if m:
            try:
                return int(round(float(m.group(1).replace(",", ""))))
            except (TypeError, ValueError):
                continue

    # Fall back to a bare number, but skip numbers that look like street
    # numbers (``123 Main``) so addresses don't get interpreted as prices.
    for m in _BARE_NUMBER_RE.finditer(text):
        tail = text[m.end(): m.end() + 24]
        if re.match(r"\s+[A-Z][A-Za-z]", tail):
            continue
        try:
            return int(round(float(m.group(1).replace(",", ""))))
        except (TypeError, ValueError):
            continue
    return None


_ADDRESS_TRAILING_WORDS = {"for", "at", "on", "price", "worth", "amount", "total", "of"}


def _clean_address(raw: str) -> str:
    cleaned = raw.strip().rstrip(".").rstrip(",").strip()
    # Drop trailing words like "... Main St for" (the preposition was swept
    # up by the greedy character class).
    tokens = cleaned.split()
    while tokens and tokens[-1].lower() in _ADDRESS_TRAILING_WORDS:
        tokens.pop()
    return " ".join(tokens)


def _extract_address(text: str):
    m = re.search(
        r"(?:at|on|for)\s+(\d+\s+[A-Za-z0-9 '.,-]{2,80}?)(?=\s+(?:for|price|worth|amount|at|on)\b|\s*\$|[.;\n]|$)",
        text, flags=re.IGNORECASE,
    )
    if m:
        return _clean_address(m.group(1))
    m = re.search(r"(\d+\s+[A-Za-z][A-Za-z0-9 '.,-]{2,80}?)(?=\s+(?:for|price|worth|amount|at|on)\b|\s*\$|[.;\n]|$)", text)
    if m:
        return _clean_address(m.group(1))
    m = re.search(r"(\d+\s+[A-Za-z][A-Za-z0-9 '.,-]{2,80})", text)
    if m:
        return _clean_address(m.group(1))
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

    if any(k in text for k in (
        "listing presentation", "pitch deck", "listing pitch",
        "make a presentation", "build a presentation",
    )):
        return {
            "intent":          "listing_presentation",
            "suggestion_type": "presentation",
            "title":           "Listing Presentation",
            "body":            body,
            "address":         _extract_address(body),
        }

    if any(k in text for k in ("flyer", "make a flyer", "design flyer", "create flyer")):
        return {
            "intent":          "make_flyer",
            "suggestion_type": "flyer",
            "title":           "Make Flyer",
            "body":            body,
            "address":         _extract_address(body),
        }

    # Expense intent is checked BEFORE income because "I paid $X in closing
    # costs" should be an expense, not income.
    EXPENSE_STRONG = (
        "expense", "log expense", "record expense",
        "paid for", "i paid", "closing cost", "closing costs",
        "toll", "tolls", "mileage", "receipt",
    )
    # Ambiguous tokens that only fire when accompanied by a money/amount cue.
    # "gas" matches "I bought gas"; "lunch"/"meal" match "lunch with client".
    EXPENSE_AMBIGUOUS = ("gas", "mile", "miles", "lunch", "meal")

    amount_hint = _extract_amount(body)
    has_money_cue = ("$" in body) or (amount_hint is not None)

    if any(k in text for k in EXPENSE_STRONG) or (
        has_money_cue and any(k in text for k in EXPENSE_AMBIGUOUS)
    ):
        return {
            "intent":          "add_expense",
            "suggestion_type": "expense",
            "title":           "Log Expense",
            "body":            body,
            "amount":          amount_hint,
        }

    INCOME_STRONG = (
        "commission", "at closing", "closing commission",
        "log income", "record income", "got paid",
    )
    # Substring matches like "received"/"earned"/"income" trip on
    # everyday phrases ("I received a text", "earned a coffee break").
    # Only treat them as income when there's a money/amount cue.
    INCOME_AMBIGUOUS = ("received", "earned", "income")

    if any(k in text for k in INCOME_STRONG) or (
        has_money_cue and any(k in text for k in INCOME_AMBIGUOUS)
    ):
        return {
            "intent":          "add_income",
            "suggestion_type": "income",
            "title":           "Log Income",
            "body":            body,
            "amount":          amount_hint,
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
