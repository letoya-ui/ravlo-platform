from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, and_

from LoanMVP.extensions import db
from LoanMVP.models.loan_models import LoanNotification

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


def _base_template():
    role = (getattr(current_user, "role", "") or "").strip().lower()
    if role == "borrower":
        return "layouts/ravlo_borrower_base.html"
    if role == "investor":
        return "layouts/ravlo_base.html"
    return "layouts/ravlo_employee_base.html"


def _visible_to_current_user():
    """A notification is visible to the current user if it was sent
    directly to them (user_id match), or if it's a role-wide broadcast
    (user_id is null and role matches, or role == "all")."""
    role = (getattr(current_user, "role", "") or "").lower()
    return or_(
        LoanNotification.user_id == current_user.id,
        and_(
            LoanNotification.user_id.is_(None),
            or_(LoanNotification.role == role, LoanNotification.role == "all"),
        ),
    )


# ============================
# NOTIFICATIONS DASHBOARD
# ============================
@notifications_bp.route("/")
@login_required
def dashboard():
    notifications = (
        LoanNotification.query
        .filter(_visible_to_current_user())
        .order_by(LoanNotification.created_at.desc())
        .limit(50)
        .all()
    )

    ICON_MAP = {
        "emailed": "📩",
        "opened": "📬",
        "viewed": "👁",
        "downloaded": "⬇️",
        "uploaded": "📤",
        "condition_requested": "⚠️",
        "condition_cleared": "✔️",
        "status_changed": "🔄",
        "payment_made": "💳",
        "ai_summary": "🤖",
        "ai": "🤖",
    }

    COLOR_MAP = {
        "emailed": "#7ab8ff",
        "opened": "#9ad468",
        "viewed": "#ebb76a",
        "downloaded": "#7ab8ff",
        "uploaded": "#68d4e6",
        "condition_requested": "#ff6b6b",
        "condition_cleared": "#42d77d",
        "status_changed": "#7ab8ff",
        "payment_made": "#b29dff",
        "ai_summary": "#ffdd65",
        "ai": "#ffdd65",
    }

    return render_template(
        "notifications/dashboard.html",
        notifications=notifications,
        ICON_MAP=ICON_MAP,
        COLOR_MAP=COLOR_MAP,
        base_template=_base_template(),
        active_tab="notifications",
        title="Notifications"
    )


# ============================
# API — Get latest notification items
# ============================
@notifications_bp.route("/api/latest")
@login_required
def api_latest():
    new_items = (
        LoanNotification.query
        .filter(_visible_to_current_user())
        .order_by(LoanNotification.created_at.desc())
        .limit(5)
        .all()
    )

    return jsonify({"new": [n.to_dict() for n in new_items]})


# ============================
# MARK ONE READ
# ============================
@notifications_bp.route("/mark_read/<int:notif_id>", methods=["POST"])
@login_required
def mark_read(notif_id):
    notif = LoanNotification.query.filter(
        LoanNotification.id == notif_id, _visible_to_current_user()
    ).first()

    if not notif:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    notif.is_read = True
    db.session.commit()
    return jsonify({"success": True})


# ============================
# MARK ALL READ
# ============================
@notifications_bp.route("/mark_all_read", methods=["POST"])
@login_required
def mark_all_read():
    LoanNotification.query.filter(_visible_to_current_user()).update(
        {"is_read": True}, synchronize_session=False
    )
    db.session.commit()

    return jsonify({"success": True, "message": "All notifications marked as read."})


# =========================================================
# Global Context Processor for Unread Counts
# =========================================================
@notifications_bp.app_context_processor
def inject_notification_counts():
    if not current_user.is_authenticated:
        return {}

    try:
        current_unread = LoanNotification.query.filter(
            _visible_to_current_user(), LoanNotification.is_read.is_(False)
        ).count()
    except Exception:
        current_unread = 0

    return dict(current_unread=current_unread)
