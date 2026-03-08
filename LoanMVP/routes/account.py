from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from LoanMVP.extensions import db
from LoanMVP.models import User

account_bp = Blueprint("account", __name__, url_prefix="/account")


@account_bp.route("/profile")
@login_required
def profile():
    return render_template(
        "account/profile.html",
        user=current_user,
        active_tab="profile"
    )


@account_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():

    if request.method == "POST":

        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")

        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.email = email

        db.session.commit()

        flash("Profile updated successfully.", "success")

        return redirect(url_for("account.settings"))

    return render_template(
        "account/settings.html",
        user=current_user,
        active_tab="settings"
    )


@account_bp.route("/security")
@login_required
def security():
    return render_template(
        "account/security.html",
        active_tab="security"
    )