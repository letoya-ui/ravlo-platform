# =========================================================
# 🧩 System Control & Monitoring — LoanMVP Unified Version
# =========================================================

from flask import (
    Blueprint, render_template, request,
    jsonify, redirect, url_for, flash, current_app
)
from flask_login import current_user
from datetime import datetime

from LoanMVP.extensions import db, csrf
from LoanMVP.models.system_models import System, SystemLog, AuditLog, SystemSettings
from LoanMVP.models.loan_models import (
    BorrowerProfile, CreditProfile, LoanApplication, LoanIntakeSession,
    LoanNotification, LoanQuote, Upload,
)
from LoanMVP.models.document_models import (
    DocumentRequest, ESignedDocument, LoanDocument,
)
from LoanMVP.models.investor_models import (
    DealConversation, DealMessage, FundingRequest, InvestorProfile, Project,
)
from LoanMVP.models.borrowers import Deal, ProjectBudget, PropertyAnalysis
from LoanMVP.models.call_model import CallLog
from LoanMVP.models.renovation_models import RenovationMockup, BuildProject
from LoanMVP.models.ai_models import (
    AIAssistantInteraction, AIIntakeSummary, LoanAIConversation,
)
from LoanMVP.models.partner_models import (
    ExternalPartnerLead, PartnerConnectionRequest, PartnerJob,
)
from LoanMVP.models.activity_models import BorrowerActivity
from LoanMVP.models.credit_models import SoftCreditReport
from LoanMVP.models.campaign_model import Campaign, CampaignRecipient
from LoanMVP.models.processor_model import ProcessorProfile
from LoanMVP.models.underwriter_model import (
    UnderwriterProfile, UnderwriterTask, UnderwritingCondition, ConditionRequest,
)
from LoanMVP.models.crm_models import Lead, Message, CRMNote, Task
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.user_model import User

from LoanMVP.utils.decorators import role_required
from LoanMVP.ai.master_ai import master_ai   # Correct AI engine

system_bp = Blueprint("system", __name__, url_prefix="/system")
print(">>> SYSTEM ROUTES LOADED FROM:", __file__)


def _is_company_admin(user) -> bool:
    return ((getattr(user, "role", "") or "").strip().lower() == "admin")


def _is_owner_admin(user) -> bool:
    email = (getattr(user, "email", "") or "").strip().lower()
    owner_email = _owner_admin_email()
    return bool(owner_email and email == owner_email)


def _company_admin_guard(user):
    if not _is_company_admin(user):
        return None, None

    company_id = getattr(user, "company_id", None)
    if _is_owner_admin(user):
        return None, None

    if not company_id:
        # Admin without a company sees all users (same as non-company admin)
        return None, None

    return company_id, None


def _single_admin_mode_enabled() -> bool:
    return False


def _owner_admin_email() -> str:
    return (current_app.config.get("OWNER_ADMIN_EMAIL") or "").strip().lower()


def _remaining_user_count(excluded_user_id: int) -> int:
    return User.query.filter(User.id != excluded_user_id).count()


# =========================================================
# 🧭 Helper — Context Builder
# =========================================================
def get_system_context():
    """Central helper for system-wide context (info, logs, audits, uptime)."""

    system = System.query.first()
    if not system:
        system = System(
            name="LoanMVP Core",
            version="v1.0",
            uptime_start=datetime.utcnow()
        )
        db.session.add(system)
        db.session.commit()

    uptime_days = (datetime.utcnow() - system.uptime_start).days

    logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(20).all()
    audits = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(20).all()

    return {
        "system": system,
        "uptime_days": uptime_days,
        "logs": logs,
        "audits": audits
    }


