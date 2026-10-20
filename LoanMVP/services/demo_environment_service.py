"""Idempotent demo-environment provisioning for the executive Demo Center.

Ensures one dedicated demo User (+ role profile + a little realistic
sample data) exists per role, so Letoya/Sandra can instantly view
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

The white_label variant additionally gets a full sample pipeline built
around four named borrowers (Danielle Carter, Marcus Reyes, Ade & Lisa
Okafor, Priya Nair) instead of one generic borrower repeated across five
identical-looking loans -- see _seed_meridian_capital_pipeline() below.
Each borrower's story exercises a different seat at the company:
Danielle is the loan-officer story (quote engine -> preapproval), Marcus
is the processor story (open conditions/documents), and the Okafors are
the underwriting story -- with a handful of CRM leads across a small
team of loan officers giving the broker-owner (admin) a real pipeline to
see across Chris/Priya/Sam rather than a single person's book.
"""
from datetime import date, datetime, timedelta

from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.borrowers import Deal
from LoanMVP.models.crm_models import Lead, LeadSource, Partner, Task
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.loan_models import BorrowerProfile, CreditProfile, LoanApplication, LoanQuote, LoanStatusEvent
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.processor_model import ProcessorProfile
from LoanMVP.models.property import SavedProperty
from LoanMVP.models.underwriter_model import ConditionRequest, UnderwriterProfile, UnderwritingCondition
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
        "brand_logo_url": None,
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
        "brand_logo_url": "images/demo/meridian_capital_logo.png",
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
    "brand_logo_url",
)

# Kept for backward compatibility with anything importing the old names directly.
DEMO_COMPANY_NAME = DEMO_VARIANTS["ravlo"]["company_name"]
DEMO_EMAIL_DOMAIN = DEMO_VARIANTS["ravlo"]["email_domain"]

# The white_label variant gets named people instead of "Demo Officer" /
# "Demo Processor" -- it's the one shown to real prospects, so it should
# read like an actual mortgage company. The ravlo variant keeps the
# generic names (nothing depends on Meridian's roster there).
_LENDING_PERSONA_NAMES = {
    "white_label": {
        "admin": ("Renata", "Castillo"),
        "loan_officer": ("Chris", "Nakamura"),
        "processor": ("Jamie", "Ortiz"),
        "underwriter": ("Devon", "Marsh"),
        "borrower": ("Danielle", "Carter"),
    },
}


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


def _persona_name(variant_key, role, default_first, default_last):
    first, last = _LENDING_PERSONA_NAMES.get(variant_key, {}).get(role, (default_first, default_last))
    return first, last


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


