import os
import requests

RENOVATION_ENGINE_URL = os.getenv("RENOVATION_ENGINE_URL", "http://renovation-engine:8000")

def generate_concept(payload):
    """
    Sends a generation request to the Renovation Engine Docker service.
    """
    response = requests.post(
        f"{RENOVATION_ENGINE_URL}/generate",
        json=payload,
        timeout=180
    )
    response.raise_for_status()
    return response.json()