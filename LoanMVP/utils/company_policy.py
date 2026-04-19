# ─────────────────────────────────────────────────────────────────────────────
# LoanMVP/utils/company_policy.py
#
# Company-level lending policy.
# Replaces all the individual lo_is_external / lo_licensed_residential flags.
# The restriction flows from the company down to every LO under it.
# ─────────────────────────────────────────────────────────────────────────────

from flask import current_app


def get_caughman_mason_company_id() -> int:
    """
    Returns Caughman Mason's company_id from app config.
    Set CAUGHMAN_MASON_COMPANY_ID in your .env or app config.
    """
    return int(current_app.config.get("CAUGHMAN_MASON_COMPANY_ID", 1))


def get_company_lending_policy(company) -> dict:
    """
    Returns the lending policy for a company.

    Caughman Mason:
        investment_only = True   (fix & flip, DSCR, bridge, construction, etc.)
        licensed_residential = False

    Every other company (external licensed LOs, future lenders):
        investment_only = False  (their license covers what it covers)
        licensed_residential = True by default — they are responsible for their scope

    Returns dict:
        {
            "investment_only": bool,
            "licensed_residential": bool,
            "company_name": str,
            "is_caughman_mason": bool,
        }
    """
    if company is None:
        # No company = platform-level user (admin, etc.)
        return {
            "investment_only": False,
            "licensed_residential": True,
            "company_name": "Ravlo Platform",
            "is_caughman_mason": False,
        }

    try:
        cm_id = get_caughman_mason_company_id()
        is_cm = (company.id == cm_id)
    except Exception:
        is_cm = False

    return {
        "investment_only": is_cm,
        "licensed_residential": not is_cm,
        "company_name": company.name or "Unknown Company",
        "is_caughman_mason": is_cm,
    }


def get_user_lending_policy(user) -> dict:
    """
    Resolve lending policy for any user by looking up their company.
    Use this in VIP dashboard routing and loan type validation.
    """
    from LoanMVP.models.admin import Company

    company_id = getattr(user, "company_id", None)
    company = Company.query.get(company_id) if company_id else None
    return get_company_lending_policy(company)


def is_investment_only_user(user) -> bool:
    """Quick check — is this user restricted to investment loans only?"""
    return get_user_lending_policy(user)["investment_only"]


def is_out_of_scope_loan_type(loan_type: str, policy: dict) -> bool:
    """
    Returns True if the loan type is outside this company's licensing scope.
    Used to flag or block residential loans for Caughman Mason LOs.
    """
    if not policy["investment_only"]:
        return False  # No restriction for this company

    RESIDENTIAL_TYPES = {
        "conventional", "fha", "va", "usda", "conforming",
        "primary residence", "owner occupied", "owner-occupied",
        "heloc", "home equity",
    }
    lt = (loan_type or "").strip().lower()
    return any(r in lt for r in RESIDENTIAL_TYPES)


# Investment loan types — valid for all companies
INVESTMENT_LOAN_TYPES = [
    "Fix & Flip",
    "Rental / DSCR",
    "Bridge Loan",
    "New Construction",
    "Investor Capital",
    "Land Acquisition",
    "Development Capital",
    "Hard Money",
    "Private Money",
]

# Full loan type list — for licensed external LOs
ALL_LOAN_TYPES = INVESTMENT_LOAN_TYPES + [
    "Conventional",
    "FHA",
    "VA",
    "USDA",
    "Jumbo",
    "HELOC",
    "Home Equity",
    "Refinance",
    "Cash-Out Refi",
]
