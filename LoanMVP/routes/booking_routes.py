# LoanMVP/routes/booking_routes.py
"""Booking capability: dashboard availability management. The public
calendar + booking form live in public_pages.py (VIPProfile workspaces
are already looked up there by public_slug; booking reuses that same
slug resolution rather than inventing a second one).

Auto-registered by LoanMVP/app.py blueprint scanner.
"""
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from LoanMVP.services.booking_service import (
    add_availability_window,
    delete_availability_window,
    get_availability,
)
from LoanMVP.services.payments_service import resolve_current_owner

booking_bp = Blueprint("booking", __name__, url_prefix="/booking")

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _public_slug_for(owner_type: str, owner_id: int):
    if owner_type == "vip_profile":
        from LoanMVP.models.vip_models import VIPProfile
        profile = VIPProfile.query.get(owner_id)
        return profile.public_slug if profile else None
    if owner_type == "stylist_profile":
        from LoanMVP.models.salon_models import StylistProfile
        profile = StylistProfile.query.get(owner_id)
        return profile.public_slug if profile else None
    return None


@booking_bp.route("/availability", methods=["GET", "POST"])
@login_required
def availability():
    owner_type, owner_id, display_name, brand_color, logo_url = resolve_current_owner(current_user)
    if not owner_type:
        abort(404)

    if request.method == "POST":
        action_type = request.form.get("action_type")

        if action_type == "add":
            day_of_week = request.form.get("day_of_week", type=int)
            slot_minutes = request.form.get("slot_minutes", type=int) or 60

            try:
                start_time = datetime.strptime((request.form.get("start_time") or "").strip(), "%H:%M").time()
                end_time = datetime.strptime((request.form.get("end_time") or "").strip(), "%H:%M").time()
            except ValueError:
                flash("Enter valid start and end times.", "warning")
                return redirect(url_for("booking.availability"))

            if day_of_week is None or day_of_week not in range(7) or end_time <= start_time:
                flash("Enter a valid day and time range.", "warning")
                return redirect(url_for("booking.availability"))

            add_availability_window(owner_type, owner_id, day_of_week, start_time, end_time, slot_minutes)
            flash("Availability added.", "success")

        elif action_type == "delete":
            window_id = request.form.get("window_id", type=int)
            if delete_availability_window(owner_type, owner_id, window_id):
                flash("Availability removed.", "success")

        return redirect(url_for("booking.availability"))

    my_windows = get_availability(owner_type, owner_id)
    public_slug = _public_slug_for(owner_type, owner_id)

    return render_template(
        "booking/availability.html",
        windows=my_windows,
        weekdays=WEEKDAYS,
        display_name=display_name,
        public_slug=public_slug,
    )
