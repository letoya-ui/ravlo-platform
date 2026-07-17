"""Regression tests for restoring Bonnie's VIP realtor account and public
landing page after they were deleted in production.

Unlike Jamaine and Keyona, Bonnie was never added to
_PARTNER_DASHBOARD_PRESETS in auth.py, so there was no self-healing
recovery path for her Partner row if it (or her whole account) ever got
deleted. Separately, her public landing page (/p/bonnie-sells-oc-homes)
depended entirely on a live VIPProfile row -- unlike John Headley/Keyona,
who have a SLUG_STATIC_CONTEXT fallback -- and vip.py's get-or-create
VIPProfile logic creates a blank profile (marketplace_enabled="no", no
public_slug) if hers is missing, so simply logging back in would NOT have
restored her public page. This adds both the self-healing preset and the
static-context fallback, mirroring the exact pattern already used for
John Headley and Keyona.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import Lead, Partner
from LoanMVP.models.user_model import User
from LoanMVP.routes.auth import _PARTNER_DASHBOARD_PRESETS, _ensure_partner_dashboard_profile


def test_bonnie_has_a_dashboard_preset():
    assert "bonniesellsochomes@gmail.com" in _PARTNER_DASHBOARD_PRESETS
    preset = _PARTNER_DASHBOARD_PRESETS["bonniesellsochomes@gmail.com"]
    assert preset["active"] is True
    assert preset["approved"] is True
    assert preset["subscription_tier"] == "Premium"
    assert preset["category"] == "realtor"
    assert "Hudson Valley" in preset["service_area"]


def test_ensure_partner_dashboard_profile_recreates_missing_bonnie_partner(db_session):
    company = Company(name="Bonnie Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email="bonniesellsochomes@gmail.com", role="partner", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    assert Partner.query.filter_by(user_id=user.id).first() is None

    _ensure_partner_dashboard_profile(user)
    db_session.commit()

    partner = Partner.query.filter_by(user_id=user.id).first()
    assert partner is not None
    assert partner.active is True
    assert partner.approved is True
    assert partner.subscription_tier == "Premium"
    assert (partner.category or "").lower() == "realtor"


def test_landing_page_renders_without_a_live_vip_profile(client):
    """Simulates the actual production failure: her VIPProfile row is gone
    (never created in this test's fresh DB), so the page must render from
    the static-context fallback instead of 404ing."""
    resp = client.get("/p/bonnie-sells-oc-homes")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Bonnie" in body
    assert "Hudson Valley" in body


def test_landing_page_contact_form_creates_lead_for_bonnie(db_session, client):
    company = Company(name="Bonnie Lead Co", is_active=True)
    db_session.add(company)
    db_session.commit()
    bonnie = User(email="Bonniesellsochomes@gmail.com", role="partner", is_active=True, company_id=company.id)
    db_session.add(bonnie)
    db_session.commit()

    resp = client.post(
        "/p/bonnie-sells-oc-homes/contact",
        data={
            "client_name": "Prospective Buyer",
            "client_email": "buyer@example.com",
            "interest": "buyer",
            "message": "Looking for a home in Orange County.",
        },
    )

    assert resp.status_code == 200
    lead = Lead.query.filter_by(email="buyer@example.com").first()
    assert lead is not None
    assert lead.assigned_to == bonnie.id
