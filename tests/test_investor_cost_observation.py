"""Regression test for the Deal Architect build-cost learning signal.

generate_build_costs_from_package() constructed CostObservation(...) without
ever importing it -- every call raised NameError, silently caught by the
surrounding except Exception, so the row was never actually persisted.
"""
from unittest.mock import patch

from LoanMVP.models.admin import Company
from LoanMVP.models.borrowers import Deal
from LoanMVP.models.cost_models import CostObservation
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_investor(db_session, email="investor@example.com"):
    company = Company(name="Investor Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    profile = InvestorProfile(user_id=user.id, full_name="Ivy Vestor")
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_deal(db_session, user, **extra):
    extra.setdefault(
        "results_json",
        {
            "build_project": {
                "property_type": "single_family",
                "square_feet_target": 1800,
                "project_name": "Test Build",
            }
        },
    )
    deal = Deal(
        user_id=user.id,
        title="Test Deal",
        city="Tampa",
        state="FL",
        zip_code="33602",
        purchase_price=250000,
        arv=400000,
        strategy="build",
        **extra,
    )
    db_session.add(deal)
    db_session.commit()
    return deal


def test_generate_build_costs_records_cost_observation(db_session, client):
    user, profile = _make_investor(db_session)
    deal = _make_deal(db_session, user)
    login_as(client, user)

    with patch(
        "LoanMVP.routes.investor_routes._post_scope_engine_json",
        side_effect=Exception("scope engine unavailable in tests"),
    ):
        resp = client.post(
            "/investor/deal-studio/deal-architect/generate-build-costs",
            json={"deal_id": deal.id, "square_feet": 1800},
        )

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"

    observation = CostObservation.query.filter_by(deal_id=deal.id).first()
    assert observation is not None
    assert observation.source == "engine_estimate"
    assert observation.user_id == user.id
    assert observation.zip_code == "33602"
