# =========================================================
# 🔐 ROLE HELPERS — Ravlo
# =========================================================

from datetime import datetime

ADMIN_ROLES = {
    "admin",
    "master_admin",
    "lending_admin",
    "platform_admin",
}

EXECUTIVE_ROLES = {
    "executive",
}

STAFF_ROLES = {
    "loan_officer",
    "processor",
    "underwriter",
}

USER_ROLES = {
    "investor",
    "borrower",
    "partner",
}


# ---------------------------------------------------------
# Core checks
# ---------------------------------------------------------

def is_admin(user) -> bool:
    if not user:
        return False
    return (user.role or "").strip().lower() in ADMIN_ROLES


def is_executive(user) -> bool:
    if not user:
        return False
    return (user.role or "").strip().lower() in EXECUTIVE_ROLES


def is_platform_admin(user) -> bool:
    return (user.role or "").strip().lower() == "platform_admin"


def is_master_admin(user) -> bool:
    return (user.role or "").strip().lower() == "master_admin"


def is_lending_admin(user) -> bool:
    return (user.role or "").strip().lower() == "lending_admin"


def is_staff(user) -> bool:
    return (user.role or "").strip().lower() in STAFF_ROLES


def is_user_role(user) -> bool:
    return (user.role or "").strip().lower() in USER_ROLES


# ---------------------------------------------------------
# Display helper (🔥 useful for UI)
# ---------------------------------------------------------

def get_role_label(role: str) -> str:
    role = (role or "").replace("_", " ").title()

    role_labels = {
        "Platform Admin": "Platform Admin (Full Control)",
        "Master Admin": "Master Admin (Operations)",
        "Lending Admin": "Lending Admin",
        "Executive": "Executive",
        "Admin": "Company Admin",
        "Loan Officer": "Loan Officer",
        "Processor": "Processor",
        "Underwriter": "Underwriter",
        "Investor": "Investor",
        "Borrower": "Borrower",
        "Partner": "Partner",
    }

    return role_labels.get(role, role)

def get_role_badge_class(role: str) -> str:
    role = (role or "").lower()

    if role == "platform_admin":
        return "badge badge-danger"
    if role == "master_admin":
        return "badge badge-warning"
    if role == "lending_admin":
        return "badge badge-info"
    if role == "executive":
        return "badge badge-info"
    if role == "admin":
        return "badge badge-primary"

    return "badge badge-neutral"

def get_request_type_display(request_type: str) -> str:
    request_type = (request_type or "").strip().lower()

    mapping = {
        "company_setup": "Company Setup",
        "license_application": "License Application",
        "access_request": "Access Request",
        "general": "General Request",
    }

    return mapping.get(request_type, request_type.replace("_", " ").title())

def get_status_display(status: str) -> str:
    status = (status or "").lower()

    mapping = {
        "pending": "Pending",
        "approved": "Approved",
        "denied": "Denied",
        "rejected": "Rejected",
    }

    return mapping.get(status, status.title() if status else "Unknown")


def get_status_badge(status: str) -> str:
    status = (status or "").lower()

    if status == "pending":
        return "badge badge-warning"
    if status == "approved":
        return "badge badge-success"
    if status in ["denied", "rejected"]:
        return "badge badge-danger"

    return "badge badge-neutral"

def get_billing_status_badge(status: str) -> str:
    status = normalize_text(status)
    if status == "active":
        return "badge badge-success"
    if status == "past_due":
        return "badge badge-warning"
    if status == "blocked":
        return "badge badge-danger"
    if status == "suspended":
        return "badge badge-danger"
    return "badge badge-neutral"

def auto_block_company_for_non_payment(company):
    company.is_blocked = True
    company.blocked_at = datetime.utcnow()
    company.blocked_reason = "non_payment"
    company.blocked_note = "Automatically blocked after failed payment and expired grace period."
    company.billing_status = "blocked"


# Ravlo staff roles that operate across every company and are never gated
# by any single company's billing state. Mirrors admin.py's FULL_ADMIN_ROLES
# -- duplicated here rather than importing a route module into this one.
FULL_RAVLO_STAFF_ROLES = {"platform_admin", "master_admin", "lending_admin", "executive"}


def company_billing_hold_reason(company):
    """Short reason code if a company's workspace should be held from
    further access, or None if it's fine.

    'blocked'        -- an admin (or auto-block below) explicitly blocked
                        this workspace
    'inactive'       -- workspace deactivated, whether by hand
                        (company_settings) or by Stripe (subscription
                        fully canceled)
    'billing_lapsed' -- billing_status is past_due and the grace period
                        (Company.is_billing_current()) has expired
    """
    if company is None:
        return None
    if company.is_blocked:
        return "blocked"
    if company.is_active is False:
        return "inactive"
    if not company.is_billing_current():
        return "billing_lapsed"
    return None


def enforce_company_billing_hold(company):
    """Check a company's billing hold state, lazily transitioning a company
    whose grace period has just expired into is_blocked=True so
    billing_status stays accurate without a cron sweep (Stripe only calls
    the webhook on payment attempts, never exactly at the grace-period
    deadline). Returns the hold reason (or None) after any transition.
    """
    reason = company_billing_hold_reason(company)
    if reason == "billing_lapsed" and not company.is_blocked:
        from LoanMVP.extensions import db
        auto_block_company_for_non_payment(company)
        db.session.commit()
        return "blocked"
    return reason


def get_request_type_display(request_type: str) -> str:
    request_type = (request_type or "").strip().lower()
    mapping = {
        "company_setup": "Company Setup",
        "license_application": "License Application",
        "access_request": "Access Request",
        "general": "General Request",
    }
    return mapping.get(request_type, request_type.replace("_", " ").title())


def get_role_display(role: str) -> str:
    role = (role or "").strip().lower()
    role_map = {
        "platform_admin": "Platform Admin",
        "master_admin": "Master Admin",
        "lending_admin": "Lending Admin",
        "executive": "Executive",
        "admin": "Admin",
        "loan_officer": "Loan Officer",
        "processor": "Processor",
        "underwriter": "Underwriter",
        "investor": "Investor",
        "borrower": "Borrower",
        "partner": "Partner",
    }
    return role_map.get(role, role.replace("_", " ").title() if role else "—")


def get_status_display(status: str) -> str:
    status = (status or "").strip().lower()
    mapping = {
        "pending": "Pending",
        "approved": "Approved",
        "denied": "Denied",
        "rejected": "Rejected",
    }
    return mapping.get(status, status.title() if status else "Unknown")


def get_status_badge(status: str) -> str:
    status = (status or "").strip().lower()
    if status == "pending":
        return "badge badge-warning"
    if status == "approved":
        return "badge badge-success"
    if status in ["denied", "rejected"]:
        return "badge badge-danger"
    return "badge badge-neutral"

# ---------------------------------------------------------
# Permission helper (🔥 powerful)
# ---------------------------------------------------------

def can_access_admin_panel(user) -> bool:
    return is_admin(user)


def can_manage_users(user) -> bool:
    return is_admin(user)


def can_approve_licensing(user) -> bool:
    role = (getattr(user, "role", "") or "").strip().lower()
    return is_platform_admin(user) or is_master_admin(user) or role == "executive"


def can_block_accounts(user) -> bool:
    return is_platform_admin(user) or is_master_admin(user)
