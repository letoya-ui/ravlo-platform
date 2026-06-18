"""
Create Ericka Moore's white-label Lending OS beta account (2-month trial).

    python -m LoanMVP.create_ericka_moore_brokerage --password <choose-a-password>

What this script creates:
  - User            role=partner, email=moorstonerealestate@gmail.com
  - Partner         subscription_tier=Premium, category=Broker,
                    approved=True, active=True, paid_until=60 days from now
  - VIPProfile      role_type=loan_officer  (unlocks Lending OS / white-label dashboard)

At beta expiry a payment-request email is sent automatically by:
    python -m LoanMVP.scripts.send_beta_payment_requests

Safe to run multiple times — existing records are updated in place.
"""

import argparse
import json
import os
from datetime import datetime, timedelta

from LoanMVP.app import app
from LoanMVP.extensions import db
from LoanMVP.models.user_model import User
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.vip_models import VIPProfile

EMAIL      = "moorstonerealestate@gmail.com"
FULL_NAME  = "Ericka Moore"
FIRST_NAME = "Ericka"
LAST_NAME  = "Moore"

BETA_DURATION_DAYS = 60  # 2-month beta


def create_ericka_moore_brokerage(password: str):
    with app.app_context():
        beta_expires = datetime.utcnow() + timedelta(days=BETA_DURATION_DAYS)

        # -- 1. User -------------------------------------------------------
        user = User.query.filter(
            db.func.lower(User.email) == EMAIL.lower()
        ).first()
        created_user = False

        if not user:
            user = User(
                email=EMAIL,
                first_name=FIRST_NAME,
                last_name=LAST_NAME,
                username=FIRST_NAME,
                role="partner",
                is_active=True,
                invite_accepted=True,
                onboarding_complete=True,
                subscription="pro",
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            created_user = True
        else:
            user.role = "partner"
            user.is_active = True
            user.first_name = FIRST_NAME
            user.last_name = LAST_NAME
            user.subscription = "pro"
            if not user.password_hash:
                user.set_password(password)

        # -- 2. Partner ----------------------------------------------------
        partner = Partner.query.filter_by(user_id=user.id).first()
        created_partner = False

        if not partner:
            partner = Partner(
                user_id=user.id,
                name=FULL_NAME,
                email=EMAIL,
                category="Broker",
                type="Broker",
                specialty="Real Estate Brokerage",
                subscription_tier="Premium",
                approved=True,
                active=True,
                status="Active",
                paid_until=beta_expires,
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
            partner.category = "Broker"
            partner.type = "Broker"
            partner.subscription_tier = "Premium"
            partner.approved = True
            partner.active = True
            partner.status = "Active"
            partner.paid_until = beta_expires
            partner.crm_enabled = True
            partner.deal_visibility_enabled = True
            partner.proposal_builder_enabled = True
            partner.ai_assist_enabled = True
            partner.priority_placement_enabled = True
            partner.smart_notifications_enabled = True

        # -- 3. VIP Profile ------------------------------------------------
        vip = VIPProfile.query.filter_by(user_id=user.id).first()
        created_vip = False

        if not vip:
            vip = VIPProfile(
                user_id=user.id,
                display_name=FULL_NAME,
                business_name="Moorstone Real Estate",
                role_type="loan_officer",   # Lending OS dashboard
                assistant_name="Ravlo",
                marketplace_enabled="yes",
                public_slug="moorstone-real-estate",
                headline="Full-Service Real Estate Brokerage",
                service_area="",
                specialties="Residential • Commercial • Investment",
                enabled_modules=json.dumps([
                    "crm", "finances", "ai_pilot", "content_studio", "canva",
                ]),
            )
            db.session.add(vip)
            created_vip = True
        else:
            vip.role_type = "loan_officer"
            vip.business_name = vip.business_name or "Moorstone Real Estate"
            vip.marketplace_enabled = "yes"
            if not vip.public_slug:
                vip.public_slug = "moorstone-real-estate"
            if not vip.headline:
                vip.headline = "Full-Service Real Estate Brokerage"

        db.session.commit()

        # -- Summary -------------------------------------------------------
        print()
        print("=" * 60)
        print("  Ericka Moore — White Label Lending OS Beta Account")
        print("=" * 60)
        print(f"  Email      : {EMAIL}")
        print(f"  Password   : {'*' * len(password)}")
        print(f"  Role       : partner  (Premium tier)")
        print(f"  VIP type   : loan_officer  (Lending OS / white-label)")
        print(f"  Beta ends  : {beta_expires.strftime('%B %d, %Y')}  (2 months)")
        print(f"  User       : {'created' if created_user    else 'updated'} (id={user.id})")
        print(f"  Partner    : {'created' if created_partner  else 'updated'} (id={partner.id})")
        print(f"  VIPProfile : {'created' if created_vip     else 'updated'} (id={vip.id})")
        print("=" * 60)
        print("  Dashboards unlocked:")
        print("    /vip/loan-officer  — Lending OS workspace")
        print("    /partners/         — Partner OS")
        print(f"    /p/{vip.public_slug}  — Public landing page")
        print()
        print("  Auto payment request scheduled:")
        print(f"    Run daily cron: python -m LoanMVP.scripts.send_beta_payment_requests")
        print(f"    Email fires on {beta_expires.strftime('%B %d, %Y')} with Stripe checkout link.")
        print("=" * 60)
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create Ericka Moore's white-label Lending OS beta account.",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("ERICKA_MOORE_PASSWORD", ""),
        help="Login password (or set ERICKA_MOORE_PASSWORD env var)",
    )
    args = parser.parse_args()

    if not args.password:
        parser.error(
            "Password is required. Pass --password <pw> or set ERICKA_MOORE_PASSWORD."
        )

    create_ericka_moore_brokerage(args.password)
