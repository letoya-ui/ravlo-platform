# LoanMVP/routes/stylist.py
"""Stylist dashboard -- the Salon/Beauty vertical (GotStyles Beauty and any
other salon licensing Ravlo's white-label platform).

Mirrors the loan_officer.py pattern: one StylistProfile row per stylist
User, lazily created on first dashboard visit (see _get_or_create_stylist_profile),
with company_id denormalized directly onto every child row (clients,
appointments, sales, reviews) so every list/dashboard query can filter on
it directly -- the same tenant-isolation approach LoanApplication/
BorrowerProfile use, and for the same reason (a salon's own stylists and
clients must never be visible to a different salon on the platform).

Scope note: this is the "core dashboard" slice of the GotStyles Beauty
vertical -- real models, real routes, real CRUD. The Client Portal
(clients booking their own appointments, uploading inspiration photos,
chatting with their stylist) and the salon-specific Ravlo AI assistant
are deliberately out of scope here and left as follow-ups.
"""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required

from LoanMVP.extensions import db
from LoanMVP.utils.decorators import role_required
from LoanMVP.models.salon_models import (
    StylistProfile,
    SalonClient,
    Appointment,
    ClientFormula,
    ClientPhoto,
    ProductSale,
    SalonReview,
    LoyaltyTransaction,
)

stylist_bp = Blueprint("stylist", __name__, url_prefix="/stylist")

APPOINTMENT_STATUSES = ["scheduled", "completed", "cancelled", "no_show"]


def _get_or_create_stylist_profile():
    profile = StylistProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = StylistProfile(
            user_id=current_user.id,
            company_id=getattr(current_user, "company_id", None),
            full_name=f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email,
            email=getattr(current_user, "email", None),
        )
        db.session.add(profile)
        db.session.commit()
        flash("Stylist profile created.", "info")
    return profile


def _client_or_404(profile, client_id):
    return SalonClient.query.filter_by(id=client_id, stylist_id=profile.id).first_or_404()


def _to_decimal(raw, default="0"):
    try:
        return Decimal(str(raw or default))
    except InvalidOperation:
        return Decimal(default)


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

