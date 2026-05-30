#!/usr/bin/env python3
"""
CLI script to provision a free preview investor account.

Usage (from project root):
  python LoanMVP/scripts/create_preview_investor.py \
    --email investor@example.com \
    --first-name John \
    --last-name Smith

The script creates the User + InvestorProfile with subscription='preview',
prints the temporary password, and optionally sends the welcome email.
"""
import argparse
import secrets
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from LoanMVP.app import create_app
from LoanMVP.extensions import db
from LoanMVP.models.user_model import User
from LoanMVP.models.investor_models import InvestorProfile
from sqlalchemy import func


def main():
    parser = argparse.ArgumentParser(description="Create a free preview investor account.")
    parser.add_argument("--email", required=True, help="Investor email address")
    parser.add_argument("--first-name", default="", help="First name")
    parser.add_argument("--last-name", default="", help="Last name")
    parser.add_argument("--no-email", action="store_true", help="Skip sending the welcome email")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        email = args.email.strip().lower()
        first_name = args.first_name.strip()
        last_name = args.last_name.strip()

        existing = User.query.filter(func.lower(User.email) == email).first()
        if existing:
            if (existing.subscription or "").strip().lower() == "preview":
                print(f"[preview] {email} already has a preview account.")
            else:
                existing.subscription = "preview"
                db.session.commit()
                print(f"[preview] Updated existing account {email} to preview.")
            return

        temp_password = secrets.token_urlsafe(12)
        user = User(
            first_name=first_name or None,
            last_name=last_name or None,
            username=f"{first_name} {last_name}".strip() or email,
            email=email,
            role="investor",
            subscription="preview",
            is_active=True,
            invite_accepted=True,
            onboarding_complete=True,
        )
        user.set_password(temp_password)
        db.session.add(user)
        db.session.flush()

        profile = InvestorProfile(
            user_id=user.id,
            full_name=f"{first_name} {last_name}".strip() or email,
            email=email,
        )
        db.session.add(profile)
        db.session.commit()

        print(f"\n[preview] Account created successfully!")
        print(f"  Email:     {email}")
        print(f"  Password:  {temp_password}")
        print(f"  Role:      investor (preview)")
        print()

        if not args.no_email:
            try:
                from flask_mail import Message as MailMessage
                from LoanMVP.app import mail
                from flask import url_for
                with app.test_request_context():
                    login_url = url_for("auth.login", _external=True)
                    reset_url = url_for("auth.forgot_password", _external=True)
                    msg = MailMessage(
                        subject="You've been invited to preview Ravlo",
                        recipients=[email],
                        body=(
                            f"Hi {first_name or 'there'},\n\n"
                            f"You've been given free preview access to Ravlo.\n\n"
                            f"Log in: {login_url}\n"
                            f"Email: {email}\n"
                            f"Temporary password: {temp_password}\n\n"
                            f"Change your password: {reset_url}\n\n"
                            f"When you're ready for full access, click 'Request Full Access' from your dashboard.\n\n"
                            f"The Ravlo Team"
                        ),
                    )
                    mail.send(msg)
                print(f"  Welcome email sent to {email}")
            except Exception as exc:
                print(f"  Warning: could not send email — {exc}")


if __name__ == "__main__":
    main()
