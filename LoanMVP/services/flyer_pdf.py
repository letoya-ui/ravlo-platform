"""Native, brand-driven flyer generation -- no Canva required.

Canva's real API has no "generate a design matching this logo/style"
endpoint; the only programmatic branding mechanism (Autofill) needs a
Brand Template hand-built by a human inside Canva's own editor first.
These flyers instead draw directly from each partner's own VIPProfile
brand data (logo, brand color, business name) with reportlab -- the
same library already used for deal-plan PDFs (see
LoanMVP.services.investor.deal_plans_pdf) -- so "set up your brand
once" is enough to produce a flyer with zero external dependency.
"""
import io

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from LoanMVP.services.investor.investor_media_helpers import download_image_bytes

PAGE_W, PAGE_H = LETTER
MARGIN = 0.5 * 72  # 0.5in in points
DEFAULT_BRAND_COLOR = "#4f6bed"


def _hex_to_rgb01(hex_color):
    hex_color = (hex_color or "").strip().lstrip("#")
    if len(hex_color) != 6:
        hex_color = DEFAULT_BRAND_COLOR.lstrip("#")
    try:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)
    except ValueError:
        return _hex_to_rgb01(DEFAULT_BRAND_COLOR)


def _draw_wrapped_text(c, text, x, y, max_width, font="Helvetica", size=10, leading=13, max_lines=None):
    """Draw word-wrapped text starting at (x, y), writing downward. Returns the y position after the last line."""
    if not text:
        return y
    c.setFont(font, size)
    lines = simpleSplit(text, font, size, max_width)
    if max_lines:
        lines = lines[:max_lines]
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def _draw_logo_or_business_name(c, logo_url, business_name, x, y, max_width=140, max_height=50, text_color=(1, 1, 1)):
    """Draw the logo image if it downloads cleanly, else the business name as text. Returns nothing (fixed-position header element)."""
    raw = None
    try:
        raw = download_image_bytes(logo_url) if logo_url else None
    except Exception:
        raw = None
    if raw:
        try:
            img = ImageReader(io.BytesIO(raw))
            iw, ih = img.getSize()
            scale = min(max_width / iw, max_height / ih)
            w, h = iw * scale, ih * scale
            c.drawImage(img, x, y - h, width=w, height=h, preserveAspectRatio=True, mask="auto")
            return
        except Exception:
            pass
    c.setFillColorRGB(*text_color)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y - 20, business_name or "Ravlo Partner")


def _draw_photo_or_placeholder(c, photo_url, x, y, width, height, accent_rgb):
    raw = None
    try:
        raw = download_image_bytes(photo_url) if photo_url else None
    except Exception:
        raw = None
    if raw:
        try:
            img = ImageReader(io.BytesIO(raw))
            c.drawImage(img, x, y - height, width=width, height=height, preserveAspectRatio=True, anchor="c", mask="auto")
            return
        except Exception:
            pass
    c.setFillColorRGB(*[min(1, v + 0.25) for v in accent_rgb])
    c.rect(x, y - height, width, height, fill=1, stroke=0)
    c.setFillColorRGB(*accent_rgb)
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(x + width / 2, y - height / 2, "Photo unavailable")


def _contact_line(contact_email, contact_phone):
    parts = [p for p in (contact_phone, contact_email) if p]
    return "  •  ".join(parts)


def _draw_footer(c, profile, contact_email, contact_phone, accent_rgb):
    c.setFillColorRGB(*accent_rgb)
    c.rect(0, 0, PAGE_W, 0.6 * 72, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN, 0.32 * 72, (profile.business_name or profile.display_name or "Ravlo Partner"))
    c.setFont("Helvetica", 9)
    contact = _contact_line(contact_email, contact_phone)
    if contact:
        c.drawRightString(PAGE_W - MARGIN, 0.32 * 72, contact)
    c.setFont("Helvetica", 6.5)
    c.drawString(MARGIN, 0.12 * 72, "Powered by Ravlo")


