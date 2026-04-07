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