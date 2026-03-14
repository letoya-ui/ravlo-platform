from flask import Blueprint, render_template

marketing_bp = Blueprint("marketing", __name__)

@marketing_bp.route("/")
def home():
    return render_template("marketing/home.html")


@marketing_bp.route("/about")
def about():
    return render_template("marketing/about.html")


@marketing_bp.route("/enter")
def enter():
    return render_template("marketing/enter.html")
