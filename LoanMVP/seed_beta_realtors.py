# LoanMVP/seed_beta_realtors.py
"""Idempotent seed for the beta realtor pair (Frank + Elena).

Runs under the Flask app context and makes sure:

    Frank (Frankgolio@gmail.com)
      - User account (realtor role), password TempPass123!
      - PartnerProfile (category=Realtor, subscription_tier=Premium)
      - VIPProfile (role_type=realtor, markets_json=["Hudson Valley", "Sarasota"])

    Elena (first realtor partner found, or seeds a placeholder)
      - VIPProfile markets_json defaults to ["Hudson Valley"] so she keeps
        her single-market experience.

Usage:
    python -m LoanMVP.seed_beta_realtors

Safe to run multiple times — existing users / profiles are updated in place.
"""
import json

from werkzeug.security import generate_password_hash

from LoanMVP.app import app
from LoanMVP.extensions import db
from LoanMVP.models import User
from LoanMVP.models.crm_models import Partner as PartnerProfile
from LoanMVP.models.vip_models import VIPProfile


FRANK_EMAIL    = "Frankgolio@gmail.com"
FRANK_NAME     = "Frank Golio"
FRANK_PASSWORD = "TempPass123!"
FRANK_MARKETS  = ["Hudson Valley", "Sarasota"]

ELENA_DEFAULT_MARKETS = ["Hudson Valley"]


def _ensure_user(email: str, full_name: str, password: str, role: str = "realtor") -> User:
    user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            role=role,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.flush()
        print(f"  + created user {email} (id={user.id})")
    else:
        # Keep existing password if already set — avoid clobbering real ones.
        if not getattr(user, "password_hash", None):
            user.password_hash = generate_password_hash(password)
        if role and getattr(user, "role", None) != role:
            user.role = role
        print(f"  = user {email} already exists (id={user.id})")
    return user


def _ensure_partner(user: User, name: str, *, category: str, tier: str) -> PartnerProfile:
    partner = PartnerProfile.query.filter_by(user_id=user.id).first()
    if partner is None:
        partner = PartnerProfile(
            user_id=user.id,
            name=name,
            email=user.email,
            category=category,
            type=category,
            subscription_tier=tier,
            status="Active",
            active=True,
            approved=True,
        )
        db.session.add(partner)
        db.session.flush()
        print(f"  + created PartnerProfile for {user.email} (tier={tier})")
    else:
        partner.category = category
        partner.type = partner.type or category
        partner.subscription_tier = tier
        partner.status = "Active"
        partner.active = True
        partner.approved = True
        print(f"  = PartnerProfile for {user.email} upgraded to tier={tier}")
    return partner


def _ensure_vip_profile(user: User, *, role_type: str, markets: list[str],
                        display_name: str) -> VIPProfile:
    profile = VIPProfile.query.filter_by(user_id=user.id).first()
    if profile is None:
        profile = VIPProfile(
            user_id=user.id,
            role_type=role_type,
            display_name=display_name,
            markets_json=json.dumps(markets),
            enabled_modules=json.dumps([
                "crm", "finances", "ai_pilot", "content_studio", "canva",
            ]),
        )
        db.session.add(profile)
        db.session.flush()
        print(f"  + created VIPProfile for {user.email} with markets={markets}")
    else:
        profile.role_type     = role_type
        profile.markets_json  = json.dumps(markets)
        if not profile.display_name:
            profile.display_name = display_name
        print(f"  = VIPProfile for {user.email} markets set to {markets}")
    return profile


def seed_beta_realtors() -> None:
    with app.app_context():
        print("Seeding beta realtor pair (Frank + Elena)...")

        frank_user = _ensure_user(FRANK_EMAIL, FRANK_NAME, FRANK_PASSWORD, role="realtor")
        _ensure_partner(frank_user, FRANK_NAME, category="Realtor", tier="Premium")
        _ensure_vip_profile(
            frank_user,
            role_type="realtor",
            markets=FRANK_MARKETS,
            display_name=FRANK_NAME,
        )

        # Elena: don't create a user if one doesn't exist — just make sure the
        # first realtor-tier partner profile we find has at least one market
        # configured so her dashboard behaves sensibly with the new code.
        elena_partners = (
            PartnerProfile.query
            .filter(db.func.lower(PartnerProfile.category) == "realtor")
            .filter(PartnerProfile.user_id != frank_user.id)
            .all()
        )
        touched_elena = 0
        for partner in elena_partners:
            if partner.user_id is None:
                continue
            profile = VIPProfile.query.filter_by(user_id=partner.user_id).first()
            if profile is None:
                continue
            if not profile.markets_json or profile.markets_json in ("[]", "null"):
                profile.markets_json = json.dumps(ELENA_DEFAULT_MARKETS)
                touched_elena += 1
                print(f"  = VIPProfile user_id={partner.user_id} seeded markets={ELENA_DEFAULT_MARKETS}")

        db.session.commit()
        print(
            "Done. Frank dual-market configured; "
            f"{touched_elena} other realtor profile(s) defaulted to single-market."
        )


if __name__ == "__main__":
    seed_beta_realtors()
