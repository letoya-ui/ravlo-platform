"""
Create Bonnie's VIP Realtor account.

    python -m LoanMVP.create_bonnie_realtor

What this script creates:
  - User            role=partner, email=Bonniesellsochomes@gmail.com
  - Partner         subscription_tier=Premium, category=Realtor,
                    approved=True, active=True
  - VIPProfile      role_type=realtor  (unlocks VIP realtor dashboard)

Safe to run multiple times — existing records are updated in place.
"""

import json
import os
from datetime import datetime, timedelta

from LoanMVP.app import app
from LoanMVP.extensions import db
from LoanMVP.models.user_model import User
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.vip_models import VIPProfile

EMAIL      = "Bonniesellsochomes@gmail.com"
FIRST_NAME = "Bonnie"
LAST_NAME  = ""
PASSWORD   = "TempPass123!"


def create_bonnie_realtor():
    with app.app_context():
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
            user.set_password(PASSWORD)
            db.session.add(user)
            db.session.flush()
            created_user = True
        else:
            user.role = "partner"
            user.is_active = True
            user.first_name = FIRST_NAME
            user.subscription = "pro"
            if not user.password_hash:
                user.set_password(PASSWORD)

        # -- 2. Partner ----------------------------------------------------
        partner = Partner.query.filter_by(user_id=user.id).first()
        created_partner = False

        if not partner:
            partner = Partner(
                user_id=user.id,
                name=FIRST_NAME,
                email=EMAIL,
                category="Realtor",
                type="Realtor",
                specialty="Residential Real Estate",
                subscription_tier="Premium",
                approved=True,
                active=True,
                status="Active",
                paid_until=datetime.utcnow() + timedelta(days=365),
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
            partner.subscription_tier = "Premium"
            partner.approved = True
            partner.active = True
            partner.status = "Active"
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
                display_name=FIRST_NAME,
                role_type="realtor",
                assistant_name="Elena",
                marketplace_enabled="yes",
                enabled_modules=json.dumps([
                    "crm", "finances", "ai_pilot", "content_studio", "canva",
                ]),
            )
            db.session.add(vip)
            created_vip = True
        else:
            vip.role_type = "realtor"
            vip.marketplace_enabled = "yes"

        db.session.commit()

        # -- Summary -------------------------------------------------------
        print()
        print("=" * 55)
        print("  Bonnie — VIP Realtor Account")
        print("=" * 55)
        print(f"  Email    : {EMAIL}")
        print(f"  Password : {PASSWORD}")
        print(f"  Role     : partner  (VIP Premium tier)")
        print(f"  VIP type : realtor")
        print(f"  User     : {'created' if created_user   else 'updated'} (id={user.id})")
        print(f"  Partner  : {'created' if created_partner else 'updated'} (id={partner.id})")
        print(f"  VIPProfile: {'created' if created_vip   else 'updated'} (id={vip.id})")
        print("=" * 55)
        print("  Dashboards unlocked:")
        print("    /vip/realtor     — Realtor VIP workspace")
        print("    /partners/       — Partner OS")
        print("=" * 55)
        print()


if __name__ == "__main__":
    create_bonnie_realtor()
