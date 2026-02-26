from LoanMVP.models.document_models import DocumentNeed
from LoanMVP.extensions import db
from LoanMVP.ai.master_ai import master_ai

def generate_needs(borrower, loan, credit):
    """AI document needs engine — evaluates file + returns checklist."""

    credit_json = credit.credit_data if credit else {}

    packet = f"""
Borrower: {borrower.full_name}
Income: {borrower.income}
Secondary Income: {getattr(borrower, 'monthly_income_secondary', None)}
Employer: {borrower.employer_name}
Job Title: {getattr(borrower, 'job_title', '')}
Years at Job: {getattr(borrower, 'years_at_job', '')}

Loan Type: {loan.loan_type}
Loan Amount: {loan.amount}
Property Value: {loan.property_value}

Credit Score: {credit.credit_score if credit else 'N/A'}
Credit Report JSON: {credit_json}

Provide a JSON array of required documents in this format:

[
  {{"name": "...", "reason": "..."}},
  {{"name": "...", "reason": "..."}}
]

Rules:
- Return ONLY valid JSON.
- Tailor needs to borrower type (W2, 1099, DSCR, FHA, etc.).
- Include risk-flag docs if needed (large deposits, new inquiries, etc.).
"""

    # AI GENERATION
    reply = master_ai.generate(packet, role="processor")

    # SAFE JSON PARSE
    import json
    try:
        needs_list = json.loads(reply)
    except:
        needs_list = []

    # SAVE NEEDS
    for item in needs_list:
        need = DocumentNeed(
            borrower_id=borrower.id,
            loan_id=loan.id,
            name=item.get("name"),
            reason=item.get("reason")
        )
        db.session.add(need)

    db.session.commit()

    return needs_list
