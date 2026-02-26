# LoanMVP/utils/decorators.py
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user, login_required

def role_required(*roles):
    """
    Restrict access to users with specific roles.
    Usage:
        @role_required("admin")
        @role_required("admin", "loan_officer")
    """
    def wrapper(fn):
        @wraps(fn)
        @login_required
        def decorated_view(*args, **kwargs):
            if current_user.role not in roles:
                flash("🚫 You do not have permission to access this page.", "danger")
                return redirect(url_for("auth.login"))
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper
