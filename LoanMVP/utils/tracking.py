from LoanMVP.extensions import db
from LoanMVP.utils.engagement_alerts import check_engagement_spike
from LoanMVP.models.loan_models import LoanApplication, DocumentEvent, BorrowerProfile
from flask import request


def track_event(loan_id, borrower_id, document_name, event_type):
    """Record a document-related event and trigger engagement alerts."""

    event = DocumentEvent(
        loan_id=loan_id,
        borrower_id=borrower_id,
        document_name=document_name,
        event_type=event_type,
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.remote_addr
    )

    db.session.add(event)
    db.session.commit()

    # Run engagement alert engine
    borrower = BorrowerProfile.query.get(borrower_id)
    loan = LoanApplication.query.get(loan_id)

    check_engagement_spike(borrower, loan)