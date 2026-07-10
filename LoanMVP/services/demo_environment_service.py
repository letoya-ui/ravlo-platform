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

DEMO_COMPANY_NAME = "Ravlo Demo Co"
DEMO_EMAIL_DOMAIN = "demo.ravlohq.com"

DEMO_ROLE_EMAILS = {
    "admin": f"demo-admin@{DEMO_EMAIL_DOMAIN}",
    "investor": f"demo-investor@{DEMO_EMAIL_DOMAIN}",
    "loan_officer": f"demo-loanofficer@{DEMO_EMAIL_DOMAIN}",
    "processor": f"demo-processor@{DEMO_EMAIL_DOMAIN}",
    "underwriter": f"demo-underwriter@{DEMO_EMAIL_DOMAIN}",
    "borrower": f"demo-borrower@{DEMO_EMAIL_DOMAIN}",
    "partner": f"demo-partner@{DEMO_EMAIL_DOMAIN}",
}


def _get_or_create_demo_company():
    company = Company.query.filter_by(name=DEMO_COMPANY_NAME).first()
    if company:
        return company
    company = Company(
        name=DEMO_COMPANY_NAME,
        email_domain=DEMO_EMAIL_DOMAIN,
        is_active=True,
        subscription_tier="enterprise",
        max_users=50,
    )
    db.session.add(company)
    db.session.flush()
    return company


def _get_or_create_user(email, role, company_id, first_name, last_name):
    user = User.query.filter_by(email=email).first()
    if user:
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


def ensure_demo_environment():
    """Create the demo company/users/sample data if they don't already
    exist, and return {role: User} for every demo persona.
    """
    company = _get_or_create_demo_company()

    admin_user = _get_or_create_user(DEMO_ROLE_EMAILS["admin"], "admin", company.id, "Demo", "Admin")
    investor_user = _get_or_create_user(DEMO_ROLE_EMAILS["investor"], "investor", company.id, "Demo", "Investor")
    lo_user = _get_or_create_user(DEMO_ROLE_EMAILS["loan_officer"], "loan_officer", company.id, "Demo", "Officer")
    proc_user = _get_or_create_user(DEMO_ROLE_EMAILS["processor"], "processor", company.id, "Demo", "Processor")
    uw_user = _get_or_create_user(DEMO_ROLE_EMAILS["underwriter"], "underwriter", company.id, "Demo", "Underwriter")
    borrower_user = _get_or_create_user(DEMO_ROLE_EMAILS["borrower"], "borrower", company.id, "Demo", "Borrower")
    partner_user = _get_or_create_user(DEMO_ROLE_EMAILS["partner"], "partner", company.id, "Demo", "Partner")

    investor_profile = InvestorProfile.query.filter_by(user_id=investor_user.id).first()
    if not investor_profile:
        investor_profile = InvestorProfile(user_id=investor_user.id, full_name="Demo Investor", strategy="flip")
        db.session.add(investor_profile)

    lo_profile = LoanOfficerProfile.query.filter_by(user_id=lo_user.id).first()
    if not lo_profile:
        lo_profile = LoanOfficerProfile(
            user_id=lo_user.id,
            name="Demo Officer",
            email=DEMO_ROLE_EMAILS["loan_officer"],
            license_verified=True,
            licensed_states="FL,GA,TX,NY",
        )
        db.session.add(lo_profile)

    proc_profile = ProcessorProfile.query.filter_by(user_id=proc_user.id).first()
    if not proc_profile:
        proc_profile = ProcessorProfile(user_id=proc_user.id, full_name="Demo Processor", email=DEMO_ROLE_EMAILS["processor"])
        db.session.add(proc_profile)

    uw_profile = UnderwriterProfile.query.filter_by(user_id=uw_user.id).first()
    if not uw_profile:
        uw_profile = UnderwriterProfile(user_id=uw_user.id, full_name="Demo Underwriter", email=DEMO_ROLE_EMAILS["underwriter"])
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
            email=DEMO_ROLE_EMAILS["borrower"],
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
