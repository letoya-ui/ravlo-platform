"""Regression tests for the "Send Portal Invite" action on
property.unit_detail() -- the property manager's half of onboarding a
renter into the portal. Mirrors the ownership-scoping discipline
established in test_listing_ownership_scoping.py: an investor must never
be able to invite (or otherwise touch) a tenant belonging to another
investor's unit by guessing its id.
"""
import re
from decimal import Decimal

from LoanMVP.extensions import db
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.property import Property, PropertyUnit, Tenant
from LoanMVP.models.user_model import User
from LoanMVP.services.renter_invite_service import decode_invite_token

from tests.conftest import login_as


def _make_investor(db_session, email="landlord@example.com", full_name="Larry Landlord"):
    user = User(email=email, role="investor", is_active=True)
    db_session.add(user)
    db_session.commit()
    profile = InvestorProfile(user_id=user.id, full_name=full_name, email=email)
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_unit_with_tenant(db_session, investor_profile, tenant_name="Rita Renter", tenant_email="rita@example.com"):
    prop = Property(address="1 Main St", owner_investor_id=investor_profile.id)
    db_session.add(prop)
    db_session.commit()
    unit = PropertyUnit(property_id=prop.id, unit_label="Unit A", market_rent=Decimal("1500"))
    db_session.add(unit)
    db_session.commit()
    tenant = Tenant(
        unit_id=unit.id, full_name=tenant_name, email=tenant_email,
        monthly_rent=Decimal("1500"), is_active=True,
    )
    db_session.add(tenant)
    db_session.commit()
    return prop, unit, tenant


def test_invite_tenant_flashes_a_working_invite_link(db_session, client):
    user, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)
    login_as(client, user)

    resp = client.post(
        f"/property/unit/{unit.id}",
        data={"action_type": "invite_tenant", "tenant_id": str(tenant.id)},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "/renter/invite/" in body

    # Extract the token from the flashed link and confirm it actually
    # decodes back to this tenant.
    match = re.search(r"/renter/invite/([\w.\-]+)", body)
    assert match is not None
    assert decode_invite_token(match.group(1)) == tenant.id


def test_invite_tenant_rejects_another_investors_tenant(db_session, client):
    user, profile = _make_investor(db_session, email="me@example.com")
    other_user, other_profile = _make_investor(db_session, email="other@example.com", full_name="Other Landlord")
    _, other_unit, other_tenant = _make_unit_with_tenant(
        db_session, other_profile, tenant_name="Not Mine", tenant_email="notmine@example.com"
    )
    login_as(client, user)

    # The unit itself 404s for a non-owner before the action_type is ever
    # dispatched -- _get_owned_unit_or_404() gates the whole route.
    resp = client.post(
        f"/property/unit/{other_unit.id}",
        data={"action_type": "invite_tenant", "tenant_id": str(other_tenant.id)},
    )

    assert resp.status_code == 404
    db_session.refresh(other_tenant)
    assert other_tenant.user_id is None


def test_invite_tenant_already_active_shows_info_message(db_session, client):
    user, profile = _make_investor(db_session)
    _, unit, tenant = _make_unit_with_tenant(db_session, profile)

    renter_user = User(email="already@example.com", role="renter", is_active=True)
    db_session.add(renter_user)
    db_session.commit()
    tenant.user_id = renter_user.id
    db_session.commit()

    login_as(client, user)
    resp = client.post(
        f"/property/unit/{unit.id}",
        data={"action_type": "invite_tenant", "tenant_id": str(tenant.id)},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "already has a portal login" in resp.get_data(as_text=True)
