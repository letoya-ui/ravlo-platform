"""Facebook Login for Business: connect a company's Page (and its linked
Instagram professional account, if any) for Lead Ads without an admin
having to dig a Page Access Token out of Meta Business Suite by hand.

Auto-registered by LoanMVP/app.py blueprint scanner.
"""
from flask import (
    Blueprint, current_app, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required, login_user

from LoanMVP.extensions import db, csrf
from LoanMVP.models.crm_models import FacebookPageConnection
from LoanMVP.models.user_model import User
from LoanMVP.routes.admin import _ensure_company_access, admin_required
from LoanMVP.services.facebook_oauth_service import (
    FacebookOAuthError,
    build_oauth_url,
    decode_oauth_state,
    exchange_code_for_user_token,
    exchange_for_long_lived_token,
    list_managed_pages,
    subscribe_page_to_leadgen,
)
from LoanMVP.utils.decorators import role_required

facebook_connect_bp = Blueprint("facebook_connect", __name__, url_prefix="/integrations/facebook")


def _redirect_uri() -> str:
    return url_for("facebook_connect.callback", _external=True)


@facebook_connect_bp.get("/connect/<int:company_id>")
@login_required
@role_required("admin_group")
@admin_required
def connect(company_id):
    from LoanMVP.models.admin import Company

    company = Company.query.get_or_404(company_id)
    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    try:
        auth_url = build_oauth_url(company_id, current_user.id, _redirect_uri())
    except FacebookOAuthError as exc:
        flash(f"Facebook connection isn't configured yet: {exc}", "danger")
        return redirect(url_for("admin.company_settings", company_id=company_id))

    return redirect(auth_url)


@facebook_connect_bp.get("/callback")
def callback():
    """No @login_required on purpose -- see LoanMVP.routes.canva.callback
    for the identical reasoning. Who started this and which company it's
    for is recovered from the signed `state` param, which round-trips
    through Facebook untouched and doesn't depend on the session at all."""
    error = request.args.get("error")
    state = request.args.get("state")
    code = request.args.get("code")

    decoded_state = decode_oauth_state(state)
    company_id = decoded_state.get("company_id") if decoded_state else None
    user_id = decoded_state.get("uid") if decoded_state else None

    if not company_id or not user_id:
        flash("Your Facebook connection attempt expired or is no longer valid. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    from LoanMVP.models.admin import Company

    company = Company.query.get(company_id)
    user = User.query.get(user_id)
    if not company or not user or not user.is_active or user.is_blocked:
        flash("Your Facebook connection attempt expired or is no longer valid. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    if not current_user.is_authenticated or current_user.id != user.id:
        login_user(user)

    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    if error:
        flash(f"Facebook connection failed: {error}", "danger")
        return redirect(url_for("admin.company_settings", company_id=company_id))

    if not code:
        flash("Missing Facebook authorization code.", "danger")
        return redirect(url_for("admin.company_settings", company_id=company_id))

    try:
        short_lived_token = exchange_code_for_user_token(code, _redirect_uri())
        user_access_token = exchange_for_long_lived_token(short_lived_token)
        pages = list_managed_pages(user_access_token)
    except FacebookOAuthError as exc:
        current_app.logger.error("[facebook_connect] oauth exchange failed: %s", exc)
        flash(f"Facebook connection failed: {exc}", "danger")
        return redirect(url_for("admin.company_settings", company_id=company_id))

    if not pages:
        flash(
            "No Facebook Pages found for that account. Make sure you're an admin of at least one Page.",
            "warning",
        )
        return redirect(url_for("admin.company_settings", company_id=company_id))

    if len(pages) == 1:
        return _connect_page(company, pages[0])

    return render_template(
        "admin/facebook_connect_pages.html",
        company=company,
        pages=pages,
    )


def _connect_page(company, page: dict):
    try:
        subscribe_page_to_leadgen(page["id"], page["access_token"])
    except FacebookOAuthError as exc:
        current_app.logger.error("[facebook_connect] subscribe failed for page_id=%s: %s", page["id"], exc)
        flash(f"Connected the Page, but couldn't subscribe it to lead events: {exc}", "warning")

    connection = FacebookPageConnection.query.filter_by(company_id=company.id).first()
    if not connection:
        connection = FacebookPageConnection(company_id=company.id)
        db.session.add(connection)

    connection.page_id = page["id"]
    connection.page_name = page["name"]
    connection.page_access_token = page["access_token"]
    connection.platform = "instagram" if page.get("instagram_username") else "facebook"
    connection.is_active = True
    connection.connected_by_user_id = current_user.id

    db.session.commit()
    flash(f'Connected "{page["name"]}" -- Lead Ad submissions will now flow into your Leads pipeline.', "success")
    return redirect(url_for("admin.company_settings", company_id=company.id))


@facebook_connect_bp.post("/connect/<int:company_id>/finish")
@login_required
@role_required("admin_group")
@admin_required
@csrf.exempt
def finish(company_id):
    """Handles the Page picker's submit when an admin manages more than
    one Page. The chosen page's id/name/token/instagram_username round-
    trip through hidden form fields set by facebook_connect_pages.html --
    same trust model the existing manual-token form already used."""
    from LoanMVP.models.admin import Company

    company = Company.query.get_or_404(company_id)
    access_redirect = _ensure_company_access(company)
    if access_redirect:
        return access_redirect

    page = {
        "id": (request.form.get("page_id") or "").strip(),
        "name": (request.form.get("page_name") or "").strip(),
        "access_token": (request.form.get("page_access_token") or "").strip(),
        "instagram_username": (request.form.get("instagram_username") or "").strip() or None,
    }
    if not page["id"] or not page["access_token"]:
        flash("Please choose a Page to connect.", "warning")
        return redirect(url_for("admin.company_settings", company_id=company_id))

    return _connect_page(company, page)
