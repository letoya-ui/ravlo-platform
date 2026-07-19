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
from LoanMVP.models.admin import AECommissionEntry, BusinessInquiry, Company
from LoanMVP.models.user_model import User
from LoanMVP.services import ae_pricing

account_executive_bp = Blueprint("account_executive", __name__, url_prefix="/account-executive")

AE_STAGES = ["prospect", "contacted", "demo_scheduled", "demo_completed", "contract_sent", "signed", "lost"]

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

    deal_ids = [d.id for d in deals]
    entries = AECommissionEntry.query.filter(AECommissionEntry.deal_id.in_(deal_ids)).all() if deal_ids else []
    pending_commission = sum((e.amount for e in entries if e.status == "pending"), Decimal("0.00"))
    paid_commission = sum((e.amount for e in entries if e.status == "paid"), Decimal("0.00"))
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


def _build_quote(deal, form):
    """Reads the AE's quote-calculator inputs, looks up the rate card,
    and stamps the deal with the quoted numbers + required approval
    level -- see LoanMVP/services/ae_pricing.py for the actual figures.
    Returns an error message string, or None on success."""
    pricing_plan = (form.get("pricing_plan") or "").strip().lower()
    if pricing_plan == "enterprise":
        list_price = ae_pricing.enterprise_tier_for_user_count(form.get("enterprise_user_count"))
        if list_price is None:
            return (
                "300+ seat deals are an Executive Quote -- there's no rate-card "
                "number to look up. Work this one directly with an executive."
            )
    else:
        list_price = ae_pricing.STANDARD_PLANS.get(pricing_plan)
        if list_price is None:
            return "Choose a valid pricing plan."

    discount_percent = _to_decimal(form.get("discount_percent")) or Decimal("0")
    setup_fee_waived = _to_decimal(form.get("setup_fee_waived")) or Decimal("0")
    is_white_label = form.get("is_white_label") == "on"
    is_custom_development = form.get("is_custom_development") == "on"
    is_multi_year = form.get("is_multi_year") == "on"
    is_strategic_partnership = form.get("is_strategic_partnership") == "on"

    approval_level = ae_pricing.required_approval_level(
        is_enterprise=(pricing_plan == "enterprise"),
        is_white_label=is_white_label,
        is_custom_development=is_custom_development,
        is_multi_year=is_multi_year,
        is_strategic_partnership=is_strategic_partnership,
        discount_percent=discount_percent,
        setup_fee_waived=setup_fee_waived,
    )
    quoted_setup, quoted_monthly = ae_pricing.compute_quote(
        list_price["setup"], list_price["monthly"], discount_percent, setup_fee_waived
    )

    deal.pricing_plan = pricing_plan
    deal.enterprise_user_count = (
        int(form.get("enterprise_user_count")) if pricing_plan == "enterprise" and (form.get("enterprise_user_count") or "").isdigit() else None
    )
    deal.list_setup_fee = list_price["setup"]
    deal.list_monthly_fee = list_price["monthly"]
    deal.discount_percent = discount_percent
    deal.setup_fee_waived = setup_fee_waived
    deal.is_white_label = is_white_label
    deal.is_custom_development = is_custom_development
    deal.is_multi_year = is_multi_year
    deal.is_strategic_partnership = is_strategic_partnership
    deal.approval_level_required = approval_level
    deal.approval_status = "not_required" if approval_level == "ae" else "pending"
    deal.approved_by_id = None
    deal.approved_at = None

    # The quote is the source of truth for the deal's contract value --
    # an AE can still hand-adjust it later via "update_terms" if the
    # final signed contract differs.
    deal.contract_value = quoted_setup + (quoted_monthly * 12)
    return None


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
                setup_fee = _to_decimal(request.form.get("signed_setup_fee"))
                monthly_fee = _to_decimal(request.form.get("signed_monthly_fee"))
                setup_commission_rate = _to_decimal(request.form.get("setup_commission_rate"))
                monthly_commission_rate = _to_decimal(request.form.get("monthly_commission_rate"))
                renewal_commission_rate = _to_decimal(request.form.get("renewal_commission_rate"))

                if (deal.approval_level_required or "ae") != "ae" and deal.approval_status != "approved":
                    flash(
                        f"This quote requires {(deal.approval_level_required or '').replace('_', ' ').title()} "
                        "approval before it can be marked signed.",
                        "danger",
                    )
                elif setup_fee is None or monthly_fee is None:
                    flash("Enter the setup fee and monthly fee to mark this deal signed.", "danger")
                elif setup_commission_rate is None or not (
                    ae_pricing.SETUP_COMMISSION_RATE_MIN <= setup_commission_rate <= ae_pricing.SETUP_COMMISSION_RATE_MAX
                ):
                    flash(
                        f"Setup commission rate must be between {ae_pricing.SETUP_COMMISSION_RATE_MIN:.0%} "
                        f"and {ae_pricing.SETUP_COMMISSION_RATE_MAX:.0%}.",
                        "danger",
                    )
                elif monthly_commission_rate is None or not (
                    ae_pricing.MONTHLY_COMMISSION_RATE_MIN <= monthly_commission_rate <= ae_pricing.MONTHLY_COMMISSION_RATE_MAX
                ):
                    flash(
                        f"Monthly commission rate must be between {ae_pricing.MONTHLY_COMMISSION_RATE_MIN:.0%} "
                        f"and {ae_pricing.MONTHLY_COMMISSION_RATE_MAX:.0%}.",
                        "danger",
                    )
                elif renewal_commission_rate is not None and not (
                    ae_pricing.RENEWAL_COMMISSION_RATE_MIN <= renewal_commission_rate <= ae_pricing.RENEWAL_COMMISSION_RATE_MAX
                ):
                    flash(
                        f"Renewal commission rate must be between {ae_pricing.RENEWAL_COMMISSION_RATE_MIN:.0%} "
                        f"and {ae_pricing.RENEWAL_COMMISSION_RATE_MAX:.0%} (or left blank).",
                        "danger",
                    )
                else:
                    deal.signed_setup_fee = setup_fee
                    deal.signed_monthly_fee = monthly_fee
                    deal.setup_commission_rate = setup_commission_rate
                    deal.monthly_commission_rate = monthly_commission_rate
                    deal.renewal_commission_rate = renewal_commission_rate
                    deal.contract_value = setup_fee + monthly_fee * 12
                    deal.billing_cycle = (request.form.get("billing_cycle") or deal.billing_cycle or "annual")
                    deal.ae_stage = "signed"
                    deal.signed_at = datetime.utcnow()

                    schedule = ae_pricing.build_commission_schedule(
                        setup_fee, monthly_fee, setup_commission_rate, monthly_commission_rate
                    )
                    for entry in schedule:
                        db.session.add(AECommissionEntry(deal_id=deal.id, **entry))

                    db.session.commit()
                    flash(
                        "Deal marked signed and the commission payout schedule (setup + 12 monthly entries) "
                        "was generated. A Ravlo admin still needs to approve the license application "
                        "to create the live company account.",
                        "success",
                    )
            else:
                deal.ae_stage = new_stage
                db.session.commit()
                flash("Stage updated.", "success")

        elif action_type == "update_terms":
            billing_cycle = (request.form.get("billing_cycle") or "").strip()
            if billing_cycle:
                deal.billing_cycle = billing_cycle
                db.session.commit()
                flash("Billing cycle updated.", "success")
            else:
                flash("Choose a billing cycle.", "danger")

        elif action_type == "save_worksheet":
            deal.worksheet_industry = (request.form.get("worksheet_industry") or "").strip() or None
            user_count = request.form.get("worksheet_user_count")
            deal.worksheet_user_count = int(user_count) if (user_count or "").isdigit() else None
            workspace_count = request.form.get("worksheet_workspace_count")
            deal.worksheet_workspace_count = int(workspace_count) if (workspace_count or "").isdigit() else None
            branding = (request.form.get("worksheet_branding") or "").strip().lower()
            deal.worksheet_branding = branding if branding in {"ravlo", "co_branded", "white_label"} else None
            complexity = (request.form.get("worksheet_implementation_complexity") or "").strip().lower()
            deal.worksheet_implementation_complexity = (
                complexity if complexity in {"standard", "advanced", "enterprise"} else None
            )
            deal.worksheet_training_required = request.form.get("worksheet_training_required") == "yes"
            db.session.commit()
            flash("Quote Worksheet saved.", "success")

        elif action_type == "build_quote":
            error = _build_quote(deal, request.form)
            if error:
                flash(error, "danger")
            else:
                db.session.commit()
                if deal.approval_level_required == "ae":
                    flash("Quote calculated -- within your authority, no approval needed.", "success")
                else:
                    flash(
                        f"Quote calculated -- requires {deal.approval_level_required.replace('_', ' ').title()} "
                        "approval before it can be signed.",
                        "warning",
                    )

        elif action_type == "approve_quote":
            if not _is_full_visibility(current_user):
                flash("Only Ravlo staff can approve a quote.", "danger")
            elif deal.approval_status != "pending":
                flash("This quote isn't awaiting approval.", "info")
            else:
                deal.approval_status = "approved"
                deal.approved_by_id = current_user.id
                deal.approved_at = datetime.utcnow()
                db.session.commit()
                flash("Quote approved.", "success")

        elif action_type == "link_company":
            company_id = request.form.get("company_id")
            company = Company.query.get(int(company_id)) if (company_id or "").isdigit() else None
            if not company:
                flash("Select a valid company to link.", "danger")
            else:
                deal.linked_company_id = company.id
                db.session.commit()
                flash(f"Linked to {company.name}.", "success")

        elif action_type == "mark_ledger_entry_paid":
            if not _is_full_visibility(current_user):
                flash("Only Ravlo staff can mark a commission entry as paid.", "danger")
            else:
                entry_id = request.form.get("entry_id")
                entry = next((e for e in deal.commission_entries if str(e.id) == str(entry_id)), None)
                if entry is None:
                    flash("That commission entry wasn't found on this deal.", "danger")
                elif entry.status == "paid":
                    flash("That entry is already paid.", "info")
                else:
                    entry.status = "paid"
                    entry.paid_at = datetime.utcnow()
                    db.session.commit()
                    flash("Commission entry marked paid.", "success")

        elif action_type == "record_renewal_commission":
            if not _is_full_visibility(current_user):
                flash("Only Ravlo staff can record a renewal commission.", "danger")
            elif not deal.renewal_commission_rate:
                flash("This deal has no renewal commission rate set.", "danger")
            else:
                existing_renewal_count = sum(1 for e in deal.commission_entries if e.entry_type == "renewal")
                entry = ae_pricing.next_renewal_commission_entry(
                    deal.signed_monthly_fee, deal.renewal_commission_rate, existing_renewal_count
                )
                db.session.add(AECommissionEntry(deal_id=deal.id, **entry))
                db.session.commit()
                flash("Renewal commission entry added.", "success")

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

    quoted_setup_fee = quoted_monthly_fee = None
    if deal.pricing_plan:
        quoted_setup_fee, quoted_monthly_fee = ae_pricing.compute_quote(
            deal.list_setup_fee, deal.list_monthly_fee, deal.discount_percent, deal.setup_fee_waived
        )

    return render_template(
        "account_executive/deal_detail.html",
        deal=deal,
        ae_stages=AE_STAGES,
        companies=companies,
        is_full_visibility=_is_full_visibility(current_user),
        title=deal.company_name,
        active_tab="deals",
        partner_plans=ae_pricing.STANDARD_PARTNER_PLANS,
        lending_plans=ae_pricing.STANDARD_LENDING_PLANS,
        enterprise_tiers=ae_pricing.ENTERPRISE_TIERS,
        add_ons=ae_pricing.ADD_ONS,
        quoted_setup_fee=quoted_setup_fee,
        quoted_monthly_fee=quoted_monthly_fee,
        default_setup_commission_rate=ae_pricing.DEFAULT_SETUP_COMMISSION_RATE,
        default_monthly_commission_rate=ae_pricing.DEFAULT_MONTHLY_COMMISSION_RATE,
        setup_commission_rate_min=ae_pricing.SETUP_COMMISSION_RATE_MIN,
        setup_commission_rate_max=ae_pricing.SETUP_COMMISSION_RATE_MAX,
        monthly_commission_rate_min=ae_pricing.MONTHLY_COMMISSION_RATE_MIN,
        monthly_commission_rate_max=ae_pricing.MONTHLY_COMMISSION_RATE_MAX,
        renewal_commission_rate_min=ae_pricing.RENEWAL_COMMISSION_RATE_MIN,
        renewal_commission_rate_max=ae_pricing.RENEWAL_COMMISSION_RATE_MAX,
    )
