"""White Label branding only ever reached the sidebar logo/mark -- the
--accent/--accent-2/--accent-deep CSS variables that actually drive
button colors, chart fills, and highlights across the whole portal
(ravlo_employee.css, ravlo_tokens.css) stayed hardcoded to Ravlo's own
colors regardless of the logged-in company's brand palette. A paying
white-label customer got a swapped logo and Ravlo-blue everywhere else.

ravlo_employee_base.html and ravlo_borrower_base.html now inject a
:root override for these variables whenever effective_brand() returns
something other than Ravlo's own branding.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_staff(db_session, email, role="executive"):
    # demo_login() is gated to a fixed allowlist of real staff emails
    # (admin.py's _DEMO_LOGIN_ALLOWED_EMAILS) -- any other email 302s back
    # to the demo center instead of actually starting a demo session.
    company = Company.query.filter_by(name="Theme Staff Co").first()
    if not company:
        company = Company(name="Theme Staff Co", is_active=True)
        db_session.add(company)
        db_session.commit()
    user = User(email=email, role=role, company_id=company.id, is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def test_white_label_loan_officer_dashboard_overrides_global_accent_colors(db_session, client):
    staff = _make_staff(db_session, "letoya@ravlohq.com")
    login_as(client, staff)

    login_resp = client.post(
        "/admin/demo-login/loan_officer",
        data={"variant": "white_label"},
        follow_redirects=False,
    )
    body = client.get(login_resp.headers["Location"]).get_data(as_text=True)

    assert "--accent: #0F2D52;" in body
    assert "--accent-2: #0E7C66;" in body
    assert "--accent-deep: #C9A227;" in body


def test_ravlo_variant_loan_officer_dashboard_has_no_accent_override(db_session, client):
    staff = _make_staff(db_session, "sandra@ravlohq.com")
    login_as(client, staff)

    login_resp = client.post(
        "/admin/demo-login/loan_officer",
        data={"variant": "ravlo"},
        follow_redirects=False,
    )
    body = client.get(login_resp.headers["Location"]).get_data(as_text=True)

    assert "--accent:" not in body


def test_white_label_borrower_dashboard_overrides_global_accent_colors(db_session, client):
    staff = _make_staff(db_session, "aishagelahun@gmail.com")
    login_as(client, staff)

    login_resp = client.post(
        "/admin/demo-login/borrower",
        data={"variant": "white_label"},
        follow_redirects=False,
    )
    body = client.get(login_resp.headers["Location"], follow_redirects=True).get_data(as_text=True)

    assert "--accent: #0F2D52;" in body
    assert "--accent-2: #0E7C66;" in body


def test_white_label_company_without_secondary_color_falls_back_to_accent(db_session, client):
    company = Company(
        name="No Secondary Lending",
        is_active=True,
        subscription_tier="white_label",
        brand_name="No Secondary Lending Co",
        brand_primary_color="#111111",
        brand_accent_color="#222222",
    )
    db_session.add(company)
    db_session.commit()

    from LoanMVP.utils.branding import effective_brand
    brand = effective_brand(company)
    assert brand.secondary == "#222222"
