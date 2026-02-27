import os
from openai import OpenAI

def get_openai_client() -> OpenAI:
    # Render env vars sometimes end with newline (common when copy/paste)
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=key)
