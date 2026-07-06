from datetime import datetime
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from LoanMVP.extensions import db
from flask_mail import Message as MailMessage

from LoanMVP.extensions import mail
from LoanMVP.models.contractor_models import (
    BidProposal, BidSuggestion, ContractorBidOpportunity, ConstructionProject,
)
from LoanMVP.models.crm_models import Partner

construction_bids_bp = Blueprint("construction_bids", __name__, url_prefix="/construction/bids")


def _construction_return_url(default_endpoint="executive.construction_center"):
    """Return only construction-safe pages after bid actions.

    Some users can enter the flow from partner pages. After saving/sending a
    construction opportunity, never send Jamaine back to the realtor/partner
    dashboard; keep the workflow inside construction.
    """
    next_url = (request.form.get("next") or "").strip()
    referrer = (request.referrer or "").strip()
    fallback = url_for(default_endpoint)

    allowed_prefixes = (
        "/executive/construction",
        "/construction/bids",
        "/construction-office/packages",
    )

    for candidate in (next_url, referrer):
        if not candidate:
            continue
        parsed = urlparse(candidate)
        path = parsed.path or candidate
        if any(path.startswith(prefix) for prefix in allowed_prefixes):
            return candidate if parsed.scheme else path

    return fallback


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
        or role in {"executive", "platform_admin", "master_admin", "lending_admin"}
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
        or role in {"executive", "platform_admin", "master_admin", "lending_admin"}
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

    suggestions = []
    dismissed   = []
    if partner:
        try:
            all_sugg  = (
                BidSuggestion.query
                .filter_by(partner_id=partner.id)
                .order_by(BidSuggestion.created_at.desc())
                .all()
            )
            suggestions = [s for s in all_sugg if s.status in ("active", "follow_up")]
            dismissed   = [s for s in all_sugg if s.status == "not_interested"]
        except Exception as exc:
            current_app.logger.warning("[search_page] suggestions table not ready: %s", exc)
            db.session.rollback()

    return render_template(
        "construction/bid_search.html",
        partner=partner,
        recent_opportunities=recent_opportunities,
        search_terms=search_terms,
        suggestions=suggestions,
        dismissed=dismissed,
    )


@construction_bids_bp.route("/suggestions/add", methods=["POST"])
@login_required
def add_suggestion():
    """Manually add a suggested opportunity to the search board."""
    if not _can_use_bid_handoff():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    partner = _current_partner()
    if not partner:
        flash("Partner profile not found.", "warning")
        return redirect(url_for("construction_bids.search_page"))

    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Opportunity title is required.", "warning")
        return redirect(url_for("construction_bids.search_page"))

    est_raw = (request.form.get("estimated_value") or "").replace(",", "").strip()
    estimated_value = None
    if est_raw:
        try:
            estimated_value = float(est_raw)
        except ValueError:
            pass

    due_date = None
    due_raw = (request.form.get("due_date") or "").strip()
    if due_raw:
        try:
            due_date = datetime.strptime(due_raw, "%Y-%m-%d")
        except ValueError:
            pass

    sugg = BidSuggestion(
        partner_id      = partner.id,
        title           = title,
        category        = (request.form.get("category") or "").strip() or None,
        source_name     = (request.form.get("source_name") or "").strip() or None,
        source_url      = (request.form.get("source_url") or "").strip() or None,
        location        = (request.form.get("location") or "").strip() or None,
        due_date        = due_date,
        estimated_value = estimated_value,
        contact         = (request.form.get("contact") or "").strip() or None,
        summary         = (request.form.get("summary") or "").strip() or None,
        status          = "active",
    )
    db.session.add(sugg)
    db.session.commit()
    flash("Opportunity added to the search board.", "success")
    return redirect(url_for("construction_bids.search_page"))


