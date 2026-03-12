from flask import Blueprint, render_template, request, redirect, url_for, flash
from LoanMVP.extensions import db
from LoanMVP.models.admin import AccessRequest

public_bp = Blueprint("public", __name__)


@public_bp.route("/request-access", methods=["GET", "POST"])
def request_access():
    if request.method == "POST":
        contact_name = (request.form.get("contact_name") or "").strip()
        company_name = (request.form.get("company_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        request_type = (request.form.get("request_type") or "company_setup").strip()
        requested_role = (request.form.get("requested_role") or "").strip()
        notes = (request.form.get("notes") or "").strip()

        if not contact_name or not email:
            flash("Name and email are required.", "danger")
            return redirect(url_for("public.request_access"))

        access_request = AccessRequest(
            contact_name=contact_name,
            company_name=company_name,
            email=email,
            phone=phone,
            request_type=request_type,
            requested_role=requested_role,
            notes=notes,
            status="pending",
        )
        db.session.add(access_request)
        db.session.commit()

        notify(
            role="admin",
            title="New Access Request",
            message=f"New access request submitted by {contact_name} ({email}).",
            channels=["socket", "inapp", "email"]
        )

        flash("Your request has been submitted.", "success")
        return redirect(url_for("public.request_access"))

    return render_template("public/request_access.html")