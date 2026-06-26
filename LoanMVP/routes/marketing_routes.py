from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from sqlalchemy import func

from LoanMVP.extensions import db, csrf, limiter
from LoanMVP.models.admin import LicenseApplication
from LoanMVP.models.user_model import User


marketing_bp = Blueprint("marketing", __name__, url_prefix="/")

# ---------------------------------------------------------
# Shared page metadata
# ---------------------------------------------------------
SITE_NAME = "Ravlo"
SITE_TAGLINE = "The Operating System for Real Estate."

PAGE_META = {
    "home": {
        "title": "Ravlo | The Operating System for Real Estate",
        "description": "Run deals, analysis, budgets, projects, capital, partners, coaching, and AI in one connected real estate operating system.",
        "template": "marketing/home.html",
        "hero_image": "images/marketing/hero_combined.png",
    },
    "why_ravlo": {
        "title": "Why Ravlo | The Operating System for Real Estate",
        "description": "Learn why Ravlo connects Investor OS, Lending OS, Partner Network, Academy coaching, and AI into one real estate operating system.",
        "template": "marketing/why_ravlo.html",
        "hero_image": "images/marketing/hero_combined.png",
    },
    "about": {
        "title": "About Ravlo",
        "description": "Learn about Ravlo’s mission to give investors a smarter, clearer way to evaluate and execute real estate deals.",
        "template": "marketing/about.html",
        "hero_image": "images/marketing/city_skyline.jpg",
    },
    "plans": {
        "title": "Plans | Ravlo",
        "description": "Explore Ravlo plans for investors, teams, and growing real estate operators.",
        "template": "marketing/plans.html",
        "hero_image": "images/marketing/luxury_property.jpg",
    },
    "partners": {
        "title": "Partners | Ravlo",
        "description": "Connect with trusted real estate partners, vendors, and services through the Ravlo ecosystem.",
        "template": "marketing/partners.html",
        "hero_image": "images/partners/partners-hero.jpg",
    },
    "enter": {
        "title": "Enter Ravlo",
        "description": "Access your Ravlo workspace and step into your investor command center.",
        "template": "marketing/enter.html",
        "hero_image": "images/marketing/dashboard.jpg",
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
        "hero_image": "images/marketing/city_skyline.jpg",
    },
    "lenders_contact": {
        "title": "Lenders Contact | Ravlo",
        "description": "Request a demo, founders access, or a licensing conversation for Ravlo Lending OS.",
        "template": "marketing/lenders_contact.html",
        "hero_image": "images/marketing/lending_os_hero.jpg",
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
        "template": "marketing/terms_launch.html",
    },
    "privacy": {
        "title": "Privacy Policy | Ravlo",
        "description": "Read Ravlo’s privacy policy.",
        "template": "marketing/privacy_launch.html",
    },
    "disclaimer": {
        "title": "Disclaimer | Ravlo",
        "description": "Read Ravlo's platform disclaimer and important use limitations.",
        "template": "marketing/disclaimer.html",
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
        "hero_image": "images/vision/property.jpg",
    },
    "mission": {
        "title": "Mission | Ravlo",
        "description": "See Ravlo’s mission to simplify and elevate real estate investing workflows.",
        "template": "marketing/mission.html",
        "hero_image": "images/marketing/city_skyline.jpg",
    },
    "story": {
        "title": "Our Story | Ravlo",
        "description": "Read the story behind Ravlo and why it was built.",
        "template": "marketing/story.html",
        "hero_image": "images/about/team_strategy.jpg",
    },
    "partner_plans": {
        "title": "Partner Plans | Ravlo",
        "description": "Choose the Ravlo partner plan that fits your business and connect with investors through the platform.",
        "template": "marketing/partner_plans.html",
        "hero_image": "images/marketing/interior_luxury.jpg",
    },
    "academy": {
        "title": "Ravlo Academy | Real Estate Coaching",
        "description": "Practical real estate coaching, AI-guided learning, platform walkthroughs, and business-building resources included with Ravlo subscription access.",
        "template": "marketing/academy.html",
        "hero_image": "images/marketing/city_skyline.jpg",
    },
}


