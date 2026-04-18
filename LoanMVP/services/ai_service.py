import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_text(prompt: str) -> str:
    """
    Unified AI text generator for Elena and all other modules.
    Uses OpenAI GPT-4o-mini by default.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message["content"]
    except Exception as e:
        print("AI Provider Error:", e)
        return "⚠️ AI generation failed."
