# ===============================================================
#   RAVLO — ACCOUNT EXECUTIVE (Lending OS licensing pipeline)
# ===============================================================
"""Sales pipeline for account executives licensing out Ravlo Lending OS
to prospective lending companies.

Builds on the existing BusinessInquiry model (inquiry_type ==
"license_application") -- Ravlo's existing "prospective company wants to
license Lending OS" intake, previously only worked by admin staff via
admin.py's licensing_applications page. This module adds an AE-facing
deal pipeline (ae_stage), contract terms, and commission tracking on top
of the same rows, without touching the existing `status` field or the
admin approve/decline/Company-creation workflow -- those stay entirely
separate. Marking a deal "signed" here does NOT auto-create a Company;
a Ravlo admin still does that manually via the existing licensing
applications page (see admin.py's approve_license_application), and an
AE (or admin) later links the resulting Company back to this deal via
the "link_company" action for commission/reporting purposes.
"""

import csv
import io
import uuid
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user, login_required
from sqlalchemy import func

from LoanMVP.extensions import db
from LoanMVP.utils.decorators import role_required
from LoanMVP.models.admin import BusinessInquiry, Company
from LoanMVP.models.user_model import User

account_executive_bp = Blueprint("account_executive", __name__, url_prefix="/account-executive")

AE_STAGES = ["prospect", "contacted", "demo_scheduled", "demo_completed", "contract_sent", "signed", "lost"]
DEFAULT_COMMISSION_RATE = Decimal("0.10")

# Mirrors admin.py's FULL_ADMIN_ROLES minus lending_admin -- role_required
# already lets platform_admin/master_admin/executive through every check
# (see LoanMVP/utils/decorators.py), so these are the roles that see every
# AE's deals rather than just their own.
FULL_VISIBILITY_ROLES = {"platform_admin", "master_admin", "executive"}


def _is_full_visibility(user) -> bool:
    return (getattr(user, "role", "") or "").strip().lower() in FULL_VISIBILITY_ROLES


def _deals_query():
    query = BusinessInquiry.query.filter_by(inquiry_type="license_application")
    if _is_full_visibility(current_user):
        return query
    return query.filter_by(assigned_ae_id=current_user.id)


def _can_view_deal(deal) -> bool:
    if _is_full_visibility(current_user):
        return True
    return deal.assigned_ae_id in (None, current_user.id)


