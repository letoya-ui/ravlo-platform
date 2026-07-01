"""
LoanMVP/routes/construction_projects.py

Construction project lifecycle — from won bid to completed job.

Routes (all require login + bid-handoff access):
  POST /construction/projects/from-bid/<bid_id>   → create or retrieve project
  GET  /construction/projects/                     → project list
  GET  /construction/projects/<project_id>         → project detail
  POST /construction/projects/<project_id>/status  → update lifecycle status
  POST /construction/projects/<project_id>/notes   → update notes
"""

from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from LoanMVP.extensions import db
from LoanMVP.models.contractor_models import ContractorBidOpportunity, ConstructionProject
from LoanMVP.models.crm_models import Partner
from sqlalchemy import func

construction_projects_bp = Blueprint(
    "construction_projects", __name__, url_prefix="/construction/projects"
)

PROJECT_STATUSES = [
    ("pre_construction", "Pre-Construction",  "#5FA8FF"),
    ("active",           "Active",            "#2cb67d"),
    ("on_hold",          "On Hold",           "#f5b942"),
    ("punch_list",       "Punch List",        "#a78bfa"),
    ("completed",        "Completed",         "#2cb67d"),
    ("invoiced",         "Invoiced",          "#eab308"),
    ("paid",             "Paid",              "#34d399"),
    ("cancelled",        "Cancelled",         "#f87171"),
]
_STATUS_KEYS  = {s[0] for s in PROJECT_STATUSES}
_STATUS_COLOR = {s[0]: s[2] for s in PROJECT_STATUSES}
_STATUS_LABEL = {s[0]: s[1] for s in PROJECT_STATUSES}


def _can_access(user=None) -> bool:
    u = user or current_user
    email = (getattr(u, "email", "") or "").strip().lower()
    role  = (getattr(u, "role",  "") or "").strip().lower()
    return email in {
        "jamaine.caughman@ravlohq.com",
        "sandra@ravlohq.com",
        "letoya@ravlohq.com",
    } or role in {"executive", "platform_admin", "master_admin", "lending_admin", "partner", "contractor"}


def _current_partner():
    partner = Partner.query.filter_by(user_id=current_user.id).first()
    if partner:
        return partner
    return Partner.query.filter(
        func.lower(Partner.company) == "caughman mason construction"
    ).first()


def _project_from_bid(bid: ContractorBidOpportunity) -> ConstructionProject:
    """Create a ConstructionProject from a won bid. Idempotent — returns
    existing project if one already exists for this bid."""
    existing = ConstructionProject.query.filter_by(bid_opportunity_id=bid.id).first()
    if existing:
        return existing

    partner = Partner.query.get(bid.partner_id)
    project = ConstructionProject(
        bid_opportunity_id   = bid.id,
        partner_id           = bid.partner_id,
        project_name         = bid.project_name,
        location             = bid.location,
        category             = bid.category,
        source               = bid.source,
        estimated_value      = bid.estimated_value,
        contract_amount      = bid.estimated_value,  # editable on detail page
        notes                = bid.notes,
        bid_date             = bid.bid_deadline,
        project_manager      = "Jamaine Caughman",
        office_coordinator   = "Sandra",
        executive            = "Letoya",
        status               = "pre_construction",
    )
    db.session.add(project)
    db.session.commit()
    return project


# ── Routes ───────────────────────────────────────────────────────────────────

