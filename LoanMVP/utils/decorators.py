# LoanMVP/utils/decorators.py
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
                # send them somewhere safe
                return redirect(url_for("borrower.dashboard") if user_role == "borrower" else url_for("auth.login"))
            return fn(*args, **kwargs)
        return decorated_view
    return decorator    def wrapper(fn):
        @wraps(fn)

        @login_required
        def decorated_view(*args, **kwargs):
            if current_user.role not in roles:
                flash("🚫 You do not have permission to access this page.", "danger")
                return redirect(url_for("auth.login"))
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper
