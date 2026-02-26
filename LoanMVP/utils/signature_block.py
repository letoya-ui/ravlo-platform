from reportlab.platypus import Image, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from flask import current_app
import os

def generate_signature_block(officer):
    user = officer.user

    first = user.first_name or ""
    last = user.last_name or ""
    nmls = officer.nmls or "N/A"
    phone = officer.phone or "N/A"
    email = user.email or "N/A"

    # Build absolute path to signature image
    signature_path = os.path.join(
        current_app.root_path, "static", "images", "signature_lo.png"
    )

    style_body = ParagraphStyle(
        "Signature",
        fontName="Helvetica",
        fontSize=11,
        leading=14
    )

    flowables = [
        Spacer(1, 20),
        Image(signature_path, width=180, height=60),
        Spacer(1, 10),
        Paragraph(f"<b>{first} {last}</b>", style_body),
        Paragraph("Loan Officer — Caughman Mason Loan Services", style_body),
        Paragraph(f"NMLS: {nmls}", style_body),
        Paragraph(f"Phone: {phone}", style_body),
        Paragraph(f"Email: {email}", style_body),
        Spacer(1, 20)
    ]

    return flowables