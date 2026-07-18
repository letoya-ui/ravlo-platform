# ===============================================================
#   RAVLO PRICING PLAYBOOK -- standard/enterprise rate card + the
#   AE / Sales Manager / Executive discount-approval guardrails.
# ===============================================================
"""Encodes Ravlo's pricing so every AE quote comes from the same rate
card and the same approval rules instead of memory. Consumed by
LoanMVP/routes/account_executive.py's quote-builder on a deal.
"""
from decimal import Decimal, InvalidOperation

STANDARD_PARTNER_PLANS = {
    "solo": {"label": "Solo", "setup": Decimal("499"), "monthly": Decimal("149")},
    "professional": {"label": "Professional", "setup": Decimal("1499"), "monthly": Decimal("399")},
    "business": {"label": "Business", "setup": Decimal("2500"), "monthly": Decimal("699")},
}

STANDARD_LENDING_PLANS = {
    "individual_lo": {"label": "Individual LO", "setup": Decimal("499"), "monthly": Decimal("149")},
    "branch": {"label": "Branch", "setup": Decimal("2500"), "monthly": Decimal("799")},
    "regional": {"label": "Regional", "setup": Decimal("5000"), "monthly": Decimal("1499")},
}

# Every quotable standard plan, keyed the same way pricing_plan is stored
# on the deal. "enterprise" is looked up via ENTERPRISE_TIERS instead.
STANDARD_PLANS = {**STANDARD_PARTNER_PLANS, **STANDARD_LENDING_PLANS}

# (max_users, setup, monthly_starting, label) ordered smallest-first;
# max_users None ("300+") has no rate-card number -- it's an executive
# quote instead of a lookup.
ENTERPRISE_TIERS = [
    (25, Decimal("5000"), Decimal("1500"), "Up to 25 users"),
    (75, Decimal("10000"), Decimal("3000"), "26-75 users"),
    (150, Decimal("15000"), Decimal("5000"), "76-150 users"),
    (300, Decimal("25000"), Decimal("7500"), "151-300 users"),
    (None, None, None, "300+ users"),
]

ADD_ONS = {
    "white_label": {"label": "White Label", "setup": Decimal("5000"), "monthly": Decimal("1000")},
    "additional_workspace": {"label": "Additional Workspace", "monthly": Decimal("100")},
    "additional_training": {"label": "Additional Training", "per_session": Decimal("500")},
    "priority_support": {"label": "Priority Support", "monthly": Decimal("500")},
}
DATA_MIGRATION_MINIMUM = Decimal("1500")

AE_MAX_DISCOUNT_PERCENT = Decimal("10")
AE_MAX_SETUP_WAIVER = Decimal("500")
SALES_MANAGER_MAX_DISCOUNT_PERCENT = Decimal("20")

APPROVAL_LEVELS = ["ae", "sales_manager", "executive"]


def _dec(value, default="0"):
    if value is None or value == "":
        return Decimal(default)
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal(default)


def enterprise_tier_for_user_count(user_count):
    """Looks up the enterprise rate-card band for a given seat count.
    Returns None for the 300+ band since it has no rate-card number --
    that's a deliberate "requires an executive quote" signal, not a bug.
    """
    count = _dec(user_count)
    for max_users, setup, monthly, label in ENTERPRISE_TIERS:
        if max_users is None:
            return None
        if count <= max_users:
            return {"label": label, "setup": setup, "monthly": monthly}
    return None


def list_price_for_plan(pricing_plan, enterprise_user_count=None):
    """Returns {"label", "setup", "monthly"} list pricing for a plan key,
    or None if it can't be looked up (unknown plan, or an enterprise deal
    over 300 seats that needs a manual executive quote instead)."""
    if pricing_plan == "enterprise":
        return enterprise_tier_for_user_count(enterprise_user_count)
    return STANDARD_PLANS.get(pricing_plan)


def compute_quote(list_setup_fee, list_monthly_fee, discount_percent=None, setup_fee_waived=None):
    """Applies a monthly % discount and a flat setup-fee waiver to list
    pricing, returning the AE's actual quoted (setup, monthly) numbers."""
    list_setup_fee = _dec(list_setup_fee)
    list_monthly_fee = _dec(list_monthly_fee)
    discount_percent = _dec(discount_percent)
    setup_fee_waived = _dec(setup_fee_waived)

    quoted_monthly = (list_monthly_fee * (Decimal(1) - discount_percent / Decimal(100))).quantize(Decimal("0.01"))
    quoted_setup = max(list_setup_fee - setup_fee_waived, Decimal("0.00"))
    return quoted_setup, quoted_monthly


def required_approval_level(
    *,
    is_enterprise=False,
    is_white_label=False,
    is_custom_development=False,
    is_multi_year=False,
    is_strategic_partnership=False,
    discount_percent=None,
    setup_fee_waived=None,
):
    """Encodes the 3-tier approval structure from the Ravlo Pricing
    Playbook:
      - AE Authority: <=10% discount, <=$500 setup waiver, no approval.
      - Sales Manager: <=20% discount, can reduce setup fees further.
      - Executive Approval: enterprise deals, white-label licensing,
        custom development, discounts over 20%, multi-year agreements,
        strategic partnerships.
    Returns one of "ae", "sales_manager", "executive".
    """
    discount_percent = _dec(discount_percent)
    setup_fee_waived = _dec(setup_fee_waived)

    if (
        is_enterprise
        or is_white_label
        or is_custom_development
        or is_multi_year
        or is_strategic_partnership
        or discount_percent > SALES_MANAGER_MAX_DISCOUNT_PERCENT
    ):
        return "executive"
    if discount_percent > AE_MAX_DISCOUNT_PERCENT or setup_fee_waived > AE_MAX_SETUP_WAIVER:
        return "sales_manager"
    return "ae"
