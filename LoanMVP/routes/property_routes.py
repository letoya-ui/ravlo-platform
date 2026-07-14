from flask import (
    Blueprint, render_template, request, jsonify,
    redirect, url_for, flash, current_app, abort
)
from flask_login import login_required, current_user
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from LoanMVP.utils.decorators import role_required
from LoanMVP.extensions import db
from LoanMVP.models.property import Property, PropertyUnit, Tenant, RentPayment, MaintenanceRequest
from LoanMVP.models.investor_models import InvestorProfile
from LoanMVP.services.unified_property_resolver import resolve_property_unified
from LoanMVP.services.property_dto import to_property_card_dto
from LoanMVP.services.resolver_metrics import get_metrics_snapshot
import requests
from LoanMVP.utils.safe_http import safe_call

property_bp = Blueprint("property", __name__, url_prefix="/property")

# Ravlo staff who can see every investor's managed rental portfolio, not
# just their own. "property" is kept for continuity with the role this
# blueprint has always been gated behind (@role_required("property")) --
# no evidence any real account uses it, but nothing should regress for
# whoever does. Deliberately excludes the generic "admin" role: that role
# is a customer lending company's own admin elsewhere in this codebase,
# and Property/managed-portfolio data has no company scoping, so treating
# "admin" as full-visibility here would leak every investor's rental data
# across every customer company.
FULL_VISIBILITY_ROLES = {"platform_admin", "master_admin", "lending_admin", "executive", "property"}

MAINTENANCE_PRIORITIES = ["low", "medium", "high", "urgent"]
MAINTENANCE_STATUSES = ["open", "in_progress", "resolved"]
RENT_STATUSES = ["unpaid", "partial", "paid", "late"]


def _is_full_visibility(user) -> bool:
    return (getattr(user, "role", "") or "").strip().lower() in FULL_VISIBILITY_ROLES


def _current_investor_profile():
    return InvestorProfile.query.filter_by(user_id=current_user.id).first()


def _owned_properties_query():
    if _is_full_visibility(current_user):
        # Full-visibility staff (property/lending_admin/executive/admin) can
        # create properties themselves -- those get owner_investor_id=None
        # since staff have no InvestorProfile. Excluding NULL here made
        # staff-created properties invisible on their own dashboard/list
        # right after creation, even though _can_view_property() already
        # grants them access to any single property.
        return Property.query
    profile = _current_investor_profile()
    if not profile:
        return Property.query.filter(db.false())
    return Property.query.filter_by(owner_investor_id=profile.id)


def _can_view_property(prop) -> bool:
    if _is_full_visibility(current_user):
        return True
    profile = _current_investor_profile()
    return profile is not None and prop.owner_investor_id == profile.id


def _get_owned_property_or_404(property_id):
    prop = Property.query.get_or_404(property_id)
    if not _can_view_property(prop):
        abort(404)
    return prop


def _get_owned_unit_or_404(unit_id):
    unit = PropertyUnit.query.get_or_404(unit_id)
    if not _can_view_property(unit.property_ref):
        abort(404)
    return unit


def _to_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _to_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _property_cash_flow(prop):
    """All-time rent collected minus logged maintenance costs across every
    unit in this property."""
    rent_collected = Decimal("0")
    maintenance_cost = Decimal("0")
    open_maintenance = 0
    occupied_units = 0

    for unit in prop.units:
        for payment in unit.rent_payments:
            rent_collected += payment.amount_paid or Decimal("0")
        for req in unit.maintenance_requests:
            maintenance_cost += req.actual_cost or Decimal("0")
            if req.status != "resolved":
                open_maintenance += 1
        if unit.is_occupied:
            occupied_units += 1

    return {
        "rent_collected": rent_collected,
        "maintenance_cost": maintenance_cost,
        "net_cash_flow": rent_collected - maintenance_cost,
        "open_maintenance": open_maintenance,
        "unit_count": len(prop.units),
        "occupied_units": occupied_units,
    }


