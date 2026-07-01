from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from LoanMVP.extensions import db
from LoanMVP.models.contractor_models import ContractorBidOpportunity

construction_office_bp = Blueprint("construction_office", __name__, url_prefix="/construction-office")


def _can_access_construction_office():
    role = (getattr(current_user, "role", "") or "").strip().lower()
    email = (getattr(current_user, "email", "") or "").strip().lower()
    return (
        role in {"admin", "platform_admin", "master_admin", "lending_admin", "executive", "partner", "contractor"}
        or email in {"jamaine.caughman@ravlohq.com", "jamaine.caughman@caughmanmason.com", "letoya@ravlohq.com"}
    )


def _append_workflow_note(row, old_status, new_status, note=None):
    existing_notes = row.notes or ""
    note_lines = [existing_notes] if existing_notes else []
    actor = (getattr(current_user, "first_name", None) or getattr(current_user, "email", "") or "Team").strip()
    note_lines.append(
        f"Workflow updated by {actor} on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}: "
        f"{old_status or 'none'} → {new_status}"
    )
    if note:
        note_lines.append(f"Workflow note: {note}")
    row.notes = "\n".join(note_lines)


@construction_office_bp.route("/packages", methods=["GET"])
@login_required
def packages():
    if not _can_access_construction_office():
        flash("You do not have access to construction office tools yet.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    queue_statuses = [
        "bid_package_needed",
        "missing_information",
        "draft_bid_prepared",
        "jamaine_review_needed",
        "approval_needed",
        "approved_to_submit",
        "ready_to_send",
        "bid_submitted",
        "client_review",
        "follow_up_needed",
    ]

    package_rows = (
        ContractorBidOpportunity.query
        .filter(ContractorBidOpportunity.status.in_(queue_statuses))
        .order_by(ContractorBidOpportunity.updated_at.desc(), ContractorBidOpportunity.created_at.desc())
        .limit(50)
        .all()
    )

    return render_template(
        "construction/office_packages.html",
        package_rows=package_rows,
    )


@construction_office_bp.route("/approvals", methods=["GET"])
@login_required
def approvals():
    if not _can_access_construction_office():
        flash("You do not have access to construction approval tools yet.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    approval_rows = (
        ContractorBidOpportunity.query
        .filter(ContractorBidOpportunity.status.in_(["approval_needed", "approved_to_submit", "negotiating"]))
        .order_by(ContractorBidOpportunity.updated_at.desc(), ContractorBidOpportunity.created_at.desc())
        .limit(50)
        .all()
    )

    return render_template(
        "construction/approval_queue.html",
        approval_rows=approval_rows,
    )


@construction_office_bp.route("/packages/<int:opportunity_id>/status", methods=["POST"])
@login_required
def update_package_status(opportunity_id):
    if not _can_access_construction_office():
        flash("You do not have access to construction office tools yet.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    allowed_statuses = {
        "missing_information",
        "draft_bid_prepared",
        "jamaine_review_needed",
        "approval_needed",
        "approved_to_submit",
        "ready_to_send",
        "bid_submitted",
        "client_review",
        "follow_up_needed",
        "negotiating",
        "won",
        "lost",
        "no_bid",
    }
    status = (request.form.get("status") or "").strip().lower()
    if status not in allowed_statuses:
        flash("That package status is not available.", "warning")
        return redirect(url_for("construction_office.packages"))

    row = ContractorBidOpportunity.query.get_or_404(opportunity_id)
    old_status = row.status
    row.status = status
    _append_workflow_note(row, old_status, status, (request.form.get("workflow_note") or "").strip() or None)

    db.session.commit()

    flash("Construction package status updated.", "success")
    return redirect(request.referrer or url_for("construction_office.packages"))
