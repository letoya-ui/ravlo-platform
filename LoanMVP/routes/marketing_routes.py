from flask import Blueprint, render_template

marketing_bp = Blueprint("marketing", __name__, template_folder="templates")

# HOME
@marketing_bp.route("/")
@marketing_bp.route("/home")
def homepage():
    return render_template("marketing/home.html")

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
