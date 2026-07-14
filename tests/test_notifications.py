"""Regression tests for the notifications system fix + "Ravlo AI can
send notifications" feature.

Before this fix, the notification system was broken in multiple layers:
- LoanNotification required loan_id (NOT NULL) and had no user_id column,
  even though notify_service.notify() already tried to create rows keyed
  by user_id and investor_id (neither a real column) -- crashing
  (TypeError) every time it ran, including live from
  admin.approve_access_request().
- services/notification_service.py's notify_team_on_conversion()
  referenced an undefined `Notification` class (NameError), silently
  swallowed by a bare except at its one real call site in
  investor_routes.py's quote-to-loan conversion flow.
- notifications/dashboard.html extended a template file
  ("layouts/base.html") that doesn't exist -- GET /notifications/ would
  501 with TemplateNotFound.
- The notification bell/center was fully built (routes work) but never
  linked from any actual page.

Also covers the new capability: each of the four existing per-role AI
summary routes now pushes a real notification via
notification_service.send_ai_notification() when it generates a fresh
summary, instead of only ever rendering on a dashboard card.
"""
from types import SimpleNamespace
from unittest.mock import patch

from LoanMVP.extensions import db
from LoanMVP.models.admin import Company
from LoanMVP.models.loan_models import BorrowerProfile, LoanNotification
from LoanMVP.models.user_model import User
from LoanMVP.services.notification_service import (
    create_notification,
    notify_team_on_conversion,
    send_ai_notification,
)
from LoanMVP.services.notify_service import notify

from tests.conftest import login_as


