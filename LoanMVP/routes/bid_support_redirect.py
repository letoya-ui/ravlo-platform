from flask import Blueprint, redirect, request, url_for
from flask_login import login_required

bid_support_redirect_bp = Blueprint("bid_support_redirect", __name__)


@bid_support_redirect_bp.before_app_request
def redirect_legacy_bid_support():
    """Send the legacy executive bid-support page to the current queue.

    The old `/executive/bid-support` view only knows the first set of bid
    statuses and does not include the newer approval workflow states. The
    current construction office queue supports `approval_needed`,
    `approved_to_submit`, client review, and follow-up. Redirect GET traffic so
    Letoya, Sandra, and Jamaine all see the same active construction workflow.
    """
    if request.method != "GET":
        return None

    path = request.path.rstrip("/")
    if path == "/executive/bid-support":
        return redirect(url_for("construction_office.packages"))

    return None