# =========================================================
# 📊 PROPERTY MANAGEMENT DASHBOARD
# =========================================================
@property_bp.route("/dashboard")
@login_required
@role_required("investor", "property", "lending_admin")
def dashboard():
    properties = _owned_properties_query().order_by(Property.created_at.desc()).all()

    total_rent = Decimal("0")
    total_maintenance_cost = Decimal("0")
    total_units = 0
    occupied_units = 0
    open_maintenance = 0

    property_rows = []
    for prop in properties:
        summary = _property_cash_flow(prop)
        total_rent += summary["rent_collected"]
        total_maintenance_cost += summary["maintenance_cost"]
        total_units += summary["unit_count"]
        occupied_units += summary["occupied_units"]
        open_maintenance += summary["open_maintenance"]
        property_rows.append({"property": prop, "summary": summary})

    stats = {
        "total_properties": len(properties),
        "total_units": total_units,
        "occupied_units": occupied_units,
        "rent_collected": total_rent,
        "maintenance_cost": total_maintenance_cost,
        "net_cash_flow": total_rent - total_maintenance_cost,
        "open_maintenance": open_maintenance,
    }

    return render_template(
        "property/dashboard.html",
        property_rows=property_rows,
        stats=stats,
        title="Property Management",
        active_tab="properties",
    )


# =========================================================
# 📋 PROPERTY LIST
# =========================================================
@property_bp.route("/list")
@login_required
@role_required("investor", "property", "lending_admin")
def property_list():
    properties = _owned_properties_query().order_by(Property.created_at.desc()).all()
    return render_template(
        "property/list.html",
        properties=properties,
        title="My Properties",
        active_tab="properties",
    )


# =========================================================
# ➕ ADD PROPERTY
# =========================================================
@property_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("investor", "property", "lending_admin")
def new():
    if request.method == "POST":
        address = (request.form.get("address") or "").strip()
        if not address:
            flash("An address is required.", "danger")
            return redirect(url_for("property.new"))

        profile = _current_investor_profile()

        prop = Property(
            address=address,
            city=(request.form.get("city") or "").strip() or None,
            state=(request.form.get("state") or "").strip() or None,
            zip=(request.form.get("zip") or "").strip() or None,
            price=float(request.form.get("price")) if request.form.get("price") else None,
            beds=int(request.form.get("beds")) if request.form.get("beds") else None,
            baths=float(request.form.get("baths")) if request.form.get("baths") else None,
            sqft=int(request.form.get("sqft")) if request.form.get("sqft") else None,
            description=(request.form.get("description") or "").strip() or None,
            owner_investor_id=profile.id if profile else None,
        )
        db.session.add(prop)
        db.session.commit()

        flash("Property added to your portfolio.", "success")
        return redirect(url_for("property.view", property_id=prop.id))

    return render_template("property/new.html", title="Add Property")


# =========================================================
# 🧾 PROPERTY DETAIL
# =========================================================
@property_bp.route("/view/<int:property_id>", methods=["GET", "POST"])
@login_required
@role_required("investor", "property", "lending_admin")
def view(property_id):
    prop = _get_owned_property_or_404(property_id)

    if request.method == "POST":
        action_type = request.form.get("action_type")

        if action_type == "update_property":
            prop.address = (request.form.get("address") or prop.address).strip()
            prop.city = (request.form.get("city") or "").strip() or None
            prop.state = (request.form.get("state") or "").strip() or None
            prop.zip = (request.form.get("zip") or "").strip() or None
            if request.form.get("price"):
                prop.price = float(request.form.get("price"))
            db.session.commit()
            flash("Property updated.", "success")

        elif action_type == "add_unit":
            unit = PropertyUnit(
                property_id=prop.id,
                unit_label=(request.form.get("unit_label") or "Main Unit").strip(),
                bedrooms=int(request.form.get("bedrooms")) if request.form.get("bedrooms") else None,
                bathrooms=float(request.form.get("bathrooms")) if request.form.get("bathrooms") else None,
                sqft=int(request.form.get("sqft")) if request.form.get("sqft") else None,
                market_rent=_to_decimal(request.form.get("market_rent")),
            )
            db.session.add(unit)
            db.session.commit()
            flash("Unit added.", "success")

        return redirect(url_for("property.view", property_id=prop.id))

    summary = _property_cash_flow(prop)
    return render_template(
        "property/view.html",
        property=prop,
        summary=summary,
        title=prop.address,
        active_tab="properties",
    )


