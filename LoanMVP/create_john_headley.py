"""
Create John Headley's VIP Contractor/Realtor partner account.

    python create_john_headley.py --password <choose-a-password>

What this script creates:
  - User            role=partner, email=jsecon1212@gmail.com
  - Partner         subscription_tier=Featured, category=Contractor/Realtor,
                    approved=True, active=True, featured=True
  - VIPProfile      role_type=contractor_realtor  (unlocks VIP contractor + realtor dashboards)
"""

import argparse
import os
from datetime import datetime, timedelta

from LoanMVP.app import app
from LoanMVP.extensions import db
from LoanMVP.models.user_model import User
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.vip_models import VIPProfile

EMAIL      = "jsecon1212@gmail.com"
FIRST_NAME = "John"
LAST_NAME  = "Headley"


def create_john_headley(password: str):
    with app.app_context():
        # ── 1. User ──────────────────────────────────────────────
        user = User.query.filter_by(email=EMAIL).first()
        created_user = False

        if not user:
            user = User(
                email=EMAIL,
                first_name=FIRST_NAME,
                last_name=LAST_NAME,
                username=f"{FIRST_NAME} {LAST_NAME}",
                role="partner",
                is_active=True,
                invite_accepted=True,
                onboarding_complete=True,
                subscription="featured",
            )
            db.session.add(user)
            db.session.flush()   # get user.id
            created_user = True
        else:
            user.role       = "partner"
            user.is_active  = True
            user.first_name = FIRST_NAME
            user.last_name  = LAST_NAME
            user.subscription = "featured"

        user.set_password(password)

        # ── 2. Partner ───────────────────────────────────────────
        partner = Partner.query.filter_by(user_id=user.id).first()
        created_partner = False

        if not partner:
            partner = Partner(
                user_id=user.id,
                name=f"{FIRST_NAME} {LAST_NAME}",
                email=EMAIL,
                category="Contractor",
                type="Realtor",
                specialty="Residential Renovation & Real Estate",
                subscription_tier="Featured",
                approved=True,
                active=True,
                featured=True,
                status="Active",
                paid_until=datetime.utcnow() + timedelta(days=365),
                # Feature flags for Featured tier
                crm_enabled=True,
                deal_visibility_enabled=True,
                proposal_builder_enabled=True,
                ai_assist_enabled=True,
                priority_placement_enabled=True,
                smart_notifications_enabled=True,
            )
            db.session.add(partner)
            db.session.flush()
            created_partner = True
        else:
            partner.subscription_tier          = "Featured"
            partner.approved                   = True
            partner.active                     = True
            partner.featured                   = True
            partner.status                     = "Active"
            partner.crm_enabled                = True
            partner.deal_visibility_enabled    = True
            partner.proposal_builder_enabled   = True
            partner.ai_assist_enabled          = True
            partner.priority_placement_enabled = True
            partner.smart_notifications_enabled = True

        # ── 3. VIP Profile ───────────────────────────────────────
        vip = VIPProfile.query.filter_by(user_id=user.id).first()
        created_vip = False

        if not vip:
            vip = VIPProfile(
                user_id=user.id,
                display_name=f"{FIRST_NAME} {LAST_NAME}",
                role_type="contractor_realtor",   # unlocks both VIP dashboards
                assistant_name="Ravlo",
                marketplace_enabled="yes",
                enabled_modules="contractor,realtor,crm,finances",
            )
            db.session.add(vip)
            created_vip = True
        else:
            vip.role_type          = "contractor_realtor"
            vip.marketplace_enabled = "yes"

        db.session.commit()

        # ── Summary ──────────────────────────────────────────────
        print("\n" + "=" * 55)
        print("  John Headley — VIP Contractor/Realtor Account")
        print("=" * 55)
        print(f"  Email    : {EMAIL}")
        print(f"  Password : {password}")
        print(f"  Role     : partner  (VIP Featured tier)")
        print(f"  VIP type : contractor_realtor")
        print(f"  User     : {'created' if created_user   else 'updated'} (id={user.id})")
        print(f"  Partner  : {'created' if created_partner else 'updated'} (id={partner.id})")
        print(f"  VIPProfile: {'created' if created_vip   else 'updated'} (id={vip.id})")
        print("=" * 55)
        print("  Dashboards unlocked:")
        print("    /vip/contractor  — Contractor VIP workspace")
        print("    /vip/realtor     — Realtor VIP workspace")
        print("    /partners/       — Partner OS")
        print("=" * 55 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create John Headley VIP partner account.")
    parser.add_argument(
        "--password",
        default=os.environ.get("JOHN_HEADLEY_PASSWORD", ""),
        help="Login password (or set JOHN_HEADLEY_PASSWORD env var)",
    )
    args = parser.parse_args()

    if not args.password:
        parser.error(
            "Password is required. Pass --password <pw> or set JOHN_HEADLEY_PASSWORD."
        )

    create_john_headley(args.password)
