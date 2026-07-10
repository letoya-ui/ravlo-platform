"""Regression tests for the pixel heuristic that decides whether an
uploaded reference photo "looks like" a floor-plan diagram.

_image_bytes_look_like_floor_plan() used a loose "mostly light pixels, low
saturation" test (pct_light >= 0.38, pct_dark >= 0.012, saturation <= 72)
meant to catch black-lines-on-white-paper blueprint scans. In practice this
also matches ordinary bright, neutral-toned real estate photos (white
kitchens, coastal/farmhouse staging) -- ANY well-lit, desaturated room
photo satisfies it just as well as an actual line drawing.

When it misfires, the upload gets classified as a floor plan and stored
under payload["blueprint_image_base64"] instead of payload["image_base64"],
which (before the companion fix in llm_studio_service.py) the OpenAI
fallback never read -- so the user's actual room photo was silently
dropped and the AI redesign was generated from the text prompt alone,
completely unrelated to the real room.
"""
import io

from PIL import Image

from LoanMVP.routes.investor_routes import _image_bytes_look_like_floor_plan


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _bright_white_kitchen_photo() -> Image.Image:
    """A believable staged real estate photo: bright white cabinets/walls,
    a warm wood floor, and a few dark hardware/appliance accents.
    """
    img = Image.new("RGB", (400, 300), (245, 245, 242))
    px = img.load()
    for x in range(400):
        for y in range(200, 300):
            px[x, y] = (196, 164, 132)
    for x in range(20, 60):
        for y in range(50, 140):
            px[x, y] = (25, 25, 25)
    return img


def _coastal_room_photo() -> Image.Image:
    """A bright, airy coastal-style living room photo: light blue accent
    wall, neutral walls, one dark sofa silhouette.
    """
    img = Image.new("RGB", (400, 300), (238, 240, 235))
    px = img.load()
    for x in range(400):
        for y in range(0, 80):
            px[x, y] = (210, 225, 232)
    for x in range(300, 400):
        for y in range(150, 300):
            px[x, y] = (60, 60, 60)
    return img


def _floor_plan_diagram() -> Image.Image:
    """An actual architectural floor plan: white paper, thin black
    rectilinear lines, no color.
    """
    img = Image.new("RGB", (400, 300), (255, 255, 255))
    px = img.load()
    for x in range(400):
        for t in (-1, 0, 1):
            px[x, 20 + t] = (0, 0, 0)
            px[x, 150 + t] = (0, 0, 0)
            px[x, 280 + t] = (0, 0, 0)
    for y in range(300):
        for t in (-1, 0, 1):
            px[20 + t, y] = (0, 0, 0)
            px[200 + t, y] = (0, 0, 0)
            px[380 + t, y] = (0, 0, 0)
    return img


def test_bright_white_kitchen_photo_is_not_flagged_as_floor_plan():
    assert _image_bytes_look_like_floor_plan(_png_bytes(_bright_white_kitchen_photo())) is False


def test_coastal_room_photo_is_not_flagged_as_floor_plan():
    assert _image_bytes_look_like_floor_plan(_png_bytes(_coastal_room_photo())) is False


def test_actual_floor_plan_diagram_is_still_flagged():
    assert _image_bytes_look_like_floor_plan(_png_bytes(_floor_plan_diagram())) is True


def test_empty_bytes_is_not_flagged():
    assert _image_bytes_look_like_floor_plan(b"") is False
    assert _image_bytes_look_like_floor_plan(None) is False
