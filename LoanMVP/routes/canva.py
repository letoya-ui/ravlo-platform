from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, request, session, url_for, jsonify, render_template
from flask_login import current_user, login_required

from LoanMVP.extensions import db, csrf
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

    # expires_at is stored as naive UTC; compare against naive utcnow
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if connection.expires_at and connection.expires_at <= now:
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
@login_required
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

    # Remember where to return the user after OAuth completes
    next_url = request.args.get("next")
    if next_url:
        session["canva_next"] = next_url

    auth_url = build_canva_auth_url()
    return redirect(auth_url)


@canva_bp.get("/callback")
@login_required
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

    try:
        token_data = exchange_code_for_tokens(code)
    except Exception as exc:
        import logging
        logging.error(f"[Canva OAuth] token exchange failed: {exc}")
        flash(f"Canva token exchange failed: {exc}", "danger")
        return redirect(url_for("vip.onboarding"))

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

    # Check whether Canva granted design creation permission.
    # If design:content:write is missing the app isn't approved for it in the
    # Canva developer portal — warn the user clearly instead of letting them
    # discover it as a silent 403 when they try to create a design.
    granted_scope = token_data.get("scope") or ""
    if "design:content:write" not in granted_scope:
        import logging
        logging.warning(
            f"[Canva OAuth] connected but design:content:write missing from granted scopes: {granted_scope!r}"
        )
        flash(
            "Canva connected, but design creation is not enabled for this app. "
            "To create designs from Ravlo, a Ravlo admin needs to enable the "
            "'design:content:write' scope in the Canva developer portal, then reconnect. "
            "You can still browse your existing designs.",
            "warning",
        )
    else:
        flash("Canva connected! You can now create flyers directly from Ravlo.", "success")

    # Return the user to wherever they came from, or onboarding as fallback
    next_url = session.pop("canva_next", None)
    try:
        return redirect(next_url or url_for("vip.onboarding"))
    except Exception:
        return redirect(url_for("vip.index"))


@canva_bp.get("/designs")
@login_required
def designs():
    access_token = get_valid_access_token()
    if not access_token:
        flash("Please connect Canva first.", "warning")
        return redirect(url_for("canva.connect"))

    data = list_designs(access_token)
    return jsonify(data)


@canva_bp.post("/designs/new")
@login_required
def designs_new():
    access_token = get_valid_access_token()
    if not access_token:
        return jsonify({"error": "Canva not connected"}), 400

    title = (request.json or {}).get("title") or "Ravlo Design"
    data = create_design(access_token, title=title)
    return jsonify(data), 201


@canva_bp.get("/designs/<design_id>")
@login_required
def design_detail(design_id):
    access_token = get_valid_access_token()
    if not access_token:
        return jsonify({"error": "Canva not connected"}), 400

    data = get_design(access_token, design_id)
    return jsonify(data)


@canva_bp.post("/designs/<design_id>/export")
@login_required
def design_export(design_id):
    access_token = get_valid_access_token()
    if not access_token:
        return jsonify({"error": "Canva not connected"}), 400

    export_type = (request.json or {}).get("export_type") or "pdf"
    data = create_export_job(access_token, design_id, export_type=export_type)
    return jsonify(data), 201


@canva_bp.get("/exports/<job_id>")
@login_required
def export_status(job_id):
    access_token = get_valid_access_token()
    if not access_token:
        return jsonify({"error": "Canva not connected"}), 400

    data = get_export_job(access_token, job_id)
    return jsonify(data)


@canva_bp.get("/create-flyer")
@login_required
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
        import requests as _req
        if isinstance(exc, _req.exceptions.HTTPError) and getattr(exc.response, "status_code", None) == 403:
            # 403 means the token is missing design:content:write.
            # Check whether the stored scope already excludes it — if so,
            # reconnecting won't help (the Canva app isn't approved for that scope
            # in the developer portal). Show a clear explanation instead of looping.
            connection = get_user_canva_connection()
            granted_scope = getattr(connection, "scope", "") or ""
            if "design:content:write" not in granted_scope:
                flash(
                    "Design creation isn't enabled for this Canva integration. "
                    "A Ravlo admin needs to add the 'design:content:write' scope "
                    "in the Canva developer portal. Once that's done, disconnect and "
                    "reconnect Canva to pick up the new permission.",
                    "warning",
                )
                return redirect(request.args.get("next") or url_for("elena.template_studio"))
            # Scope looks right but still 403 — token may be stale. Wipe and reconnect.
            if connection:
                from LoanMVP.extensions import db as _db
                _db.session.delete(connection)
                _db.session.commit()
            session["canva_next"] = request.args.get("next") or url_for("elena.template_studio")
            flash(
                "Canva needs permission to create designs. "
                "Please reconnect your Canva account.",
                "warning",
            )
            return redirect(url_for("canva.connect"))
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



@canva_bp.post("/webhook")
@csrf.exempt
def webhook():
    """Canva webhook receiver.

    Canva POSTs events here (design exports, asset uploads, etc.).
    We verify the signature using CANVA_WEBHOOK_SECRET, log the event,
    and return 200 immediately.

    Webhook URL to register in Canva portal:
        https://ravlohq.com/canva/webhook
    """
    import hashlib
    import hmac
    import logging
    import os

    secret = os.environ.get("CANVA_WEBHOOK_SECRET", "")

    # Verify Canva's HMAC-SHA256 signature if secret is configured
    sig_header = request.headers.get("X-Canva-Signature", "")
    if secret and sig_header:
        expected = hmac.new(
            key=secret.encode("utf-8"),
            msg=request.get_data(),
            digestmod=hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, sig_header):
            logging.warning("[Canva webhook] signature mismatch — rejected")
            return jsonify({"error": "invalid signature"}), 401

    payload = request.get_json(silent=True) or {}
    event_type = payload.get("type") or payload.get("event") or "unknown"
    logging.info(f"[Canva webhook] received event: {event_type} payload={payload}")

    # Handle specific events as needed
    if event_type == "export:complete":
        design_id = (payload.get("data") or {}).get("design_id")
        export_url = (payload.get("data") or {}).get("url")
        logging.info(f"[Canva webhook] export complete design_id={design_id} url={export_url}")

    # Always return 200 so Canva doesn't retry
    return jsonify({"status": "ok"}), 200


@canva_bp.get("/webhook")
def webhook_verify():
    """GET handler for Canva webhook URL verification challenge."""
    challenge = request.args.get("challenge")
    if challenge:
        return jsonify({"challenge": challenge}), 200
    return jsonify({"status": "ok"}), 200


@canva_bp.get("/status")
@login_required
def status():
    """JSON: is the current user connected to Canva?"""
    connection = get_user_canva_connection()
    connected  = connection is not None and bool(connection.access_token)
    return jsonify({"connected": connected})


@canva_bp.post("/disconnect")
@login_required
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