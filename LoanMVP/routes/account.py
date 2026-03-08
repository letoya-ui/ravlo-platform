from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from LoanMVP.extensions import db

account_bp = Blueprint("account", __name__, url_prefix="/account")


@account_bp.route("/")
@login_required
def index():
    return redirect(url_for("account.profile"))


@account_bp.route("/profile")
@login_required
def profile():
    return render_template(
        "account/profile.html",
        user=current_user,
        active_tab="profile",
        title="My Profile",
    )


@account_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        username = (request.form.get("username") or "").strip()

        if not first_name or not last_name or not email:
            flash("First name, last name, and email are required.", "warning")
            return redirect(url_for("account.settings"))

        # Prevent duplicate email on another user
        existing_email = type(current_user).query.filter(
            type(current_user).email == email,
            type(current_user).id != current_user.id
        ).first()
        if existing_email:
            flash("That email is already in use.", "danger")
            return redirect(url_for("account.settings"))

        # Prevent duplicate username if provided
        if hasattr(current_user, "username") and username:
            existing_username = type(current_user).query.filter(
                type(current_user).username == username,
                type(current_user).id != current_user.id
            ).first()
            if existing_username:
                flash("That username is already taken.", "danger")
                return redirect(url_for("account.settings"))

            current_user.username = username

        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.email = email

        db.session.commit()
        flash("Account settings updated successfully.", "success")
        return redirect(url_for("account.settings"))

    return render_template(
        "account/settings.html",
        user=current_user,
        active_tab="settings",
        title="Account Settings",
    )


@account_bp.route("/security", methods=["GET", "POST"])
@login_required
def security():
    if request.method == "POST":
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not current_password or not new_password or not confirm_password:
            flash("Please complete all password fields.", "warning")
            return redirect(url_for("account.security"))

        if not check_password_hash(current_user.password_hash, current_password):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("account.security"))

        if len(new_password) < 8:
            flash("New password must be at least 8 characters.", "warning")
            return redirect(url_for("account.security"))

        if new_password != confirm_password:
            flash("New passwords do not match.", "danger")
            return redirect(url_for("account.security"))

        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()

        flash("Password updated successfully.", "success")
        return redirect(url_for("account.security"))

    return render_template(
        "account/security.html",
        user=current_user,
        active_tab="security",
        title="Security",
    )