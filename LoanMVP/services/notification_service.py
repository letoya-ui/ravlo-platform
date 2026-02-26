"""
Notification Service
--------------------
Handles internal notifications for loan officers, processors, underwriters.
"""

from LoanMVP.extensions import db
from LoanMVP.models.crm_models import Message
from LoanMVP.models.loan_models import LoanNotification
import datetime


def notify_team_on_conversion(borrower, quote, loan_app):
    """
    Notify loan officer and underwriter when a quote is converted.
    """
    officer_id = quote.assigned_officer_id
    underwriter_id = quote.assigned_underwriter_id

    msg = (
        f"📢 Borrower {borrower.full_name} converted quote #{quote.id} "
        f"into Loan Application #{loan_app.id} for {quote.property_address or 'a property'}."
    )

    if officer_id:
        db.session.add(Message(
            sender_id=borrower.user_id,
            receiver_id=officer_id,
            content=msg,
            created_at=datetime.datetime.utcnow(),
            system_generated=True
        ))

        db.session.add(Notification(
            user_id=officer_id,
            title="New Borrower Conversion",
            message=msg,
            category="loan_conversion",
            created_at=datetime.datetime.utcnow(),
            is_read=False
        ))

    if underwriter_id:
        db.session.add(Message(
            sender_id=borrower.user_id,
            receiver_id=underwriter_id,
            content=msg,
            created_at=datetime.datetime.utcnow(),
            system_generated=True
        ))

        db.session.add(Notification(
            user_id=underwriter_id,
            title="New Loan Application Ready for Review",
            message=msg,
            category="loan_conversion",
            created_at=datetime.datetime.utcnow(),
            is_read=False
        ))

    db.session.commit()