def build_listing_flyer_pdf(profile, listing, photos, contact_email=None, contact_phone=None) -> io.BytesIO:
    """A single-page 'Just Listed' style flyer for one ElenaListing, branded
    with the owning VIPProfile's logo/color/business name."""
    accent_rgb = _hex_to_rgb01(getattr(profile, "brand_color", None))

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)

    # Header band
    header_h = 1.1 * 72
    c.setFillColorRGB(*accent_rgb)
    c.rect(0, PAGE_H - header_h, PAGE_W, header_h, fill=1, stroke=0)
    _draw_logo_or_business_name(
        c, getattr(profile, "logo_url", None), profile.business_name or profile.display_name,
        MARGIN, PAGE_H - 0.3 * 72,
    )
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.45 * 72, "JUST LISTED")

    # Photo
    photo_top = PAGE_H - header_h - 0.25 * 72
    photo_h = 3.6 * 72
    photo_w = PAGE_W - 2 * MARGIN
    _draw_photo_or_placeholder(c, photos[0] if photos else None, MARGIN, photo_top, photo_w, photo_h, accent_rgb)

    # Price + address
    y = photo_top - photo_h - 0.35 * 72
    price = listing.price
    price_text = f"${price:,.0f}" if isinstance(price, (int, float)) else "Price upon request"
    c.setFillColorRGB(*accent_rgb)
    c.setFont("Helvetica-Bold", 26)
    c.drawString(MARGIN, y, price_text)

    y -= 0.32 * 72
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("Helvetica-Bold", 13)
    address_line = listing.address or ""
    c.drawString(MARGIN, y, address_line)

    y -= 0.24 * 72
    c.setFont("Helvetica", 11)
    city_line = ", ".join(p for p in (listing.city, listing.state, listing.zip_code) if p)
    c.drawString(MARGIN, y, city_line)

    # Beds/baths/sqft
    y -= 0.35 * 72
    stats = []
    if listing.beds is not None:
        stats.append(f"{listing.beds} bd")
    if listing.baths is not None:
        stats.append(f"{listing.baths} ba")
    if listing.sqft is not None:
        stats.append(f"{listing.sqft:,} sqft")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN, y, "   |   ".join(stats))

    # Description
    y -= 0.35 * 72
    _draw_wrapped_text(
        c, listing.description or "", MARGIN, y, PAGE_W - 2 * MARGIN,
        font="Helvetica", size=10, leading=13, max_lines=6,
    )

    _draw_footer(c, profile, contact_email, contact_phone, accent_rgb)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


def _business_body_text(profile):
    """profile.bio is an optional onboarding field -- most partners never
    fill it in, which used to leave the flyer body blank. Fall back to
    whatever profile fields *are* set before giving up to a generic CTA."""
    if profile.bio:
        return profile.bio
    parts = []
    specialties = getattr(profile, "specialties", None)
    service_area = getattr(profile, "service_area", None)
    if specialties:
        parts.append(f"Specializing in {specialties}.")
    if service_area:
        parts.append(f"Proudly serving {service_area}.")
    if parts:
        return " ".join(parts)
    name = profile.business_name or profile.display_name or "us"
    return f"Contact {name} today to learn more about our services."


def build_business_flyer_pdf(profile, contact_email=None, contact_phone=None) -> io.BytesIO:
    """A single-page 'About Us' style flyer for a partner with no specific
    listing to advertise (contractors, insurance agents, loan officers)."""
    accent_rgb = _hex_to_rgb01(getattr(profile, "brand_color", None))

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)

    header_h = 2.4 * 72
    c.setFillColorRGB(*accent_rgb)
    c.rect(0, PAGE_H - header_h, PAGE_W, header_h, fill=1, stroke=0)
    _draw_logo_or_business_name(
        c, getattr(profile, "logo_url", None), profile.business_name or profile.display_name,
        MARGIN, PAGE_H - 0.4 * 72, max_width=200, max_height=70,
    )
    if profile.headline:
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica", 13)
        c.drawString(MARGIN, PAGE_H - header_h + 0.5 * 72, profile.headline)

    y = PAGE_H - header_h - 0.5 * 72
    c.setFillColorRGB(0.1, 0.1, 0.1)
    y = _draw_wrapped_text(
        c, _business_body_text(profile), MARGIN, y, PAGE_W - 2 * MARGIN,
        font="Helvetica", size=12, leading=17, max_lines=16,
    )

    _draw_footer(c, profile, contact_email, contact_phone, accent_rgb)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
