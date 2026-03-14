from flask import redirect, url_for

@marketing_bp.route("/home")
def homepage_redirect():
    return redirect(url_for("marketing.homepage"))

marketing_bp = Blueprint("marketing", __name__, template_folder="templates")


# ABOUT
@marketing_bp.route("/about")
def about():
    return render_template("marketing/about.html")

# PLANS
@marketing_bp.route("/plans")
def plans():
    return render_template("marketing/plans.html")

# PARTNERS
@marketing_bp.route("/partners")
def partners():
    return render_template("marketing/partners.html")

# ENTER
@marketing_bp.route("/enter")
def enter():
    return render_template("marketing/enter.html")

# PRODUCT TOUR
@marketing_bp.route("/tour")
def tour():
    return render_template("marketing/tour.html")

@marketing_bp.route("/contact")
def contact():
    return render_template("marketing/contact.html")
