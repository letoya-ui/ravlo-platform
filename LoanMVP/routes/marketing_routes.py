from flask import Blueprint, render_template, redirect, url_for

marketing_bp = Blueprint("marketing", __name__, url_prefix="/")

# -----------------------------
# HOME
# -----------------------------
@marketing_bp.route("/")
def homepage():
    return render_template("marketing/home.html")

@marketing_bp.route("/home")
def homepage_alias():
    return redirect(url_for("marketing.homepage"))

# -----------------------------
# ABOUT
# -----------------------------
@marketing_bp.route("/about")
def about():
    return render_template("marketing/about.html")

# -----------------------------
# PLANS
# -----------------------------
@marketing_bp.route("/plans")
def plans():
    return render_template("marketing/plans.html")

# -----------------------------
# PARTNERS
# -----------------------------
@marketing_bp.route("/partners")
def partners():
    return render_template("marketing/partners.html")

# -----------------------------
# ENTER
# -----------------------------
@marketing_bp.route("/enter")
def enter():
    return render_template("marketing/enter.html")

# -----------------------------
# PRODUCT TOUR
# -----------------------------
@marketing_bp.route("/tour")
def tour():
    return render_template("marketing/tour.html")

# -----------------------------
# CONTACT
# -----------------------------
@marketing_bp.route("/contact")
def contact():
    return render_template("marketing/contact.html")

# -----------------------------
# SUPPORT
# -----------------------------
@marketing_bp.route("/support")
def support():
    return render_template("marketing/support.html")

@marketing_bp.route("/faq")
def faq():
    return render_template("marketing/faq.html")

# -----------------------------
# LEGAL
# -----------------------------
@marketing_bp.route("/terms")
def terms():
    return render_template("marketing/terms.html")

@marketing_bp.route("/privacy")
def privacy():
    return render_template("marketing/privacy.html")

# -----------------------------
# STUDIOS
# -----------------------------
@marketing_bp.route("/studios/deal-architect")
def studio_deal_architect():
    return render_template("marketing/studio_deal_architect.html")

@marketing_bp.route("/studios/renovation")
def studio_renovation():
    return render_template("marketing/studio_renovation.html")

@marketing_bp.route("/studios/build")
def studio_build():
    return render_template("marketing/studio_build.html")

# -----------------------------
# BRAND STORY PAGES
# -----------------------------
@marketing_bp.route("/vision")
def vision():
    return render_template("marketing/vision.html")

@marketing_bp.route("/mission")
def mission():
    return render_template("marketing/mission.html")

@marketing_bp.route("/story")
def story():
    return render_template("marketing/story.html")
