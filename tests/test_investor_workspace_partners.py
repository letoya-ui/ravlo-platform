"""Regression tests for the deal workspace's realtor-partner lookup.

deal_workspace() called get_workspace_partners_for_property(selected_prop)
but that function was never defined anywhere -- every call raised NameError,
silently caught, so the workspace's "partners" list was always empty and no
"Send to Realtor" panel could ever appear.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.borrowers import Deal
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.property import SavedProperty
from LoanMVP.models.user_model import User
from LoanMVP.routes.investor_routes import get_workspace_partners_for_property


def _make_investor(db_session, email="investor@example.com"):
    company = Company(name="Workspace Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    profile = InvestorProfile(user_id=user.id, full_name="Ivy Vestor")
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _make_partner(db_session, name, category="Realtor", city="Tampa", state="FL", zip_code="33602", active=True, approved=True):
    partner = Partner(
        name=name,
        company=name,
        category=category,
        type=category,
        city=city,
        state=state,
        zip_code=zip_code,
        active=active,
        approved=approved,
    )
    db_session.add(partner)
    db_session.commit()
    return partner


def _make_saved_property(db_session, investor_profile, zipcode="33602"):
    prop = SavedProperty(investor_profile_id=investor_profile.id, address="123 Main St", zipcode=zipcode)
    db_session.add(prop)
    db_session.commit()
    return prop


def _make_deal(db_session, user, city="Tampa", state="FL", zip_code="33602"):
    deal = Deal(user_id=user.id, title="Test Deal", city=city, state=state, zip_code=zip_code)
    db_session.add(deal)
    db_session.commit()
    return deal


def test_returns_matching_realtor_partners(db_session):
    user, profile = _make_investor(db_session)
    prop = _make_saved_property(db_session, profile)
    deal = _make_deal(db_session, user)
    match = _make_partner(db_session, "Tampa Realty Group")
    _make_partner(db_session, "Out Of State Realtor", city="Austin", state="TX", zip_code="78701")
    _make_partner(db_session, "Tampa Contractor", category="Contractor")

    results = get_workspace_partners_for_property(prop, deal=deal)

    names = {r["name"] for r in results}
    assert "Tampa Realty Group" in names
    assert "Out Of State Realtor" not in names
    assert "Tampa Contractor" not in names


def test_excludes_unapproved_and_inactive_partners(db_session):
    user, profile = _make_investor(db_session, email="investor2@example.com")
    prop = _make_saved_property(db_session, profile)
    deal = _make_deal(db_session, user)
    _make_partner(db_session, "Unapproved Realty", approved=False)
    _make_partner(db_session, "Inactive Realty", active=False)

    results = get_workspace_partners_for_property(prop, deal=deal)

    assert results == []


def test_returns_empty_list_with_no_location_data(db_session):
    user, profile = _make_investor(db_session, email="investor3@example.com")
    prop = SavedProperty(investor_profile_id=profile.id, address="No Zip Ave", zipcode=None)
    db_session.add(prop)
    db_session.commit()

    results = get_workspace_partners_for_property(prop, deal=None, workspace_analysis={})

    assert results == []


def test_falls_back_to_saved_property_zipcode_without_deal(db_session):
    user, profile = _make_investor(db_session, email="investor4@example.com")
    prop = _make_saved_property(db_session, profile, zipcode="33602")
    _make_partner(db_session, "Zip Fallback Realty")

    results = get_workspace_partners_for_property(prop, deal=None, workspace_analysis={})

    assert any(r["name"] == "Zip Fallback Realty" for r in results)
