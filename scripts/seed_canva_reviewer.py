"""
Seed script — Canva integration reviewer account
================================================
Creates a ready-to-use Ravlo account for integrations-support@canva.com
with demo listings and flyer drafts so the reviewer can test the
Canva integration immediately without any manual setup.

Usage (from the repo root):
    python scripts/seed_canva_reviewer.py

The script is idempotent — safe to run more than once.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from LoanMVP.app import create_app
from LoanMVP.extensions import db
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile
from LoanMVP.models.elena_models import ElenaClient, ElenaListing, ElenaFlyer

# ── Config ────────────────────────────────────────────────────────────────────

REVIEWER_EMAIL    = "integrations-support@canva.com"
REVIEWER_PASSWORD = "CanvaReview2025!"   # change if you prefer something else
REVIEWER_FIRST    = "Canva"
REVIEWER_LAST     = "Reviewer"

DEMO_LISTINGS = [
    {
        "mls_number": "MLS-001",
        "address": "42 Maple Ridge Drive",
        "city": "Beacon",
        "state": "NY",
        "zip_code": "12508",
        "beds": 4,
        "baths": 3,
        "sqft": 2400,
        "price": 649000,
        "status": "active",
        "market": "Hudson Valley",
        "description": (
            "Stunning colonial on a quiet cul-de-sac. "
            "Renovated kitchen with quartz countertops, hardwood floors throughout, "
            "and a sun-drenched backyard perfect for entertaining."
        ),
        "flyer_type": "just_listed",
        "flyer_body": (
            "Just Listed — 42 Maple Ridge Drive, Beacon NY\n\n"
            "Welcome to this beautifully updated 4-bed, 3-bath colonial in the heart of the Hudson Valley. "
            "Featuring a chef's kitchen, gleaming hardwood floors, and a sprawling backyard, "
            "this home is move-in ready and priced to move at $649,000.\n\n"
            "Contact us today to schedule your private showing."
        ),
    },
    {
        "mls_number": "MLS-002",
        "address": "17 Shoreline Court",
        "city": "Sarasota",
        "state": "FL",
        "zip_code": "34236",
        "beds": 3,
        "baths": 2,
        "sqft": 1850,
        "price": 525000,
        "status": "active",
        "market": "Sarasota",
        "description": (
            "Light-filled coastal retreat two blocks from Siesta Key Beach. "
            "Open-plan living, updated baths, private pool, and a two-car garage."
        ),
        "flyer_type": "open_house",
        "flyer_body": (
            "Open House This Sunday 12–3 PM — 17 Shoreline Court, Sarasota FL\n\n"
            "Join us for an open house at this stunning coastal home steps from Siesta Key Beach. "
            "3 beds · 2 baths · private pool · $525,000.\n\n"
            "Light refreshments provided. We look forward to seeing you!"
        ),
    },
    {
        "mls_number": "MLS-003",
        "address": "305 Oak Street, Unit 2B",
        "city": "Brooklyn",
        "state": "NY",
        "zip_code": "11201",
        "beds": 2,
        "baths": 1,
        "sqft": 950,
        "price": 875000,
        "status": "active",
        "market": "New York City",
        "description": (
            "Gut-renovated pre-war co-op in prime Brooklyn Heights. "
            "Exposed brick, chef's kitchen, in-unit W/D, and sweeping views of the Manhattan skyline."
        ),
        "flyer_type": "price_drop",
        "flyer_body": (
            "Price Improvement — 305 Oak Street #2B, Brooklyn NY\n\n"
            "Incredible value on this renovated pre-war co-op in Brooklyn Heights. "
            "Now asking $875,000 — down from $925,000. "
            "2 beds · 1 bath · exposed brick · skyline views.\n\n"
            "Don't miss this opportunity. Schedule a tour today."
        ),
    },
]

DEMO_CLIENT = {
    "name": "Demo Buyer",
    "email": "demo.buyer@example.com",
    "phone": "555-867-5309",
    "pipeline_stage": "Active Search",
    "preferred_areas": "Hudson Valley, Beacon NY",
    "budget": "$600,000 – $750,000",
    "notes": "Looking for a 4-bed colonial with a yard. Pre-approved.",
}

# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    app = create_app()

    with app.app_context():
        # ── User ──────────────────────────────────────────────────────────────
        user = User.query.filter_by(email=REVIEWER_EMAIL).first()
        if not user:
            user = User(
                email=REVIEWER_EMAIL,
                first_name=REVIEWER_FIRST,
                last_name=REVIEWER_LAST,
                username="canva_reviewer",
                role="partner",
                is_active=True,
                invite_accepted=True,
                onboarding_complete=True,
                subscription="pro",
            )
            user.set_password(REVIEWER_PASSWORD)
            db.session.add(user)
            db.session.flush()
            print(f"  Created user: {REVIEWER_EMAIL}")
        else:
            user.set_password(REVIEWER_PASSWORD)
            user.role = "partner"
            user.is_active = True
            user.onboarding_complete = True
            user.subscription = "pro"
            print(f"  Updated existing user: {REVIEWER_EMAIL}")

        # ── VIP Profile ───────────────────────────────────────────────────────
        profile = VIPProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            profile = VIPProfile(
                user_id=user.id,
                display_name="Canva Reviewer",
                business_name="Ravlo Demo Realty",
                dashboard_title="Realtor Dashboard",
                role_type="realtor",
                assistant_name="Elena",
                headline="Top-producing agent in the Hudson Valley",
                bio=(
                    "Demo account for Canva integration review. "
                    "This profile has sample listings and flyers ready to test."
                ),
                service_area="Hudson Valley, Sarasota, Brooklyn",
                specialties="Residential, Luxury, Investment",
            )
            db.session.add(profile)
            db.session.flush()
            print(f"  Created VIP profile (role: realtor)")
        else:
            print(f"  VIP profile already exists — skipping")

        # ── Demo Client ───────────────────────────────────────────────────────
        client = ElenaClient.query.filter_by(email=DEMO_CLIENT["email"]).first()
        if not client:
            client = ElenaClient(**DEMO_CLIENT)
            db.session.add(client)
            db.session.flush()
            print(f"  Created demo client: {DEMO_CLIENT['name']}")
        else:
            print(f"  Demo client already exists — skipping")

        # ── Demo Listings + Flyers ────────────────────────────────────────────
        for spec in DEMO_LISTINGS:
            flyer_type = spec.pop("flyer_type")
            flyer_body = spec.pop("flyer_body")

            listing = ElenaListing.query.filter_by(
                mls_number=spec["mls_number"]
            ).first()

            if not listing:
                listing = ElenaListing(**spec)
                db.session.add(listing)
                db.session.flush()
                print(f"  Created listing: {spec['address']}")
            else:
                print(f"  Listing already exists: {spec['address']} — skipping")

            flyer = ElenaFlyer.query.filter_by(listing_id=listing.id).first()
            if not flyer:
                flyer = ElenaFlyer(
                    flyer_type=flyer_type,
                    property_address=listing.address,
                    property_id=str(listing.id),
                    body=flyer_body,
                    listing_id=listing.id,
                    canva_status="draft",
                )
                db.session.add(flyer)
                print(f"  Created flyer ({flyer_type}) for: {listing.address}")
            else:
                print(f"  Flyer already exists for: {listing.address} — skipping")

        db.session.commit()

        print("\nDone.")
        print(f"  Email:    {REVIEWER_EMAIL}")
        print(f"  Password: {REVIEWER_PASSWORD}")
        print(f"  Role:     partner / realtor VIP")
        print(f"  Listings: {len(DEMO_LISTINGS)} demo properties with flyer drafts")


if __name__ == "__main__":
    run()
