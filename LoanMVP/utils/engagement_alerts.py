from LoanMVP.models.loan_models import DocumentEvent
from LoanMVP.app import socketio
from LoanMVP.extensions import db
from datetime import datetime, timedelta

def check_engagement_spike(borrower, loan):
    now = datetime.utcnow()

    # Events in last hour
    last_hour = now - timedelta(hours=1)
    events = DocumentEvent.query.filter(
        DocumentEvent.borrower_id == borrower.id,
        DocumentEvent.timestamp >= last_hour
    ).all()

    opens = len([e for e in events if e.event_type == "opened"])
    views = len([e for e in events if e.event_type == "viewed"])
    downloads = len([e for e in events if e.event_type == "downloaded"])
    uploads = len([e for e in events if e.event_type == "uploaded"])

    alert_message = None

    # RULE 1 → Email opened many times
    if opens >= 3:
        alert_message = f"📬 Borrower {borrower.full_name} opened the pre-approval email {opens} times within the last hour."

    # RULE 2 → Multiple downloads
    elif downloads >= 2:
        alert_message = f"⬇️ Borrower {borrower.full_name} downloaded documents {downloads} times in the last hour."

    # RULE 3 → Rapid uploads (very strong signal)
    elif uploads >= 1:
        alert_message = f"📤 Borrower {borrower.full_name} uploaded new documents."

    # RULE 4 → Portal activity surge
    elif (opens + views + downloads) >= 4:
        alert_message = f"⚡ Borrower {borrower.full_name} is very active in the portal."

    # If no alert
    if not alert_message:
        return None

    # Save alert
    from LoanMVP.models.loan_models import LoanNotification

    notif = LoanNotification(
        loan_id=loan.id,
        role="loan_officer",
        message=alert_message
    )
    db.session.add(notif)
    db.session.commit()

    # Realtime push to LO dashboard
    socketio.emit("new_notification", {
        "loan_id": loan.id,
        "role": "loan_officer",
        "message": alert_message,
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
    }, broadcast=True)

    return alert_message
