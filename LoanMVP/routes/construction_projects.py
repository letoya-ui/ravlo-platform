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
from LoanMVP.models.contractor_models import (
    ContractorBidOpportunity, ConstructionProject,
    ProjectDailyLog, ProjectPhoto, ProjectMilestone,
    ProjectExpenseItem, ProjectInvoice, ProjectChangeOrder,
)
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

    def _safe_list(q):
        try:
            return q.all()
        except Exception as exc:
            current_app.logger.warning("project_detail field query failed: %s", exc)
            db.session.rollback()
            return []

    daily_logs    = _safe_list(project.daily_logs.order_by(ProjectDailyLog.log_date.desc()))
    photos        = _safe_list(project.photos.order_by(ProjectPhoto.created_at.desc()))
    milestones    = _safe_list(project.milestones.order_by(ProjectMilestone.sort_order, ProjectMilestone.due_date))
    expense_items = _safe_list(project.expense_items.order_by(ProjectExpenseItem.created_at.desc()))
    invoices      = _safe_list(project.invoices.order_by(ProjectInvoice.issued_date.desc()))
    change_orders = _safe_list(project.change_orders.order_by(ProjectChangeOrder.created_at.desc()))

    expense_total   = sum(e.amount for e in expense_items)
    invoice_total   = sum(i.amount for i in invoices)
    co_approved_total = sum(
        (co.amount or 0) for co in change_orders if co.status == "approved"
    )

    active_tab = request.args.get("tab", "overview")

    return render_template(
        "executive/construction_project_detail.html",
        project          = project,
        statuses         = PROJECT_STATUSES,
        status_color     = _STATUS_COLOR,
        status_label     = _STATUS_LABEL,
        daily_logs       = daily_logs,
        photos           = photos,
        milestones       = milestones,
        expense_items    = expense_items,
        invoices         = invoices,
        change_orders    = change_orders,
        expense_total    = expense_total,
        invoice_total    = invoice_total,
        co_approved_total = co_approved_total,
        active_tab       = active_tab,
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


# ── Field Tools ────────────────────────────────────────────────────────────────

def _redirect_tab(project_id, tab):
    return redirect(url_for(
        "construction_projects.project_detail",
        project_id=project_id,
        tab=tab,
    ))


@construction_projects_bp.route("/<int:project_id>/daily-log", methods=["POST"])
@login_required
def add_daily_log(project_id):
    if not _can_access():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    project   = ConstructionProject.query.get_or_404(project_id)
    work_done = (request.form.get("work_done") or "").strip()
    if not work_done:
        flash("Work description is required.", "warning")
        return _redirect_tab(project_id, "daily-log")

    raw_date = (request.form.get("log_date") or "").strip()
    try:
        from datetime import date
        log_date = date.fromisoformat(raw_date) if raw_date else date.today()
    except ValueError:
        from datetime import date
        log_date = date.today()

    crew_raw = (request.form.get("crew_size") or "").strip()
    crew_size = None
    if crew_raw:
        try:
            crew_size = int(crew_raw)
        except ValueError:
            pass

    author = (getattr(current_user, "first_name", None) or getattr(current_user, "email", "Team")).strip()
    entry  = ProjectDailyLog(
        project_id = project.id,
        log_date   = log_date,
        crew_size  = crew_size,
        weather    = (request.form.get("weather") or "").strip() or None,
        work_done  = work_done,
        issues     = (request.form.get("issues") or "").strip() or None,
        created_by = author,
    )
    db.session.add(entry)
    db.session.commit()
    flash("Daily log entry added.", "success")
    return _redirect_tab(project_id, "daily-log")


@construction_projects_bp.route("/<int:project_id>/photos", methods=["POST"])
@login_required
def add_photo(project_id):
    if not _can_access():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    project = ConstructionProject.query.get_or_404(project_id)
    url     = (request.form.get("url") or "").strip()
    if not url:
        flash("Photo URL is required.", "warning")
        return _redirect_tab(project_id, "photos")

    author = (getattr(current_user, "first_name", None) or getattr(current_user, "email", "Team")).strip()
    photo  = ProjectPhoto(
        project_id = project.id,
        url        = url,
        caption    = (request.form.get("caption") or "").strip() or None,
        phase      = (request.form.get("phase") or "").strip() or None,
        created_by = author,
    )
    db.session.add(photo)
    db.session.commit()
    flash("Photo added.", "success")
    return _redirect_tab(project_id, "photos")


@construction_projects_bp.route("/<int:project_id>/milestones", methods=["POST"])
@login_required
def add_milestone(project_id):
    if not _can_access():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    project = ConstructionProject.query.get_or_404(project_id)
    title   = (request.form.get("title") or "").strip()
    if not title:
        flash("Milestone title is required.", "warning")
        return _redirect_tab(project_id, "schedule")

    raw_due = (request.form.get("due_date") or "").strip()
    due_date = None
    if raw_due:
        try:
            from datetime import date
            due_date = date.fromisoformat(raw_due)
        except ValueError:
            pass

    existing_count = project.milestones.count()
    milestone = ProjectMilestone(
        project_id = project.id,
        title      = title,
        due_date   = due_date,
        notes      = (request.form.get("notes") or "").strip() or None,
        sort_order = existing_count,
    )
    db.session.add(milestone)
    db.session.commit()
    flash("Milestone added.", "success")
    return _redirect_tab(project_id, "schedule")


@construction_projects_bp.route("/<int:project_id>/milestones/<int:milestone_id>/complete", methods=["POST"])
@login_required
def complete_milestone(project_id, milestone_id):
    if not _can_access():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    milestone = ProjectMilestone.query.get_or_404(milestone_id)
    if milestone.project_id != project_id:
        flash("Not found.", "warning")
        return _redirect_tab(project_id, "schedule")

    milestone.completed_at = None if milestone.completed_at else datetime.utcnow()
    db.session.commit()
    return _redirect_tab(project_id, "schedule")


@construction_projects_bp.route("/<int:project_id>/expenses", methods=["POST"])
@login_required
def add_expense(project_id):
    if not _can_access():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    project     = ConstructionProject.query.get_or_404(project_id)
    description = (request.form.get("description") or "").strip()
    if not description:
        flash("Description is required.", "warning")
        return _redirect_tab(project_id, "expenses")

    amt_raw = (request.form.get("amount") or "").replace(",", "").strip()
    try:
        amount = float(amt_raw)
    except ValueError:
        flash("Invalid amount.", "warning")
        return _redirect_tab(project_id, "expenses")

    raw_paid = (request.form.get("paid_date") or "").strip()
    paid_date = None
    if raw_paid:
        try:
            from datetime import date
            paid_date = date.fromisoformat(raw_paid)
        except ValueError:
            pass

    author  = (getattr(current_user, "first_name", None) or getattr(current_user, "email", "Team")).strip()
    expense = ProjectExpenseItem(
        project_id  = project.id,
        description = description,
        category    = (request.form.get("category") or "Other").strip(),
        amount      = amount,
        paid_date   = paid_date,
        vendor      = (request.form.get("vendor") or "").strip() or None,
        created_by  = author,
    )
    db.session.add(expense)
    db.session.commit()
    flash(f"Expense added: ${amount:,.2f}", "success")
    return _redirect_tab(project_id, "expenses")


@construction_projects_bp.route("/<int:project_id>/invoices", methods=["POST"])
@login_required
def add_invoice(project_id):
    if not _can_access():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    project = ConstructionProject.query.get_or_404(project_id)
    amt_raw = (request.form.get("amount") or "").replace(",", "").strip()
    try:
        amount = float(amt_raw)
    except ValueError:
        flash("Invalid amount.", "warning")
        return _redirect_tab(project_id, "invoices")

    def _parse_date(key):
        raw = (request.form.get(key) or "").strip()
        if raw:
            try:
                from datetime import date
                return date.fromisoformat(raw)
            except ValueError:
                pass
        return None

    author  = (getattr(current_user, "first_name", None) or getattr(current_user, "email", "Team")).strip()

    # Auto-number if blank
    inv_num = (request.form.get("invoice_number") or "").strip()
    if not inv_num:
        count   = project.invoices.count() + 1
        inv_num = f"INV-{project.id:04d}-{count:02d}"

    invoice = ProjectInvoice(
        project_id     = project.id,
        invoice_number = inv_num,
        description    = (request.form.get("description") or "").strip() or None,
        amount         = amount,
        issued_date    = _parse_date("issued_date"),
        due_date       = _parse_date("due_date"),
        paid_date      = _parse_date("paid_date"),
        status         = (request.form.get("status") or "draft").strip(),
        notes          = (request.form.get("notes") or "").strip() or None,
        created_by     = author,
    )
    db.session.add(invoice)
    db.session.commit()
    flash(f"Invoice {inv_num} added.", "success")
    return _redirect_tab(project_id, "invoices")


@construction_projects_bp.route("/<int:project_id>/invoices/<int:invoice_id>/status", methods=["POST"])
@login_required
def update_invoice_status(project_id, invoice_id):
    if not _can_access():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    invoice = ProjectInvoice.query.get_or_404(invoice_id)
    if invoice.project_id != project_id:
        flash("Not found.", "warning")
        return _redirect_tab(project_id, "invoices")

    new_status = (request.form.get("status") or "").strip()
    if new_status in {"draft", "sent", "paid", "overdue"}:
        invoice.status = new_status
        if new_status == "paid" and not invoice.paid_date:
            from datetime import date
            invoice.paid_date = date.today()
        db.session.commit()
        flash("Invoice status updated.", "success")
    return _redirect_tab(project_id, "invoices")


@construction_projects_bp.route("/<int:project_id>/change-orders", methods=["POST"])
@login_required
def add_change_order(project_id):
    if not _can_access():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    project = ConstructionProject.query.get_or_404(project_id)
    title   = (request.form.get("title") or "").strip()
    if not title:
        flash("Change order title is required.", "warning")
        return _redirect_tab(project_id, "change-orders")

    amt_raw = (request.form.get("amount") or "").replace(",", "").strip()
    amount  = None
    if amt_raw:
        try:
            amount = float(amt_raw)
        except ValueError:
            pass

    author = (getattr(current_user, "first_name", None) or getattr(current_user, "email", "Team")).strip()
    co     = ProjectChangeOrder(
        project_id   = project.id,
        title        = title,
        description  = (request.form.get("description") or "").strip() or None,
        amount       = amount,
        status       = "pending",
        requested_by = author,
    )
    db.session.add(co)
    db.session.commit()
    flash("Change order submitted.", "success")
    return _redirect_tab(project_id, "change-orders")


@construction_projects_bp.route("/<int:project_id>/change-orders/<int:co_id>/status", methods=["POST"])
@login_required
def update_change_order_status(project_id, co_id):
    if not _can_access():
        flash("Access denied.", "warning")
        return redirect(url_for("auth.post_login_redirect"))

    co = ProjectChangeOrder.query.get_or_404(co_id)
    if co.project_id != project_id:
        flash("Not found.", "warning")
        return _redirect_tab(project_id, "change-orders")

    new_status = (request.form.get("status") or "").strip()
    if new_status in {"pending", "approved", "rejected"}:
        co.status = new_status
        if new_status == "approved":
            author = (getattr(current_user, "first_name", None) or getattr(current_user, "email", "Team")).strip()
            co.approved_by = author
            co.approved_at = datetime.utcnow()
        db.session.commit()
        flash(f"Change order {new_status}.", "success")
    return _redirect_tab(project_id, "change-orders")
