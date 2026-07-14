"""
Notification Service
--------------------
Handles internal notifications for loan officers, processors, underwriters,
and Ravlo AI features (see create_notification / send_ai_notification below).
"""
import datetime

from flask import current_app

from LoanMVP.extensions import db
from LoanMVP.models.crm_models import Message
from LoanMVP.models.loan_models import LoanNotification


def notify_team_on_conversion(borrower, quote, loan_app):
    """
    Notify loan officer and underwriter when a quote is converted.
    """
    officer_id = quote.assigned_officer_id
    underwriter_id = quote.assigned_underwriter_id

    msg = (
        f"Borrower {borrower.full_name} converted quote #{quote.id} "
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

        db.session.add(LoanNotification(
            user_id=officer_id,
            loan_id=loan_app.id,
            title="New Borrower Conversion",
            message=msg,
            channel="inapp",
            is_read=False,
        ))

    if underwriter_id:
        db.session.add(Message(
            sender_id=borrower.user_id,
            receiver_id=underwriter_id,
            content=msg,
            created_at=datetime.datetime.utcnow(),
            system_generated=True
        ))

        db.session.add(LoanNotification(
            user_id=underwriter_id,
            loan_id=loan_app.id,
            title="New Loan Application Ready for Review",
            message=msg,
            channel="inapp",
            is_read=False,
        ))

    db.session.commit()


def create_notification(user, title: str, message: str, action_url: str = None, channel: str = "inapp") -> LoanNotification:
    """The canonical "give this specific User a notification" entry
    point. Creates and persists the row, then pushes it over the socket
    if one is available. Safe to call even if the socket emit fails --
    the row is always saved first."""
    notif = LoanNotification(
        user_id=user.id,
        role=(getattr(user, "role", None) or "").lower() or None,
        channel=channel,
        title=title[:255],
        message=message[:800],
        action_url=action_url,
    )
    db.session.add(notif)
    db.session.commit()

    try:
        from LoanMVP.app import socketio
        socketio.emit("new_notification", notif.to_dict(), room=f"user_{user.id}")
    except Exception as exc:
        current_app.logger.warning("Notification socket emit failed for user %s: %s", user.id, exc)

    return notif


def send_ai_notification(user, title: str, message: str, action_url: str = None) -> LoanNotification:
    """Ravlo AI's entry point for telling a user it has something for
    them -- same delivery path as create_notification, just a named
    wrapper so call sites read as "the AI sent this" rather than a bare
    generic notification."""
    return create_notification(user, title=title, message=message, action_url=action_url, channel="ai")