@construction_projects_bp.route("/from-bid/<int:bid_id>", methods=["POST"])
@login_required
def create_from_bid(bid_id):
    """Convert a won bid opportunity into a construction project."""
    if not _can_access():
        flash("You do not have access to construction projects.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    bid = ContractorBidOpportunity.query.get_or_404(bid_id)

    existing = ConstructionProject.query.filter_by(bid_opportunity_id=bid.id).first()
    if existing:
        flash(f"A project already exists for '{bid.project_name}'.", "info")
        return redirect(url_for("construction_projects.project_detail", project_id=existing.id))

    try:
        project = _project_from_bid(bid)
        flash(f"Project created: {project.project_name}", "success")
        return redirect(url_for("construction_projects.project_detail", project_id=project.id))
    except Exception as exc:
        current_app.logger.error("create_from_bid error: %s", exc)
        db.session.rollback()
        flash("Could not create project. Please try again.", "danger")
        return redirect(url_for("executive.construction_center"))


@construction_projects_bp.route("/", methods=["GET"])
@login_required
def project_list():
    """List all construction projects."""
    if not _can_access():
        flash("You do not have access to construction projects.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    status_filter = request.args.get("status", "").strip().lower()

    try:
        q = ConstructionProject.query.order_by(
            ConstructionProject.updated_at.desc(),
            ConstructionProject.created_at.desc(),
        )
        if status_filter and status_filter in _STATUS_KEYS:
            q = q.filter(ConstructionProject.status == status_filter)
        projects = q.all()
    except Exception as exc:
        current_app.logger.warning("project_list error: %s", exc)
        db.session.rollback()
        projects = []

    return render_template(
        "executive/construction_projects.html",
        projects        = projects,
        statuses        = PROJECT_STATUSES,
        status_color    = _STATUS_COLOR,
        status_label    = _STATUS_LABEL,
        active_filter   = status_filter,
    )


@construction_projects_bp.route("/<int:project_id>", methods=["GET"])
@login_required
def project_detail(project_id):
    """Detail view for a single construction project."""
    if not _can_access():
        flash("You do not have access to construction projects.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    project = ConstructionProject.query.get_or_404(project_id)

    return render_template(
        "executive/construction_project_detail.html",
        project      = project,
        statuses     = PROJECT_STATUSES,
        status_color = _STATUS_COLOR,
        status_label = _STATUS_LABEL,
    )


@construction_projects_bp.route("/<int:project_id>/status", methods=["POST"])
@login_required
def update_status(project_id):
    """Update the lifecycle status of a project."""
    if not _can_access():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    project    = ConstructionProject.query.get_or_404(project_id)
    new_status = (request.form.get("status") or "").strip().lower()

    if new_status not in _STATUS_KEYS:
        flash("Invalid status.", "warning")
        return redirect(url_for("construction_projects.project_detail", project_id=project_id))

    project.status = new_status

    # Auto-set start_date when first activated
    if new_status == "active" and not project.start_date:
        project.start_date = datetime.utcnow()

    # Auto-set actual_completion when completed/paid
    if new_status in {"completed", "paid"} and not project.actual_completion:
        project.actual_completion = datetime.utcnow()

    db.session.commit()
    flash(f"Status updated to {_STATUS_LABEL.get(new_status, new_status)}.", "success")
    return redirect(url_for("construction_projects.project_detail", project_id=project_id))


@construction_projects_bp.route("/<int:project_id>/notes", methods=["POST"])
@login_required
def update_notes(project_id):
    """Append or replace project notes."""
    if not _can_access():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    project = ConstructionProject.query.get_or_404(project_id)

    new_note = (request.form.get("note") or "").strip()
    if new_note:
        timestamp   = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        author      = getattr(current_user, "first_name", None) or getattr(current_user, "email", "Team")
        entry       = f"[{timestamp} — {author}] {new_note}"
        existing    = project.notes or ""
        project.notes = (existing + "\n\n" + entry).strip()
        db.session.commit()
        flash("Note added.", "success")

    return redirect(url_for("construction_projects.project_detail", project_id=project_id))


@construction_projects_bp.route("/<int:project_id>/edit", methods=["POST"])
@login_required
def update_fields(project_id):
    """Update editable project fields (contract amount, dates, team)."""
    if not _can_access():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    project = ConstructionProject.query.get_or_404(project_id)

    contract_raw = (request.form.get("contract_amount") or "").replace(",", "").strip()
    if contract_raw:
        try:
            project.contract_amount = float(contract_raw)
        except ValueError:
            pass

    for date_field in ("start_date", "estimated_completion", "actual_completion"):
        raw = (request.form.get(date_field) or "").strip()
        if raw:
            try:
                setattr(project, date_field, datetime.strptime(raw, "%Y-%m-%d"))
            except ValueError:
                pass

    for text_field in ("project_manager", "office_coordinator", "executive", "location", "category"):
        val = (request.form.get(text_field) or "").strip()
        if val:
            setattr(project, text_field, val)

    db.session.commit()
    flash("Project updated.", "success")
    return redirect(url_for("construction_projects.project_detail", project_id=project_id))
