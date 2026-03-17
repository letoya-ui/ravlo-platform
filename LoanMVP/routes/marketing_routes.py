from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request

marketing_bp = Blueprint("marketing", __name__, url_prefix="/")

# ---------------------------------------------------------
# Shared page metadata
# ---------------------------------------------------------
SITE_NAME = "Ravlo"
SITE_TAGLINE = "Investor Command Center for deals, renovation, build strategy, and budgeting."

PAGE_META = {
    "home": {
        "title": "Ravlo | Investor Command Center",
        "description": "Analyze deals, plan renovations, model new construction, and manage your investor workflow in one platform.",
        "template": "marketing/home.html",
        "hero_image": "images/marketing/hero_combined.png",
    },
    "about": {
        "title": "About Ravlo",
        "description": "Learn about Ravlo’s mission to give investors a smarter, clearer way to evaluate and execute real estate deals.",
        "template": "marketing/about.html",
        "hero_image": "images/marketing/city_skyline.jpg.PNG",
    },
    "plans": {
        "title": "Plans | Ravlo",
        "description": "Explore Ravlo plans for investors, teams, and growing real estate operators.",
        "template": "marketing/plans.html",
        "hero_image": "images/marketing/luxury_property.jpg.PNG",
    },
    "partners": {
        "title": "Partners | Ravlo",
        "description": "Connect with trusted real estate partners, vendors, and services through the Ravlo ecosystem.",
        "template": "marketing/partners.html",
        "hero_image": "images/marketing/interior_luxury.jpg.PNG",
    },
    "enter": {
        "title": "Enter Ravlo",
        "description": "Access your Ravlo workspace and step into your investor command center.",
        "template": "marketing/enter.html",
        "hero_image": "images/marketing/command_center.jpeg",
    },
    "tour": {
        "title": "Product Tour | Ravlo",
        "description": "Take a tour of Ravlo’s investor platform, workflows, deal tools, and studio experiences.",
        "template": "marketing/tour.html",
        "hero_image": "images/marketing/command_center.jpeg",
    },
    "contact": {
        "title": "Contact Ravlo",
        "description": "Get in touch with Ravlo for questions, demos, partnerships, or support.",
        "template": "marketing/contact.html",
        "hero_image": "images/marketing/city_skyline.jpg.PNG",
    },
    "support": {
        "title": "Support | Ravlo",
        "description": "Get help using Ravlo, find answers, and access support resources.",
        "template": "marketing/support.html",
        "hero_image": "images/marketing/command_center.jpeg",
    },
    "faq": {
        "title": "FAQ | Ravlo",
        "description": "Read frequently asked questions about Ravlo, plans, studios, and access.",
        "template": "marketing/faq.html",
        "hero_image": "images/marketing/deals.jpeg",
    },
    "terms": {
        "title": "Terms of Service | Ravlo",
        "description": "Read Ravlo’s terms of service.",
        "template": "marketing/terms.html",
    },
    "privacy": {
        "title": "Privacy Policy | Ravlo",
        "description": "Read Ravlo’s privacy policy.",
        "template": "marketing/privacy.html",
    },
    "deal_architect": {
        "title": "Deal Architect | Ravlo Studio",
        "description": "Model investment scenarios, analyze numbers, and shape smarter acquisition decisions.",
        "template": "marketing/studio_deal_architect.html",
        "hero_image": "images/studios/deal_architect.jpg",
    },
    "renovation": {
        "title": "Renovation Studio | Ravlo",
        "description": "Visualize renovation plans, scope improvements, and bring property transformations to life.",
        "template": "marketing/studio_renovation.html",
        "hero_image": "images/studios/renovation_studio.jpg",
    },
    "build": {
        "title": "Build Studio | Ravlo",
        "description": "Plan new construction ideas, evaluate build concepts, and move from vision to execution.",
        "template": "marketing/studio_build.html",
        "hero_image": "images/studios/build_studio.jpg",
    },
    "budget": {
        "title": "Budget Studio | Ravlo",
        "description": "Estimate project costs, manage budgets, and track real investment performance inside Ravlo.",
        "template": "marketing/studio_budget.html",
        "hero_image": "images/studios/budget_studio.jpg",
    },
    "vision": {
        "title": "Vision | Ravlo",
        "description": "Discover the long-term vision behind Ravlo and the future of investor operating systems.",
        "template": "marketing/vision.html",
        "hero_image": "images/vision/vision_placeholder.png",
    },
    "mission": {
        "title": "Mission | Ravlo",
        "description": "See Ravlo’s mission to simplify and elevate real estate investing workflows.",
        "template": "marketing/mission.html",
        "hero_image": "images/marketing/city_skyline.jpg.PNG",
    },
    "story": {
        "title": "Our Story | Ravlo",
        "description": "Read the story behind Ravlo and why it was built.",
        "template": "marketing/story.html",
        "hero_image": "images/marketing/interior_luxury.jpg.PNG",
    },
}


