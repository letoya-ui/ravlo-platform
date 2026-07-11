import io

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from LoanMVP.services.investor.investor_media_helpers import download_image_bytes
from LoanMVP.services.investor.investor_route_helpers import _get_rehab_export_payload


def _fmt_money(value):
    if value is None:
        return "—"
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _draw_image_or_label(c, x, y, url, label, max_width=200, max_height=140):
    """Embed the image at (x, y-max_height) if it downloads cleanly, else draw a text label.

    Returns the y position to continue drawing below this block.
    """
    try:
        raw = download_image_bytes(url) if url else None
    except Exception:
        raw = None
    if raw:
        try:
            img = ImageReader(io.BytesIO(raw))
            iw, ih = img.getSize()
            scale = min(max_width / iw, max_height / ih)
            w, h = iw * scale, ih * scale
            c.drawImage(img, x, y - h, width=w, height=h, preserveAspectRatio=True, mask="auto")
            return y - h - 12
        except Exception:
            pass
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(x, y - 12, f"{label} (image unavailable)")
    return y - 26


def build_deal_plans_pdf(deal) -> io.BytesIO:
    """Render a Ravlo Development Report PDF: property summary, development
    summary (purchase price, down payment, build/repair budget), key
    results, rehab summary, and the Design/Build Studio plans -- blueprint,
    site plan, and one photo per generated room -- so the whole package can
    be sent to a loan officer, another investor, or anyone else."""
    r = deal.results_json or {}
    resolved = deal.resolved_json or {}
    rehab = _get_rehab_export_payload(deal)
    build_project = r.get("build_project") or {}

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "RAVLO Development Report")
    y -= 22

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Title: {deal.title or '—'}"); y -= 14
    c.drawString(50, y, f"Property ID: {getattr(deal, 'property_id', None) or '—'}"); y -= 14
    c.drawString(50, y, f"Strategy: {getattr(deal, 'strategy', None) or '—'}"); y -= 14
    if getattr(deal, "created_at", None):
        c.drawString(50, y, f"Created: {deal.created_at.strftime('%Y-%m-%d %H:%M')}"); y -= 22
    else:
        y -= 22

    prop = (resolved.get("property") or {}) if isinstance(resolved, dict) else {}
    addr = prop.get("address")
    city = prop.get("city")
    state = prop.get("state")
    zipc = prop.get("zip")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Property Summary"); y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Address: {addr or '—'}"); y -= 14
    c.drawString(50, y, f"City/State/Zip: {city or '—'}, {state or '—'} {zipc or ''}"); y -= 18

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Development Summary"); y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Purchase Price: {_fmt_money(deal.purchase_price)}"); y -= 14
    c.drawString(50, y, f"Down Payment: {_fmt_money(r.get('down_payment'))}"); y -= 14
    c.drawString(50, y, f"Build / Repair Budget: {_fmt_money(deal.rehab_cost)}"); y -= 14
    c.drawString(50, y, f"After Repair Value (ARV): {_fmt_money(deal.arv)}"); y -= 14
    c.drawString(50, y, f"Total Project Cost: {_fmt_money(deal.total_project_cost)}"); y -= 14
    c.drawString(50, y, f"Estimated Profit: {_fmt_money(deal.estimated_profit)}"); y -= 18

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Key Results"); y -= 16
    c.setFont("Helvetica", 10)

    if "profit" in r:
        c.drawString(50, y, f"Flip Profit: {_fmt_money(r.get('profit'))}")
        y -= 14
    if "net_cashflow" in r:
        c.drawString(50, y, f"Rental Net Cashflow (mo): {_fmt_money(r.get('net_cashflow'))}")
        y -= 14
    if "net_monthly" in r:
        c.drawString(50, y, f"Airbnb Net Monthly: {_fmt_money(r.get('net_monthly'))}")
        y -= 14

    y -= 10

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Rehab Summary"); y -= 16
    c.setFont("Helvetica", 10)

    if isinstance(rehab, dict) and rehab:
        total_rehab = rehab.get("total") or rehab.get("estimated_rehab_cost")
        scope_value = rehab.get("scope")
        cpsf = rehab.get("cost_per_sqft")

        if isinstance(scope_value, dict):
            scope_label = scope_value.get("rehab_level") or "Detailed scope"
        else:
            scope_label = scope_value or "—"

        c.drawString(50, y, f"Scope: {scope_label}"); y -= 14
        c.drawString(50, y, f"Total Rehab: {_fmt_money(total_rehab)}"); y -= 14
        c.drawString(50, y, f"Cost per Sqft: {_fmt_money(cpsf)}"); y -= 14
    else:
        c.drawString(50, y, "No rehab summary available."); y -= 14

    if build_project:
        c.showPage()
        y = height - 50

        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y, "Design & Build Studio Plans")
        y -= 24

        description = build_project.get("description") or build_project.get("notes")
        if description:
            c.setFont("Helvetica", 10)
            c.drawString(50, y, description[:110])
            y -= 20

        blueprint_url = (build_project.get("blueprint") or {}).get("image_url")
        site_plan_url = (
            (build_project.get("site_plan") or {}).get("image_url")
            or (build_project.get("blueprint_floor2") or {}).get("image_url")
        )

        if blueprint_url or site_plan_url:
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "Blueprint / Site Plan"); y -= 16
            top = y
            if blueprint_url:
                _draw_image_or_label(c, 50, top, blueprint_url, "Blueprint")
            if site_plan_url:
                y = _draw_image_or_label(c, 280, top, site_plan_url, "Site plan")
            else:
                y = top - 152

        rooms = ((build_project.get("interior") or {}).get("rooms")) or []
        if rooms:
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "Rooms"); y -= 16

            col_x = [50, 280]
            col = 0
            row_top = y
            for room in rooms:
                label = " / ".join(
                    str(part) for part in (room.get("room_type"), room.get("floor"), room.get("style")) if part
                ) or "Room"
                images = room.get("images") or ([room["image_url"]] if room.get("image_url") else [])
                image_url = images[0] if images else None

                if row_top < 170:
                    c.showPage()
                    row_top = height - 60
                    col = 0

                c.setFont("Helvetica", 9)
                c.drawString(col_x[col], row_top, label)
                next_y = _draw_image_or_label(c, col_x[col], row_top - 4, image_url, label)

                if col == 0:
                    col = 1
                else:
                    col = 0
                    row_top = next_y

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
