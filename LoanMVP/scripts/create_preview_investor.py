"""
CLI script to create a preview investor account.

Usage:
    python LoanMVP/scripts/create_preview_investor.py \
        --email investor@example.com \
        --first-name Jane \
        --last-name Smith
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from LoanMVP.app import create_app
from LoanMVP.extensions import db
from LoanMVP.models.user_model import User
from LoanMVP.routes.preview_routes import grant_preview_access, _send_preview_welcome
import secrets


def main():
    parser = argparse.ArgumentParser(description="Create a free preview investor account")
    parser.add_argument("--email", required=True)
    parser.add_argument("--first-name", default="")
    parser.add_argument("--last-name", default="")
    args = parser.parse_args()

    email = args.email.strip().lower()
    app = create_app()

    with app.app_context():
        existing = User.query.filter_by(email=email).first()
        if existing:
            print(f"[error] User {email} already exists (id={existing.id})")
            sys.exit(1)

        temp_password = secrets.token_urlsafe(10)
        user = User(
            first_name=args.first_name.strip() or None,
            last_name=args.last_name.strip() or None,
            email=email,
            role="investor",
            is_active=True,
            onboarding_complete=True,
            invite_accepted=True,
        )
        user.set_password(temp_password)
        grant_preview_access(user)
        db.session.add(user)
        db.session.commit()

        print(f"[ok] Preview account created for {email}")
        print(f"     Temp password : {temp_password}")
        print(f"     Trial ends    : {user.trial_ends_at.strftime('%Y-%m-%d')}")

        _send_preview_welcome(user, temp_password)
        print(f"[ok] Welcome email sent.")


if __name__ == "__main__":
    main()