def _owner_admin_email() -> str:
    return (current_app.config.get("OWNER_ADMIN_EMAIL") or "").strip().lower()


def _single_admin_mode_enabled() -> bool:
    return bool(current_app.config.get("SINGLE_ADMIN_MODE", False))


def _owner_admin_exists() -> bool:
    owner_email = _owner_admin_email()
    if not owner_email:
        return False
    return (
        db.session.query(User.id)
        .filter(func.lower(User.email) == owner_email)
        .first()
        is not None
    )


def _workspace_recovery_mode() -> bool:
    if db.session.query(User.id).first() is None:
        return True
    return _single_admin_mode_enabled() and not _owner_admin_exists()


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
            {"label": "Why Ravlo", "endpoint": "marketing.why_ravlo"},
            {"label": "Plans", "endpoint": "marketing.plans"},
            {"label": "Partners", "endpoint": "marketing.partners"},
            {"label": "Tour", "endpoint": "marketing.tour"},
            {"label": "Contact", "endpoint": "marketing.contact"},
            {"label": "Enter", "endpoint": "marketing.enter"},
        ],
        "recovery_mode": _workspace_recovery_mode(),
        "owner_admin_email": _owner_admin_email(),
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
# HOME / WHY RAVLO
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


@marketing_bp.route("/why-ravlo")
def why_ravlo():
    return render_marketing_page("why_ravlo")


# ---------------------------------------------------------
# CORE MARKETING PAGES
# ---------------------------------------------------------
@marketing_bp.route("/about")
def about():
    return render_marketing_page("about")


@marketing_bp.route("/plans")
def plans():
    return render_marketing_page("plans")


@marketing_bp.route("/pricing")
def pricing():
    return render_template("marketing/lending_pricing.html")


@marketing_bp.route("/partners")
def partners():
    return render_marketing_page("partners")


@marketing_bp.route("/enter")
def enter():
    return render_marketing_page("enter")


@marketing_bp.route("/tour")
def tour():
    return render_marketing_page("tour")


# ---------------------------------------------------------
# CONTACT
# ---------------------------------------------------------
@marketing_bp.route("/contact", methods=["GET", "POST"])
@csrf.exempt
@limiter.limit("5 per minute", methods=["POST"])
def contact():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        subject = (request.form.get("subject") or "").strip()
        message = (request.form.get("message") or "").strip()

        if not name or not email or not message:
            flash("Name, email, and message are required.", "warning")
            return redirect(url_for("marketing.contact"))

        notes_body = f"Subject: {subject}\n\n{message}" if subject else message
        row = LicenseApplication(
            company_name="—",
            contact_name=name,
            email=email,
            business_type="contact",
            notes=notes_body,
            status="new",
        )
        db.session.add(row)
        db.session.commit()
        _notify_admin_contact(name, email, subject, message)
        flash("Message sent — we'll be in touch shortly.", "success")
        return redirect(url_for("marketing.contact"))

    return render_marketing_page("contact")


def _notify_admin_contact(name: str, email: str, subject: str, message: str) -> None:
    try:
        from LoanMVP.app import mail
        from flask_mail import Message as MailMessage

        admin_email = _owner_admin_email()
        if not admin_email:
            return

        subj_line = subject or "(no subject)"
        msg = MailMessage(
            subject=f"[Ravlo Contact] {subj_line} — {email}",
            recipients=[admin_email],
        )
        msg.body = (
            f"New contact form submission:\n\n"
            f"Name:    {name}\n"
            f"Email:   {email}\n"
            f"Subject: {subj_line}\n\n"
            f"{message}\n\n"
            f"---\nReview at https://ravlohq.com/admin/dashboard"
        )
        mail.send(msg)
    except Exception as e:
        current_app.logger.warning("Contact admin notification failed: %s", e)


