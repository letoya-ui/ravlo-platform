def _dashboard_for_role(role: str) -> str:
    """
    Return the dashboard endpoint for a given role.
    Used after login or registration.
    """

    role = (role or "").lower().strip()

    # 🔥 Handle all admin-level roles FIRST
    if role in ["admin", "platform_admin", "master_admin", "lending_admin", "executive"]:
        return "admin.dashboard"

    role_map = {
        "investor": "investor.command_center",
        "borrower": "borrower.dashboard",

        "loan_officer": "loan_officer.dashboard",
        "processor": "processor.dashboard",
        "underwriter": "underwriter.dashboard",

        "partner": "partners.dashboard",  # ⚠️ fixed typo here
    }

    return role_map.get(role, "marketing.marketing_home")

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

    return role_map.get(role, role.replace("_", " ").title())
