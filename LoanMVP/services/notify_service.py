from flask import current_app
from twilio.rest import Client
import sendgrid
from sendgrid.helpers.mail import Mail

from LoanMVP.extensions import db
from LoanMVP.app import socketio
from LoanMVP.models.loan_models import LoanNotification
from LoanMVP.models.user_model import User


def notify(
    borrower=None,
    investor=None,
    loan=None,
    role=None,
    title="Update",
    message="",
    channels=None
):
    """
    Universal Ravlo notification service.

    Direct recipients:
      borrower = BorrowerProfile object or None
      investor = InvestorProfile object or None

    Role recipients:
      role = 'admin', 'processor', 'underwriter', 'loan_officer', 'executive', etc.

    Channels:
      ["socket", "inapp", "sms", "email"]
    """

    if channels is None:
        channels = ["socket", "inapp"]

    recipients = []
    seen_user_ids = set()

    # =========================================
    # 1) DIRECT PROFILE RECIPIENTS
    # =========================================
    if borrower:
        user_id = getattr(borrower, "user_id", None)
        if user_id and user_id not in seen_user_ids:
            recipients.append({
                "kind": "borrower",
                "user_id": user_id,
                "borrower_id": borrower.id,
                "investor_id": None,
                "email": getattr(borrower, "email", None),
                "phone": getattr(borrower, "phone", None),
                "role": "borrower",
                "name": getattr(borrower, "full_name", None) or "Borrower",
            })
            seen_user_ids.add(user_id)

    if investor:
        user_id = getattr(investor, "user_id", None)
        if user_id and user_id not in seen_user_ids:
            recipients.append({
                "kind": "investor",
                "user_id": user_id,
                "borrower_id": None,
                "investor_id": investor.id,
                "email": getattr(investor, "email", None),
                "phone": getattr(investor, "phone", None),
                "role": "investor",
                "name": getattr(investor, "full_name", None) or "Investor",
            })
            seen_user_ids.add(user_id)

    # =========================================
    # 2) ROLE-BASED STAFF RECIPIENTS
    # =========================================
    if role and role not in ["borrower", "investor"]:
        staff_users = User.query.filter_by(role=role).all()

        for user in staff_users:
            if user.id in seen_user_ids:
                continue

            recipients.append({
                "kind": "staff",
                "user_id": user.id,
                "borrower_id": None,
                "investor_id": None,
                "email": getattr(user, "email", None),
                "phone": getattr(user, "phone", None),
                "role": user.role,
                "name": f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip() or user.email or user.role,
            })
            seen_user_ids.add(user.id)

    # If nobody found, stop quietly
    if not recipients:
        return

    # =========================================
    # 3) IN-APP NOTIFICATIONS
    # =========================================
    if "inapp" in channels:
        created_any = False

        for recipient in recipients:
            notif = LoanNotification(
                user_id=recipient["user_id"],
                borrower_id=recipient["borrower_id"],
                investor_id=recipient["investor_id"],
                loan_id=loan.id if loan else None,
                channel="inapp",
                role=recipient["role"],
                title=title,
                message=message,
            )
            db.session.add(notif)
            created_any = True

        if created_any:
            db.session.commit()

    # =========================================
    # 4) SOCKET REAL-TIME
    # =========================================
    if "socket" in channels:
        payload = {
            "loan_id": loan.id if loan else None,
            "role": role,
            "title": title,
            "message": message,
        }

        try:
            # general broadcast if needed
            socketio.emit("new_notification", payload)

            # per-user room delivery
            for recipient in recipients:
                socketio.emit(
                    "new_notification",
                    payload,
                    room=f"user_{recipient['user_id']}"
                )

            # optional role room delivery
            if role:
                socketio.emit(
                    "new_notification",
                    payload,
                    room=f"role_{role}"
                )
        except Exception:
            pass

    # =========================================
    # 5) SMS
    # =========================================
    if "sms" in channels:
        try:
            twilio_sid = current_app.config.get("TWILIO_SID")
            twilio_auth = current_app.config.get("TWILIO_AUTH")
            twilio_from = current_app.config.get("TWILIO_FROM")

            if twilio_sid and twilio_auth and twilio_from:
                client = Client(twilio_sid, twilio_auth)

                for recipient in recipients:
                    if recipient["phone"]:
                        client.messages.create(
                            body=f"{title}: {message}",
                            from_=twilio_from,
                            to=recipient["phone"]
                        )
        except Exception:
            pass

    # =========================================
    # 6) EMAIL
    # =========================================
    if "email" in channels:
        try:
            sendgrid_api_key = current_app.config.get("SENDGRID_API_KEY")
            from_email = current_app.config.get("NOTIFY_FROM_EMAIL", "noreply@ravlohq.com")
            brand_name = current_app.config.get("NOTIFY_BRAND_NAME", "Ravlo Lending OS")

            if sendgrid_api_key:
                sg = sendgrid.SendGridAPIClient(sendgrid_api_key)

                for recipient in recipients:
                    if recipient["email"]:
                        email_msg = Mail(
                            from_email=from_email,
                            to_emails=recipient["email"],
                            subject=title,
                            html_content=f"""
                            <div style="font-family:Inter,Arial,sans-serif;line-height:1.5;color:#111;">
                              <h2 style="margin-bottom:12px;">{title}</h2>
                              <p style="margin-bottom:16px;">{message}</p>
                              <p style="font-size:12px;color:#666;margin-top:32px;">{brand_name}</p>
                            </div>
                            """
                        )
                        sg.send(email_msg)
        except Exception:
            pass