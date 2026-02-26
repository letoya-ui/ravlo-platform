from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from datetime import datetime
from LoanMVP.utils.signature_block import generate_signature_block
from flask import current_app
import os

def generate_preapproval_pdf(
    borrower,
    loan,
    summary,
    front_dti,
    back_dti,
    ltv,
    p_and_i=None,
    taxes=None,
    insurance=None,
    pmi=None,
    total_payment=None
):
    filename = f"preapproval_{borrower.id}_{loan.id}.pdf"
    output_path = os.path.join(
        current_app.instance_path,
        "generated_letters",
        filename
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    doc = SimpleDocTemplate(output_path, pagesize=LETTER)

    style_title = ParagraphStyle(
        "Title",
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=colors.HexColor("#7ab8ff"),
        spaceAfter=20
    )

    style_body = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=11,
        textColor=colors.black,
        leading=15
    )

    story = []

    # --- Header ---
    story.append(Paragraph("Caughman Mason Loan Services", style_title))
    story.append(Paragraph("<b>PRE-APPROVAL LETTER</b>", style_title))
    story.append(Spacer(1, 20))

    # Borrower details
    story.append(Paragraph(f"<b>Borrower:</b> {borrower.full_name}", style_body))
    story.append(Paragraph(f"<b>Email:</b> {borrower.email}", style_body))
    story.append(Paragraph(f"<b>Phone:</b> {borrower.phone}", style_body))
    story.append(Spacer(1, 10))

    # Loan details
    story.append(Paragraph(f"<b>Loan Amount:</b> ${loan.amount}", style_body))
    story.append(Paragraph(f"<b>Loan Type:</b> {loan.loan_type}", style_body))
    story.append(Paragraph(f"<b>Property Value:</b> ${loan.property_value}", style_body))
    story.append(Paragraph(f"<b>Address:</b> {loan.property_address}", style_body))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Principal & Interest:</b> ${p_and_i}", style_body))
    story.append(Paragraph(f"<b>Taxes:</b> ${taxes}", style_body))
    story.append(Paragraph(f"<b>Insurance:</b> ${insurance}", style_body))
    story.append(Paragraph(f"<b>PMI:</b> ${pmi}", style_body))
    story.append(Paragraph(f"<b>Total Payment:</b> ${total_payment}", style_body))
    story.append(Spacer(1, 20))

    # Ratios (safe handling)
    ltv_display = f"{round(ltv*100,2)}%" if ltv is not None else "N/A"
    front_dti_display = f"{round(front_dti*100,2)}%" if front_dti is not None else "N/A"
    back_dti_display = f"{round(back_dti*100,2)}%" if back_dti is not None else "N/A"

    story.append(Paragraph(f"<b>LTV:</b> {ltv_display}", style_body))
    story.append(Paragraph(f"<b>Front-End DTI:</b> {front_dti_display}", style_body))
    story.append(Paragraph(f"<b>Back-End DTI:</b> {back_dti_display}", style_body))
    story.append(Spacer(1, 20))

    # AI underwriting summary
    story.append(Paragraph("<b>AI Underwriting Summary:</b>", style_body))
    story.append(Spacer(1, 10))
    for line in summary.split("\n"):
        story.append(Paragraph(line.replace("\n", "<br/>"), style_body))

    story.append(Spacer(1, 20))

    # Footer
    date_str = datetime.now().strftime("%B %d, %Y")
    story.append(Paragraph(f"Generated on {date_str} by Caughman Mason Loan Services.", style_body))
    story.append(Spacer(1, 10))
    story.append(Paragraph("This pre-approval is subject to underwriting verification and property approval.", style_body))

    # Signature block
    officer = loan.loan_officer if loan.loan_officer else None

    if officer:
        sig_block = generate_signature_block(officer)
        story.extend(sig_block)

    # Build PDF
    doc.build(story)

    print("PDF saved to:", output_path, os.path.exists(output_path))

    return output_path