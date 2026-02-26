from pdfrw import PdfReader, PdfWriter
import os

TEMPLATE_PATH = "LoanMVP/static/pdf/1003_template.pdf"
OUTPUT_DIR = "LoanMVP/generated/"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def fill_1003_pdf(borrower, loan):
    """Fill the 1003 PDF with borrower + loan data and return file path."""

    pdf = PdfReader(TEMPLATE_PATH)

    # Safe borrower + loan mapping
    data = {
        "BorrowerName": borrower.full_name or "",
        "BorrowerEmail": borrower.email or "",
        "BorrowerPhone": borrower.phone or "",
        "BorrowerAddress": borrower.address or "",
        "BorrowerCity": borrower.city or "",
        "BorrowerState": borrower.state or "",
        "BorrowerZip": borrower.zip or "",

        "EmployerName": borrower.employer_name or "",
        "Income": borrower.income or "",
        "SecondaryIncome": getattr(borrower, "monthly_income_secondary", "") or "",

        "LoanAmount": loan.amount or "",
        "LoanType": loan.loan_type or "",
        "PropertyValue": loan.property_value or "",
        "PropertyAddress": loan.property_address or "",
    }

    # Inject values into PDF AcroForm fields
    if pdf.Root.AcroForm and pdf.Root.AcroForm.Fields:
        for field in pdf.Root.AcroForm.Fields:
            try:
                raw_name = field.T
                if not raw_name:
                    continue

                key = raw_name[1:-1]  # remove parentheses

                if key in data:
                    field.V = str(data[key])
                    field.AP = None  # force redraw
            except Exception:
                pass  # ignore malformed fields

    output_path = os.path.join(OUTPUT_DIR, f"1003_{borrower.id}.pdf")
    PdfWriter().write(output_path, pdf)

    return output_path
