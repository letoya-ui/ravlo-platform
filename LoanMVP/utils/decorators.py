from functools import wraps
from flask import redirect, url_for, flash, request
from flask_login import current_user
from LoanMVP.utils.blocking_helpers import is_user_blocked, get_user_block_message

ADMIN_ROLES = {
    "admin",
    "master_admin",
    "lending_admin",
    "platform_admin",
}

STAFF_ROLES = {
    "loan_officer",
    "processor",
    "underwriter",
}


def normalize_role(role):
    return (role or "").strip().lower()


def is_admin_role(role: str) -> bool:
    return normalize_role(role) in ADMIN_ROLES


def is_staff_role(role: str) -> bool:
    return normalize_role(role) in STAFF_ROLES


def is_admin_user(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return is_admin_role(getattr(user, "role", None))


def admin_role_label(role: str) -> str:
    role = normalize_role(role)

    labels = {
        "platform_admin": "Platform Admin",
        "master_admin": "Master Admin",
        "lending_admin": "Lending Admin",
        "admin": "Admin",
        "loan_officer": "Loan Officer",
        "processor": "Processor",
        "underwriter": "Underwriter",
        "investor": "Investor",
        "borrower": "Borrower",
        "partner": "Partner",
    }

    return labels.get(role, role.replace("_", " ").title() if role else "User")


def role_required(*roles):
    roles = {normalize_role(r) for r in roles}

    def decorator(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.path))

            user_role = normalize_role(getattr(current_user, "role", ""))

            expanded_roles = set()
            for role in roles:
                if role == "admin_group":
                    expanded_roles.update(ADMIN_ROLES)
                elif role == "staff_group":
                    expanded_roles.update(STAFF_ROLES)
                else:
                    expanded_roles.add(role)

            if user_role not in expanded_roles:
                flash("Your account doesn’t have access to that page yet.", "warning")

                if user_role == "investor":
                    return redirect(url_for("investor.command_center"))

                if user_role in ADMIN_ROLES:
                    return redirect(url_for("admin.dashboard"))

                return redirect(url_for("auth.login"))

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
        if not (
            getattr(current_user, "loan_officer_onboarding_complete", False)
            or getattr(current_user, "onboarding_complete", False)
        ):
            return redirect(url_for("loan_officer.onboarding"))
        return fn(*args, **kwargs)
    return wrapper


def block_check_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))

        if is_user_blocked(current_user):
            flash(get_user_block_message(current_user), "danger")
            logout_target = url_for("auth.login")
            return redirect(logout_target)

        return fn(*args, **kwargs)
    return wrapper
