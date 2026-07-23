"""
Switch Aisha's account over to the new GotStyles Beauty stylist dashboard.

    python -m LoanMVP.create_gotstyles_aisha

What this script does:
  - Company   finds-or-creates "GotStyles Beauty" (is_active=True)
  - User      aishagelahun@gmail.com -> role=stylist, company_id=GotStyles Beauty
  - StylistProfile  finds-or-creates for that user

Aisha's account already exists (she's on the Ravlo staff demo-login
allowlist), so this does NOT touch her password -- it only reassigns her
role/company and provisions the stylist profile. Safe to run multiple
times -- existing records are updated in place.

If her account somehow doesn't exist yet, pass --password (or set
GOTSTYLES_AISHA_PASSWORD) to create it fresh.
"""

import argparse
import os

from LoanMVP.app import app
from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.models.salon_models import StylistProfile

EMAIL = "aishagelahun@gmail.com"
COMPANY_NAME = "GotStyles Beauty"


def create_gotstyles_aisha(password: str = ""):
    with app.app_context():
        # -- 1. Company ------------------------------------------------
        company = Company.query.filter_by(name=COMPANY_NAME).first()
        created_company = False
        if not company:
            company = Company(name=COMPANY_NAME, is_active=True)
            db.session.add(company)
            db.session.flush()
            created_company = True

        # -- 2. User -----------------------------------------------------
        user = User.query.filter(db.func.lower(User.email) == EMAIL.lower()).first()
        created_user = False

        if not user:
            if not password:
                raise SystemExit(
                    "No existing account for aishagelahun@gmail.com -- "
                    "pass --password <pw> or set GOTSTYLES_AISHA_PASSWORD to create one."
                )
            user = User(
                email=EMAIL,
                first_name="Aisha",
                last_name="",
                role="stylist",
                company_id=company.id,
                is_active=True,
                invite_accepted=True,
                onboarding_complete=True,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            created_user = True
        else:
            user.role = "stylist"
            user.company_id = company.id
            user.is_active = True

        # -- 3. StylistProfile --------------------------------------------
        profile = StylistProfile.query.filter_by(user_id=user.id).first()
        created_profile = False
        if not profile:
            profile = StylistProfile(
                user_id=user.id,
                company_id=company.id,
                full_name=f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
                email=user.email,
            )
            db.session.add(profile)
            created_profile = True
        else:
            profile.company_id = company.id

        db.session.commit()

        # -- Summary -------------------------------------------------------
        print()
        print("=" * 55)
        print("  Aisha — GotStyles Beauty Stylist Account")
        print("=" * 55)
        print(f"  Email    : {EMAIL}")
        print(f"  Role     : stylist")
        print(f"  Company  : {COMPANY_NAME} (id={company.id}, {'created' if created_company else 'existing'})")
        print(f"  User     : {'created' if created_user else 'updated'} (id={user.id})")
        print(f"  Profile  : {'created' if created_profile else 'updated'} (id={profile.id})")
        print("=" * 55)
        print("  Dashboard unlocked:")
        print("    /stylist/dashboard  — GotStyles Beauty stylist workspace")
        print("=" * 55)
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Switch Aisha's account to the GotStyles Beauty stylist dashboard.",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("GOTSTYLES_AISHA_PASSWORD", ""),
        help="Only needed if the account doesn't exist yet.",
    )
    args = parser.parse_args()

    create_gotstyles_aisha(args.password)
