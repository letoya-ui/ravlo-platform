"""Idempotent demo-environment provisioning for the executive Demo Center.

Ensures one dedicated demo User (+ role profile + a little realistic
sample data) exists per role, so Letoya/Jamaine/Sandra can instantly view
any dashboard without ever creating or remembering a password -- the
demo-login route logs staff in as these accounts directly via
flask_login.login_user(), bypassing the password check entirely. These
accounts are never reachable through the normal /auth/login form since
they carry no usable password_hash.

Safe to call on every demo-login click: everything here is get-or-create,
keyed on a fixed, well-known email per role under a dedicated demo
company/email domain that is clearly separate from any real customer data.

Supports more than one "variant" -- e.g. the plain Ravlo-branded demo and
a White Label variant (a fictional licensee, "Meridian Capital Lending")
that shows the exact same product under different branding, so an AE can
give a White Label prospect something concrete to look at instead of
describing the feature in the abstract.
"""
from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.borrowers import Deal
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.loan_models import BorrowerProfile, LoanApplication
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.processor_model import ProcessorProfile
from LoanMVP.models.property import SavedProperty
from LoanMVP.models.underwriter_model import UnderwriterProfile
from LoanMVP.models.user_model import User

DEMO_VARIANTS = {
    "ravlo": {
        "label": "Ravlo",
        "company_name": "Ravlo Demo Co",
        "email_domain": "demo.ravlohq.com",
        "subscription_tier": "enterprise",
        "brand_name": None,
        "brand_logo_initials": None,
        "brand_primary_color": None,
        "brand_secondary_color": None,
        "brand_accent_color": None,
        "brand_tagline": None,
    },
    "white_label": {
        "label": "Meridian Capital (White Label)",
        "company_name": "Meridian Capital Lending",
        "email_domain": "demo.meridiancapital.com",
        "subscription_tier": "white_label",
        "brand_name": "Meridian Capital",
        "brand_logo_initials": "MC",
        "brand_primary_color": "#0F2D52",
        "brand_secondary_color": "#0E7C66",
        "brand_accent_color": "#C9A227",
        "brand_tagline": "Guiding Capital. Building Futures.",
    },
}

# Fields self-healed/synced onto the demo Company row from its variant
# config -- kept as a single list so create + heal always cover the same
# set (adding a new brand_* field to DEMO_VARIANTS only requires listing
# it here once).
_BRANDING_FIELDS = (
    "subscription_tier",
    "brand_name",
    "brand_logo_initials",
    "brand_primary_color",
    "brand_secondary_color",
    "brand_accent_color",
    "brand_tagline",
)

# Kept for backward compatibility with anything importing the old names directly.
DEMO_COMPANY_NAME = DEMO_VARIANTS["ravlo"]["company_name"]
DEMO_EMAIL_DOMAIN = DEMO_VARIANTS["ravlo"]["email_domain"]


def _role_emails(email_domain):
    return {
        "admin": f"demo-admin@{email_domain}",
        "investor": f"demo-investor@{email_domain}",
        "loan_officer": f"demo-loanofficer@{email_domain}",
        "processor": f"demo-processor@{email_domain}",
        "underwriter": f"demo-underwriter@{email_domain}",
        "borrower": f"demo-borrower@{email_domain}",
        "partner": f"demo-partner@{email_domain}",
    }


DEMO_ROLE_EMAILS = _role_emails(DEMO_EMAIL_DOMAIN)


def _get_or_create_demo_company(variant):
    company = Company.query.filter_by(name=variant["company_name"]).first()
    if company:
        # Self-heal: keep the branding fields in sync with the variant
        # config in case they drifted (e.g. an earlier version of this
        # service created the row before some brand_* column existed).
        if any(getattr(company, field) != variant[field] for field in _BRANDING_FIELDS):
            for field in _BRANDING_FIELDS:
                setattr(company, field, variant[field])
            db.session.flush()
        return company
    company = Company(
        name=variant["company_name"],
        email_domain=variant["email_domain"],
        is_active=True,
        max_users=50,
        **{field: variant[field] for field in _BRANDING_FIELDS},
    )
    db.session.add(company)
    db.session.flush()
    return company


def _get_or_create_user(email, role, company_id, first_name, last_name):
    user = User.query.filter_by(email=email).first()
    if user:
        # Self-heal: a pre-existing row at this well-known demo email (from
        # earlier ad-hoc testing, a manual role change, etc.) must still
        # match its intended persona, or role_required() rejects it and
        # bounces the demo-login attempt straight back to auth.login.
        if user.role != role or user.company_id != company_id or not user.is_active:
            user.role = role
            user.company_id = company_id
            user.is_active = True
            db.session.flush()
        return user
    user = User(
        email=email,
        role=role,
        first_name=first_name,
        last_name=last_name,
        company_id=company_id,
        is_active=True,
        nda_accepted=True,
        ica_accepted=True,
        onboarding_complete=True,
        invite_accepted=True,
        subscription="enterprise",
    )
    db.session.add(user)
    db.session.flush()
    return user