def _get_or_create_supporting_officer(email, company_id, name, **profile_fields):
    """A loan officer who exists purely as pipeline data (assigned loans,
    leads) for team-visibility demos -- never a demo-login persona, so
    it's not part of ensure_demo_environment()'s returned role dict."""
    user = User.query.filter_by(email=email).first()
    if not user:
        first, last = (name.split(" ", 1) + [""])[:2]
        user = User(
            email=email, role="loan_officer", first_name=first, last_name=last,
            company_id=company_id, is_active=True, nda_accepted=True, ica_accepted=True,
            onboarding_complete=True, invite_accepted=True, subscription="enterprise",
        )
        db.session.add(user)
        db.session.flush()

    profile = LoanOfficerProfile.query.filter_by(user_id=user.id).first()
    if not profile:
        profile = LoanOfficerProfile(user_id=user.id, name=name, email=email, license_verified=True, **profile_fields)
        db.session.add(profile)
        db.session.flush()
    return user, profile


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

    admin_first, admin_last = _persona_name(variant_key, "admin", "Demo", "Admin")
    lo_first, lo_last = _persona_name(variant_key, "loan_officer", "Demo", "Officer")
    proc_first, proc_last = _persona_name(variant_key, "processor", "Demo", "Processor")
    uw_first, uw_last = _persona_name(variant_key, "underwriter", "Demo", "Underwriter")
    borrower_first, borrower_last = _persona_name(variant_key, "borrower", "Demo", "Borrower")

    admin_user = _get_or_create_user(role_emails["admin"], "admin", company.id, admin_first, admin_last)
    investor_user = _get_or_create_user(role_emails["investor"], "investor", company.id, "Demo", "Investor")
    lo_user = _get_or_create_user(role_emails["loan_officer"], "loan_officer", company.id, lo_first, lo_last)
    proc_user = _get_or_create_user(role_emails["processor"], "processor", company.id, proc_first, proc_last)
    uw_user = _get_or_create_user(role_emails["underwriter"], "underwriter", company.id, uw_first, uw_last)
    borrower_user = _get_or_create_user(role_emails["borrower"], "borrower", company.id, borrower_first, borrower_last)
    partner_user = _get_or_create_user(role_emails["partner"], "partner", company.id, "Demo", "Partner")

    investor_profile = InvestorProfile.query.filter_by(user_id=investor_user.id).first()
    if not investor_profile:
        investor_profile = InvestorProfile(user_id=investor_user.id, full_name="Demo Investor", strategy="flip")
        db.session.add(investor_profile)

    lo_profile = LoanOfficerProfile.query.filter_by(user_id=lo_user.id).first()
    if not lo_profile:
        lo_profile = LoanOfficerProfile(
            user_id=lo_user.id,
            name=f"{lo_first} {lo_last}",
            email=role_emails["loan_officer"],
            license_verified=True,
            licensed_states="FL,GA,TX,NY",
            region="Tampa Bay / Central Florida" if variant_key == "white_label" else None,
            specialization="Conventional & FHA purchase" if variant_key == "white_label" else None,
        )
        db.session.add(lo_profile)

    proc_profile = ProcessorProfile.query.filter_by(user_id=proc_user.id).first()
    if not proc_profile:
        proc_profile = ProcessorProfile(user_id=proc_user.id, full_name=f"{proc_first} {proc_last}", email=role_emails["processor"])
        db.session.add(proc_profile)

    uw_profile = UnderwriterProfile.query.filter_by(user_id=uw_user.id).first()
    if not uw_profile:
        uw_profile = UnderwriterProfile(user_id=uw_user.id, full_name=f"{uw_first} {uw_last}", email=role_emails["underwriter"])
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
            full_name=f"{borrower_first} {borrower_last}",
            email=role_emails["borrower"],
            company_id=company.id,
            state="FL",
            assigned_officer_id=lo_profile.id,
        )
        db.session.add(borrower_profile)
        db.session.flush()

    if variant_key == "white_label":
        _seed_meridian_capital_pipeline(company, lo_user, lo_profile, proc_user, proc_profile, uw_user, uw_profile, borrower_user, borrower_profile)
    else:
        _seed_generic_pipeline(company, borrower_profile, lo_profile, proc_profile, uw_profile)

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


def _seed_generic_pipeline(company, borrower_profile, lo_profile, proc_profile, uw_profile):
    """The original plain-Ravlo demo: one borrower reused across five
    loans at different stages. Left exactly as it was -- nothing outside
    the white_label/Meridian story depends on richer data here."""
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


