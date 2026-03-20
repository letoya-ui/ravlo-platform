import os
import uuid
import base64
import requests
from flask import current_app


def save_ai_image(base64_str, folder="uploads/studios"):
    filename = f"{uuid.uuid4().hex}.png"
    relative_path = f"{folder}/{filename}"
    absolute_path = os.path.join(current_app.root_path, "static", relative_path)

    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)

    with open(absolute_path, "wb") as f:
        f.write(base64.b64decode(base64_str))

    return relative_path


def transform_image_style(image_path, style_prompt):
    """
    image_path = relative path like 'uploads/studios/input.png'
    """

    try:
        # -------------------------------
        # LOAD IMAGE FROM STATIC
        # -------------------------------
        absolute_path = os.path.join(current_app.root_path, "static", image_path)

        with open(absolute_path, "rb") as f:
            image_bytes = f.read()

        # Convert to base64 for API
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "image": image_b64,
            "prompt": f"Transform this room into: {style_prompt}",
        }

        AI_URL = "http://localhost:5001/ai/image/transform"

        resp = requests.post(AI_URL, json=payload, timeout=120)
        resp.raise_for_status()

        data = resp.json()

        # -------------------------------
        # EXPECT BASE64 BACK
        # -------------------------------
        output_b64 = data.get("image")

        if not output_b64:
            raise ValueError("No image returned from AI")

        # -------------------------------
        # SAVE OUTPUT
        # -------------------------------
        saved_path = save_ai_image(output_b64)

        return f"/static/{saved_path}"

    except Exception as e:
        print("AI transform error:", str(e))

        # fallback image
        return "/static/images/placeholders/rehab_placeholder.jpg"