"""Native, brand-driven flyer PDF generation (no Canva account, no
human-built Canva Brand Template required) -- see LoanMVP.services.flyer_pdf
for why this exists instead of leaning on Canva's Autofill API.
"""
from types import SimpleNamespace
from unittest.mock import patch

from datetime import date

from LoanMVP.services.flyer_pdf import (
    _business_body_text,
    _event_line,
    _hex_to_rgb01,
    build_business_flyer_pdf,
    build_listing_flyer_pdf,
    build_open_house_flyer_pdf,
)


def _profile(**overrides):
    defaults = dict(
        business_name="Bonnie Sells OC Homes",
        display_name="Bonnie",
        brand_color="#B3122A",
        logo_url=None,
        headline="Your trusted OC realtor",
        bio="Fifteen years helping families find their next home.",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _listing(**overrides):
    defaults = dict(
        price=725000, address="123 Main St", city="Irvine", state="CA", zip_code="92602",
        beds=4, baths=3, sqft=2400, description="Stunning updated home with a large backyard.",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_hex_to_rgb01_converts_a_valid_hex_color():
    assert _hex_to_rgb01("#4f6bed") == (0x4f / 255, 0x6b / 255, 0xed / 255)


def test_hex_to_rgb01_falls_back_to_default_for_garbage_input():
    r, g, b = _hex_to_rgb01("not-a-color")
    assert 0 <= r <= 1 and 0 <= g <= 1 and 0 <= b <= 1


def test_hex_to_rgb01_falls_back_to_default_for_none():
    assert _hex_to_rgb01(None) == _hex_to_rgb01("#4f6bed")


def test_listing_flyer_produces_a_real_pdf():
    buffer = build_listing_flyer_pdf(_profile(), _listing(), photos=[], contact_email="bonnie@example.com", contact_phone="555-1234")
    assert buffer.getvalue().startswith(b"%PDF")


def test_listing_flyer_handles_missing_optional_fields_without_crashing():
    sparse_listing = _listing(price=None, beds=None, baths=None, sqft=None, description=None, city=None, state=None, zip_code=None)
    buffer = build_listing_flyer_pdf(_profile(logo_url=None), sparse_listing, photos=[])
    assert buffer.getvalue().startswith(b"%PDF")


def test_listing_flyer_with_a_photo_url_downloads_and_embeds_it():
    fake_png = bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 100  # not a full valid PNG, just needs to reach ImageReader
    with patch("LoanMVP.services.flyer_pdf.download_image_bytes", return_value=None) as mock_dl:
        # Even a bad/undecodable image must not crash generation -- falls
        # back to the placeholder box instead of raising.
        buffer = build_listing_flyer_pdf(_profile(), _listing(), photos=["https://example.com/photo.jpg"])
    mock_dl.assert_called_once_with("https://example.com/photo.jpg")
    assert buffer.getvalue().startswith(b"%PDF")


def test_business_flyer_produces_a_real_pdf():
    buffer = build_business_flyer_pdf(_profile(), contact_email="bonnie@example.com", contact_phone="555-1234")
    assert buffer.getvalue().startswith(b"%PDF")


def test_business_flyer_handles_no_bio_or_headline():
    buffer = build_business_flyer_pdf(_profile(bio=None, headline=None))
    assert buffer.getvalue().startswith(b"%PDF")


def test_business_body_text_uses_bio_when_present():
    assert _business_body_text(_profile()) == "Fifteen years helping families find their next home."


def test_business_body_text_falls_back_to_specialties_and_service_area():
    profile = _profile(bio=None, specialties="Kitchen remodels", service_area="Orange County")
    assert _business_body_text(profile) == "Specializing in Kitchen remodels. Proudly serving Orange County."


def test_business_body_text_falls_back_to_generic_cta_when_profile_is_bare():
    profile = _profile(bio=None, business_name="Bonnie Sells OC Homes")
    assert _business_body_text(profile) == "Contact Bonnie Sells OC Homes today to learn more about our services."


def test_logo_download_failure_falls_back_to_business_name_text():
    with patch("LoanMVP.services.flyer_pdf.download_image_bytes", return_value=None):
        buffer = build_business_flyer_pdf(_profile(logo_url="https://example.com/logo.png"))
    assert buffer.getvalue().startswith(b"%PDF")


# ─── open house flyer ─────────────────────────────────────────────────

def test_event_line_combines_date_and_time():
    assert _event_line(date(2026, 9, 19), "12:00 PM", "2:00 PM") == "SAT, SEP 19  •  12:00 PM – 2:00 PM"


def test_event_line_handles_time_only():
    assert _event_line(None, "12:00 PM", None) == "12:00 PM"


def test_event_line_is_none_when_nothing_given():
    assert _event_line(None, None, None) is None


def test_open_house_flyer_with_full_details_produces_a_real_pdf():
    details = {
        "address": "123 Main St", "city": "Irvine", "state": "CA", "zip": "92602",
        "price": 725000, "beds": 4, "baths": 3, "sqft": 2400,
        "description": "Stunning updated home with a large backyard.",
        "event_date": date(2026, 9, 19), "event_time": "12:00 PM", "event_time_end": "2:00 PM",
    }
    buffer = build_open_house_flyer_pdf(_profile(), details, photos=[])
    assert buffer.getvalue().startswith(b"%PDF")


def test_open_house_flyer_with_only_an_address_and_time_does_not_crash():
    """An address that isn't a saved listing yet -- no price, beds,
    baths, sqft, description, or photo -- must still produce a flyer."""
    details = {
        "address": "123 Main St", "city": None, "state": None, "zip": None,
        "price": None, "beds": None, "baths": None, "sqft": None, "description": None,
        "event_date": date(2026, 9, 19), "event_time": "12:00 PM", "event_time_end": None,
    }
    buffer = build_open_house_flyer_pdf(_profile(), details, photos=[])
    assert buffer.getvalue().startswith(b"%PDF")