def _seed_meridian_capital_pipeline(company, chris_user, chris_lo, jamie_user, jamie_proc, devon_user, devon_uw, danielle_user, danielle_profile):
    """Four named borrowers, each carrying a different seat's demo story,
    instead of one generic borrower repeated across identical loans:

    - Danielle Carter (loan officer story): new borrower -> Quote Engine
      side-by-side lender comparison -> preapproval -> a follow-up task.
    - Marcus Reyes (processor story): a file sitting on two open
      conditions/documents after two are already cleared.
    - Ade & Lisa Okafor (underwriting story): in underwriting review with
      one condition cleared and two still open.
    - Priya Nair: a DSCR investment purchase, clear to close -- rounds
      out the pipeline so it isn't only purchase/refi consumer loans.

    Also seeds two supporting loan officers (Priya Shah, Sam Torres) and
    a handful of CRM leads across all three, so the admin/broker-owner
    view has an actual team pipeline to show, not one person's book.
    """
    if LoanApplication.query.filter_by(company_id=company.id).count() > 0:
        return  # already seeded -- idempotent, matches _get_or_create_* elsewhere in this module

    priya_shah_user, priya_shah_lo = _get_or_create_supporting_officer(
        f"priya.shah@{company.email_domain}", company.id, "Priya Shah",
        licensed_states="FL,GA", region="Sarasota / Southwest Florida",
        specialization="Conventional purchase, jumbo",
    )
    sam_torres_user, sam_torres_lo = _get_or_create_supporting_officer(
        f"sam.torres@{company.email_domain}", company.id, "Sam Torres",
        licensed_states="FL", region="St. Petersburg / Pinellas County",
        specialization="DSCR & investor loans, non-QM",
    )

    today = date.today()

    # ---- Danielle Carter: loan officer story ---------------------------
    danielle_profile.address = "4128 Bayshore Vista Dr"
    danielle_profile.city = "Tampa"
    danielle_profile.state = "FL"
    danielle_profile.zip = "33611"
    danielle_profile.phone = "813-555-0148"
    danielle_profile.employment_status = "Employed"
    danielle_profile.employer_name = "Tampa General Hospital"
    danielle_profile.job_title = "Registered Nurse"
    danielle_profile.annual_income = 78000
    danielle_profile.credit_score = 740
    danielle_profile.assigned_officer_id = chris_lo.id

    danielle_loan = LoanApplication(
        company_id=company.id,
        borrower_profile_id=danielle_profile.id,
        loan_officer_id=chris_lo.id,
        lender_name="Palmetto Federal",
        amount=460750,
        property_value=485000,
        property_address="4128 Bayshore Vista Dr, Tampa, FL 33611",
        loan_type="Conventional",
        term_months=360,
        rate=6.25,
        ltv=95.0,
        status="Pending",
        milestone_stage="Pre-Approval",
        front_end_dti=27.5,
        back_end_dti=38.0,
        monthly_debt_total=1150,
        monthly_housing_payment=2838,
        description="First-time buyer, conventional purchase. Preapproved; following up on inspection scheduling before moving to processing.",
    )
    db.session.add(danielle_loan)
    db.session.flush()

    db.session.add(CreditProfile(borrower_profile_id=danielle_profile.id, loan_app_id=danielle_loan.id, credit_score=740, score=740))

    for lender, rate, selected in (("Harbor Trust", 6.375, False), ("Palmetto Federal", 6.25, True), ("Coastline Mortgage", 6.5, False)):
        db.session.add(LoanQuote(
            borrower_profile_id=danielle_profile.id,
            loan_application_id=danielle_loan.id,
            lender_name=lender,
            rate=rate,
            term_months=360,
            loan_amount=460750,
            loan_type="Conventional",
            property_address="4128 Bayshore Vista Dr, Tampa, FL",
            purchase_price=485000,
            fico_score=740,
            loan_category="Conventional Purchase",
            status="selected" if selected else "quoted",
            selected=selected,
            assigned_officer_id=chris_lo.id,
        ))

    db.session.add(LoanStatusEvent(
        loan_id=danielle_loan.id, event_name="Application Received",
        description="Initial application and documentation received.",
        status="completed", timestamp=datetime.utcnow() - timedelta(days=3),
    ))
    db.session.add(LoanStatusEvent(
        loan_id=danielle_loan.id, event_name="Preapproval Letter Sent",
        description="Preapproval letter issued for $485,000 conventional purchase.",
        status="completed", timestamp=datetime.utcnow() - timedelta(days=1),
    ))
    db.session.add(Task(
        borrower_id=danielle_profile.id,
        loan_id=danielle_loan.id,
        title="Call Danielle re: inspection date",
        description="Confirm home inspection scheduling before moving the file to processing.",
        assigned_to=chris_user.id,
        due_date=today + timedelta(days=1),
        priority="Normal",
        status="Pending",
    ))

    # ---- Marcus Reyes: processor story ----------------------------------
    marcus_profile = BorrowerProfile(
        full_name="Marcus Reyes", email="marcus.reyes@example.com", phone="407-555-0192",
        address="210 Willow Bend Ct", city="Orlando", state="FL", zip="32828",
        employment_status="Employed", employer_name="Orange County Public Schools",
        job_title="Facilities Manager", annual_income=64000,
        credit_score=682, company_id=company.id, assigned_officer_id=priya_shah_lo.id,
    )
    db.session.add(marcus_profile)
    db.session.flush()

    marcus_loan = LoanApplication(
        company_id=company.id,
        borrower_profile_id=marcus_profile.id,
        loan_officer_id=priya_shah_lo.id,
        processor_id=jamie_proc.id,
        lender_name="Meridian Capital Lending",
        amount=310000,
        property_value=326000,
        property_address="210 Willow Bend Ct, Orlando, FL 32828",
        loan_type="FHA",
        term_months=360,
        rate=6.75,
        ltv=95.1,
        status="In Review",
        milestone_stage="Processing",
        front_end_dti=31.0,
        back_end_dti=44.0,
        monthly_debt_total=980,
        description="Rate-and-term refinance, FHA. Two conditions cleared; awaiting an updated bank statement and homeowners insurance proof before moving to underwriting.",
    )
    db.session.add(marcus_loan)
    db.session.flush()

    db.session.add(CreditProfile(borrower_profile_id=marcus_profile.id, loan_app_id=marcus_loan.id, credit_score=682, score=682))

    for document_name, condition_type, status in (
        ("Signed loan application", "Application", "cleared"),
        ("Two years of W-2s", "Income", "cleared"),
        ("Updated bank statement (last 30 days)", "Assets", "pending"),
        ("Proof of homeowners insurance", "Insurance", "pending"),
    ):
        db.session.add(ConditionRequest(
            loan_id=marcus_loan.id,
            borrower_profile_id=marcus_profile.id,
            document_name=document_name,
            condition_type=condition_type,
            status=status,
            requested_by=jamie_user.id,
            assigned_to=jamie_user.id if status == "pending" else None,
        ))

    # ---- Ade & Lisa Okafor: underwriting story --------------------------
    okafor_profile = BorrowerProfile(
        full_name="Ade & Lisa Okafor", email="ade.okafor@example.com", phone="941-555-0173",
        address="88 Harborview Ln", city="Sarasota", state="FL", zip="34236",
        employment_status="Employed", employer_name="Raymond James Financial",
        job_title="Software Engineer", annual_income=168000,
        credit_score=760, company_id=company.id, assigned_officer_id=chris_lo.id,
    )
    db.session.add(okafor_profile)
    db.session.flush()

    okafor_loan = LoanApplication(
        company_id=company.id,
        borrower_profile_id=okafor_profile.id,
        loan_officer_id=chris_lo.id,
        underwriter_id=devon_uw.id,
        lender_name="Meridian Capital Lending",
        amount=489600,
        property_value=612000,
        property_address="88 Harborview Ln, Sarasota, FL 34236",
        loan_type="Conventional",
        term_months=360,
        rate=6.375,
        ltv=80.0,
        status="In Review",
        milestone_stage="Underwriting",
        front_end_dti=24.0,
        back_end_dti=31.0,
        monthly_debt_total=1450,
        description="Conventional purchase, strong credit profile. In underwriting review with one condition cleared and two outstanding.",
    )
    db.session.add(okafor_loan)
    db.session.flush()

    db.session.add(CreditProfile(borrower_profile_id=okafor_profile.id, loan_app_id=okafor_loan.id, credit_score=760, score=760))

    for condition_type, description, severity, status in (
        ("Income", "Most recent pay stub covering the last 30 days.", "Standard", "Cleared"),
        ("Assets", "Explanation letter for large deposit on primary checking account.", "Standard", "Open"),
        ("Insurance", "Updated homeowner's insurance binder reflecting the new purchase price.", "Low", "Open"),
    ):
        db.session.add(UnderwritingCondition(
            borrower_profile_id=okafor_profile.id,
            loan_id=okafor_loan.id,
            condition_type=condition_type,
            description=description,
            severity=severity,
            status=status,
            requested_by=f"{devon_user.first_name} {devon_user.last_name}",
            cleared_by=f"{devon_user.first_name} {devon_user.last_name}" if status == "Cleared" else None,
        ))

    # ---- Priya Nair: DSCR investment purchase, clear to close ----------
    priya_nair_profile = BorrowerProfile(
        full_name="Priya Nair", email="priya.nair@example.com", phone="727-555-0164",
        address="55 Palmetto Row", city="St. Petersburg", state="FL", zip="33701",
        employment_status="Employed", employer_name="Duke Energy",
        job_title="Product Manager", annual_income=145000,
        credit_score=720, company_id=company.id, assigned_officer_id=sam_torres_lo.id,
    )
    db.session.add(priya_nair_profile)
    db.session.flush()

    priya_nair_loan = LoanApplication(
        company_id=company.id,
        borrower_profile_id=priya_nair_profile.id,
        loan_officer_id=sam_torres_lo.id,
        lender_name="Meridian Capital Lending",
        amount=201000,
        property_value=268000,
        property_address="55 Palmetto Row, St. Petersburg, FL 33701",
        loan_type="DSCR",
        term_months=360,
        rate=7.5,
        ltv=75.0,
        status="Clear to Close",
        milestone_stage="Clear to Close",
        description="DSCR investment purchase, 1.24x debt-service coverage ratio. Clear to close, funding scheduled.",
    )
    db.session.add(priya_nair_loan)

    # ---- CRM leads: broker-owner story (arriving, assigned, converted) -
    fb_source = LeadSource.query.filter_by(source_name="Facebook Lead Ads").first()
    if not fb_source:
        fb_source = LeadSource(source_name="Facebook Lead Ads", source_type="Facebook", active=True)
        db.session.add(fb_source)
    ig_source = LeadSource.query.filter_by(source_name="Instagram Ads").first()
    if not ig_source:
        ig_source = LeadSource(source_name="Instagram Ads", source_type="Instagram", active=True)
        db.session.add(ig_source)
    web_source = LeadSource.query.filter_by(source_name="Website").first()
    if not web_source:
        web_source = LeadSource(source_name="Website", source_type="Website", active=True)
        db.session.add(web_source)
    db.session.flush()

    db.session.add(Lead(
        name="Ade Okafor", email="ade.okafor@example.com", phone="941-555-0173",
        message="Interested in a $600k+ purchase near Sarasota, preapproval needed soon.",
        source_id=fb_source.id, assigned_officer_id=chris_lo.id, assigned_to=chris_user.id,
        status="Converted", external_lead_id="demo-fb-ade-okafor-001",
    ))
    db.session.add(Lead(
        name="Jordan Blake", email="jordan.blake@example.com",
        message="Saw your ad about first-time buyer programs, want to learn more.",
        source_id=ig_source.id, assigned_officer_id=chris_lo.id, assigned_to=chris_user.id,
        status="New", external_lead_id="demo-ig-jordan-blake-001",
    ))
    db.session.add(Lead(
        name="Monica Fields", email="monica.fields@example.com",
        message="Refinance inquiry submitted via the website contact form.",
        source_id=web_source.id, assigned_officer_id=priya_shah_lo.id, assigned_to=priya_shah_user.id,
        status="Contacted",
    ))
    db.session.add(Lead(
        name="Tariq Whitfield", email="tariq.whitfield@example.com",
        message="Looking at DSCR options for a second rental property.",
        source_id=fb_source.id, assigned_officer_id=sam_torres_lo.id, assigned_to=sam_torres_user.id,
        status="New", external_lead_id="demo-fb-tariq-whitfield-001",
    ))
