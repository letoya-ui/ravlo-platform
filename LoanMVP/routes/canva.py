from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, request, session, url_for, jsonify
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
    if not state or state != expected_state:
        flash("Invalid Canva OAuth state.", "danger")
        return redirect(url_for("vip.index"))

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

    flash("Canva connected successfully.", "success")
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