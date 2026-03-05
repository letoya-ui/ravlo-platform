import cv2
import numpy as np
import requests
from io import BytesIO
from PIL import Image

def extract_blueprint_structure(blueprint_url):
    img = _load_image(blueprint_url)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Wall detection (Hough lines)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80, minLineLength=40, maxLineGap=10)

    walls = []
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0]:
            walls.append({"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)})

    # Fixtures (MVP: detect circles for toilets/sinks)
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=40,
                               param1=50, param2=30, minRadius=10, maxRadius=60)

    fixtures = []
    if circles is not None:
        for c in circles[0]:
            fixtures.append({"type": "circle", "x": int(c[0]), "y": int(c[1]), "r": int(c[2])})

    return {
        "walls": walls,
        "fixtures": fixtures,
        "doors": [],
        "windows": [],
        "layout_mask": None,
        "depth_map": None
    }

def _load_image(url):
    r = requests.get(url)
    img = Image.open(BytesIO(r.content)).convert("RGB")
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def infer_room_type(structure):
    fixtures = structure.get("fixtures", [])

    # MVP rules
    if len(fixtures) >= 2:
        return "bathroom"
    if len(fixtures) == 1:
        return "kitchen"
    return "living_room"