def ensure_demo_environment(variant_key="ravlo"):
    """Create the demo company/users/sample data for the given variant if
    they don't already exist, and return {role: User} for every demo
    persona in that variant. Each variant is a fully separate company
    (own email domain, own sample loans/deals) so switching variants
    never mixes data.
    """
    variant = DEMO_VARIANTS.get(variant_key, DEMO_VARIANTS["ravlo"])
    role_emails = _role_emails(variant["email_domain"])
    company = _get_or_create_demo_company(variant)

    admin_user = _get_or_create_user(role_emails["admin"], "admin", company.id, "Demo", "Admin")
    investor_user = _get_or_create_user(role_emails["investor"], "investor", company.id, "Demo", "Investor")
    lo_user = _get_or_create_user(role_emails["loan_officer"], "loan_officer", company.id, "Demo", "Officer")
    proc_user = _get_or_create_user(role_emails["processor"], "processor", company.id, "Demo", "Processor")
    uw_user = _get_or_create_user(role_emails["underwriter"], "underwriter", company.id, "Demo", "Underwriter")
    borrower_user = _get_or_create_user(role_emails["borrower"], "borrower", company.id, "Demo", "Borrower")
    partner_user = _get_or_create_user(role_emails["partner"], "partner", company.id, "Demo", "Partner")

    investor_profile = InvestorProfile.query.filter_by(user_id=investor_user.id).first()
    if not investor_profile:
        investor_profile = InvestorProfile(user_id=investor_user.id, full_name="Demo Investor", strategy="flip")
        db.session.add(investor_profile)

    lo_profile = LoanOfficerProfile.query.filter_by(user_id=lo_user.id).first()
    if not lo_profile:
        lo_profile = LoanOfficerProfile(
            user_id=lo_user.id,
            name="Demo Officer",
            email=role_emails["loan_officer"],
            license_verified=True,
            licensed_states="FL,GA,TX,NY",
        )
        db.session.add(lo_profile)

    proc_profile = ProcessorProfile.query.filter_by(user_id=proc_user.id).first()
    if not proc_profile:
        proc_profile = ProcessorProfile(user_id=proc_user.id, full_name="Demo Processor", email=role_emails["processor"])
        db.session.add(proc_profile)

    uw_profile = UnderwriterProfile.query.filter_by(user_id=uw_user.id).first()
    if not uw_profile:
        uw_profile = UnderwriterProfile(user_id=uw_user.id, full_name="Demo Underwriter", email=role_emails["underwriter"])
        db.session.add(uw_profile)

    partner_profile = Partner.query.filter_by(user_id=partner_user.id).first()
    if not partner_profile:
        partner_profile = Partner(
            user_id=partner_user.id,
            name="Demo Partner Co",
            company="Demo Partner Co",
            category="Realtor",
            type="Realtor",
            active=True,
            approved=True,
            is_verified=True,
        )
        db.session.add(partner_profile)

    db.session.flush()

    borrower_profile = BorrowerProfile.query.filter_by(user_id=borrower_user.id).first()
    if not borrower_profile:
        borrower_profile = BorrowerProfile(
            user_id=borrower_user.id,
            full_name="Demo Borrower",
            email=role_emails["borrower"],
            company_id=company.id,
            state="FL",
            assigned_officer_id=lo_profile.id,
        )
        db.session.add(borrower_profile)
        db.session.flush()

    # Sample loans across the pipeline, assigned across officer/processor/underwriter
    if LoanApplication.query.filter_by(company_id=company.id).count() == 0:
        sample_loans = [
            dict(status="Submitted", milestone_stage="Application Started", amount=285000, property_address="410 Palmview Ave, Tampa, FL"),
            dict(status="In Review", milestone_stage="Processing", amount=340000, property_address="88 Ridgecrest Dr, Orlando, FL"),
            dict(status="Approved", milestone_stage="Underwriting", amount=210000, property_address="12 Lakeshore Ct, Miami, FL"),
            dict(status="Clear to Close", milestone_stage="Clear to Close", amount=495000, property_address="732 Bayview Ter, Sarasota, FL"),
            dict(status="Funded", milestone_stage="Funded", amount=178000, property_address="55 Harborside Ln, St. Petersburg, FL"),
        ]
        for entry in sample_loans:
            db.session.add(LoanApplication(
                company_id=company.id,
                borrower_profile_id=borrower_profile.id,
                loan_officer_id=lo_profile.id,
                processor_id=proc_profile.id,
                underwriter_id=uw_profile.id,
                loan_type="DSCR",
                term_months=360,
                rate=8.25,
                **entry,
            ))

    # Investor sample saved properties + deals
    if SavedProperty.query.filter_by(investor_profile_id=investor_profile.id).count() == 0:
        for addr, zipc in (
            ("214 Sunset Palm Dr, Tampa, FL", "33602"),
            ("77 Ocean Breeze Way, Sarasota, FL", "34236"),
        ):
            db.session.add(SavedProperty(investor_profile_id=investor_profile.id, address=addr, zipcode=zipc))

    if Deal.query.filter_by(user_id=investor_user.id).count() == 0:
        db.session.add(Deal(
            user_id=investor_user.id,
            investor_profile_id=investor_profile.id,
            title="214 Sunset Palm Dr",
            city="Tampa",
            state="FL",
            zip_code="33602",
            strategy="flip",
            purchase_price=245000,
            arv=365000,
            estimated_rent=2400,
            rehab_cost=42000,
        ))
        db.session.add(Deal(
            user_id=investor_user.id,
            investor_profile_id=investor_profile.id,
            title="77 Ocean Breeze Way",
            city="Sarasota",
            state="FL",
            zip_code="34236",
            strategy="rental",
            purchase_price=298000,
            arv=410000,
            estimated_rent=2650,
            rehab_cost=18000,
        ))

    db.session.commit()

    return {
        "admin": admin_user,
        "investor": investor_user,
        "loan_officer": lo_user,
        "processor": proc_user,
        "underwriter": uw_user,
        "borrower": borrower_user,
        "partner": partner_user,
    }
