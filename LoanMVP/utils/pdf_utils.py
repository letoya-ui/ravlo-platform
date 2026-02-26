from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfReader, PdfWriter

def add_signature_to_pdf(input_pdf, signature_img, output_pdf):
    packet = io.BytesIO()

    # Create a blank PDF for signature overlay
    can = canvas.Canvas(packet, pagesize=letter)
    can.drawImage(signature_img, 100, 100, width=200, height=80)  # position signature
    can.save()

    packet.seek(0)
    overlay = PdfReader(packet)
    existing_pdf = PdfReader(open(input_pdf, "rb"))
    output = PdfWriter()

    # Merge overlay onto first page
    page = existing_pdf.pages[0]
    page.merge_page(overlay.pages[0])
    output.add_page(page)

    # Copy remaining pages
    for p in existing_pdf.pages[1:]:
        output.add_page(p)

    with open(output_pdf, "wb") as f:
        output.write(f)
