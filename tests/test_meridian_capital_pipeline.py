"""The white_label demo variant used to reuse one generic borrower across
five identical-looking loans -- unconvincing next to the /lending-os
marketing page's Meridian Capital story (Danielle Carter, Marcus Reyes,
the Okafors, Priya Nair). ensure_demo_environment("white_label") now seeds
that same named pipeline so the public page and the real product tell the
same story.

Covers: _seed_meridian_capital_pipeline() creating each borrower's loan at
the right milestone with the right supporting records (quotes, conditions,
tasks, credit profile), the supporting loan officers (Priya Shah, Sam
Torres) existing as real team pipeline without being demo-login personas,
the CRM leads giving the admin/broker-owner a team-wide view, and the
whole thing staying idempotent across repeated calls.
"""
from LoanMVP.models.crm_models import Lead
from LoanMVP.models.loan_models import BorrowerProfile, LoanApplication, LoanQuote
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.underwriter_model import ConditionRequest, UnderwritingCondition
from LoanMVP.models.user_model import User
from LoanMVP.services.demo_environment_service import ensure_demo_environment


def _seed(db_session):
    roles = ensure_demo_environment("white_label")
    company_id = roles["admin"].company_id
    return roles, company_id


def test_danielle_carter_is_the_loan_officer_story(db_session):
    roles, company_id = _seed(db_session)

    danielle = BorrowerProfile.query.filter_by(full_name="Danielle Carter", company_id=company_id).first()
    assert danielle is not None
    assert danielle.user_id == roles["borrower"].id
    assert danielle.address == "4128 Bayshore Vista Dr"
    assert danielle.credit_score == 740

    loan = LoanApplication.query.filter_by(borrower_profile_id=danielle.id).first()
    assert loan.milestone_stage == "Pre-Approval"
    assert loan.amount == 460750
    assert loan.property_value == 485000
    assert loan.back_end_dti == 38.0

    quotes = LoanQuote.query.filter_by(loan_application_id=loan.id).all()
    assert len(quotes) == 3
    selected = [q for q in quotes if q.selected]
    assert len(selected) == 1
    assert selected[0].lender_name == "Palmetto Federal"


def test_marcus_reyes_is_the_processor_story(db_session):
    roles, company_id = _seed(db_session)

    marcus = BorrowerProfile.query.filter_by(full_name="Marcus Reyes", company_id=company_id).first()
    assert marcus is not None
    assert marcus.user_id is None  # pipeline-only, not a demo-login persona

    loan = LoanApplication.query.filter_by(borrower_profile_id=marcus.id).first()
    assert loan.milestone_stage == "Processing"

    conditions = ConditionRequest.query.filter_by(loan_id=loan.id).all()
    assert len(conditions) == 4
    pending = [c for c in conditions if c.status == "pending"]
    cleared = [c for c in conditions if c.status == "cleared"]
    assert len(pending) == 2
    assert len(cleared) == 2


def test_okafors_are_the_underwriting_story(db_session):
    roles, company_id = _seed(db_session)

    okafor = BorrowerProfile.query.filter_by(full_name="Ade & Lisa Okafor", company_id=company_id).first()
    assert okafor is not None

    loan = LoanApplication.query.filter_by(borrower_profile_id=okafor.id).first()
    assert loan.milestone_stage == "Underwriting"

    conditions = UnderwritingCondition.query.filter_by(loan_id=loan.id).all()
    assert len(conditions) == 3
    open_conditions = [c for c in conditions if c.status == "Open"]
    assert len(open_conditions) == 2


def test_priya_nair_is_a_dscr_clear_to_close_loan(db_session):
    roles, company_id = _seed(db_session)

    priya = BorrowerProfile.query.filter_by(full_name="Priya Nair", company_id=company_id).first()
    assert priya is not None

    loan = LoanApplication.query.filter_by(borrower_profile_id=priya.id).first()
    assert loan.loan_type == "DSCR"
    assert loan.status == "Clear to Close"


def test_supporting_officers_exist_but_are_not_demo_login_personas(db_session):
    roles, company_id = _seed(db_session)

    assert set(roles.keys()) == {
        "admin", "investor", "loan_officer", "processor",
        "underwriter", "borrower", "partner",
    }

    priya_shah = User.query.filter_by(email=f"priya.shah@demo.meridiancapital.com").first()
    sam_torres = User.query.filter_by(email=f"sam.torres@demo.meridiancapital.com").first()
    assert priya_shah is not None
    assert sam_torres is not None
    assert LoanOfficerProfile.query.filter_by(user_id=priya_shah.id).first() is not None
    assert LoanOfficerProfile.query.filter_by(user_id=sam_torres.id).first() is not None


def test_crm_leads_give_the_broker_owner_a_team_wide_view(db_session):
    roles, company_id = _seed(db_session)

    leads = Lead.query.filter(Lead.external_lead_id.like("demo-%")).all()
    assert len(leads) >= 3
    statuses = {lead.status for lead in leads}
    assert "Converted" in statuses
    assert "New" in statuses


def test_seeding_is_idempotent_across_repeated_calls(db_session):
    _seed(db_session)
    before = LoanApplication.query.count()
    lead_count_before = Lead.query.count()

    ensure_demo_environment("white_label")

    assert LoanApplication.query.count() == before
    assert Lead.query.count() == lead_count_before