# =========================================================
# 🧠 CM MASTER OPERATIONS DASHBOARD
# =========================================================
@system_bp.route("/cm-dashboard")
@role_required("system")
def cm_dashboard():

    # ---- LEADS ----
    leads = Lead.query.order_by(Lead.created_at.desc()).limit(5).all()

    # ---- LOANS ----
    loans = LoanApplication.query.order_by(LoanApplication.created_at.desc()).limit(5).all()

    # ---- PENDING DOCUMENT REQUESTS ----
    pending_docs = (
        DocumentRequest.query.filter_by(status="requested")
        .order_by(DocumentRequest.created_at.desc())
        .limit(10)
        .all()
    )

    # ---- STATS ----
    stats = {
        "total_leads": Lead.query.count(),
        "active_loans": LoanApplication.query.filter(LoanApplication.status != "completed").count(),
        "pending_conditions": DocumentRequest.query.filter_by(status="requested").count(),
    }

    # ---- AI Summary ----
    try:
        ai_summary = master_ai.ask(
            """
            Provide an executive-level summary of all departments:
            - Loan Officer
            - Processor
            - Underwriter
            
            Be direct, clear, and actionable.
            """,
            role="executive"
        )
    except:
        ai_summary = "⚠️ AI summary unavailable."

    return render_template(
        "system/cm_dashboard.html",
        leads=leads,
        loans=loans,
        pending_docs=pending_docs,
        stats=stats,
        ai_summary=ai_summary,
        title="CM Master Dashboard"
    )


# =========================================================
# 🔁 Heartbeat (System Ping)
# =========================================================
@system_bp.route("/heartbeat", methods=["POST"])
@csrf.exempt
@role_required("system")
def heartbeat():
    system = System.query.first()
    if not system:
        return jsonify({"status": "error", "message": "System not initialized"}), 404

    system.last_heartbeat = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "status": "ok",
        "timestamp": system.last_heartbeat.strftime("%Y-%m-%d %H:%M:%S")
    })


# =========================================================
# 📜 System Logs
# =========================================================
@system_bp.route("/logs")
@role_required("system")
def logs():
    ctx = get_system_context()
    ctx["logs"] = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(50).all()
    ctx["title"] = "System Logs"
    return render_template("system/logs.html", **ctx)


# =========================================================
# 🧾 Audit Console
# =========================================================
@system_bp.route("/audits")
@role_required("system")
def audits():
    ctx = get_system_context()
    ctx["audits"] = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(50).all()
    ctx["title"] = "Audit Console"
    return render_template("system/audits.html", **ctx)




# =========================================================
# 👥 User Management
# =========================================================
@system_bp.route("/users")
@role_required("system", "admin")
def users():
    company_id, redirect_response = _company_admin_guard(current_user)
    if redirect_response:
        return redirect_response

    ctx = get_system_context()
    if _is_company_admin(current_user) and company_id is not None:
        ctx["users"] = (
            User.query
            .filter_by(company_id=company_id)
            .order_by(User.created_at.desc())
            .all()
        )
        ctx["company"] = current_user.company
    else:
        ctx["users"] = User.query.order_by(User.created_at.desc()).all()

    ctx["title"] = "User Management"
    ctx["single_admin_mode"] = _single_admin_mode_enabled()
    ctx["owner_admin_email"] = _owner_admin_email()
    return render_template("system/users.html", **ctx)


# =========================================================
# 🟢 Toggle User Active Status
# =========================================================
@system_bp.route("/toggle_user/<int:user_id>", methods=["POST"])
@role_required("system", "admin")
def toggle_user(user_id):
    company_id, redirect_response = _company_admin_guard(current_user)
    if redirect_response:
        return redirect_response

    user = User.query.get_or_404(user_id)
    if _single_admin_mode_enabled() and (user.email or "").strip().lower() == _owner_admin_email():
        flash("The owner admin account is protected in single-admin mode.", "warning")
        return redirect(url_for("system.users"))

    if _is_company_admin(current_user) and company_id is not None and user.company_id != company_id:
        flash("You can only manage users from your own company.", "warning")
        return redirect(url_for("admin.company_dashboard", company_id=company_id))

    user.is_active = not user.is_active
    db.session.commit()

    flash(f"{'Deactivated' if not user.is_active else 'Activated'} user {user.email}.", "info")
    return redirect(url_for("system.users"))

