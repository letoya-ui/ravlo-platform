def detect_objection(text):
    text = text.lower()

    patterns = {
        "rate_objection": [
            "rate too high", "high rate", "better rate",
            "another lender", "shopping", "shop around"
        ],
        "payment_objection": [
            "payment too high", "can't afford",
            "too expensive", "monthly payment"
        ],
        "trust_objection": [
            "not sure", "don't trust", "scam", "nervous", "unsure"
        ],
        "documentation_objection": [
            "too many documents", "don't want to upload",
            "privacy", "why do you need"
        ],
        "timing_objection": [
            "need to think", "call later",
            "not ready", "wait", "maybe later"
        ]
    }

    for obj_type, triggers in patterns.items():
        if any(t in text for t in triggers):
            return obj_type

    return None