# =========================================================
# 🗑️ DELETE PROPERTY
# =========================================================
@property_bp.route("/delete/<int:property_id>", methods=["POST"])
@login_required
@role_required("investor", "property", "lending_admin")
def delete(property_id):
    prop = _get_owned_property_or_404(property_id)
    db.session.delete(prop)
    db.session.commit()
    flash("Property removed.", "success")
    return redirect(url_for("property.property_list"))


# =========================================================
# 🏢 UNIT DETAIL — tenant, rent roll, maintenance
# =========================================================
@property_bp.route("/unit/<int:unit_id>", methods=["GET", "POST"])
@login_required
@role_required("investor", "property", "lending_admin")
def unit_detail(unit_id):
    unit = _get_owned_unit_or_404(unit_id)

    if request.method == "POST":
        action_type = request.form.get("action_type")

        if action_type == "update_unit":
            unit.unit_label = (request.form.get("unit_label") or unit.unit_label).strip()
            if request.form.get("bedrooms"):
                unit.bedrooms = int(request.form.get("bedrooms"))
            if request.form.get("bathrooms"):
                unit.bathrooms = float(request.form.get("bathrooms"))
            if request.form.get("sqft"):
                unit.sqft = int(request.form.get("sqft"))
            market_rent = _to_decimal(request.form.get("market_rent"))
            if market_rent is not None:
                unit.market_rent = market_rent
            db.session.commit()
            flash("Unit updated.", "success")

        elif action_type == "add_tenant":
            full_name = (request.form.get("full_name") or "").strip()
            if not full_name:
                flash("Tenant name is required.", "danger")
            else:
                tenant = Tenant(
                    unit_id=unit.id,
                    full_name=full_name,
                    email=(request.form.get("email") or "").strip() or None,
                    phone=(request.form.get("phone") or "").strip() or None,
                    lease_start=_to_date(request.form.get("lease_start")),
                    lease_end=_to_date(request.form.get("lease_end")),
                    monthly_rent=_to_decimal(request.form.get("monthly_rent")),
                    security_deposit=_to_decimal(request.form.get("security_deposit")),
                    is_active=True,
                )
                db.session.add(tenant)
                db.session.commit()
                flash("Tenant added.", "success")

        elif action_type == "end_tenancy":
            tenant_id = request.form.get("tenant_id")
            tenant = Tenant.query.get(int(tenant_id)) if (tenant_id or "").isdigit() else None
            if tenant and tenant.unit_id == unit.id:
                tenant.is_active = False
                tenant.lease_end = tenant.lease_end or date.today()
                db.session.commit()
                flash("Tenancy ended.", "info")

        elif action_type == "log_rent_payment":
            period_month = _to_date(request.form.get("period_month"))
            amount_due = _to_decimal(request.form.get("amount_due"))
            if not period_month or amount_due is None:
                flash("A period and amount due are required.", "danger")
            else:
                amount_paid = _to_decimal(request.form.get("amount_paid")) or Decimal("0")
                status = (request.form.get("status") or "").strip().lower()
                if status not in RENT_STATUSES:
                    status = "paid" if amount_paid >= amount_due else ("partial" if amount_paid > 0 else "unpaid")
                payment = RentPayment(
                    unit_id=unit.id,
                    tenant_id=unit.active_tenant.id if unit.active_tenant else None,
                    period_month=period_month,
                    amount_due=amount_due,
                    amount_paid=amount_paid,
                    paid_date=_to_date(request.form.get("paid_date")),
                    status=status,
                    notes=(request.form.get("notes") or "").strip() or None,
                )
                db.session.add(payment)
                db.session.commit()
                flash("Rent payment logged.", "success")

        elif action_type == "add_maintenance_request":
            title = (request.form.get("title") or "").strip()
            if not title:
                flash("A title is required.", "danger")
            else:
                priority = (request.form.get("priority") or "medium").strip().lower()
                req = MaintenanceRequest(
                    unit_id=unit.id,
                    reported_by_user_id=current_user.id,
                    title=title,
                    description=(request.form.get("description") or "").strip() or None,
                    priority=priority if priority in MAINTENANCE_PRIORITIES else "medium",
                    status="open",
                )
                db.session.add(req)
                db.session.commit()
                flash("Maintenance request logged.", "success")

        elif action_type == "update_maintenance_status":
            request_id = request.form.get("request_id")
            new_status = (request.form.get("status") or "").strip().lower()
            req = MaintenanceRequest.query.get(int(request_id)) if (request_id or "").isdigit() else None
            if req and req.unit_id == unit.id and new_status in MAINTENANCE_STATUSES:
                req.status = new_status
                if new_status == "resolved":
                    req.resolved_at = datetime.utcnow()
                    actual_cost = _to_decimal(request.form.get("actual_cost"))
                    if actual_cost is not None:
                        req.actual_cost = actual_cost
                else:
                    req.resolved_at = None
                db.session.commit()
                flash("Maintenance request updated.", "success")

        return redirect(url_for("property.unit_detail", unit_id=unit.id))

    rent_payments = sorted(unit.rent_payments, key=lambda p: p.period_month, reverse=True)
    maintenance_requests = sorted(unit.maintenance_requests, key=lambda r: r.created_at, reverse=True)

    return render_template(
        "property/unit_detail.html",
        unit=unit,
        rent_payments=rent_payments,
        maintenance_requests=maintenance_requests,
        maintenance_priorities=MAINTENANCE_PRIORITIES,
        maintenance_statuses=MAINTENANCE_STATUSES,
        title=f"{unit.property_ref.address} — {unit.unit_label}",
        active_tab="properties",
    )


