from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from LoanMVP.extensions import db
from LoanMVP.models.contractor_models import ContractorBidOpportunity
from LoanMVP.models.crm_models import Partner

construction_bids_bp = Blueprint("construction_bids", __name__, url_prefix="/construction/bids")


def _current_partner():
    """Return the active construction partner profile for bid handoff.

    Jamaine's construction workflow should not fail just because the partner
    profile has not been manually linked yet. If the current user is Jamaine or
    a construction-enabled operator, attach or create the Caughman Mason
    Construction partner profile on demand.
    """
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if partner:
        return partner

    email = (getattr(current_user, "email", "") or "").strip().lower()
    role = (getattr(current_user, "role", "") or "").strip().lower()
    can_seed_construction_profile = (
        email in {
            "jamaine.caughman@ravlohq.com",
            "jamaine.caughman@caughmanmason.com",
            "letoya@ravlohq.com",
        }
        or role in {"executive", "platform_admin", "master_admin", "lending_admin", "partner", "contractor"}
    )

    if not can_seed_construction_profile:
        return None

    partner = Partner.query.filter(
        func.lower(func.coalesce(Partner.company, "")) == "caughman mason construction"
    ).first()

    if partner:
        if not partner.user_id and email.startswith("jamaine"):
            partner.user_id = current_user.id
            partner.email = partner.email or email
            partner.active = True
            partner.approved = True
            partner.status = partner.status or "Active"
            db.session.commit()
        return partner

    display_name = (
        getattr(current_user, "full_name", None)
        or getattr(current_user, "username", None)
        or "Caughman Mason Construction"
    )
    partner = Partner(
        user_id=current_user.id if email.startswith("jamaine") else None,
        name=display_name,
        company="Caughman Mason Construction",
        email=email or None,
        category="contractor",
        type="Contractor",
        specialty="General contracting, renovation, rehab, demo, and ironwork",
        service_area="Tampa Bay, FL",
        city="Tampa",
        state="FL",
        bio="Caughman Mason Construction supports demo, renovation, repair, rehab, and small GC opportunities in the Tampa Bay market.",
        listing_description="Construction and renovation services for investors, property owners, and commercial clients in the Tampa Bay area.",
        active=True,
        approved=True,
        featured=False,
        status="Active",
        subscription_tier="Premium",
        crm_enabled=True,
        deal_visibility_enabled=True,
        proposal_builder_enabled=True,
        instant_quote_enabled=True,
        ai_assist_enabled=True,
        smart_notifications_enabled=True,
        portfolio_showcase_enabled=True,
        is_verified=True,
    )
    db.session.add(partner)
    db.session.commit()
    return partner


def _can_use_bid_handoff() -> bool:
    email = (getattr(current_user, "email", "") or "").strip().lower()
    role = (getattr(current_user, "role", "") or "").strip().lower()

    return (
        email in {
            "jamaine.caughman@ravlohq.com",
            "jamaine.caughman@caughmanmason.com",
            "sandra@ravlohq.com",
            "letoya@ravlohq.com",
        }
        or role in {"executive", "platform_admin", "master_admin", "lending_admin", "partner", "contractor"}
    )


@construction_bids_bp.route("/search", methods=["GET"])
@login_required
def search_page():
    """Dedicated construction opportunity search and capture page."""
    if not _can_use_bid_handoff():
        flash("You do not have access to construction bid tools yet.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    partner = _current_partner()
    recent_opportunities = []
    if partner:
        recent_opportunities = (
            ContractorBidOpportunity.query
            .filter_by(partner_id=partner.id)
            .order_by(ContractorBidOpportunity.created_at.desc())
            .limit(10)
            .all()
        )

    search_terms = [
        {
            "label": "Tampa Demo Jobs",
            "url": "https://www.google.com/search?q=Tampa+demo+construction+bid+opportunities",
            "note": "Demolition, cleanout, teardown, and removal leads.",
        },
        {
            "label": "Small GC Jobs",
            "url": "https://www.google.com/search?q=Tampa+small+GC+construction+bid+opportunities",
            "note": "Small general contracting, repair, and renovation work.",
        },
        {
            "label": "Hillsborough Bids",
            "url": "https://www.google.com/search?q=Hillsborough+County+construction+bids+demo+repair",
            "note": "County/public bid leads around Tampa and Hillsborough.",
        },
        {
            "label": "Pinellas Bids",
            "url": "https://www.google.com/search?q=Pinellas+County+construction+bids+renovation+demo",
            "note": "Nearby county opportunities for renovation and demo.",
        },
        {
            "label": "Ironwork",
            "url": "https://www.google.com/search?q=Tampa+ironwork+subcontractor+bid+opportunities",
            "note": "Steel, welding, stairs, rails, structural, and subcontractor work.",
        },
        {
            "label": "Property Preservation",
            "url": "https://www.google.com/search?q=Tampa+property+preservation+contractor+opportunities",
            "note": "REO, cleanup, turnover, maintenance, and preservation work.",
        },
        {
            "label": "Commercial Maintenance",
            "url": "https://www.google.com/search?q=Tampa+commercial+property+maintenance+contractor+opportunities",
            "note": "Recurring repair and maintenance opportunities.",
        },
        {
            "label": "Investor Renovations",
            "url": "https://www.google.com/search?q=Tampa+investor+renovation+contractor+opportunities",
            "note": "Fix-and-flip and rental renovation work.",
        },
    ]

    return render_template(
        "construction/bid_search.html",
        partner=partner,
        recent_opportunities=recent_opportunities,
        search_terms=search_terms,
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
        flash("Construction partner profile could not be prepared yet.", "warning")
        return redirect(url_for("executive.construction_center"))

    project_name = (request.form.get("project_name") or "").strip()
    if not project_name:
        flash("Project name is required before saving a bid opportunity.", "warning")
        return redirect(request.referrer or url_for("executive.construction_center"))

    estimated_value_raw = (request.form.get("estimated_value") or "").replace(",", "").replace("$", "").strip()
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
    return redirect(request.form.get("next") or request.referrer or url_for("executive.construction_center"))


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
    return redirect(request.referrer or url_for("executive.construction_center"))


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