# =========================================================
# 🗑️ Delete User
# =========================================================
@system_bp.route("/delete_user/<int:user_id>", methods=["POST"])
@role_required("system", "admin")
def delete_user(user_id):
    company_id, redirect_response = _company_admin_guard(current_user)
    if redirect_response:
        return redirect_response

    user = User.query.get_or_404(user_id)
    if _single_admin_mode_enabled() and (user.email or "").strip().lower() == _owner_admin_email():
        flash("The owner admin account is protected in single-admin mode.", "warning")
        return redirect(url_for("system.users"))

    if _is_company_admin(current_user) and company_id is not None and user.company_id != company_id:
        flash("You can only manage users from your own company.", "warning")
        return redirect(url_for("admin.company_dashboard", company_id=company_id))

    if user.id == current_user.id:
        flash("You cannot delete your own account from this screen.", "warning")
        return redirect(url_for("system.users"))

    if _remaining_user_count(user.id) == 0:
        flash("You cannot delete the last remaining user. Create another account first.", "warning")
        return redirect(url_for("system.users"))

    try:
        # Explicitly remove related rows whose FK is NOT NULL and
        # would otherwise cause a constraint violation when the ORM
        # tries to SET user_id = NULL during cascade.

        # -- CRM / messaging -------------------------------------------
        Message.query.filter(
            (Message.sender_id == user.id) | (Message.receiver_id == user.id)
        ).delete(synchronize_session="fetch")
        CRMNote.query.filter_by(user_id=user.id).delete(synchronize_session="fetch")

        conversation_ids = [
            c.id for c in DealConversation.query
            .filter_by(user_id=user.id)
            .with_entities(DealConversation.id)
            .all()
        ]
        if conversation_ids:
            DealMessage.query.filter(
                DealMessage.conversation_id.in_(conversation_ids)
            ).delete(synchronize_session="fetch")
        DealConversation.query.filter_by(user_id=user.id).delete(synchronize_session="fetch")

        # -- Renovation mockups & build projects -------------------------
        # Must delete BEFORE deals because RenovationMockup.deal_id is a FK
        # to deals.id (no ondelete clause → RESTRICT by default).
        RenovationMockup.query.filter_by(user_id=user.id).delete(
            synchronize_session="fetch"
        )
        # BuildProject child rows: ProjectBudget via build_project_id
        build_project_ids = [
            bp.id for bp in BuildProject.query
            .filter_by(user_id=user.id)
            .with_entities(BuildProject.id)
            .all()
        ]
        if build_project_ids:
            ProjectBudget.query.filter(
                ProjectBudget.build_project_id.in_(build_project_ids)
            ).delete(synchronize_session="fetch")
        BuildProject.query.filter_by(user_id=user.id).delete(
            synchronize_session="fetch"
        )

        # -- Deals & child rows ----------------------------------------
        deal_ids = [
            d.id for d in Deal.query
            .filter_by(user_id=user.id)
            .with_entities(Deal.id)
            .all()
        ]
        if deal_ids:
            FundingRequest.query.filter(
                FundingRequest.deal_id.in_(deal_ids)
            ).delete(synchronize_session="fetch")
            Project.query.filter(
                Project.deal_id.in_(deal_ids)
            ).delete(synchronize_session="fetch")
            ProjectBudget.query.filter(
                ProjectBudget.deal_id.in_(deal_ids)
            ).delete(synchronize_session="fetch")
            # Nullify deal_id on tables that reference these deals
            PartnerConnectionRequest.query.filter(
                PartnerConnectionRequest.deal_id.in_(deal_ids)
            ).update({"deal_id": None}, synchronize_session="fetch")
            RenovationMockup.query.filter(
                RenovationMockup.deal_id.in_(deal_ids)
            ).update({"deal_id": None}, synchronize_session="fetch")
        # User's own funding requests on other users' deals
        FundingRequest.query.filter_by(investor_id=user.id).delete(
            synchronize_session="fetch"
        )
        Deal.query.filter_by(user_id=user.id).delete(synchronize_session="fetch")

        # -- Calls, AI -------------------------------------------------
        CallLog.query.filter_by(user_id=user.id).delete(synchronize_session="fetch")
        AIAssistantInteraction.query.filter_by(user_id=user.id).delete(
            synchronize_session="fetch"
        )

        # -- Partner leads & uploads -----------------------------------
        ExternalPartnerLead.query.filter_by(
            created_by_user_id=user.id
        ).delete(synchronize_session="fetch")
        Upload.query.filter_by(uploaded_by_id=user.id).delete(
            synchronize_session="fetch"
        )

        # -- Campaigns & recipients ------------------------------------
        campaign_ids = [
            c.id for c in Campaign.query
            .filter_by(created_by_id=user.id)
            .with_entities(Campaign.id)
            .all()
        ]
        if campaign_ids:
            CampaignRecipient.query.filter(
                CampaignRecipient.campaign_id.in_(campaign_ids)
            ).delete(synchronize_session="fetch")
        Campaign.query.filter_by(created_by_id=user.id).delete(
            synchronize_session="fetch"
        )

        # -- Processor & underwriter profiles --------------------------
        # Nullify nullable FK references on child tables before deleting
        # profiles, so LoanApplications / Tasks / Quotes are preserved.
        proc_ids = [
            p.id for p in ProcessorProfile.query
            .filter_by(user_id=user.id)
            .with_entities(ProcessorProfile.id)
            .all()
        ]
        if proc_ids:
            LoanApplication.query.filter(
                LoanApplication.processor_id.in_(proc_ids)
            ).update({"processor_id": None}, synchronize_session="fetch")

        uw_ids = [
            u.id for u in UnderwriterProfile.query
            .filter_by(user_id=user.id)
            .with_entities(UnderwriterProfile.id)
            .all()
        ]
        if uw_ids:
            LoanApplication.query.filter(
                LoanApplication.underwriter_id.in_(uw_ids)
            ).update({"underwriter_id": None}, synchronize_session="fetch")
            UnderwriterTask.query.filter(
                UnderwriterTask.assigned_to.in_(uw_ids)
            ).update({"assigned_to": None}, synchronize_session="fetch")
            LoanQuote.query.filter(
                LoanQuote.assigned_underwriter_id.in_(uw_ids)
            ).update({"assigned_underwriter_id": None}, synchronize_session="fetch")

        ProcessorProfile.query.filter_by(user_id=user.id).delete(
            synchronize_session="fetch")
        UnderwriterProfile.query.filter_by(user_id=user.id).delete(
            synchronize_session="fetch")

        # -- Investor profile: detach loan applications --------------------
        # User.investor_profile uses cascade="all, delete-orphan", which
        # means db.session.delete(user) will ORM-cascade-delete the
        # InvestorProfile.  InvestorProfile.capital_requests also has
        # cascade="all, delete-orphan" → that would wipe out every linked
        # LoanApplication (and *their* children: tasks, quotes, documents,
        # conditions, budgets, scenarios, …).
        # Nullify the FK first so those loans are detached before the
        # cascade fires.  Investor-specific data (investments, saved
        # properties, credit profiles, etc.) is still cleaned up by the
        # cascade — only the loan pipeline is preserved.
        inv_ids = [
            ip.id for ip in InvestorProfile.query
            .filter_by(user_id=user.id)
            .with_entities(InvestorProfile.id)
            .all()
        ]
        if inv_ids:
            # 1) Delete NOT NULL investor_profile_id rows (cannot nullify)
            BorrowerActivity.query.filter(
                BorrowerActivity.investor_profile_id.in_(inv_ids)
            ).delete(synchronize_session="fetch")
            AIIntakeSummary.query.filter(
                AIIntakeSummary.investor_profile_id.in_(inv_ids)
            ).delete(synchronize_session="fetch")
            ESignedDocument.query.filter(
                ESignedDocument.investor_profile_id.in_(inv_ids)
            ).delete(synchronize_session="fetch")

            # 2) Nullify investor_profile_id on shared child tables so
            #    ORM cascade-delete of InvestorProfile doesn't wipe them
            LoanApplication.query.filter(
                LoanApplication.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            LoanDocument.query.filter(
                LoanDocument.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            UnderwritingCondition.query.filter(
                UnderwritingCondition.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            ConditionRequest.query.filter(
                ConditionRequest.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            CreditProfile.query.filter(
                CreditProfile.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            LoanQuote.query.filter(
                LoanQuote.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            PropertyAnalysis.query.filter(
                PropertyAnalysis.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            LoanIntakeSession.query.filter(
                LoanIntakeSession.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            DocumentRequest.query.filter(
                DocumentRequest.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            ProjectBudget.query.filter(
                ProjectBudget.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            LoanAIConversation.query.filter(
                LoanAIConversation.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            Task.query.filter(
                Task.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            SoftCreditReport.query.filter(
                SoftCreditReport.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            PartnerConnectionRequest.query.filter(
                PartnerConnectionRequest.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            PartnerJob.query.filter(
                PartnerJob.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")
            ExternalPartnerLead.query.filter(
                ExternalPartnerLead.investor_profile_id.in_(inv_ids)
            ).update({"investor_profile_id": None},
                     synchronize_session="fetch")

        # -- Loan officer profile: detach loans & borrowers ----------------
        # User.loan_officer_profile has cascade="all, delete", which
        # ORM-cascade-deletes the LoanOfficerProfile.  That profile has
        # cascade="all, delete-orphan" on loans and borrowers, wiping out
        # every assigned LoanApplication and BorrowerProfile (plus all
        # *their* children).  Nullify the FKs to preserve the pipeline.
        lo_ids = [
            lo.id for lo in LoanOfficerProfile.query
            .filter_by(user_id=user.id)
            .with_entities(LoanOfficerProfile.id)
            .all()
        ]
        if lo_ids:
            LoanApplication.query.filter(
                LoanApplication.loan_officer_id.in_(lo_ids)
            ).update({"loan_officer_id": None},
                     synchronize_session="fetch")
            BorrowerProfile.query.filter(
                BorrowerProfile.assigned_officer_id.in_(lo_ids)
            ).update({"assigned_officer_id": None},
                     synchronize_session="fetch")
            LoanIntakeSession.query.filter(
                LoanIntakeSession.assigned_officer_id.in_(lo_ids)
            ).update({"assigned_officer_id": None},
                     synchronize_session="fetch")
            LoanQuote.query.filter(
                LoanQuote.assigned_officer_id.in_(lo_ids)
            ).update({"assigned_officer_id": None},
                     synchronize_session="fetch")

        # Force the ORM to reload all relationship collections from the
        # database so the cascade triggered by db.session.delete(user)
        # sees the nullified FK values rather than stale in-memory state.
        db.session.expire_all()

        db.session.delete(user)
        db.session.commit()
        flash(f"Deleted user {user.email}.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Could not delete user: {e}", "danger")

    return redirect(url_for("system.users"))


# =========================================================
# 🔬 Diagnostics
# =========================================================
@system_bp.route("/diagnostics")
@role_required("system")
def diagnostics():
    ctx = get_system_context()

    metrics = {
        "total_users": User.query.count(),
        "uptime_days": ctx["uptime_days"],
        "recent_logs": len(ctx["logs"]),
        "system_name": ctx["system"].name,
        "version": ctx["system"].version,
    }

    return render_template(
        "system/diagnostics.html",
        metrics=metrics,
        title="System Diagnostics"
    )
