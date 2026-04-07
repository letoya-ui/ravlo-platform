# =========================================================
# 🔐 ROLE HELPERS — Ravlo
# =========================================================

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
    return is_platform_admin(user) or is_master_admin(user)


def can_block_accounts(user) -> bool:
    return is_platform_admin(user) or is_master_admin(user)