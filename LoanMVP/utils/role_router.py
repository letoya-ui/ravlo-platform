def _dashboard_for_role(role: str) -> str:
    """
    Return the dashboard endpoint for a given role.
    Used after login or registration.
    """

    role = (role or "").lower().strip()

    role_map = {
        "investor": "investor.command_center",

        "borrower": "borrower.dashboard",

        "loan_officer": "loan_officer.dashboard",
        "processor": "processor.dashboard",
        "underwriter": "underwriter.dashboard",

        "admin": "admin.dashboard",
        "executive": "admin.dashboard",
        "partner": "partner.dashboard",
    }

    return role_map.get(role, "investor.command_center")