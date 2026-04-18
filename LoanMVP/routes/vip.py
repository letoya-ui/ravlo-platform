# LoanMVP/routes/vip.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user

from LoanMVP.extensions import db
from LoanMVP.models.vip_models import (
    VIPProfile,
    VIPIncome,
    VIPExpense,
    VIPAssistantSuggestion,
)
from LoanMVP.services.vip_ai_pilot import parse_vip_command
from LoanMVP.utils.decorators import role_required

vip_bp = Blueprint("vip", __name__, url_prefix="/vip")


def get_or_create_vip_profile():
    profile = VIPProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = VIPProfile(
            user_id=current_user.id,
            display_name=getattr(current_user, "name", None) or getattr(current_user, "email", "VIP User"),
            role_type="realtor",
            assistant_name="Ravlo",
        )
        db.session.add(profile)
        db.session.commit()
    return profile


def get_dashboard_name(profile):
    return profile.dashboard_title or profile.business_name or profile.display_name or "VIP Workspace"


@vip_bp.get("/")
@role_required("partner_group", "admin")
def index():
    profile = get_or_create_vip_profile()

    role_map = {
        "realtor": "vip.realtor_dashboard",
        "contractor": "vip.contractor_dashboard",
        "designer": "vip.designer_dashboard",
        "partner": "vip.partner_dashboard",
        "loan_officer": "vip.loan_officer_dashboard",
        "lender": "vip.loan_officer_dashboard",
    }
    return redirect(url_for(role_map.get(profile.role_type, "vip.realtor_dashboard")))


@vip_bp.get("/realtor")
@role_required("partner_group", "admin")
def realtor_dashboard():
    profile = get_or_create_vip_profile()
    return render_template(
        "vip/realtor/dashboard.html",
        vip_profile=profile,
        header_name=get_dashboard_name(profile),
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.realtor_dashboard"),
    )


@vip_bp.get("/contractor")
@role_required("partner_group", "admin")
def contractor_dashboard():
    profile = get_or_create_vip_profile()
    return render_template(
        "vip/contractor/dashboard.html",
        vip_profile=profile,
        header_name=get_dashboard_name(profile),
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.contractor_dashboard"),
    )


@vip_bp.get("/designer")
@role_required("partner_group", "admin")
def designer_dashboard():
    profile = get_or_create_vip_profile()
    return render_template(
        "vip/designer/dashboard.html",
        vip_profile=profile,
        header_name=get_dashboard_name(profile),
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.designer_dashboard"),
    )


@vip_bp.get("/partner")
@role_required("partner_group", "admin")
def partner_dashboard():
    profile = get_or_create_vip_profile()
    return render_template(
        "vip/partner/dashboard.html",
        vip_profile=profile,
        header_name=get_dashboard_name(profile),
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.partner_dashboard"),
    )


@vip_bp.get("/loan-officer")
@role_required("partner_group", "admin")
def loan_officer_dashboard():
    profile = get_or_create_vip_profile()
    return render_template(
        "vip/loan_officer/dashboard.html",
        vip_profile=profile,
        header_name=get_dashboard_name(profile),
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.loan_officer_dashboard"),
    )


@vip_bp.get("/finances")
@role_required("partner_group", "admin")
def finances():
    profile = get_or_create_vip_profile()

    incomes = (
        VIPIncome.query
        .filter_by(vip_profile_id=profile.id)
        .order_by(VIPIncome.created_at.desc())
        .limit(25)
        .all()
    )
    expenses = (
        VIPExpense.query
        .filter_by(vip_profile_id=profile.id)
        .order_by(VIPExpense.created_at.desc())
        .limit(25)
        .all()
    )

    total_income = sum((item.amount or 0) for item in incomes)
    total_expenses = sum((item.amount or 0) for item in expenses)
    net_profit = total_income - total_expenses

    return render_template(
        "vip/finances.html",
        vip_profile=profile,
        header_name=get_dashboard_name(profile),
        incomes=incomes,
        expenses=expenses,
        total_income=total_income,
        total_expenses=total_expenses,
        net_profit=net_profit,
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.index"),
    )


@vip_bp.get("/ai-pilot")
@role_required("partner_group", "admin")
def ai_pilot():
    profile = get_or_create_vip_profile()

    suggestions = (
        VIPAssistantSuggestion.query
        .filter_by(vip_profile_id=profile.id)
        .order_by(VIPAssistantSuggestion.created_at.desc())
        .limit(20)
        .all()
    )

    return render_template(
        "vip/ai_pilot.html",
        vip_profile=profile,
        header_name=get_dashboard_name(profile),
        suggestions=suggestions,
        portal="vip",
        portal_name="VIP",
        portal_home=url_for("vip.index"),
    )


@vip_bp.post("/ai-pilot/command")
@role_required("partner_group", "admin")
def ai_pilot_command():
    profile = get_or_create_vip_profile()

    command = (request.form.get("command") or "").strip()
    if not command:
        flash("Please enter a command.", "warning")
        return redirect(url_for("vip.ai_pilot"))

    result = parse_vip_command(command)

    suggestion = VIPAssistantSuggestion(
        vip_profile_id=profile.id,
        suggestion_type=result["suggestion_type"],
        title=result["title"],
        body=result.get("body"),
        source="manual",
    )
    db.session.add(suggestion)
    db.session.commit()

    flash("Assistant suggestion created.", "success")
    return redirect(url_for("vip.ai_pilot"))
