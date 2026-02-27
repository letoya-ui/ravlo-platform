import os
import base64
from openai import OpenAI

def generate_renovation_images(
    before_image_url: str,
    style_prompt: str,
    variations: int = 2,
):
    """
    Generates HGTV-style renovation variations.
    Returns list of base64 image strings.
    """

    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY missing.")

    client = OpenAI(api_key=key)

    # Ensure safe variation range
    variations = max(1, min(int(variations), 4))

    prompt = f"""
    HGTV renovation transformation.
    Keep same room layout and perspective.
    Apply this style: {style_prompt}.
    High realism. Professional real estate photography.
    """

    results = []

    for _ in range(variations):
        response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
            image=before_image_url
        )

        # Base64 image returned
        img_b64 = response.data[0].b64_json
        img_data_url = f"data:image/png;base64,{img_b64}"
        results.append(img_data_url)

    return results