def _to_decimal(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _compute_commission(contract_value, commission_rate):
    if contract_value is None or commission_rate is None:
        return None
    return (Decimal(contract_value) * Decimal(commission_rate)).quantize(Decimal("0.01"))


# company_name/contact_name/email are all NOT NULL on BusinessInquiry, but a
# freshly-imported prospect frequently has no known contact yet -- these are
# obvious, internal-only placeholders (never a real-looking name/address) so
# the row satisfies the schema until an AE fills in the real contact via the
# "update_contact" action below.
_PLACEHOLDER_CONTACT_NAME = "Unknown Contact"


def _placeholder_email() -> str:
    return f"no-contact-{uuid.uuid4().hex[:10]}@prospects.internal"


# ===============================================================
#   DASHBOARD
# ===============================================================
@account_executive_bp.route("/dashboard")
@login_required
@role_required("account_executive")
def dashboard():
    deals = _deals_query().all()
    stage_counts = Counter((d.ae_stage or "prospect") for d in deals)

    pending_commission = sum((d.commission_amount or 0) for d in deals if d.commission_status == "pending")
    paid_commission = sum((d.commission_amount or 0) for d in deals if d.commission_status == "paid")
    signed_count = sum(1 for d in deals if d.ae_stage == "signed")

    recent_deals = sorted(deals, key=lambda d: d.created_at, reverse=True)[:8]

    return render_template(
        "account_executive/dashboard.html",
        deals=deals,
        stage_counts=stage_counts,
        ae_stages=AE_STAGES,
        pending_commission=pending_commission,
        paid_commission=paid_commission,
        signed_count=signed_count,
        recent_deals=recent_deals,
        title="Account Executive Dashboard",
        active_tab="dashboard",
    )


# ===============================================================
#   DEAL LIST
# ===============================================================
@account_executive_bp.route("/deals")
@login_required
@role_required("account_executive")
def deals():
    stage_filter = (request.args.get("stage") or "").strip().lower()
    query = _deals_query()
    if stage_filter in AE_STAGES:
        query = query.filter_by(ae_stage=stage_filter)

    deal_rows = query.order_by(BusinessInquiry.created_at.desc()).all()

    return render_template(
        "account_executive/deals.html",
        deals=deal_rows,
        ae_stages=AE_STAGES,
        stage_filter=stage_filter,
        title="Deal Pipeline",
        active_tab="deals",
    )


# ===============================================================
#   NEW DEAL
# ===============================================================
@account_executive_bp.route("/deals/new", methods=["GET", "POST"])
@login_required
@role_required("account_executive")
def new_deal():
    if request.method == "POST":
        company_name = (request.form.get("company_name") or "").strip()
        contact_name = (request.form.get("contact_name") or "").strip()
        email = (request.form.get("email") or "").strip()

        if not company_name or not contact_name or not email:
            flash("Company name, contact name, and email are required.", "danger")
            return redirect(url_for("account_executive.new_deal"))

        assigned_ae_id = current_user.id
        if _is_full_visibility(current_user):
            picked = request.form.get("assigned_ae_id")
            assigned_ae_id = int(picked) if picked else None

        deal = BusinessInquiry(
            inquiry_type="license_application",
            company_name=company_name,
            contact_name=contact_name,
            email=email,
            phone=(request.form.get("phone") or "").strip() or None,
            website=(request.form.get("website") or "").strip() or None,
            business_type=(request.form.get("business_type") or "").strip() or None,
            plan_interest=(request.form.get("plan_interest") or "").strip() or None,
            monthly_loan_volume=(request.form.get("monthly_loan_volume") or "").strip() or None,
            notes=(request.form.get("notes") or "").strip() or None,
            status="new",
            assigned_ae_id=assigned_ae_id,
            ae_stage="prospect",
        )
        db.session.add(deal)
        db.session.commit()

        flash("New deal added to your pipeline.", "success")
        return redirect(url_for("account_executive.deal_detail", deal_id=deal.id))

    ae_users = []
    if _is_full_visibility(current_user):
        ae_users = User.query.filter_by(role="account_executive").order_by(User.email).all()

    return render_template(
        "account_executive/new_deal.html",
        ae_users=ae_users,
        title="New Deal",
        active_tab="new_deal",
    )


# ===============================================================
#   PROSPECT POOL (unclaimed target companies any AE can pick up)
# ===============================================================
@account_executive_bp.route("/prospects")
@login_required
@role_required("account_executive")
def prospects():
    pool = (
        BusinessInquiry.query
        .filter_by(inquiry_type="license_application", ae_stage="prospect", assigned_ae_id=None)
        .order_by(BusinessInquiry.created_at.desc())
        .all()
    )

    return render_template(
        "account_executive/prospects.html",
        prospects=pool,
        is_full_visibility=_is_full_visibility(current_user),
        title="Prospect Pool",
        active_tab="prospects",
    )


# ===============================================================
#   IMPORT PROSPECTS (CSV bulk-add to the pool -- Ravlo staff only)
# ===============================================================
@account_executive_bp.route("/prospects/import", methods=["GET", "POST"])
@login_required
@role_required("account_executive")
def import_prospects():
    if not _is_full_visibility(current_user):
        flash("Only Ravlo staff can import prospect lists.", "danger")
        return redirect(url_for("account_executive.prospects"))

    if request.method == "POST":
        upload = request.files.get("csv_file")
        if not upload or not upload.filename:
            flash("Choose a CSV file to import.", "danger")
            return redirect(url_for("account_executive.import_prospects"))

        try:
            raw = upload.stream.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(raw))
        except Exception:
            flash("Could not read that file. Make sure it's a CSV.", "danger")
            return redirect(url_for("account_executive.import_prospects"))

        fieldnames = {(name or "").strip().lower() for name in (reader.fieldnames or [])}
        if "company_name" not in fieldnames:
            flash("CSV must include at least a 'company_name' column.", "danger")
            return redirect(url_for("account_executive.import_prospects"))

        created = 0
        skipped = 0

        for row in reader:
            normalized = {(key or "").strip().lower(): (value or "").strip() for key, value in row.items()}
            company_name = normalized.get("company_name")
            if not company_name:
                skipped += 1
                continue

            duplicate = BusinessInquiry.query.filter(
                BusinessInquiry.inquiry_type == "license_application",
                func.lower(BusinessInquiry.company_name) == company_name.lower(),
            ).first()
            if duplicate:
                skipped += 1
                continue

            db.session.add(BusinessInquiry(
                inquiry_type="license_application",
                company_name=company_name,
                contact_name=normalized.get("contact_name") or _PLACEHOLDER_CONTACT_NAME,
                email=normalized.get("email") or _placeholder_email(),
                phone=normalized.get("phone") or None,
                website=normalized.get("website") or None,
                business_type=normalized.get("business_type") or None,
                notes=normalized.get("notes") or None,
                status="new",
                assigned_ae_id=None,
                ae_stage="prospect",
            ))
            created += 1

        db.session.commit()
        flash(f"Imported {created} new prospect(s). Skipped {skipped} (duplicate company or missing name).", "success")
        return redirect(url_for("account_executive.prospects"))

    return render_template(
        "account_executive/import_prospects.html",
        title="Import Prospects",
        active_tab="prospects",
    )


