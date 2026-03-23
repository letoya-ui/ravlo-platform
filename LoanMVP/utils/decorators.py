from functools import wraps
from flask import redirect, url_for, flash, request
from flask_login import current_user, login_required

def role_required(*roles):
    roles = {r.strip().lower() for r in roles}

    def decorator(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.path))

            user_role = (getattr(current_user, "role", "") or "").strip().lower()

            if user_role not in roles:
                flash("Your account doesn’t have access to that page yet.", "warning")
                return redirect(
                    url_for("investor.command_center")
                    if user_role == "investor"
                    else url_for("auth.login")
                )

            return fn(*args, **kwargs)
        return decorated_view
    return decorator

def partner_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.partner_profile:
            flash("You must be a partner to access this page.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper



def loan_officer_onboarding_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not getattr(current_user, "loan_officer_onboarding_complete", False):
            return redirect(url_for("loan_officer.onboarding"))
        return fn(*args, **kwargs)
    return wrapper