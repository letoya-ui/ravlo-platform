"""
Set up Mason-Fultz Commercial Cleaning's VIP Contractor account + public
landing page.

    python -m LoanMVP.create_mason_fultz_cleaning

The account already exists (email MasonFultz45cleaningservice@gmail.com),
so this script never touches the password -- it only fills in the
business profile (Partner + VIPProfile) needed to unlock the VIP
contractor dashboard and the public landing page at
/p/mason-fultz-cleaning. Safe to run multiple times; existing records are
updated in place without overwriting anything already customized.
"""

import os
from datetime import datetime, timedelta

from LoanMVP.app import app
from LoanMVP.extensions import db
from LoanMVP.models.user_model import User
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.vip_models import VIPProfile

EMAIL         = "MasonFultz45cleaningservice@gmail.com"
FIRST_NAME    = "Sandra"
LAST_NAME     = "Mason-Fultz"
BUSINESS_NAME = "Mason-Fultz Commercial Cleaning"
PUBLIC_SLUG   = "mason-fultz-cleaning"
LOGO_URL      = "/static/images/vip/mason_fultz_logo.png"
BRAND_COLOR   = "#1A4EA1"
PHONE         = "615-967-5742"
HEADLINE      = "Professional cleaning services you can count on — so you can focus on your business."
BIO           = (
    "Mason-Fultz Commercial Cleaning provides reliable, professional cleaning "
    "services for offices, medical facilities, retail spaces, churches, and "
    "more -- tailored cleaning plans built around your business and your budget."
)
SERVICE_AREA  = "Our Community and Surrounding Areas"


def create_mason_fultz_cleaning():
    with app.app_context():
        # -- 1. User (must already exist -- never create or reset a password) --
        user = User.query.filter(db.func.lower(User.email) == EMAIL.lower()).first()
        if not user:
            raise SystemExit(
                f"No existing account found for {EMAIL}. This script only sets up "
                "the business profile for an account that already exists."
            )

        if user.role not in ("partner",):
            user.role = "partner"
        user.is_active = True
        if not user.first_name:
            user.first_name = FIRST_NAME
        if not user.last_name:
            user.last_name = LAST_NAME

        # -- 2. Partner ------------------------------------------------------
        partner = Partner.query.filter_by(user_id=user.id).first()
        created_partner = False

        if not partner:
            partner = Partner(
                user_id=user.id,
                name=BUSINESS_NAME,
                email=EMAIL,
                phone=PHONE,
                category="Cleaning",
                type="Commercial Cleaning",
                specialty="Commercial & Office Cleaning",
                service_area=SERVICE_AREA,
                subscription_tier="Featured",
                approved=True,
                active=True,
                featured=True,
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
            partner.name = partner.name or BUSINESS_NAME
            partner.phone = partner.phone or PHONE
            partner.service_area = partner.service_area or SERVICE_AREA
            partner.subscription_tier = "Featured"
            partner.approved = True
            partner.active = True
            partner.featured = True
            partner.status = "Active"
            partner.crm_enabled = True
            partner.deal_visibility_enabled = True
            partner.proposal_builder_enabled = True
            partner.ai_assist_enabled = True
            partner.priority_placement_enabled = True
            partner.smart_notifications_enabled = True

        # -- 3. VIP Profile ----------------------------------------------------
        vip = VIPProfile.query.filter_by(user_id=user.id).first()
        created_vip = False

        if not vip:
            vip = VIPProfile(
                user_id=user.id,
                display_name=BUSINESS_NAME,
                business_name=BUSINESS_NAME,
                role_type="contractor",
                assistant_name="Ravlo",
                marketplace_enabled="yes",
                public_slug=PUBLIC_SLUG,
                headline=HEADLINE,
                bio=BIO,
                service_area=SERVICE_AREA,
                specialties="Commercial & Office Cleaning",
                brand_color=BRAND_COLOR,
                logo_url=LOGO_URL,
                enabled_modules="contractor,crm,finances",
            )
            db.session.add(vip)
            created_vip = True
        else:
            vip.role_type = "contractor"
            vip.marketplace_enabled = "yes"
            vip.display_name = vip.display_name or BUSINESS_NAME
            vip.business_name = vip.business_name or BUSINESS_NAME
            if not vip.public_slug:
                vip.public_slug = PUBLIC_SLUG
            if not vip.brand_color:
                vip.brand_color = BRAND_COLOR
            if not vip.logo_url:
                vip.logo_url = LOGO_URL
            if not vip.headline:
                vip.headline = HEADLINE
            if not vip.bio:
                vip.bio = BIO
            if not vip.service_area:
                vip.service_area = SERVICE_AREA

        db.session.commit()

        print()
        print("=" * 55)
        print("  Mason-Fultz Commercial Cleaning — VIP Contractor Account")
        print("=" * 55)
        print(f"  Email     : {EMAIL}")
        print(f"  Role      : partner  (VIP Featured tier)")
        print(f"  VIP type  : contractor")
        print(f"  Partner   : {'created' if created_partner else 'updated'} (id={partner.id})")
        print(f"  VIPProfile: {'created' if created_vip else 'updated'} (id={vip.id})")
        print("=" * 55)
        print("  Dashboards unlocked:")
        print("    /vip/contractor          — Contractor VIP workspace")
        print("    /partners/               — Partner OS")
        print(f"    /p/{vip.public_slug}   — Public landing page")
        print("=" * 55)
        print()


if __name__ == "__main__":
    create_mason_fultz_cleaning()