@construction_bids_bp.route("/suggestions/<int:suggestion_id>/action", methods=["POST"])
@login_required
def suggestion_action(suggestion_id):
    """Act on a suggested opportunity: save, send to Sandra, dismiss, or follow-up."""
    if not _can_use_bid_handoff():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    sugg   = BidSuggestion.query.get_or_404(suggestion_id)
    action = (request.form.get("action") or "").strip().lower()

    if action in ("save", "send_to_sandra"):
        bid_status = "saved_opportunity" if action == "save" else "bid_package_needed"
        existing = ContractorBidOpportunity.query.filter_by(
            partner_id   = sugg.partner_id,
            project_name = sugg.title,
        ).first()
        if existing:
            flash(f"'{sugg.title}' is already in the bid pipeline.", "info")
        else:
            opp = ContractorBidOpportunity(
                partner_id      = sugg.partner_id,
                project_name    = sugg.title,
                source          = sugg.source_name or "Bid Search",
                category        = sugg.category,
                location        = sugg.location,
                estimated_value = sugg.estimated_value,
                bid_deadline    = sugg.due_date,
                notes           = sugg.summary,
                status          = bid_status,
            )
            db.session.add(opp)
        sugg.status = "saved"
        db.session.commit()
        if action == "save":
            flash(f"'{sugg.title}' saved to the bid pipeline.", "success")
        else:
            flash(f"'{sugg.title}' sent to Sandra for bid package preparation.", "success")

    elif action == "not_interested":
        sugg.status = "not_interested"
        db.session.commit()
        flash(f"'{sugg.title}' dismissed.", "info")

    elif action == "follow_up":
        sugg.status = "follow_up"
        db.session.commit()
        flash(f"'{sugg.title}' marked for follow-up.", "info")

    else:
        flash("Unknown action.", "warning")

    return redirect(url_for("construction_bids.search_page"))


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
        return redirect(_construction_return_url())

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
    return redirect(_construction_return_url())


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
    return redirect(_construction_return_url())


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
        "approval_needed",
        "approved_to_submit",
        "ready_to_send",
        "bid_submitted",
        "client_review",
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
        return redirect(_construction_return_url())

    opportunity = ContractorBidOpportunity.query.get_or_404(opportunity_id)
    old_status = opportunity.status
    opportunity.status = new_status

    note = (request.form.get("workflow_note") or "").strip()
    if note or old_status != new_status:
        existing_notes = opportunity.notes or ""
        note_lines = [existing_notes] if existing_notes else []
        actor = (getattr(current_user, "first_name", None) or getattr(current_user, "email", "") or "Team").strip()
        note_lines.append(
            f"Workflow updated by {actor} on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}: "
            f"{old_status or 'none'} → {new_status}"
        )
        if note:
            note_lines.append(f"Workflow note: {note}")
        opportunity.notes = "\n".join(note_lines)

    db.session.commit()

    # When a bid is won, automatically spin up a construction project
    if new_status == "won":
        try:
            existing = ConstructionProject.query.filter_by(bid_opportunity_id=opportunity.id).first()
            if existing:
                flash(
                    f"Bid marked as Won. Project already exists — "
                    f"<a href=\"{url_for('construction_projects.project_detail', project_id=existing.id)}\" "
                    f"style=\"color:#2cb67d;text-decoration:underline;\">View Project →</a>",
                    "info",
                )
            else:
                project = ConstructionProject(
                    bid_opportunity_id = opportunity.id,
                    partner_id         = opportunity.partner_id,
                    project_name       = opportunity.project_name,
                    location           = opportunity.location,
                    category           = opportunity.category,
                    source             = opportunity.source,
                    estimated_value    = opportunity.estimated_value,
                    contract_amount    = opportunity.estimated_value,
                    notes              = opportunity.notes,
                    bid_date           = opportunity.bid_deadline,
                    project_manager    = "Jamaine Caughman",
                    office_coordinator = "Sandra",
                    executive          = "Letoya",
                    status             = "pre_construction",
                )
                db.session.add(project)
                db.session.commit()
                flash(
                    f"Bid marked as Won. Construction project created — "
                    f"<a href=\"{url_for('construction_projects.project_detail', project_id=project.id)}\" "
                    f"style=\"color:#2cb67d;text-decoration:underline;\">Open Project →</a>",
                    "success",
                )
        except Exception as exc:
            current_app.logger.error("auto project creation failed for bid %s: %s", opportunity_id, exc)
            db.session.rollback()
            flash("Bid marked as Won. Project creation failed — create it manually from the Projects page.", "warning")
        return redirect(url_for("construction_projects.project_list"))

    flash("Bid status updated.", "success")
    return redirect(_construction_return_url())


