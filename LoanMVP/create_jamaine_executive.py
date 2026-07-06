"""
Create Jamaine Caughman's executive/contractor account.

    python -m LoanMVP.create_jamaine_executive --password <choose-a-password>

His email (jamaine.caughman@ravlohq.com) is already special-cased in
routes/construction_bids.py and routes/construction_office.py, so once
this account exists with role="executive", the first request he makes
to those routes auto-links (or creates) the "Caughman Mason Construction"
Tampa partner profile to his account -- no separate Partner/VIPProfile
setup needed here.
"""

import argparse
import os

from LoanMVP.app import app
from LoanMVP.extensions import db
from LoanMVP.models.user_model import User

EMAIL      = "jamaine.caughman@ravlohq.com"
FIRST_NAME = "Jamaine"
LAST_NAME  = "Caughman"
ROLE       = "executive"


def create_jamaine_executive(password: str):
    with app.app_context():
        user = User.query.filter_by(email=EMAIL).first()
        created = False

        if not user:
            user = User(
                email=EMAIL,
                first_name=FIRST_NAME,
                last_name=LAST_NAME,
                username=f"{FIRST_NAME} {LAST_NAME}",
                role=ROLE,
                is_active=True,
                invite_accepted=True,
                onboarding_complete=True,
            )
            db.session.add(user)
            created = True
        else:
            user.role = ROLE
            user.is_active = True
            user.first_name = FIRST_NAME
            user.last_name = LAST_NAME

        user.set_password(password)
        db.session.commit()

        print("\n" + "=" * 55)
        print("  Jamaine Caughman — Executive/Contractor Account")
        print("=" * 55)
        print(f"  Email : {EMAIL}")
        print(f"  Role  : {ROLE}")
        print(f"  User  : {'created' if created else 'updated'} (id={user.id})")
        print("=" * 55)
        print("  Dashboards unlocked:")
        print("    /executive/dashboard      — Executive dashboard")
        print("    /construction-office/*    — Bid/package management (staff tools)")
        print("    /construction-bids/*      — Auto-links Caughman Mason Construction")
        print("                                partner profile on first use")
        print("=" * 55 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create/update Jamaine's executive account.")
    parser.add_argument(
        "--password",
        default=os.environ.get("JAMAINE_EXECUTIVE_PASSWORD", ""),
        help="Login password (or set JAMAINE_EXECUTIVE_PASSWORD env var)",
    )
    args = parser.parse_args()

    if not args.password:
        parser.error(
            "Password is required. Pass --password <pw> or set JAMAINE_EXECUTIVE_PASSWORD."
        )

    create_jamaine_executive(args.password)
