"""
Switch Aisha's account over to the new GotStyles Beauty stylist dashboard.

    python -m LoanMVP.create_gotstyles_aisha

What this script does:
  - Company   finds-or-creates "GotStyles Beauty" (is_active=True)
  - User      aishagelahun@gmail.com -> role=stylist, company_id=GotStyles Beauty
  - StylistProfile  finds-or-creates for that user, with her public booking
                     page slug/branding set, and a default weekly
                     availability (Tue-Sat, 10am-6pm) so the booking
                     calendar isn't empty on first launch.

Aisha's account already exists (she's on the Ravlo staff demo-login
allowlist), so this does NOT touch her password -- it only reassigns her
role/company and provisions the stylist profile. Safe to run multiple
times -- existing records are updated in place.

If her account somehow doesn't exist yet, pass --password (or set
GOTSTYLES_AISHA_PASSWORD) to create it fresh.
"""

import argparse
import os
from datetime import time as dtime

from LoanMVP.app import app
from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User
from LoanMVP.models.salon_models import StylistProfile, SalonAvailability

EMAIL = "aishagelahun@gmail.com"
COMPANY_NAME = "GotStyles Beauty"
DISPLAY_NAME = "GotStyles by Aisha"
PUBLIC_SLUG = "gotstyles-beauty"
BRAND_COLOR = "#B76E79"
LOGO_URL = "/static/images/salon/gotstyles_logo.png"
HEADLINE = "All Things Beauty"
PHONE = "(615) 546-2397"
ADDRESS = "1925 Madison Square, Suite 400, LaVergne, TN 37086"
SERVICE_AREA = "LaVergne, TN"

# Tuesday-Saturday, 10am-6pm, 60-minute slots -- a reasonable default so
# the public booking calendar has open times from day one; Aisha can
# adjust or replace these anytime from /stylist/availability.
DEFAULT_AVAILABILITY = [(dow, dtime(10, 0), dtime(18, 0)) for dow in (1, 2, 3, 4, 5)]


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
                full_name=DISPLAY_NAME,
                email=user.email,
            )
            db.session.add(profile)
            created_profile = True
        else:
            profile.company_id = company.id

        profile.full_name = DISPLAY_NAME
        profile.public_slug = PUBLIC_SLUG
        profile.brand_color = BRAND_COLOR
        profile.logo_url = LOGO_URL
        profile.headline = HEADLINE
        profile.phone = PHONE
        profile.address = ADDRESS
        profile.service_area = SERVICE_AREA
        db.session.commit()

        # -- 4. Default availability ---------------------------------------
        created_availability = 0
        if not SalonAvailability.query.filter_by(stylist_id=profile.id).count():
            for day_of_week, start_time, end_time in DEFAULT_AVAILABILITY:
                db.session.add(SalonAvailability(
                    stylist_id=profile.id,
                    day_of_week=day_of_week,
                    start_time=start_time,
                    end_time=end_time,
                    slot_minutes=60,
                ))
                created_availability += 1
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
        print(f"  Availability windows added: {created_availability}")
        print("=" * 55)
        print("  Dashboard unlocked:")
        print("    /stylist/dashboard  — GotStyles Beauty stylist workspace")
        print(f"    /salon/{PUBLIC_SLUG}  — public landing page")
        print(f"    /salon/{PUBLIC_SLUG}/book  — public booking calendar")
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