@marketing_bp.route("/lenders-contact")
def lenders_contact():
    topic = request.args.get("topic", "")
    return render_marketing_page("lenders_contact", selected_topic=topic)


# ---------------------------------------------------------
# SUPPORT / FAQ / LEGAL
# ---------------------------------------------------------
@marketing_bp.route("/support")
def support():
    return render_marketing_page("support")


@marketing_bp.route("/faq")
def faq():
    return render_marketing_page("faq")


@marketing_bp.route("/terms")
def terms():
    return render_marketing_page("terms")


@marketing_bp.route("/privacy")
def privacy():
    return render_marketing_page("privacy")


@marketing_bp.route("/disclaimer")
def disclaimer():
    return render_marketing_page("disclaimer")


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


@marketing_bp.route("/partners/plans")
def partner_plans():
    return render_marketing_page("partner_plans")


# ---------------------------------------------------------
# LENDING OS
# ---------------------------------------------------------
@marketing_bp.route("/lending-os")
def lending_os():
    return render_template(
        "marketing/lending_os.html",
        page_title="Ravlo Lending OS",
        meta_description="Ravlo Lending OS for modern lending workflow, borrower intake, team execution, and software licensing.",
        page_key="lending_os",
        hero_image="images/marketing/lending_os_hero.jpg",
    )


