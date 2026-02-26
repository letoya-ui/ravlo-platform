from LoanMVP.extensions import db
from LoanMVP.app import socketio
from LoanMVP.models.loan_models import LoanNotification
from flask import current_app
from twilio.rest import Client
import sendgrid
from sendgrid.helpers.mail import Mail

def notify(
    borrower=None,
    loan=None,
    role=None,
    title="Update",
    message="",
    channels=["socket", "inapp"]
):
    """
    borrower  = BorrowerProfile obj or None
    loan      = LoanApplication obj or None
    role      = 'processor', 'underwriter', 'loan_officer', 'executive'
    channels  = ["socket", "sms", "email", "inapp"]
    """

    # ================================
    # 1️⃣ IN-APP NOTIFICATION
    # ================================
    if "inapp" in channels and borrower:
        notif = LoanNotification(
            borrower_id=borrower.id,
            loan_id=loan.id if loan else None,
            channel="inapp",
            title=title,
            message=message
        )
        db.session.add(notif)
        db.session.commit()

    # ================================
    # 2️⃣ SOCKET.IO REAL-TIME
    # ================================
    if "socket" in channels and loan:
        socketio.emit(
            "new_notification",
            {
                "loan_id": loan.id,
                "role": role,
                "title": title,
                "message": message,
            }
        )

    # ================================
    # 3️⃣ SMS
    # ================================
    if "sms" in channels and borrower and borrower.phone:
        try:
            client = Client(
                current_app.config["TWILIO_SID"],
                current_app.config["TWILIO_AUTH"]
            )
            client.messages.create(
                body=f"{title}: {message}",
                from_=current_app.config["TWILIO_FROM"],
                to=borrower.phone
            )
        except Exception:
            pass

    # ================================
    # 4️⃣ EMAIL
    # ================================
    if "email" in channels and borrower and borrower.email:
        try:
            sg = sendgrid.SendGridAPIClient(
                current_app.config["SENDGRID_API_KEY"]
            )
            email_msg = Mail(
                from_email="noreply@caughmanmason.com",
                to_emails=borrower.email,
                subject=title,
                html_content=f"""
                <h2>{title}</h2>
                <p>{message}</p>
                <br><br>
                <small style='color:#555'>Caughman Mason Loan Services</small>
                """
            )
            sg.send(email_msg)
        except Exception:
            pass