# ===============================================================
#   DEAL DETAIL
# ===============================================================
@account_executive_bp.route("/deals/<int:deal_id>", methods=["GET", "POST"])
@login_required
@role_required("account_executive")
def deal_detail(deal_id):
    deal = BusinessInquiry.query.get_or_404(deal_id)
    if deal.inquiry_type != "license_application":
        abort(404)
    if not _can_view_deal(deal):
        flash("You don't have access to that deal.", "warning")
        return redirect(url_for("account_executive.deals"))

    if request.method == "POST":
        action_type = request.form.get("action_type")

        if action_type == "claim":
            if deal.assigned_ae_id is None:
                deal.assigned_ae_id = current_user.id
                db.session.commit()
                flash("Deal claimed.", "success")
            else:
                flash("This deal is already assigned.", "warning")

        elif action_type == "update_stage":
            new_stage = (request.form.get("ae_stage") or "").strip().lower()
            if new_stage not in AE_STAGES:
                flash("Invalid stage.", "danger")
            elif new_stage == "lost":
                deal.ae_stage = "lost"
                deal.lost_reason = (request.form.get("lost_reason") or "").strip() or None
                db.session.commit()
                flash("Deal marked lost.", "info")
            elif new_stage == "signed":
                contract_value = _to_decimal(request.form.get("contract_value"))
                commission_rate = _to_decimal(request.form.get("commission_rate")) or DEFAULT_COMMISSION_RATE
                if contract_value is None:
                    flash("Enter the contract value to mark this deal signed.", "danger")
                else:
                    deal.contract_value = contract_value
                    deal.commission_rate = commission_rate
                    deal.billing_cycle = (request.form.get("billing_cycle") or deal.billing_cycle or "annual")
                    deal.commission_amount = _compute_commission(deal.contract_value, deal.commission_rate)
                    deal.commission_status = "pending"
                    deal.ae_stage = "signed"
                    deal.signed_at = datetime.utcnow()
                    db.session.commit()
                    flash(
                        "Deal marked signed and commission calculated. "
                        "A Ravlo admin still needs to approve the license application "
                        "to create the live company account.",
                        "success",
                    )
            else:
                deal.ae_stage = new_stage
                db.session.commit()
                flash("Stage updated.", "success")

        elif action_type == "update_terms":
            contract_value = _to_decimal(request.form.get("contract_value"))
            commission_rate = _to_decimal(request.form.get("commission_rate"))
            if contract_value is not None:
                deal.contract_value = contract_value
            if commission_rate is not None:
                deal.commission_rate = commission_rate
            billing_cycle = (request.form.get("billing_cycle") or "").strip()
            if billing_cycle:
                deal.billing_cycle = billing_cycle
            if deal.ae_stage == "signed":
                deal.commission_amount = _compute_commission(deal.contract_value, deal.commission_rate)
            db.session.commit()
            flash("Contract terms updated.", "success")

        elif action_type == "link_company":
            company_id = request.form.get("company_id")
            company = Company.query.get(int(company_id)) if (company_id or "").isdigit() else None
            if not company:
                flash("Select a valid company to link.", "danger")
            else:
                deal.linked_company_id = company.id
                db.session.commit()
                flash(f"Linked to {company.name}.", "success")

        elif action_type == "mark_commission_paid":
            if not _is_full_visibility(current_user):
                flash("Only Ravlo staff can mark commission as paid.", "danger")
            elif deal.commission_status != "pending":
                flash("Commission isn't pending.", "info")
            else:
                deal.commission_status = "paid"
                db.session.commit()
                flash("Commission marked paid.", "success")

        elif action_type == "update_contact":
            contact_name = (request.form.get("contact_name") or "").strip()
            email = (request.form.get("email") or "").strip()
            if not contact_name or not email:
                flash("Contact name and email are required.", "danger")
            else:
                deal.contact_name = contact_name
                deal.email = email
                deal.phone = (request.form.get("phone") or "").strip() or None
                deal.website = (request.form.get("website") or "").strip() or None
                db.session.commit()
                flash("Contact info updated.", "success")

        elif action_type == "add_note":
            note = (request.form.get("note") or "").strip()
            if note:
                stamp = f"[{datetime.utcnow():%Y-%m-%d}] {current_user.email}: {note}"
                deal.notes = f"{deal.notes}\n{stamp}" if deal.notes else stamp
                db.session.commit()
                flash("Note added.", "success")

        return redirect(url_for("account_executive.deal_detail", deal_id=deal.id))

    companies = Company.query.order_by(Company.name).all() if _is_full_visibility(current_user) else []

    return render_template(
        "account_executive/deal_detail.html",
        deal=deal,
        ae_stages=AE_STAGES,
        companies=companies,
        is_full_visibility=_is_full_visibility(current_user),
        title=deal.company_name,
        active_tab="deals",
    )
