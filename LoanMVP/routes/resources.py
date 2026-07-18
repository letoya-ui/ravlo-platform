# =========================================================
# 📚 Internal Sales Resources — one-pager + dashboard talking points
# for Account Executives, Ravlo admins, and executives.
# =========================================================
from flask import Blueprint, render_template
from flask_login import login_required

from LoanMVP.utils.decorators import role_required
from LoanMVP.services import ae_pricing

resources_bp = Blueprint("resources", __name__, url_prefix="/resources")


@resources_bp.route("/")
@login_required
@role_required("account_executive", "admin_group")
def index():
    return render_template("resources/index.html", title="Sales Resources")


@resources_bp.route("/pricing-playbook")
@login_required
@role_required("account_executive", "admin_group")
def pricing_playbook():
    """The Ravlo Pricing Playbook -- reads straight from
    LoanMVP/services/ae_pricing.py (the same rate card and approval rules
    the Account Executive deal tool enforces) so this reference can never
    drift out of sync with what a quote actually calculates.
    """
    sample_quotes = []
    for plan_key, discount, waiver in [("professional", 5, 0), ("branch", 15, 500)]:
        plan = ae_pricing.STANDARD_PLANS[plan_key]
        setup, monthly = ae_pricing.compute_quote(plan["setup"], plan["monthly"], discount, waiver)
        sample_quotes.append({
            "plan_label": plan["label"],
            "list_setup": plan["setup"],
            "list_monthly": plan["monthly"],
            "discount_percent": discount,
            "setup_fee_waived": waiver,
            "quoted_setup": setup,
            "quoted_monthly": monthly,
            "approval_level": ae_pricing.required_approval_level(discount_percent=discount, setup_fee_waived=waiver),
        })

    return render_template(
        "resources/pricing_playbook.html",
        title="Ravlo Pricing Playbook",
        partner_plans=ae_pricing.STANDARD_PARTNER_PLANS,
        lending_plans=ae_pricing.STANDARD_LENDING_PLANS,
        enterprise_tiers=ae_pricing.ENTERPRISE_TIERS,
        add_ons=ae_pricing.ADD_ONS,
        data_migration_minimum=ae_pricing.DATA_MIGRATION_MINIMUM,
        ae_max_discount=ae_pricing.AE_MAX_DISCOUNT_PERCENT,
        ae_max_waiver=ae_pricing.AE_MAX_SETUP_WAIVER,
        sales_manager_max_discount=ae_pricing.SALES_MANAGER_MAX_DISCOUNT_PERCENT,
        sample_quotes=sample_quotes,
    )