# =========================================================
# 🗑️ DELETE UNIT
# =========================================================
@property_bp.route("/unit/<int:unit_id>/delete", methods=["POST"])
@login_required
@role_required("investor", "property", "lending_admin")
def delete_unit(unit_id):
    unit = _get_owned_unit_or_404(unit_id)
    property_id = unit.property_id
    db.session.delete(unit)
    db.session.commit()
    flash("Unit removed.", "success")
    return redirect(url_for("property.view", property_id=property_id))


# =========================================================
# 🔍 GOOGLE PLACES AUTOCOMPLETE (address lookup)
# =========================================================
@property_bp.route("/autocomplete", methods=["POST"])
def autocomplete():
    data = request.get_json() or {}
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"predictions": []})

    api_key = current_app.config.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        return jsonify({"predictions": []})

    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": query,
        "key": api_key,
        "types": "address",
        "components": "country:us"
    }

    try:
        resp = safe_call(requests.get, url, params=params, timeout=5)
        data = resp.json()
    except Exception:
        return jsonify({"predictions": []})

    predictions = [
        {
            "description": p.get("description", ""),
            "place_id": p.get("place_id", "")
        }
        for p in data.get("predictions", [])
    ]

    return jsonify({"predictions": predictions})


# =========================================================
# 🧠 UNIFIED PROPERTY RESOLVER
# =========================================================
@property_bp.route("/resolve", methods=["POST"])
def resolve():
    address = request.json.get("address")
    if not address:
        return jsonify({"error": "Missing address"}), 400

    unified = resolve_property_unified(address)

    if unified.get("status") != "ok":
        return jsonify(unified), 200

    return jsonify({
        "status": "ok",
        "card": to_property_card_dto(unified),
        "raw": unified,
    })


# =========================================================
# 📈 RESOLVER METRICS
# =========================================================
@property_bp.route("/resolver/metrics")
def resolver_metrics():
    return jsonify(get_metrics_snapshot())


# =========================================================
# 🔎 PROPERTY SEARCH PAGE
# =========================================================
@property_bp.route("/search")
def search_page():
    return render_template("property/search.html")


# =========================================================
# 🧩 Legacy alias — the old "management panel" URL now shows the same
# real dashboard rather than the broken PropertyAnalysis CRUD it used to.
# =========================================================
@property_bp.route("/manage")
@login_required
@role_required("investor", "property", "lending_admin")
def manage():
    return redirect(url_for("property.dashboard"))