def _make_user(db_session, email, role):
    company = Company(name=f"NotifCo {email}", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role=role, is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def _make_user_in_company(db_session, email, role, company):
    user = User(email=email, role=role, is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def _make_company(db_session, name):
    company = Company(name=name, is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()
    return company


def _ai_outcome(summary_text="A helpful AI summary."):
    return {"result": {"summary": summary_text}, "context": {}, "provider": "template"}


# ---------------------------------------------------------------------------
# Model fix: user_id + nullable loan_id no longer crash
# ---------------------------------------------------------------------------

def test_create_notification_persists_without_loan(db_session):
    user = _make_user(db_session, "solo@example.com", "investor")

    notif = create_notification(user, title="Hi", message="Body text", action_url="/somewhere")

    assert notif.id is not None
    assert notif.user_id == user.id
    assert notif.loan_id is None


def test_send_ai_notification_uses_ai_channel(db_session):
    user = _make_user(db_session, "ai-user@example.com", "loan_officer")

    notif = send_ai_notification(user, title="AI title", message="AI body")

    assert notif.channel == "ai"
    assert notif.user_id == user.id


# ---------------------------------------------------------------------------
# notify_service.notify() no longer crashes (root cause of the bug that
# broke admin.approve_access_request())
# ---------------------------------------------------------------------------

def test_notify_role_broadcast_creates_inapp_rows_for_each_staff_user(db_session):
    admin_a = _make_user(db_session, "admin-a@example.com", "admin")
    admin_b = _make_user(db_session, "admin-b@example.com", "admin")

    notify(role="admin", title="Role Test", message="hello admins", channels=["inapp"])

    rows = LoanNotification.query.filter_by(title="Role Test").all()
    assert {r.user_id for r in rows} == {admin_a.id, admin_b.id}


def test_notify_investor_direct_recipient_creates_row(db_session):
    from LoanMVP.models.investor_models import InvestorProfile

    user = _make_user(db_session, "investor-notify@example.com", "investor")
    investor = InvestorProfile(user_id=user.id, full_name="Ivy Vestor")
    db_session.add(investor)
    db_session.commit()

    notify(investor=investor, title="Investor Ping", message="hi", channels=["inapp"])

    row = LoanNotification.query.filter_by(title="Investor Ping").first()
    assert row is not None
    assert row.user_id == user.id
    assert row.investor_profile_id == investor.id


# ---------------------------------------------------------------------------
# notify_team_on_conversion no longer NameErrors
# ---------------------------------------------------------------------------

def test_notify_team_on_conversion_creates_notifications_for_officer_and_underwriter(db_session):
    officer = _make_user(db_session, "officer@example.com", "loan_officer")
    underwriter = _make_user(db_session, "uw@example.com", "underwriter")
    borrower_user = _make_user(db_session, "borrower-conv@example.com", "borrower")

    borrower = SimpleNamespace(full_name="Bo Rower", user_id=borrower_user.id)
    quote = SimpleNamespace(
        id=1, assigned_officer_id=officer.id, assigned_underwriter_id=underwriter.id,
        property_address="123 Main St",
    )
    loan_app = SimpleNamespace(id=999)

    notify_team_on_conversion(borrower, quote, loan_app)

    assert LoanNotification.query.filter_by(user_id=officer.id, title="New Borrower Conversion").count() == 1
    assert LoanNotification.query.filter_by(user_id=underwriter.id, title="New Loan Application Ready for Review").count() == 1


# ---------------------------------------------------------------------------
# notifications/ dashboard renders (was TemplateNotFound) and scopes
# correctly (own notifications + role-wide broadcasts, never another
# user's personal notification)
# ---------------------------------------------------------------------------

def test_notifications_dashboard_renders_and_scopes_to_current_user(db_session, client):
    me = _make_user(db_session, "me@example.com", "loan_officer")
    other = _make_user(db_session, "other@example.com", "loan_officer")

    create_notification(me, title="MineOne", message="m1")
    create_notification(other, title="TheirsOnly", message="t")
    db.session.add(LoanNotification(role="loan_officer", user_id=None, title="Broadcast", message="b", channel="inapp"))
    db.session.commit()

    login_as(client, me)
    resp = client.get("/notifications/")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "MineOne" in body
    assert "Broadcast" in body
    assert "TheirsOnly" not in body


def test_notifications_dashboard_renders_for_borrower_and_investor_roles(db_session, client):
    from LoanMVP.models.investor_models import InvestorProfile

    borrower_user = _make_user(db_session, "borrower-dash@example.com", "borrower")
    db_session.add(BorrowerProfile(user_id=borrower_user.id, full_name="Bo Rower"))
    db_session.commit()
    login_as(client, borrower_user)
    resp = client.get("/notifications/")
    assert resp.status_code == 200

    investor_user = _make_user(db_session, "investor-dash@example.com", "investor")
    db_session.add(InvestorProfile(user_id=investor_user.id, full_name="Ivy Vestor"))
    db_session.commit()
    login_as(client, investor_user)
    resp2 = client.get("/notifications/")
    assert resp2.status_code == 200


def test_mark_read_only_affects_own_notification(db_session, client, app):
    me = _make_user(db_session, "mark-me@example.com", "processor")
    other = _make_user(db_session, "mark-other@example.com", "processor")
    mine = create_notification(me, title="Mine", message="m")
    theirs = create_notification(other, title="Theirs", message="t")

    login_as(client, me)
    app.config["WTF_CSRF_ENABLED"] = False

    resp_ok = client.post(f"/notifications/mark_read/{mine.id}")
    assert resp_ok.get_json()["success"] is True
    assert LoanNotification.query.get(mine.id).is_read is True

    resp_forbidden = client.post(f"/notifications/mark_read/{theirs.id}")
    assert resp_forbidden.status_code == 403
    assert LoanNotification.query.get(theirs.id).is_read is False


def test_mark_all_read_does_not_touch_other_users_notifications(db_session, client, app):
    me = _make_user(db_session, "markall-me@example.com", "underwriter")
    other = _make_user(db_session, "markall-other@example.com", "underwriter")
    create_notification(me, title="MineA", message="a")
    create_notification(me, title="MineB", message="b")
    theirs = create_notification(other, title="Theirs", message="t")

    login_as(client, me)
    app.config["WTF_CSRF_ENABLED"] = False
    resp = client.post("/notifications/mark_all_read")

    assert resp.get_json()["success"] is True
    assert all(n.is_read for n in LoanNotification.query.filter_by(user_id=me.id).all())
    assert LoanNotification.query.get(theirs.id).is_read is False


# ---------------------------------------------------------------------------
# Notification bell is actually reachable from real pages now
# ---------------------------------------------------------------------------

def test_notification_bell_appears_on_account_profile_page(db_session, client):
    user = _make_user(db_session, "bell-user@example.com", "loan_officer")
    create_notification(user, title="Bell Test", message="ring ring")

    login_as(client, user)
    resp = client.get("/account/profile")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "notifications.dashboard" in body or "/notifications" in body


# ---------------------------------------------------------------------------
# Ravlo AI sends notifications when a fresh summary is generated
# ---------------------------------------------------------------------------

def test_investor_portfolio_ai_summary_sends_notification(db_session, client):
    from LoanMVP.models.investor_models import InvestorProfile

    user = _make_user(db_session, "investor-ai@example.com", "investor")
    db_session.add(InvestorProfile(user_id=user.id, full_name="Ivy Vestor"))
    db_session.commit()
    login_as(client, user)

    with patch(
        "LoanMVP.services.investor_portfolio_ai_service.explain_investor_portfolio",
        return_value=_ai_outcome(),
    ):
        resp = client.post("/investor/portfolio/ai-summary", json={})

    assert resp.status_code == 200
    notif = LoanNotification.query.filter_by(user_id=user.id, channel="ai").first()
    assert notif is not None
    assert "portfolio" in notif.title.lower()


def test_loan_officer_pipeline_ai_summary_sends_notification(db_session, client):
    user = _make_user(db_session, "lo-ai@example.com", "loan_officer")
    login_as(client, user)

    with patch(
        "LoanMVP.services.loan_officer_pipeline_ai_service.explain_loan_officer_pipeline",
        return_value=_ai_outcome(),
    ):
        resp = client.post("/loan_officer/pipeline/ai-summary", json={})

    assert resp.status_code == 200
    notif = LoanNotification.query.filter_by(user_id=user.id, channel="ai").first()
    assert notif is not None
    assert "pipeline" in notif.title.lower()


def test_processor_queue_ai_summary_sends_notification(db_session, client):
    user = _make_user(db_session, "proc-ai@example.com", "processor")
    login_as(client, user)

    with patch(
        "LoanMVP.services.processor_queue_ai_service.explain_processor_queue",
        return_value=_ai_outcome(),
    ):
        resp = client.post("/processor/queue/ai-summary", json={})

    assert resp.status_code == 200
    notif = LoanNotification.query.filter_by(user_id=user.id, channel="ai").first()
    assert notif is not None
    assert "queue" in notif.title.lower()


def test_borrower_ai_assistant_sends_notification(db_session, client):
    user = _make_user(db_session, "borrower-ai@example.com", "borrower")
    db_session.add(BorrowerProfile(user_id=user.id, full_name="Bo Rower"))
    db_session.commit()
    login_as(client, user)

    with patch(
        "LoanMVP.services.borrower_ai_service.explain_borrower_status",
        return_value=_ai_outcome(),
    ):
        resp = client.post("/borrower/ai/assistant", json={})

    assert resp.status_code == 200
    notif = LoanNotification.query.filter_by(user_id=user.id, channel="ai").first()
    assert notif is not None


# ---------------------------------------------------------------------------
# Admin/Ravlo-AI can manually send a notification (new admin.send_notification
# route), scoped so a company admin can only ever reach their own company.
# ---------------------------------------------------------------------------

def test_company_admin_can_send_notification_to_specific_user(db_session, client, app):
    company = _make_company(db_session, "Scoped Co A")
    admin = _make_user_in_company(db_session, "admin-a@example.com", "admin", company)
    teammate = _make_user_in_company(db_session, "teammate-a@example.com", "loan_officer", company)

    login_as(client, admin)
    app.config["WTF_CSRF_ENABLED"] = False
    resp = client.post(
        "/admin/notifications/send",
        data={
            "target_type": "user",
            "recipient_id": str(teammate.id),
            "title": "Heads up",
            "message": "New process starting Monday.",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 302
    notif = LoanNotification.query.filter_by(user_id=teammate.id, channel="admin").first()
    assert notif is not None
    assert notif.title == "Heads up"


def test_company_admin_cannot_send_notification_to_user_in_another_company(db_session, client, app):
    company_a = _make_company(db_session, "Scoped Co B")
    company_b = _make_company(db_session, "Scoped Co C")
    admin = _make_user_in_company(db_session, "admin-b@example.com", "admin", company_a)
    outsider = _make_user_in_company(db_session, "outsider-b@example.com", "loan_officer", company_b)

    login_as(client, admin)
    app.config["WTF_CSRF_ENABLED"] = False
    resp = client.post(
        "/admin/notifications/send",
        data={
            "target_type": "user",
            "recipient_id": str(outsider.id),
            "title": "Leak attempt",
            "message": "Should not be delivered.",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert LoanNotification.query.filter_by(user_id=outsider.id, title="Leak attempt").first() is None


def test_company_admin_send_to_role_only_notifies_own_company(db_session, client, app):
    company_a = _make_company(db_session, "Scoped Co D")
    company_b = _make_company(db_session, "Scoped Co E")
    admin = _make_user_in_company(db_session, "admin-d@example.com", "admin", company_a)
    own_officer = _make_user_in_company(db_session, "officer-d@example.com", "loan_officer", company_a)
    other_officer = _make_user_in_company(db_session, "officer-e@example.com", "loan_officer", company_b)

    login_as(client, admin)
    app.config["WTF_CSRF_ENABLED"] = False
    resp = client.post(
        "/admin/notifications/send",
        data={
            "target_type": "role",
            "role": "loan_officer",
            "title": "Role broadcast",
            "message": "For loan officers only.",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert LoanNotification.query.filter_by(user_id=own_officer.id, title="Role broadcast").first() is not None
    assert LoanNotification.query.filter_by(user_id=other_officer.id, title="Role broadcast").first() is None


def test_company_admin_send_to_everyone_notifies_only_own_company(db_session, client, app):
    company_a = _make_company(db_session, "Scoped Co F")
    company_b = _make_company(db_session, "Scoped Co G")
    admin = _make_user_in_company(db_session, "admin-f@example.com", "admin", company_a)
    own_teammate = _make_user_in_company(db_session, "teammate-f@example.com", "processor", company_a)
    other_company_user = _make_user_in_company(db_session, "teammate-g@example.com", "processor", company_b)

    login_as(client, admin)
    app.config["WTF_CSRF_ENABLED"] = False
    resp = client.post(
        "/admin/notifications/send",
        data={
            "target_type": "everyone",
            "title": "Company-wide update",
            "message": "For everyone in the workspace.",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert LoanNotification.query.filter_by(user_id=admin.id, title="Company-wide update").first() is not None
    assert LoanNotification.query.filter_by(user_id=own_teammate.id, title="Company-wide update").first() is not None
    assert LoanNotification.query.filter_by(user_id=other_company_user.id, title="Company-wide update").first() is None


def test_send_notification_page_rejects_non_admin_roles(db_session, client):
    user = _make_user(db_session, "not-admin@example.com", "loan_officer")
    login_as(client, user)

    resp = client.get("/admin/notifications/send")

    assert resp.status_code in (302, 403)
