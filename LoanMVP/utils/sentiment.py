def analyze_sentiment(text):
    text_lower = text.lower()

    # Stress / frustration
    if any(w in text_lower for w in ["i don't know", "confused", "lost", "stressed", "upset", "frustrated", "worried"]):
        return "negative"

    # Hesitation
    if any(w in text_lower for w in ["maybe", "not sure", "i guess", "thinking about", "possibly"]):
        return "hesitant"

    # Excited / confident
    if any(w in text_lower for w in ["great", "perfect", "love it", "awesome", "ready", "let's do it"]):
        return "positive"

    # Neutral
    return "neutral"