@construction_bids_bp.route("/<int:bid_id>/proposal", methods=["GET", "POST"])
@login_required
def bid_proposal(bid_id):
    """Build and view the client-facing proposal for a bid opportunity."""
    if not _can_use_bid_handoff():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    bid = ContractorBidOpportunity.query.get_or_404(bid_id)
    proposal = bid.proposal

    if request.method == "POST":
        if proposal is None:
            partner = _current_partner()
            proposal = BidProposal(
                bid_opportunity_id=bid.id,
                partner_id=partner.id if partner else bid.partner_id,
            )
            db.session.add(proposal)

        proposal.client_name    = (request.form.get("client_name")    or "").strip() or None
        proposal.client_email   = (request.form.get("client_email")   or "").strip() or None
        proposal.client_phone   = (request.form.get("client_phone")   or "").strip() or None
        proposal.client_address = (request.form.get("client_address") or "").strip() or None
        proposal.scope_of_work  = (request.form.get("scope_of_work")  or "").strip() or None
        proposal.terms          = (request.form.get("terms")          or "").strip() or None
        proposal.notes_for_client = (request.form.get("notes_for_client") or "").strip() or None
        proposal.prepared_by    = (request.form.get("prepared_by")    or "").strip() or "Caughman Mason Construction"

        raw_follow_up = (request.form.get("follow_up_date") or "").strip()
        if raw_follow_up:
            try:
                from datetime import date
                proposal.follow_up_date = date.fromisoformat(raw_follow_up)
            except ValueError:
                pass
        else:
            proposal.follow_up_date = None

        # Line items: each row posted as line_desc_N / line_qty_N / line_unit_N / line_unit_cost_N
        items = []
        i = 0
        while True:
            desc = request.form.get(f"line_desc_{i}")
            if desc is None:
                break
            desc = desc.strip()
            if desc:
                try:
                    qty       = float(request.form.get(f"line_qty_{i}") or 1)
                    unit_cost = float(request.form.get(f"line_unit_cost_{i}") or 0)
                except ValueError:
                    qty = 1
                    unit_cost = 0.0
                items.append({
                    "desc":      desc,
                    "qty":       qty,
                    "unit":      (request.form.get(f"line_unit_{i}") or "").strip() or "LS",
                    "unit_cost": unit_cost,
                    "total":     round(qty * unit_cost, 2),
                })
            i += 1

        proposal.line_items = items if items else None
        db.session.commit()
        flash("Proposal saved.", "success")
        return redirect(url_for("construction_bids.bid_proposal", bid_id=bid_id))

    return render_template(
        "construction/bid_proposal.html",
        bid=bid,
        proposal=proposal,
    )


