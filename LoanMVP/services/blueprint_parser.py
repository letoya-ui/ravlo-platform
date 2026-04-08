try:
    import cv2
except ModuleNotFoundError:
    cv2 = None
import numpy as np
import requests
from io import BytesIO
from PIL import Image

def extract_blueprint_structure(blueprint_url: str):
    img = _load_image(blueprint_url)
    h, w = img.shape[:2]

    # Keep investor routes bootable even when OpenCV is unavailable in the
    # current runtime. We return a lightweight structural shell instead of
    # failing the entire blueprint import.
    if cv2 is None:
        return {
            "image_w": int(w),
            "image_h": int(h),
            "walls": [],
            "fixtures": [],
            "doors": [],
            "windows": [],
            "layout_mask": None,
            "depth_map": None,
            "parser_status": "cv2_unavailable",
        }

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Wall detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80, minLineLength=40, maxLineGap=10)

    walls = []
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0]:
            walls.append({"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)})

    # Fixtures (circles)
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT,
        dp=1.2, minDist=40,
        param1=50, param2=30,
        minRadius=10, maxRadius=60
    )

    fixtures = []
    if circles is not None:
        for c in circles[0]:
            fixtures.append({"type": "circle", "x": int(c[0]), "y": int(c[1]), "r": int(c[2])})

    return {
        "image_w": int(w),
        "image_h": int(h),
        "walls": walls,
        "fixtures": fixtures,
        "doors": [],
        "windows": [],
        "layout_mask": None,
        "depth_map": None
    }

def _load_image(url: str):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    img = Image.open(BytesIO(r.content)).convert("RGB")
    arr = np.array(img)
    if cv2 is None:
        return arr
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

def infer_room_type(structure: dict) -> str:
    """
    MVP heuristic. Treat as best-effort only.
    """
    fixtures = structure.get("fixtures", []) or []
    n = len(fixtures)

    if n >= 2:
        return "bathroom"
    if n == 1:
        # could be kitchen OR bath; keep safe:
        return "kitchen"
    return "living_room"