@marketing_bp.route("/lending-os/request-preview", methods=["POST"])
@csrf.exempt
@limiter.limit("5 per minute")
def lending_os_request_preview():
    first_name = (request.form.get("first_name") or "").strip()
    last_name = (request.form.get("last_name") or "").strip()
    company = (request.form.get("company") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    phone = (request.form.get("phone") or "").strip()

    if not email:
        flash("Email is required.", "warning")
        return redirect(url_for("marketing.lending_os") + "#request-preview")

    existing = LicenseApplication.query.filter(
        func.lower(LicenseApplication.email) == email,
        LicenseApplication.business_type == "lending_os_lead",
    ).first()
    if not existing:
        app_row = LicenseApplication(
            company_name=company or "—",
            contact_name=f"{first_name} {last_name}".strip() or email,
            email=email,
            phone=phone or None,
            business_type="lending_os_lead",
            status="new",
        )
        db.session.add(app_row)
        db.session.commit()

    _notify_admin_lending_os_lead(first_name, last_name, company, email, phone)
    _send_lending_os_lead_confirmation(first_name, email)
    return redirect(url_for("marketing.lending_os_preview_thanks"))


@marketing_bp.route("/lending-os/preview-requested")
def lending_os_preview_thanks():
    return render_template("marketing/lending_os_preview_thanks.html")


def _send_lending_os_lead_confirmation(first_name: str, email: str) -> None:
    try:
        from LoanMVP.app import mail
        from flask_mail import Message as MailMessage

        name = first_name or "there"
        msg = MailMessage(
            subject="We received your Ravlo Lending OS request",
            recipients=[email],
        )
        msg.html = f"""
        <div style="font-family:Inter,sans-serif;max-width:560px;margin:0 auto;padding:32px 24px;color:#0f1117;">
          <img src="https://ravlohq.com/static/images/ravlo-logo-dark.png" alt="Ravlo" style="height:32px;margin-bottom:28px;">
          <h2 style="font-size:22px;font-weight:700;margin:0 0 12px;">Hey {name}, we got your request!</h2>
          <p style="font-size:15px;line-height:1.6;color:#374151;">
            Thanks for your interest in Ravlo Lending OS. A member of our team will reach out within <strong>2 business hours</strong> to walk you through the platform and set up your team's access.
          </p>
          <p style="font-size:15px;line-height:1.6;color:#374151;margin-top:16px;">In the meantime, feel free to reply to this email with any questions.</p>
          <p style="margin-top:28px;font-size:13px;color:#9ca3af;">— The Ravlo Team</p>
        </div>
        """
        mail.send(msg)
    except Exception as e:
        print(f"[lending_os] lead confirmation email failed: {e}")


def _notify_admin_lending_os_lead(first_name, last_name, company, email, phone) -> None:
    try:
        from LoanMVP.app import mail
        from flask_mail import Message as MailMessage
        from LoanMVP.routes.auth import _owner_admin_email

        admin_email = _owner_admin_email()
        if not admin_email:
            return

        msg = MailMessage(
            subject=f"[Ravlo] New Lending OS Lead — {email}",
            recipients=[admin_email],
        )
        msg.body = (
            f"New Lending OS lead:\n\n"
            f"Name: {first_name} {last_name}\n"
            f"Company: {company}\n"
            f"Email: {email}\n"
            f"Phone: {phone}\n\n"
            f"Follow up within 2 hours, then invite them via the admin invite system.\n"
            f"https://ravlohq.com/admin/dashboard"
        )
        mail.send(msg)
    except Exception as e:
        print(f"[lending_os] admin notification failed: {e}")


# ---------------------------------------------------------
# APPLICATIONS / ACADEMY
# ---------------------------------------------------------
@marketing_bp.route("/apply", methods=["GET", "POST"])
@csrf.exempt
@limiter.limit("5 per minute", methods=["POST"])
def apply():
    if request.method == "POST":
        company_name = (request.form.get("company_name") or "").strip()
        contact_name = (request.form.get("contact_name") or "").strip()
        email = (request.form.get("email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        website = (request.form.get("website") or "").strip()
        business_type = (request.form.get("business_type") or "").strip()
        team_size = (request.form.get("team_size") or "").strip()
        plan_interest = (request.form.get("plan_interest") or "").strip()
        monthly_loan_volume = (request.form.get("monthly_loan_volume") or "").strip()
        current_tools = (request.form.get("current_tools") or "").strip()
        goals = (request.form.get("goals") or "").strip()
        notes = (request.form.get("notes") or "").strip()

        if not company_name or not contact_name or not email:
            flash("Company name, contact name, and email are required.", "warning")
            return render_template("marketing/apply.html")

        app_row = LicenseApplication(
            company_name=company_name,
            contact_name=contact_name,
            email=email,
            phone=phone,
            website=website,
            business_type=business_type,
            team_size=team_size,
            plan_interest=plan_interest,
            monthly_loan_volume=monthly_loan_volume,
            current_tools=current_tools,
            goals=goals,
            notes=notes,
            status="new",
        )
        db.session.add(app_row)
        db.session.commit()
        flash("Your application has been submitted.", "success")
        return redirect(url_for("marketing.apply_success"))

    return render_template("marketing/apply.html")


@marketing_bp.route("/apply/success")
def apply_success():
    return render_template("marketing/apply_success.html")


@marketing_bp.route("/academy")
def academy():
    return render_template("marketing/academy.html")


@marketing_bp.route("/university")
def university_redirect():
    return redirect(url_for("marketing.academy"), code=301)


@marketing_bp.route("/university/portal")
def university_portal_redirect():
    return redirect(url_for("university.portal"), code=301)


@marketing_bp.route("/investor-access")
def investor_access():
    return render_template(
        "marketing/investor_access.html",
        page_title="Investor Access Program | Ravlo",
        meta_description="5 exclusive spots — get up to 3 months of Ravlo Enterprise free in exchange for feedback. One survey per month, one free month earned.",
    )


@marketing_bp.route("/refer")
def referral():
    return render_template(
        "marketing/referral.html",
        page_title="Refer & Earn | Ravlo",
        meta_description="Refer a friend to Ravlo and you both get a free month when they sign up. No limits — every referral earns another month.",
    )
