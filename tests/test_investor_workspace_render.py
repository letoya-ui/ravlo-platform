from LoanMVP.models.admin import Company
from LoanMVP.models.crm_models import Partner
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.models.property import SavedProperty
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def test_deal_workspace_renders_partner_panel(db_session, client):
    company = Company(name="Render Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email="render-investor@example.com", role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()

    profile = InvestorProfile(user_id=user.id, full_name="Ivy Vestor")
    db_session.add(profile)
    db_session.commit()

    prop = SavedProperty(investor_profile_id=profile.id, address="123 Main St", zipcode="33602")
    db_session.add(prop)
    db_session.commit()

    partner = Partner(
        name="Tampa Realty Group", company="Tampa Realty Group", category="Realtor", type="Realtor",
        city="Tampa", state="FL", zip_code="33602", active=True, approved=True,
    )
    db_session.add(partner)
    db_session.commit()

    login_as(client, user)

    resp = client.get(f"/investor/deals/workspace?prop_id={prop.id}")

    assert resp.status_code == 200
    assert b"Tampa Realty Group" in resp.data
    assert b"Send to Realtor" in resp.data
