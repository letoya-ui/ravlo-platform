# LoanMVP/services/vip_ai_pilot.py

def parse_vip_command(command: str) -> dict:
    text = (command or "").strip().lower()

    if not text:
        return {
            "suggestion_type": "note",
            "title": "Empty command",
            "body": "",
        }

    if "email" in text:
        return {
            "suggestion_type": "email",
            "title": "Draft Email",
            "body": command,
        }

    if "text" in text or "sms" in text:
        return {
            "suggestion_type": "text",
            "title": "Draft Text Message",
            "body": command,
        }

    if "follow up" in text or "remind me" in text:
        return {
            "suggestion_type": "follow_up",
            "title": "Create Follow-Up",
            "body": command,
        }

    if "paid" in text or "expense" in text or "toll" in text or "mile" in text:
        return {
            "suggestion_type": "expense",
            "title": "Log Expense",
            "body": command,
        }

    return {
        "suggestion_type": "note",
        "title": "Save Note",
        "body": command,
    }
