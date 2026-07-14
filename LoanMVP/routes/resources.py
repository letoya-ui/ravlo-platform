# =========================================================
# 📚 Internal Sales Resources — one-pager + dashboard talking points
# for Account Executives, Ravlo admins, and executives.
# =========================================================
from flask import Blueprint, render_template
from flask_login import login_required

from LoanMVP.utils.decorators import role_required

resources_bp = Blueprint("resources", __name__, url_prefix="/resources")


@resources_bp.route("/")
@login_required
@role_required("account_executive", "admin_group")
def index():
    return render_template("resources/index.html", title="Sales Resources")
