# LoanMVP/routes/notifications.py

from flask import Blueprint, render_template, jsonify
from LoanMVP.extensions import db
from LoanMVP.models.loan_models import LoanNotification
from flask_login import login_required, current_user

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


# ============================
# NOTIFICATIONS DASHBOARD
# ============================
@notifications_bp.route("/")
@login_required
def dashboard():

    # Pull newest 50 notifications
    notifications = (
        LoanNotification.query
        .order_by(LoanNotification.created_at.desc())
        .limit(50)
        .all()
    )

    # Icons per event type
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
        "ai_summary": "🤖"
    }

    # Color per event type
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
        "ai_summary": "#ffdd65"
    }

    return render_template(
        "notifications/dashboard.html",
        notifications=notifications,
        ICON_MAP=ICON_MAP,
        COLOR_MAP=COLOR_MAP
    )


# ============================
# API — Get latest notification items
# ============================
@notifications_bp.route("/api/latest")
@login_required
def api_latest():
    role = getattr(current_user, "role", "all").lower()

    new_items = (
        LoanNotification.query
        .filter((LoanNotification.role == role) | (LoanNotification.role == "all"))
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
    notif = LoanNotification.query.get_or_404(notif_id)
    notif.is_read = True
    db.session.commit()
    return jsonify({"success": True})


# ============================
# MARK ALL READ
# ============================
@notifications_bp.route("/mark_all_read", methods=["POST"])
@login_required
def mark_all_read():
    role = getattr(current_user, "role", "all").lower()

    LoanNotification.query.filter(
        (LoanNotification.role == role) | (LoanNotification.role == "all")
    ).update({"is_read": True})

    db.session.commit()
    return jsonify({"success": True, "message": "All notifications marked as read."})


# =========================================================
# 🧠 Global Context Processor for Unread Counts
# =========================================================
@notifications_bp.app_context_processor
def inject_notification_counts():

    if not current_user.is_authenticated:
        return {}

    try:
        crm_unread = LoanNotification.query.filter_by(role="crm", is_read=False).count()
        loan_unread = LoanNotification.query.filter_by(role="loan_officer", is_read=False).count()
        processor_unread = LoanNotification.query.filter_by(role="processor", is_read=False).count()
        compliance_unread = LoanNotification.query.filter_by(role="compliance", is_read=False).count()
        underwriter_unread = LoanNotification.query.filter_by(role="underwriter", is_read=False).count()
        executive_unread = LoanNotification.query.filter_by(role="executive", is_read=False).count()
    except Exception:
        crm_unread = loan_unread = processor_unread = compliance_unread = underwriter_unread = executive_unread = 0

    return dict(
        crm_unread=crm_unread,
        loan_unread=loan_unread,
        processor_unread=processor_unread,
        compliance_unread=compliance_unread,
        underwriter_unread=underwriter_unread,
        executive_unread=executive_unread
    )