@stylist_bp.route("/dashboard")
@login_required
@role_required("stylist")
def dashboard():
    profile = _get_or_create_stylist_profile()

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    todays_appointments = (
        Appointment.query.filter(
            Appointment.stylist_id == profile.id,
            Appointment.scheduled_at >= today_start,
            Appointment.scheduled_at < today_end,
        )
        .order_by(Appointment.scheduled_at.asc())
        .all()
    )

    upcoming_appointments = (
        Appointment.query.filter(
            Appointment.stylist_id == profile.id,
            Appointment.scheduled_at >= today_end,
            Appointment.status == "scheduled",
        )
        .order_by(Appointment.scheduled_at.asc())
        .limit(5)
        .all()
    )

    total_clients = SalonClient.query.filter_by(stylist_id=profile.id).count()
    recent_clients = (
        SalonClient.query.filter_by(stylist_id=profile.id)
        .order_by(SalonClient.created_at.desc())
        .limit(5)
        .all()
    )

    appointment_revenue_month = (
        db.session.query(db.func.coalesce(db.func.sum(Appointment.price), 0))
        .filter(
            Appointment.stylist_id == profile.id,
            Appointment.status == "completed",
            Appointment.scheduled_at >= month_start,
        )
        .scalar()
    ) or Decimal("0")

    product_sales_month = (
        db.session.query(db.func.coalesce(db.func.sum(ProductSale.total), 0))
        .filter(ProductSale.stylist_id == profile.id, ProductSale.sold_at >= month_start)
        .scalar()
    ) or Decimal("0")

    revenue_month = Decimal(appointment_revenue_month) + Decimal(product_sales_month)

    recent_photos = (
        ClientPhoto.query.join(SalonClient, ClientPhoto.client_id == SalonClient.id)
        .filter(SalonClient.stylist_id == profile.id)
        .order_by(ClientPhoto.created_at.desc())
        .limit(6)
        .all()
    )

    recent_sales = (
        ProductSale.query.filter_by(stylist_id=profile.id)
        .order_by(ProductSale.sold_at.desc())
        .limit(5)
        .all()
    )

    reviews = SalonReview.query.filter_by(stylist_id=profile.id).order_by(SalonReview.created_at.desc()).all()
    review_count = len(reviews)
    avg_rating = round(sum(r.rating for r in reviews) / review_count, 1) if review_count else None
    recent_reviews = reviews[:4]

    loyalty_points_outstanding = (
        db.session.query(db.func.coalesce(db.func.sum(SalonClient.loyalty_points), 0))
        .filter(SalonClient.stylist_id == profile.id)
        .scalar()
    ) or 0

    return render_template(
        "stylist/dashboard.html",
        profile=profile,
        todays_appointments=todays_appointments,
        upcoming_appointments=upcoming_appointments,
        total_clients=total_clients,
        recent_clients=recent_clients,
        revenue_month=revenue_month,
        recent_photos=recent_photos,
        recent_sales=recent_sales,
        review_count=review_count,
        avg_rating=avg_rating,
        recent_reviews=recent_reviews,
        loyalty_points_outstanding=loyalty_points_outstanding,
        active_tab="dashboard",
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLIENTS
# ─────────────────────────────────────────────────────────────────────────────

@stylist_bp.route("/clients", methods=["GET", "POST"])
@login_required
@role_required("stylist")
def clients():
    profile = _get_or_create_stylist_profile()

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        if not full_name:
            flash("Client name is required.", "warning")
            return redirect(url_for("stylist.clients"))

        client = SalonClient(
            company_id=profile.company_id,
            stylist_id=profile.id,
            full_name=full_name,
            email=(request.form.get("email") or "").strip() or None,
            phone=(request.form.get("phone") or "").strip() or None,
            notes=(request.form.get("notes") or "").strip() or None,
        )
        db.session.add(client)
        db.session.commit()
        flash(f"Added {full_name} to your client list.", "success")
        return redirect(url_for("stylist.clients"))

    client_list = (
        SalonClient.query.filter_by(stylist_id=profile.id)
        .order_by(SalonClient.full_name.asc())
        .all()
    )
    return render_template("stylist/clients.html", profile=profile, clients=client_list, active_tab="clients")


@stylist_bp.route("/clients/<int:client_id>")
@login_required
@role_required("stylist")
def client_detail(client_id):
    profile = _get_or_create_stylist_profile()
    client = _client_or_404(profile, client_id)

    appointments = (
        Appointment.query.filter_by(client_id=client.id)
        .order_by(Appointment.scheduled_at.desc())
        .all()
    )
    formulas = (
        ClientFormula.query.filter_by(client_id=client.id)
        .order_by(ClientFormula.created_at.desc())
        .all()
    )
    photos = (
        ClientPhoto.query.filter_by(client_id=client.id)
        .order_by(ClientPhoto.created_at.desc())
        .all()
    )
    loyalty_transactions = (
        LoyaltyTransaction.query.filter_by(client_id=client.id)
        .order_by(LoyaltyTransaction.created_at.desc())
        .all()
    )

    return render_template(
        "stylist/client_detail.html",
        profile=profile,
        client=client,
        appointments=appointments,
        formulas=formulas,
        photos=photos,
        loyalty_transactions=loyalty_transactions,
        active_tab="clients",
    )


# ─────────────────────────────────────────────────────────────────────────────
# APPOINTMENTS
# ─────────────────────────────────────────────────────────────────────────────

@stylist_bp.route("/appointments", methods=["GET", "POST"])
@login_required
@role_required("stylist")
def appointments():
    profile = _get_or_create_stylist_profile()

    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        service_type = (request.form.get("service_type") or "").strip()
        scheduled_at_raw = (request.form.get("scheduled_at") or "").strip()

        client = SalonClient.query.filter_by(id=client_id, stylist_id=profile.id).first() if client_id else None
        if not client or not service_type or not scheduled_at_raw:
            flash("Client, service, and date/time are all required.", "warning")
            return redirect(url_for("stylist.appointments"))

        try:
            scheduled_at = datetime.strptime(scheduled_at_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("Invalid date/time.", "warning")
            return redirect(url_for("stylist.appointments"))

        appointment = Appointment(
            company_id=profile.company_id,
            stylist_id=profile.id,
            client_id=client.id,
            service_type=service_type,
            scheduled_at=scheduled_at,
            duration_minutes=request.form.get("duration_minutes", type=int) or 60,
            price=_to_decimal(request.form.get("price"), default="0") or None,
            notes=(request.form.get("notes") or "").strip() or None,
        )
        db.session.add(appointment)
        db.session.commit()
        flash(f"Booked {service_type} for {client.full_name}.", "success")
        return redirect(url_for("stylist.appointments"))

    appointment_list = (
        Appointment.query.filter_by(stylist_id=profile.id)
        .order_by(Appointment.scheduled_at.desc())
        .limit(100)
        .all()
    )
    client_list = SalonClient.query.filter_by(stylist_id=profile.id).order_by(SalonClient.full_name.asc()).all()
    return render_template(
        "stylist/appointments.html",
        profile=profile,
        appointments=appointment_list,
        clients=client_list,
        appointment_statuses=APPOINTMENT_STATUSES,
        active_tab="appointments",
    )


@stylist_bp.route("/appointments/<int:appointment_id>/status", methods=["POST"])
@login_required
@role_required("stylist")
def update_appointment_status(appointment_id):
    profile = _get_or_create_stylist_profile()
    appointment = Appointment.query.filter_by(id=appointment_id, stylist_id=profile.id).first_or_404()

    new_status = (request.form.get("status") or "").strip().lower()
    if new_status not in APPOINTMENT_STATUSES:
        flash("Unknown status.", "warning")
        return redirect(url_for("stylist.appointments"))

    appointment.status = new_status
    if new_status == "completed":
        appointment.client.last_visit_at = appointment.scheduled_at
    db.session.commit()
    flash("Appointment updated.", "success")
    return redirect(url_for("stylist.appointments"))


# ─────────────────────────────────────────────────────────────────────────────
# FORMULAS & COLOR NOTES
# ─────────────────────────────────────────────────────────────────────────────

@stylist_bp.route("/formulas", methods=["GET", "POST"])
@login_required
@role_required("stylist")
def formulas():
    profile = _get_or_create_stylist_profile()

    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        title = (request.form.get("title") or "").strip()
        notes = (request.form.get("notes") or "").strip()

        client = SalonClient.query.filter_by(id=client_id, stylist_id=profile.id).first() if client_id else None
        if not client or not title or not notes:
            flash("Client, title, and formula notes are all required.", "warning")
            return redirect(url_for("stylist.formulas"))

        formula = ClientFormula(client_id=client.id, stylist_id=profile.id, title=title, notes=notes)
        db.session.add(formula)
        db.session.commit()
        flash(f"Saved formula for {client.full_name}.", "success")
        return redirect(url_for("stylist.formulas"))

    formula_list = (
        ClientFormula.query.filter_by(stylist_id=profile.id)
        .order_by(ClientFormula.created_at.desc())
        .all()
    )
    client_list = SalonClient.query.filter_by(stylist_id=profile.id).order_by(SalonClient.full_name.asc()).all()
    return render_template(
        "stylist/formulas.html", profile=profile, formulas=formula_list, clients=client_list, active_tab="formulas"
    )


# ─────────────────────────────────────────────────────────────────────────────
# BEFORE & AFTER PHOTOS
# ─────────────────────────────────────────────────────────────────────────────

@stylist_bp.route("/photos", methods=["GET", "POST"])
@login_required
@role_required("stylist")
def photos():
    profile = _get_or_create_stylist_profile()

    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        image_url = (request.form.get("image_url") or "").strip()
        photo_type = (request.form.get("photo_type") or "after").strip().lower()

        client = SalonClient.query.filter_by(id=client_id, stylist_id=profile.id).first() if client_id else None
        if not client or not image_url:
            flash("Client and photo link are both required.", "warning")
            return redirect(url_for("stylist.photos"))
        if photo_type not in ("before", "after"):
            photo_type = "after"

        photo = ClientPhoto(
            client_id=client.id,
            photo_type=photo_type,
            image_url=image_url,
            caption=(request.form.get("caption") or "").strip() or None,
        )
        db.session.add(photo)
        db.session.commit()
        flash(f"Added {photo_type} photo for {client.full_name}.", "success")
        return redirect(url_for("stylist.photos"))

    photo_list = (
        ClientPhoto.query.join(SalonClient, ClientPhoto.client_id == SalonClient.id)
        .filter(SalonClient.stylist_id == profile.id)
        .order_by(ClientPhoto.created_at.desc())
        .all()
    )
    client_list = SalonClient.query.filter_by(stylist_id=profile.id).order_by(SalonClient.full_name.asc()).all()
    return render_template(
        "stylist/photos.html", profile=profile, photos=photo_list, clients=client_list, active_tab="photos"
    )


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCT SALES
# ─────────────────────────────────────────────────────────────────────────────

@stylist_bp.route("/product-sales", methods=["GET", "POST"])
@login_required
@role_required("stylist")
def product_sales():
    profile = _get_or_create_stylist_profile()

    if request.method == "POST":
        product_name = (request.form.get("product_name") or "").strip()
        quantity = request.form.get("quantity", type=int) or 1
        unit_price = _to_decimal(request.form.get("unit_price"))
        client_id = request.form.get("client_id", type=int)

        if not product_name or unit_price <= 0:
            flash("Product name and a valid price are required.", "warning")
            return redirect(url_for("stylist.product_sales"))

        client = SalonClient.query.filter_by(id=client_id, stylist_id=profile.id).first() if client_id else None

        sale = ProductSale(
            company_id=profile.company_id,
            stylist_id=profile.id,
            client_id=client.id if client else None,
            product_name=product_name,
            quantity=quantity,
            unit_price=unit_price,
            total=unit_price * quantity,
        )
        db.session.add(sale)
        db.session.commit()
        flash(f"Logged sale of {product_name}.", "success")
        return redirect(url_for("stylist.product_sales"))

    sale_list = (
        ProductSale.query.filter_by(stylist_id=profile.id)
        .order_by(ProductSale.sold_at.desc())
        .all()
    )
    total_revenue = sum((s.total for s in sale_list), Decimal("0"))
    client_list = SalonClient.query.filter_by(stylist_id=profile.id).order_by(SalonClient.full_name.asc()).all()
    return render_template(
        "stylist/product_sales.html",
        profile=profile,
        sales=sale_list,
        total_revenue=total_revenue,
        clients=client_list,
        active_tab="product_sales",
    )


# ─────────────────────────────────────────────────────────────────────────────
# REVIEWS
# ─────────────────────────────────────────────────────────────────────────────

@stylist_bp.route("/reviews", methods=["GET", "POST"])
@login_required
@role_required("stylist")
def reviews():
    profile = _get_or_create_stylist_profile()

    if request.method == "POST":
        client_name = (request.form.get("client_name") or "").strip()
        rating = request.form.get("rating", type=int)

        if not client_name or not rating or not (1 <= rating <= 5):
            flash("A client name and a rating from 1-5 are required.", "warning")
            return redirect(url_for("stylist.reviews"))

        review = SalonReview(
            company_id=profile.company_id,
            stylist_id=profile.id,
            client_name=client_name,
            rating=rating,
            comment=(request.form.get("comment") or "").strip() or None,
            source=(request.form.get("source") or "direct").strip() or "direct",
        )
        db.session.add(review)
        db.session.commit()
        flash("Review added.", "success")
        return redirect(url_for("stylist.reviews"))

    review_list = SalonReview.query.filter_by(stylist_id=profile.id).order_by(SalonReview.created_at.desc()).all()
    avg_rating = round(sum(r.rating for r in review_list) / len(review_list), 1) if review_list else None
    return render_template(
        "stylist/reviews.html", profile=profile, reviews=review_list, avg_rating=avg_rating, active_tab="reviews"
    )


# ─────────────────────────────────────────────────────────────────────────────
# LOYALTY PROGRAM
# ─────────────────────────────────────────────────────────────────────────────

@stylist_bp.route("/loyalty", methods=["GET", "POST"])
@login_required
@role_required("stylist")
def loyalty():
    profile = _get_or_create_stylist_profile()

    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        points = request.form.get("points", type=int)
        reason = (request.form.get("reason") or "").strip() or None

        client = SalonClient.query.filter_by(id=client_id, stylist_id=profile.id).first() if client_id else None
        if not client or not points:
            flash("Client and a non-zero point amount are required.", "warning")
            return redirect(url_for("stylist.loyalty"))

        client.loyalty_points = (client.loyalty_points or 0) + points
        db.session.add(LoyaltyTransaction(client_id=client.id, points=points, reason=reason))
        db.session.commit()
        flash(f"{'Added' if points > 0 else 'Redeemed'} {abs(points)} points for {client.full_name}.", "success")
        return redirect(url_for("stylist.loyalty"))

    client_list = (
        SalonClient.query.filter_by(stylist_id=profile.id)
        .order_by(SalonClient.loyalty_points.desc())
        .all()
    )
    return render_template("stylist/loyalty.html", profile=profile, clients=client_list, active_tab="loyalty")
