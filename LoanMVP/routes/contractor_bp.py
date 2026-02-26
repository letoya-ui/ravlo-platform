from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from LoanMVP.extensions import db
from LoanMVP.models.contractor_models import Contractor, ContractorPayment
from datetime import datetime

contractor_bp = Blueprint("contractor_bp", __name__, url_prefix="/contractors")

# ==== Admin view: list all contractors ====
@contractor_bp.route("/admin")
@login_required
def admin_contractors():
    if not current_user.role == "Admin":
        flash("Access denied.", "danger")
        return redirect(url_for("main.dashboard"))
    contractors = Contractor.query.order_by(Contractor.date_joined.desc()).all()
    return render_template("admin/contractors.html", contractors=contractors)

# ==== Approve / feature contractors ====
@contractor_bp.route("/admin/update/<int:id>", methods=["POST"])
@login_required
def update_contractor(id):
    contractor = Contractor.query.get_or_404(id)
    contractor.approved = bool(request.form.get("approved"))
    contractor.featured = bool(request.form.get("featured"))
    db.session.commit()
    flash(f"Contractor {contractor.name} updated.", "success")
    return redirect(url_for("contractor_bp.admin_contractors"))

# ==== Public registration form ====
@contractor_bp.route("/register", methods=["GET", "POST"])
def register_contractor():
    if request.method == "POST":
        new = Contractor(
            name=request.form["name"],
            category=request.form["category"],
            phone=request.form["phone"],
            email=request.form["email"],
            website=request.form["website"],
            location=request.form["location"],
            description=request.form["description"]
        )
        db.session.add(new)
        db.session.commit()
        flash("Registration submitted. Awaiting approval.", "info")
        return redirect(url_for("contractor_bp.register_contractor"))
    return render_template("contractors/register.html")

# ==== Borrower directory ====
@contractor_bp.route("/directory")
@login_required
def contractor_directory():
    contractors = Contractor.query.filter_by(approved=True).order_by(Contractor.featured.desc()).all()
    return render_template("borrower/resource_center.html", contractors=contractors)
