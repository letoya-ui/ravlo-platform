import requests

def transform_image_style(image, style_prompt):
    """
    Sends image + style prompt to your AI image endpoint.
    """

    payload = {
        "image": image,
        "prompt": f"Transform this room into: {style_prompt}",
    }

    AI_URL = "http://localhost:5001/ai/image/transform"  # adjust as needed

    resp = requests.post(AI_URL, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data.get("image")
