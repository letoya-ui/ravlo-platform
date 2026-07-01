from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from LoanMVP.extensions import db
from LoanMVP.models.contractor_models import ContractorBidOpportunity
from LoanMVP.models.crm_models import Partner

construction_bids_bp = Blueprint("construction_bids", __name__, url_prefix="/construction/bids")


def _current_partner():
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if partner:
        return partner

    return Partner.query.filter(
        func.lower(Partner.company) == "caughman mason construction"
    ).first()


def _can_use_bid_handoff() -> bool:
    email = (getattr(current_user, "email", "") or "").strip().lower()
    role = (getattr(current_user, "role", "") or "").strip().lower()

    return (
        email in {
            "jamaine.caughman@ravlohq.com",
            "sandra@ravlohq.com",
            "letoya@ravlohq.com",
        }
        or role in {"executive", "platform_admin", "master_admin", "lending_admin", "partner", "contractor"}
    )


@construction_bids_bp.route("/create", methods=["POST"])
@login_required
def create_bid_opportunity():
    """Create a manually sourced construction bid opportunity."""
    if not _can_use_bid_handoff():
        flash("You do not have access to construction bid tools yet.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    partner = _current_partner()
    if not partner:
        flash("Construction partner profile not found yet.", "warning")
        return redirect(url_for("executive.construction_center"))

    project_name = (request.form.get("project_name") or "").strip()
    if not project_name:
        flash("Project name is required before saving a bid opportunity.", "warning")
        return redirect(url_for("executive.construction_center"))

    estimated_value_raw = (request.form.get("estimated_value") or "").replace(",", "").strip()
    estimated_value = None
    if estimated_value_raw:
        try:
            estimated_value = float(estimated_value_raw)
        except ValueError:
            estimated_value = None

    bid_deadline = None
    deadline_raw = (request.form.get("bid_deadline") or "").strip()
    if deadline_raw:
        try:
            bid_deadline = datetime.strptime(deadline_raw, "%Y-%m-%d")
        except ValueError:
            bid_deadline = None

    opportunity = ContractorBidOpportunity(
        partner_id=partner.id,
        project_name=project_name,
        source=(request.form.get("source") or "Manual Search").strip() or "Manual Search",
        category=(request.form.get("category") or "Bid Search").strip() or "Bid Search",
        location=(request.form.get("location") or "").strip() or None,
        estimated_value=estimated_value,
        bid_deadline=bid_deadline,
        notes=(request.form.get("notes") or "").strip() or None,
        status="saved_opportunity",
    )
    db.session.add(opportunity)
    db.session.commit()

    flash("Bid opportunity saved. Send it to Sandra when it needs a bid package.", "success")
    return redirect(url_for("executive.construction_center"))


@construction_bids_bp.route("/<int:opportunity_id>/send-to-sandra", methods=["POST"])
@login_required
def send_to_sandra(opportunity_id):
    """Move a construction opportunity into Sandra's bid-support workflow."""
    if not _can_use_bid_handoff():
        flash("You do not have access to construction bid tools yet.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    opportunity = ContractorBidOpportunity.query.get_or_404(opportunity_id)
    opportunity.status = "bid_package_needed"

    handoff_note = (request.form.get("handoff_note") or "").strip()
    existing_notes = opportunity.notes or ""
    note_lines = [existing_notes] if existing_notes else []
    note_lines.append(
        f"Sent to Sandra for bid package on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    )
    if handoff_note:
        note_lines.append(f"Handoff note: {handoff_note}")
    opportunity.notes = "\n".join(note_lines)

    db.session.commit()

    flash("Sent to Sandra for bid package.", "success")
    return redirect(url_for("executive.construction_center"))


@construction_bids_bp.route("/<int:opportunity_id>/status", methods=["POST"])
@login_required
def update_bid_status(opportunity_id):
    """Update the pipeline status for a construction bid opportunity."""
    if not _can_use_bid_handoff():
        flash("You do not have access to construction bid tools yet.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    allowed_statuses = {
        "saved_opportunity",
        "bid_package_needed",
        "missing_information",
        "site_visit_needed",
        "site_visit_scheduled",
        "estimate_needed",
        "draft_bid_prepared",
        "jamaine_review_needed",
        "ready_to_send",
        "bid_submitted",
        "follow_up_needed",
        "negotiating",
        "won",
        "in_progress",
        "completed",
        "invoice_sent",
        "paid",
        "lost",
        "no_bid",
    }

    new_status = (request.form.get("status") or "").strip().lower()
    if new_status not in allowed_statuses:
        flash("That bid status is not available.", "warning")
        return redirect(url_for("executive.construction_center"))

    opportunity = ContractorBidOpportunity.query.get_or_404(opportunity_id)
    opportunity.status = new_status
    db.session.commit()

    flash("Bid status updated.", "success")
    return redirect(request.referrer or url_for("executive.construction_center"))