@construction_bids_bp.route("/<int:bid_id>/proposal/send", methods=["POST"])
@login_required
def bid_proposal_send(bid_id):
    """Mark a proposal as sent and optionally email it to the client."""
    if not _can_use_bid_handoff():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    bid = ContractorBidOpportunity.query.get_or_404(bid_id)
    proposal = bid.proposal
    if not proposal:
        flash("Save the proposal first before sending.", "warning")
        return redirect(url_for("construction_bids.bid_proposal", bid_id=bid_id))

    actor = (
        getattr(current_user, "first_name", None)
        or getattr(current_user, "email", None)
        or "Team"
    ).strip()

    # Update client email if provided in the send form
    new_email = (request.form.get("client_email") or "").strip()
    if new_email:
        proposal.client_email = new_email

    proposal.sent_at = datetime.utcnow()
    proposal.sent_by = actor

    raw_follow_up = (request.form.get("follow_up_date") or "").strip()
    if raw_follow_up:
        try:
            from datetime import date
            proposal.follow_up_date = date.fromisoformat(raw_follow_up)
        except ValueError:
            pass

    db.session.commit()

    # Attempt to email the proposal to the client
    if proposal.client_email:
        try:
            total = sum(item.get("total", 0) for item in (proposal.line_items or []))
            line_rows = ""
            for item in (proposal.line_items or []):
                line_rows += (
                    f"<tr><td style='padding:8px 12px;border-bottom:1px solid #e5e7eb'>{item['desc']}</td>"
                    f"<td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;text-align:center'>{item['qty']} {item.get('unit','LS')}</td>"
                    f"<td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;text-align:right'>${item['unit_cost']:,.2f}</td>"
                    f"<td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;text-align:right;font-weight:600'>${item['total']:,.2f}</td></tr>"
                )
            scope_html = (proposal.scope_of_work or "").replace("\n", "<br>")
            msg = MailMessage(
                subject=f"Proposal — {bid.project_name} | Caughman Mason Construction",
                sender=current_app.config.get("MAIL_DEFAULT_SENDER", "noreply@ravlohq.com"),
                recipients=[proposal.client_email],
                html=f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;padding:32px 16px;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);">
  <tr><td style="background:#1a2635;padding:32px 40px;">
    <p style="color:#c9a84c;font-size:12px;letter-spacing:.1em;text-transform:uppercase;margin:0 0 8px;">Construction Proposal</p>
    <h1 style="color:#fff;font-size:22px;font-weight:700;margin:0 0 4px;">{bid.project_name}</h1>
    <p style="color:#94a3b8;font-size:13px;margin:0;">{bid.location or ''}</p>
  </td></tr>
  <tr><td style="padding:32px 40px;">
    <p style="font-size:13px;color:#6b7280;margin:0 0 24px;">Date: {proposal.sent_at.strftime('%B %d, %Y')}</p>
    {'<p style="font-size:14px;color:#374151;margin:0 0 4px;"><strong>Prepared for:</strong> ' + (proposal.client_name or '') + '</p>' if proposal.client_name else ''}
    {'<p style="font-size:13px;color:#6b7280;margin:0 0 24px;">' + (proposal.client_address or '') + '</p>' if proposal.client_address else '<br>'}

    {'<h3 style="font-size:14px;font-weight:700;color:#1a2635;margin:0 0 12px;text-transform:uppercase;letter-spacing:.05em;">Scope of Work</h3><p style="font-size:14px;color:#374151;line-height:1.7;margin:0 0 24px;">' + scope_html + '</p>' if proposal.scope_of_work else ''}

    {'<h3 style="font-size:14px;font-weight:700;color:#1a2635;margin:0 0 12px;text-transform:uppercase;letter-spacing:.05em;">Line Items</h3><table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;margin-bottom:24px;"><thead><tr style="background:#f9fafb;"><th style="padding:10px 12px;text-align:left;font-size:12px;color:#6b7280">Description</th><th style="padding:10px 12px;text-align:center;font-size:12px;color:#6b7280">Qty</th><th style="padding:10px 12px;text-align:right;font-size:12px;color:#6b7280">Unit Cost</th><th style="padding:10px 12px;text-align:right;font-size:12px;color:#6b7280">Total</th></tr></thead><tbody>' + line_rows + '</tbody><tfoot><tr style="background:#f9fafb"><td colspan="3" style="padding:12px;font-weight:700;text-align:right;font-size:14px;color:#1a2635">Total</td><td style="padding:12px;font-weight:700;text-align:right;font-size:16px;color:#c9a84c">${total:,.2f}</td></tr></tfoot></table>' if proposal.line_items else ''}

    {'<h3 style="font-size:14px;font-weight:700;color:#1a2635;margin:0 0 8px;text-transform:uppercase;letter-spacing:.05em;">Terms</h3><p style="font-size:13px;color:#6b7280;line-height:1.65;margin:0 0 24px;">' + (proposal.terms or '').replace(chr(10), '<br>') + '</p>' if proposal.terms else ''}
    {'<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:6px;padding:16px 20px;margin-bottom:24px;"><p style="font-size:13px;color:#92400e;margin:0;">' + (proposal.notes_for_client or '').replace(chr(10), '<br>') + '</p></div>' if proposal.notes_for_client else ''}

    <div style="border-top:1px solid #e5e7eb;padding-top:24px;margin-top:8px;">
      <p style="font-size:13px;color:#374151;margin:0 0 4px;"><strong>Prepared by:</strong> {proposal.prepared_by or 'Caughman Mason Construction'}</p>
      <p style="font-size:13px;color:#6b7280;margin:0;">Questions? Reply to this email or call us directly.</p>
    </div>
  </td></tr>
</table>
</td></tr>
</table>
</body></html>""",
            )
            mail.send(msg)
            flash(f"Proposal sent to {proposal.client_email}.", "success")
        except Exception as exc:
            current_app.logger.warning("[bid_proposal_send] email failed: %s", exc)
            flash("Proposal marked as sent, but the email could not be delivered. Check mail config.", "warning")
    else:
        flash("Proposal marked as sent. Add a client email to send it by email.", "info")

    # Update bid status to reflect submission
    if bid.status not in {"bid_submitted", "follow_up_needed", "won", "lost", "paid"}:
        bid.status = "bid_submitted"
        db.session.commit()

    return redirect(url_for("construction_bids.bid_proposal", bid_id=bid_id))