# ---------------------------------------------------------
# Shared renderer
# ---------------------------------------------------------
def render_marketing_page(page_key, **extra_context):
    page = PAGE_META[page_key]

    context = {
        "site_name": SITE_NAME,
        "site_tagline": SITE_TAGLINE,
        "page_title": page.get("title", SITE_NAME),
        "meta_description": page.get("description", SITE_TAGLINE),
        "hero_image": page.get("hero_image"),
        "canonical_url": request.base_url,
        "page_key": page_key,
        "nav_links": [
            {"label": "Home", "endpoint": "marketing.homepage"},
            {"label": "About", "endpoint": "marketing.about"},
            {"label": "Plans", "endpoint": "marketing.plans"},
            {"label": "Partners", "endpoint": "marketing.partners"},
            {"label": "Tour", "endpoint": "marketing.tour"},
            {"label": "Contact", "endpoint": "marketing.contact"},
            {"label": "Enter", "endpoint": "marketing.enter"},
        ],
    }

    context.update(extra_context)
    return render_template(page["template"], **context)


@marketing_bp.app_context_processor
def inject_marketing_globals():
    return {
        "site_name": SITE_NAME,
        "site_tagline": SITE_TAGLINE,
        "current_year": datetime.utcnow().year,
    }


# ---------------------------------------------------------
# HOME
# ---------------------------------------------------------
@marketing_bp.route("/")
def homepage():
    return render_marketing_page(
        "home",
        featured_studios=[
            {
                "name": "Deal Architect",
                "endpoint": "marketing.studio_deal_architect",
                "description": "Run scenarios, compare strategies, and analyze your deal before you move.",
            },
            {
                "name": "Renovation Studio",
                "endpoint": "marketing.studio_renovation",
                "description": "Plan renovations and visualize improvements with clarity.",
            },
            {
                "name": "Build Studio",
                "endpoint": "marketing.studio_build",
                "description": "Explore new construction ideas and build concepts in one place.",
            },
            {
                "name": "Budget Studio",
                "endpoint": "marketing.studio_budget",
                "description": "Estimate costs, track expenses, and stay in control of your investment.",
            },
        ],
    )


@marketing_bp.route("/home")
def homepage_alias():
    return redirect(url_for("marketing.homepage"), code=301)


# ---------------------------------------------------------
# ABOUT
# ---------------------------------------------------------
@marketing_bp.route("/about")
def about():
    return render_marketing_page("about")


# ---------------------------------------------------------
# PLANS
# ---------------------------------------------------------
@marketing_bp.route("/plans")
def plans():
    return render_marketing_page("plans")


# ---------------------------------------------------------
# PARTNERS
# ---------------------------------------------------------
@marketing_bp.route("/partners")
def partners():
    return render_marketing_page("partners")


# ---------------------------------------------------------
# ENTER
# ---------------------------------------------------------
@marketing_bp.route("/enter")
def enter():
    return render_marketing_page("enter")


# ---------------------------------------------------------
# PRODUCT TOUR
# ---------------------------------------------------------
@marketing_bp.route("/tour")
def tour():
    return render_marketing_page("tour")


# ---------------------------------------------------------
# CONTACT
# ---------------------------------------------------------
@marketing_bp.route("/contact")
def contact():
    return render_marketing_page("contact")


# ---------------------------------------------------------
# SUPPORT / FAQ
# ---------------------------------------------------------
@marketing_bp.route("/support")
def support():
    return render_marketing_page("support")


@marketing_bp.route("/faq")
def faq():
    return render_marketing_page("faq")


# ---------------------------------------------------------
# LEGAL
# ---------------------------------------------------------
@marketing_bp.route("/terms")
def terms():
    return render_marketing_page("terms")


@marketing_bp.route("/privacy")
def privacy():
    return render_marketing_page("privacy")


# ---------------------------------------------------------
# STUDIOS
# ---------------------------------------------------------
@marketing_bp.route("/studios/deal-architect")
def studio_deal_architect():
    return render_marketing_page("deal_architect")


@marketing_bp.route("/studios/renovation")
def studio_renovation():
    return render_marketing_page("renovation")


@marketing_bp.route("/studios/build")
def studio_build():
    return render_marketing_page("build")


@marketing_bp.route("/studios/budget")
def studio_budget():
    return render_marketing_page("budget")


# ---------------------------------------------------------
# BRAND STORY
# ---------------------------------------------------------
@marketing_bp.route("/vision")
def vision():
    return render_marketing_page("vision")


@marketing_bp.route("/mission")
def mission():
    return render_marketing_page("mission")


@marketing_bp.route("/story")
def story():
    return render_marketing_page("story")
