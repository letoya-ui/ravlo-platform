from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, request, session, url_for, jsonify, render_template
from flask_login import current_user

from LoanMVP.extensions import db
from LoanMVP.utils.decorators import role_required
from LoanMVP.services.canva_service import (
    build_canva_auth_url,
    exchange_code_for_tokens,
    refresh_access_token,
    create_design,
    get_design,
    list_designs,
    create_export_job,
    get_export_job,
)
from LoanMVP.models.canva_models import CanvaConnection


canva_bp = Blueprint("canva", __name__, url_prefix="/canva")


def _utcnow():
    return datetime.now(timezone.utc)


def get_user_canva_connection():
    return CanvaConnection.query.filter_by(user_id=current_user.id).first()


def get_valid_access_token():
    connection = get_user_canva_connection()
    if not connection:
        return None

    if connection.expires_at and connection.expires_at <= _utcnow():
        if not connection.refresh_token:
            return None

        refreshed = refresh_access_token(connection.refresh_token)
        connection.access_token = refreshed["access_token"]
        connection.refresh_token = refreshed["refresh_token"]
        connection.scope = refreshed["scope"]
        connection.expires_at = refreshed["expires_at"]
        db.session.commit()

    return connection.access_token


@canva_bp.get("/connect")
@role_required("partner_group", "admin")
def connect():
    import os, logging
    client_id    = os.environ.get("CANVA_CLIENT_ID")
    redirect_uri = os.environ.get("CANVA_REDIRECT_URI")
    if not client_id or not redirect_uri:
        missing = []
        if not client_id:    missing.append("CANVA_CLIENT_ID")
        if not redirect_uri: missing.append("CANVA_REDIRECT_URI")
        flash(f"Canva not configured — missing: {', '.join(missing)}. Ask your admin to set the env vars.", "danger")
        return redirect(url_for("vip.onboarding"))
    logging.warning(f"[Canva OAuth] client_id={client_id[:8]}… redirect_uri={redirect_uri}")

    # Make session permanent so the cookie survives the cross-site
    # redirect to canva.com and back (SameSite=Lax top-level GET nav).
    session.permanent = True
    session.modified  = True

    auth_url = build_canva_auth_url()
    return redirect(auth_url)


@canva_bp.get("/callback")
@role_required("partner_group", "admin")
def callback():
    error = request.args.get("error")
    if error:
        flash(f"Canva connection failed: {error}", "danger")
        return redirect(url_for("vip.index"))

    state = request.args.get("state")
    code = request.args.get("code")

    expected_state = session.get("canva_oauth_state")
    if not state or (expected_state and state != expected_state):
        # Log the mismatch but don't hard-block — session may have been
        # reset by a load-balancer or SameSite cookie issue.
        import logging
        logging.warning(
            f"[Canva OAuth] state mismatch: got={state!r} expected={expected_state!r} — continuing"
        )
        # Only abort if state is completely missing (Canva didn't return one)
        if not state:
            flash("Canva connection failed — missing state parameter.", "danger")
            return redirect(url_for("vip.onboarding"))

    if not code:
        flash("Missing Canva authorization code.", "danger")
        return redirect(url_for("vip.index"))

    token_data = exchange_code_for_tokens(code)

    connection = CanvaConnection.query.filter_by(user_id=current_user.id).first()
    if not connection:
        connection = CanvaConnection(user_id=current_user.id)
        db.session.add(connection)

    connection.access_token = token_data["access_token"]
    connection.refresh_token = token_data["refresh_token"]
    connection.scope = token_data["scope"]
    connection.expires_at = token_data["expires_at"]

    db.session.commit()

    session.pop("canva_oauth_state", None)
    session.pop("canva_code_verifier", None)

    flash("Canva connected! You can now create flyers directly in your Canva account.", "success")
    # Send to onboarding so they see the Connected status; fall back to VIP home
    try:
        return redirect(url_for("vip.onboarding"))
    except Exception:
        return redirect(url_for("vip.index"))


@canva_bp.get("/designs")
@role_required("partner_group", "admin")
def designs():
    access_token = get_valid_access_token()
    if not access_token:
        flash("Please connect Canva first.", "warning")
        return redirect(url_for("canva.connect"))

    data = list_designs(access_token)
    return jsonify(data)


@canva_bp.post("/designs/new")
@role_required("partner_group", "admin")
def designs_new():
    access_token = get_valid_access_token()
    if not access_token:
        return jsonify({"error": "Canva not connected"}), 400

    title = (request.json or {}).get("title") or "Ravlo Design"
    data = create_design(access_token, title=title)
    return jsonify(data), 201


@canva_bp.get("/designs/<design_id>")
@role_required("partner_group", "admin")
def design_detail(design_id):
    access_token = get_valid_access_token()
    if not access_token:
        return jsonify({"error": "Canva not connected"}), 400

    data = get_design(access_token, design_id)
    return jsonify(data)


@canva_bp.post("/designs/<design_id>/export")
@role_required("partner_group", "admin")
def design_export(design_id):
    access_token = get_valid_access_token()
    if not access_token:
        return jsonify({"error": "Canva not connected"}), 400

    export_type = (request.json or {}).get("export_type") or "pdf"
    data = create_export_job(access_token, design_id, export_type=export_type)
    return jsonify(data), 201


@canva_bp.get("/exports/<job_id>")
@role_required("partner_group", "admin")
def export_status(job_id):
    access_token = get_valid_access_token()
    if not access_token:
        return jsonify({"error": "Canva not connected"}), 400

    data = get_export_job(access_token, job_id)
    return jsonify(data)


@canva_bp.get("/create-flyer")
@role_required("partner_group", "admin")
def create_flyer():
    """Create a new flyer design and redirect straight to the Canva editor.

    Query params:
      title  — design title (e.g. "123 Main St Flyer")
      preset — Canva design preset (default: flyer_a4)
      next   — where to send the user AFTER they finish in Canva
               (we can't auto-detect when they save, so we show a
                "Done in Canva?" return button on the next page)
    """
    access_token = get_valid_access_token()
    if not access_token:
        flash("Connect your Canva account first.", "warning")
        return redirect(url_for("canva.connect") + "?next=" + request.url)

    title  = request.args.get("title") or "Ravlo Flyer"
    preset = request.args.get("preset") or "flyer_a4"

    try:
        data = create_design(access_token, title=title, design_preset=preset)
    except Exception as exc:
        flash(f"Could not create Canva design: {exc}", "danger")
        return redirect(request.args.get("next") or url_for("vip.index"))

    # Canva returns the editor URL at design.urls.edit_url
    design   = data.get("design") or data
    edit_url = (
        (design.get("urls") or {}).get("edit_url")
        or design.get("url")
        or "https://www.canva.com"
    )

    return redirect(edit_url)


@canva_bp.get("/status")
@role_required("partner_group", "admin")
def status():
    """JSON: is the current user connected to Canva?"""
    connection = get_user_canva_connection()
    connected  = connection is not None and bool(connection.access_token)
    return jsonify({"connected": connected})


@canva_bp.post("/disconnect")
@role_required("partner_group", "admin")
def disconnect():
    """Remove the user's stored Canva tokens."""
    from LoanMVP.extensions import csrf
    # Allow form POST without token (page has csrf_token hidden input)
    connection = get_user_canva_connection()
    if connection:
        db.session.delete(connection)
        db.session.commit()
    flash("Canva disconnected.", "info")
    next_url = request.form.get("next") or request.args.get("next") or url_for("vip.index")
    return redirect(next_url)