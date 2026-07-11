"""Regression tests for the "Send Plans" feature: an investor emails a
development-report PDF (property summary, purchase price/budget, and the
Design/Build Studio plans) to a loan officer, another investor, or anyone
else, by email address -- no in-app recipient directory required.
"""
from unittest.mock import patch

from LoanMVP.models.admin import Company
from LoanMVP.models.borrowers import Deal, DealPlanShare
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.user_model import User
from LoanMVP.services.investor.deal_plans_pdf import build_deal_plans_pdf

from tests.conftest import login_as


def _make_investor(db_session, email="investor@example.com"):
    company = Company(name="Plans Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    profile = InvestorProfile(user_id=user.id, full_name="Ivy Vestor")
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_deal(db_session, user, with_build_project=True):
    results_json = {}
    if with_build_project:
        results_json["build_project"] = {
            "blueprint": {"image_url": "https://example.com/blueprint.png"},
            "interior": {
                "rooms": [
                    {
                        "room_type": "kitchen",
                        "floor": "main",
                        "style": "modern_farmhouse",
                        "images": ["https://example.com/kitchen-1.png"],
                    }
                ]
            },
        }
    deal = Deal(
        user_id=user.id,
        title="123 Main St Flip",
        address="123 Main St",
        purchase_price=200000,
        rehab_cost=50000,
        arv=320000,
        results_json=results_json,
    )
    db_session.add(deal)
    db_session.commit()
    return deal


def test_build_deal_plans_pdf_with_build_project(db_session):
    user, _ = _make_investor(db_session)
    deal = _make_deal(db_session, user)

    with patch(
        "LoanMVP.services.investor.deal_plans_pdf.download_image_bytes",
        return_value=None,
    ):
        buffer = build_deal_plans_pdf(deal)

    assert buffer.getvalue().startswith(b"%PDF")


def test_build_deal_plans_pdf_without_build_project(db_session):
    user, _ = _make_investor(db_session, email="investor2@example.com")
    deal = _make_deal(db_session, user, with_build_project=False)

    buffer = build_deal_plans_pdf(deal)

    assert buffer.getvalue().startswith(b"%PDF")


def test_build_deal_plans_pdf_survives_one_bad_image_url(db_session):
    user, _ = _make_investor(db_session, email="investor3@example.com")
    deal = _make_deal(db_session, user)

    def flaky_download(url):
        if "blueprint" in url:
            raise Exception("boom")
        return None

    with patch(
        "LoanMVP.services.investor.deal_plans_pdf.download_image_bytes",
        side_effect=flaky_download,
    ):
        buffer = build_deal_plans_pdf(deal)

    assert buffer.getvalue().startswith(b"%PDF")


def test_send_deal_plans_creates_share_and_sends_email(db_session, client):
    user, _ = _make_investor(db_session, email="investor4@example.com")
    deal = _make_deal(db_session, user)
    login_as(client, user)

    with patch(
        "LoanMVP.routes.investor_routes.download_image_bytes",
        return_value=None,
    ), patch(
        "LoanMVP.routes.investor_routes.send_pdf_bytes_attachment"
    ) as mock_send:
        resp = client.post(
            f"/investor/deals/{deal.id}/send-plans",
            data={
                "recipient_name": "Jamie Rivera",
                "recipient_email": "jamie@example.com",
                "note": "Take a look when you can.",
            },
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["recipient_email"] == "jamie@example.com"

    shares = DealPlanShare.query.filter_by(deal_id=deal.id).all()
    assert len(shares) == 1
    assert shares[0].recipient_email == "jamie@example.com"
    assert shares[0].sent_by_user_id == user.id

    assert mock_send.call_count == 1
    assert mock_send.call_args[0][0] == "jamie@example.com"


def test_send_deal_plans_rejects_missing_email(db_session, client):
    user, _ = _make_investor(db_session, email="investor5@example.com")
    deal = _make_deal(db_session, user)
    login_as(client, user)

    with patch("LoanMVP.routes.investor_routes.send_pdf_bytes_attachment") as mock_send:
        resp = client.post(
            f"/investor/deals/{deal.id}/send-plans",
            data={"recipient_name": "Jamie Rivera", "recipient_email": ""},
        )

    assert resp.status_code == 400
    assert DealPlanShare.query.filter_by(deal_id=deal.id).count() == 0
    mock_send.assert_not_called()


def test_send_deal_plans_blocks_other_investors_deal(db_session, client):
    owner, _ = _make_investor(db_session, email="owner@example.com")
    other, _ = _make_investor(db_session, email="other@example.com")
    deal = _make_deal(db_session, owner)
    login_as(client, other)

    resp = client.post(
        f"/investor/deals/{deal.id}/send-plans",
        data={"recipient_name": "Jamie Rivera", "recipient_email": "jamie@example.com"},
    )

    assert resp.status_code == 404
    assert DealPlanShare.query.filter_by(deal_id=deal.id).count() == 0
