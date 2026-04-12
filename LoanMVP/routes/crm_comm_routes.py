# =========================================================
# 💼 LoanMVP CRM Routes — 2025 Unified Final Version
# =========================================================

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, make_response
from flask_login import current_user
from datetime import datetime
from sqlalchemy import func, case, or_
from random import choice
import json
import re
import csv

from io import StringIO
from LoanMVP.app import socketio
from LoanMVP.extensions import db, csrf
from LoanMVP.ai.base_ai import AIAssistant
from LoanMVP.models.crm_models import Lead, Task, Message, Partner, LeadSource
from LoanMVP.models.call_model import CallLog
from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile
from LoanMVP.models.campaign_model import Campaign
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.user_model import User
from LoanMVP.utils.decorators import role_required

# ---------------------------------------------------------
# Blueprint Setup
# ---------------------------------------------------------
crm_bp = Blueprint("crm", __name__, url_prefix="/crm")
assistant = AIAssistant()


def _crm_company_loan_officers():
    query = LoanOfficerProfile.query.join(User, LoanOfficerProfile.user_id == User.id)
    if getattr(current_user, "company_id", None):
        query = query.filter(User.company_id == current_user.company_id)
    return query.order_by(User.first_name.asc(), User.last_name.asc()).all()


def _company_scoped_leads_query():
    officers = _crm_company_loan_officers()
    officer_ids = [officer.id for officer in officers]
    officer_user_ids = [officer.user_id for officer in officers if getattr(officer, "user_id", None)]

    role = (getattr(current_user, "role", "") or "").lower()
    if role == "loan_officer":
        officer = LoanOfficerProfile.query.filter_by(user_id=current_user.id).first()
        return Lead.query.filter(
            (Lead.assigned_to == current_user.id) |
            (Lead.assigned_officer_id == getattr(officer, "id", None))
        )

    if officer_ids or officer_user_ids:
        clauses = []
        if officer_ids:
            clauses.append(Lead.assigned_officer_id.in_(officer_ids))
        if officer_user_ids:
            clauses.append(Lead.assigned_to.in_(officer_user_ids))
        return Lead.query.filter(or_(*clauses))

    return Lead.query.filter(Lead.assigned_to == current_user.id)


def _choose_auto_assignee(officers):
    if not officers:
        return None

    ranked = []
    for officer in officers:
        active_count = (
            Lead.query.filter(
                (Lead.assigned_officer_id == officer.id) |
                (Lead.assigned_to == officer.user_id)
            ).count()
        )
        ranked.append((active_count, officer))

    ranked.sort(key=lambda item: (item[0], (item[1].full_name or item[1].name or item[1].email or "").lower()))
    return ranked[0][1]


def _lead_source_record(source_name):
    normalized = (source_name or "AI Lead Engine").strip() or "AI Lead Engine"
    record = LeadSource.query.filter(func.lower(LeadSource.source_name) == normalized.lower()).first()
    if record:
        return record

    record = LeadSource(source_name=normalized, source_type="AI")
    db.session.add(record)
    db.session.flush()
    return record


def _parse_ai_leads(raw_text):
    text = (raw_text or "").strip()
    if not text:
        return []

    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return []

    try:
        payload = json.loads(match.group(0))
    except Exception:
        return []

    if not isinstance(payload, list):
        return []

    leads = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        leads.append({
            "name": name,
            "email": (item.get("email") or "").strip() or None,
            "phone": (item.get("phone") or "").strip() or None,
            "message": (item.get("message") or item.get("notes") or "").strip() or None,
        })
    return leads

# ---------------------------------------------------------
# 🧭 CRM Dashboard
# ---------------------------------------------------------
@crm_bp.route("/dashboard")
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def dashboard():
    """Central CRM Dashboard — unified adaptive view."""
    from datetime import datetime, timedelta

    role = (current_user.role or "").lower()
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    # ----------------------------------------
    # Role-based lead & task visibility
    # ----------------------------------------
    if role == "loan_officer":
        leads_list = _company_scoped_leads_query().order_by(Lead.created_at.desc()).all()
        tasks_list = (
            Task.query.filter_by(assigned_to=current_user.id)
            .order_by(Task.due_date.asc())
            .all()
        )
        role_view = "Loan Officer CRM"

    elif role == "processor":
        leads_list = (
            _company_scoped_leads_query()
            .filter(Lead.status.in_(["submitted", "processing"]))
            .order_by(Lead.created_at.desc())
            .all()
        )
        tasks_list = (
            Task.query.filter_by(assigned_to=current_user.id)
            .order_by(Task.due_date.asc())
            .all()
        )
        role_view = "Processor CRM"

    elif role in ["executive", "admin", "crm"]:
        leads_list = _company_scoped_leads_query().order_by(Lead.created_at.desc()).limit(50).all()
        tasks_list = Task.query.order_by(Task.due_date.asc()).limit(50).all()
        role_view = "Executive CRM Overview"

    else:
        leads_list = _company_scoped_leads_query().filter_by(status="active").limit(10).all()
        tasks_list = []
        role_view = "Basic CRM View"

    # ----------------------------------------
    # Additional Data Sets
    # ----------------------------------------
    contacted_leads = (
        _company_scoped_leads_query().filter(Lead.updated_at >= week_ago)
        .order_by(Lead.updated_at.desc())
        .limit(5)
        .all()
    )

    leads_recent = (
        _company_scoped_leads_query().order_by(Lead.created_at.desc())
        .limit(5)
        .all()
    )

    total_calls = CallLog.query.count()
    total_messages = Message.query.count()

    stats = {
        "total_leads": len(leads_list),
        "active_leads": sum(
            1 for l in leads_list
            if l.status and l.status.lower() in ["active", "new"]
        ),
        "recent_leads": len(leads_recent),
        "contacted_leads": len(contacted_leads),
        "tasks_due": len(tasks_list),
        "calls": total_calls,
        "messages": total_messages,
        "conversion": "38%"
    }

    # ----------------------------------------
    # AI Summary
    # ----------------------------------------
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize {role_view} with stats: {stats}.",
            f"crm_{role}_dashboard"
        )
    except Exception as e:
        print("AI summary error:", e)
        ai_summary = "AI CRM summary unavailable."

    # ----------------------------------------
    # Render Template
    # ----------------------------------------
    return render_template(
        "crm/dashboard.html",
        leads=leads_list,
        contacted_leads=contacted_leads,
        leads_recent=leads_recent,
        tasks=tasks_list,
        stats=stats,
        ai_summary=ai_summary,
        title=role_view,
        active_tab="dashboard"
    )

# ---------------------------------------------------------
# ☎️ Smart Dialer

@crm_bp.route("/dialer", methods=["GET", "POST"])
@csrf.exempt
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def dialer():
    """Manual & AI-assisted call logging system."""
    calls = CallLog.query.order_by(CallLog.created_at.desc()).limit(10).all()

    if request.method == "POST":
        phone = request.form.get("phone")
        note = request.form.get("note")
        status = request.form.get("status")
        direction = "outbound"

        try:
           ai_feedback = assistant.generate_reply(
               f"Analyze call sentiment and summarize outcome for: {note}. "
               f"Respond briefly with tone summary and key feedback.",
               "crm_dialer_ai"
           )

           # simple keyword classification fallback
           sentiment = "Neutral"
           if any(word in ai_feedback.lower() for word in ["great", "positive", "happy", "satisfied", "good"]):
               sentiment = "Positive"
           elif any(word in ai_feedback.lower() for word in ["angry", "upset", "negative", "bad", "unhappy"]):
              sentiment = "Negative"

        except Exception:
           ai_feedback = "AI feedback unavailable."
           sentiment = "Neutral"

        # Save call to DB
        call_log = CallLog(
           user_id=current_user.id,
           contact_name="Unknown",
           contact_phone=phone,
           direction="outbound",
           notes=note,
           ai_summary=ai_feedback,
           sentiment=sentiment,
           created_at=datetime.utcnow()
        )
        db.session.add(call_log)
        db.session.commit()

        flash("📞 Call logged successfully!", "success")

        # refresh call list
        calls = CallLog.query.order_by(CallLog.created_at.desc()).limit(10).all()

        return render_template(
            "crm/dialer_result.html",
            calls=calls,
            ai_feedback=ai_feedback,
            summary={
                "connected": len([c for c in calls if c.outcome == "Success"]),
                "voicemail": len([c for c in calls if c.outcome == "Voicemail"]),
                "noanswer": len([c for c in calls if c.outcome == "No Answer"]),
                "failed": len([c for c in calls if c.outcome not in ["Success", "Voicemail", "No Answer"]]),
            },
            agent_labels=["Letoya", "Jamaine", "Jonathan"],
            agent_data=[4, 3, 2],
            title="Dialer Results"
        )

    return render_template("crm/dialer.html", calls=calls, title="Smart Dialer")

@crm_bp.route("/call_log/<int:call_id>")
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def view_call(call_id):
    """Detailed view for a single call log entry."""
    call = CallLog.query.get_or_404(call_id)

    related_lead = None
    if call.related_lead_id:
        related_lead = Lead.query.get(call.related_lead_id)

    return render_template(
        "crm/view_call.html",
        call=call,
        related_lead=related_lead,
        title=f"Call Log • {call.contact_name or call.contact_phone}"
    )
# -----------------------------------------
# 🤖 AI Call Assistant
# -----------------------------------------
@crm_bp.route("/call_ai", methods=["GET", "POST"])
@csrf.exempt
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def call_ai():
    """Logs calls and provides AI summaries & next-action prompts."""
    summary = None
    leads_list = Lead.query.order_by(Lead.created_at.desc()).all()

    if request.method == "POST":
        notes = request.form.get("notes", "")
        lead_id = request.form.get("lead_id")
        selected_lead = Lead.query.get(lead_id)

        try:
            summary = assistant.generate_reply(
                f"Summarize and generate follow-up actions for call notes: {notes}",
                "crm_call_ai"
            )
        except Exception as e:
            print(" Call AI error:", e)
            summary = "AI summary unavailable."

        if selected_lead:
            msg = Message(lead_id=selected_lead.id, sender="AI", content=summary)
            db.session.add(msg)
            db.session.commit()

    return render_template("crm/call_ai.html", leads=leads_list, summary=summary, title="AI Call Assistant")


# -----------------------------------------
# ✉️ AI Follow-Up Generator
# -----------------------------------------
@crm_bp.route("/ai_followup", methods=["GET", "POST"])
@csrf.exempt
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def ai_followup():
    """Generate custom follow-up messages from context."""
    message = None
    if request.method == "POST":
        name = request.form.get("name", "")
        context = request.form.get("context", "")
        try:
            message = assistant.generate_reply(
                f"Write a short, professional follow-up message for {name} about: {context}",
                "crm_followup_ai"
            )
        except Exception as e:
            print(" AI follow-up error:", e)
            message = "AI follow-up unavailable."

    return render_template("crm/ai_followup.html", message=message, title="AI Follow-Up Generator")

@crm_bp.route("/call_insights", methods=["GET", "POST"])
@csrf.exempt
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def call_insights():
    from datetime import timedelta
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    selected_role = request.form.get("role_filter", "All")

    query = (
        db.session.query(
            func.concat(User.first_name, " ", User.last_name).label("name"),
            User.role.label("role"),
            func.count(CallLog.id).label("total_calls"),
            func.avg(
                case(
                    (CallLog.sentiment == "Positive", 1),
                    (CallLog.sentiment == "Neutral", 0.5),
                    (CallLog.sentiment == "Negative", 0),
                    else_=0.5
                )
            ).label("avg_sentiment"),
            func.avg(CallLog.duration_seconds).label("avg_duration")
        )
        .join(User, User.id == CallLog.user_id)
        .group_by(User.id)
    )

    if selected_role != "All":
        query = query.filter(User.role == selected_role)

    leaderboard = query.order_by(func.count(CallLog.id).desc()).limit(5).all()

    total_calls = CallLog.query.count()
    success_calls = CallLog.query.filter(CallLog.outcome == "Success").count()
    voicemail_calls = CallLog.query.filter(CallLog.outcome == "Voicemail").count()
    followup_calls = CallLog.query.filter(CallLog.outcome == "Follow-Up Scheduled").count()
    avg_duration = db.session.query(func.avg(CallLog.duration_seconds)).scalar() or 0

    # Sentiment distribution
    positive_calls = CallLog.query.filter(CallLog.sentiment == "Positive").count()
    neutral_calls = CallLog.query.filter(CallLog.sentiment == "Neutral").count()
    negative_calls = CallLog.query.filter(CallLog.sentiment == "Negative").count()

    # AI Feedback log
    ai_feedbacks = [
        {"id": c.id, "ai_summary": c.ai_summary or ""}
        for c in CallLog.query.order_by(CallLog.created_at.desc()).limit(5)
    ]

    # Role list for filter
    roles = [r[0] for r in db.session.query(User.role).distinct() if r[0]]

    # === 🧠 AI Leaderboard Summary ===
    try:
        if leaderboard:
            top_user = leaderboard[0]
            ai_text = (
                f"{top_user.name} ({top_user.role.title()}) leads this week with "
                f"{int(top_user.total_calls)} calls and "
                f"{round((top_user.avg_sentiment or 0)*100)}% average sentiment score."
            )

            ai_summary = assistant.generate_reply(
                f"Write a concise one-line performance summary for CRM leaderboard: {ai_text}",
                "crm_leaderboard_summary"
            )
        else:
            ai_summary = "No leaderboard data yet."
    except Exception:
        ai_summary = choice([
            "AI summary unavailable. Try again later.",
            "No insight generated — minimal call data available."
        ])

    # ✅ Chart data for template
    labels = ["Total", "Success", "Voicemail", "Follow-Up", "Positive", "Neutral", "Negative"]
    values = [
        total_calls,
        success_calls,
        voicemail_calls,
        followup_calls,
        positive_calls,
        neutral_calls,
        negative_calls
    ]

    # ✅ Must pass labels and values to render_template
    return render_template(
        "crm/call_insights.html",
        total_calls=total_calls,
        success_calls=success_calls,
        voicemail_calls=voicemail_calls,
        followup_calls=followup_calls,
        avg_duration=round(avg_duration, 1),
        positive_calls=positive_calls,
        neutral_calls=neutral_calls,
        negative_calls=negative_calls,
        leaderboard=leaderboard,
        ai_feedbacks=ai_feedbacks,
        roles=roles,
        selected_role=selected_role,
        ai_summary=ai_summary,
        labels=labels,        # ✅ added
        values=values,        # ✅ added
        title="Call Intelligence Dashboard"
    )

@crm_bp.route("/refresh_ai_summary", methods=["POST"])
@csrf.exempt
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def refresh_ai_summary():
    """Refreshes the AI leaderboard summary dynamically via AJAX."""
    try:
        # Get top performer again
        top_user = (
            db.session.query(
                User.full_name.label("name"),
                User.role.label("role"),
                func.count(CallLog.id).label("total_calls"),
                func.avg(
                    case(
                        (CallLog.sentiment == "Positive", 1),
                        (CallLog.sentiment == "Neutral", 0.5),
                        (CallLog.sentiment == "Negative", 0),
                        else_=0.5
                    )
                ).label("avg_sentiment")
            )
            .join(User, User.id == CallLog.user_id)
            .group_by(User.id)
            .order_by(func.count(CallLog.id).desc())
            .first()
        )

        if not top_user:
            return jsonify({"message": "No call data available yet."})

        text = (
            f"{top_user.name} ({top_user.role.title()}) leads this week with "
            f"{int(top_user.total_calls)} calls and "
            f"{round((top_user.avg_sentiment or 0)*100)}% average sentiment."
        )

        ai_summary = assistant.generate_reply(
            f"Write a concise, motivational leaderboard insight based on: {text}",
            "crm_leaderboard_refresh"
        )

        return jsonify({"message": ai_summary})
    except Exception as e:
        print(" AI refresh error:", e)
        return jsonify({"message": "AI summary unavailable."})

@crm_bp.route("/call_table_refresh", methods=["GET"])
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def call_table_refresh():
    """Return updated HTML table of recent calls (for async refresh)."""
    recent_calls = CallLog.query.order_by(CallLog.created_at.desc()).limit(20).all()
    return render_template("crm/_call_table.html", calls=recent_calls)

@crm_bp.route("/generate_ai_summaries_async", methods=["POST"])
@csrf.exempt
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def generate_ai_summaries_async():
    """Asynchronous AI summary generation (AJAX version)."""
    from LoanMVP.ai.assistant import assistant

    recent_calls = (
        CallLog.query
        .filter((CallLog.ai_summary == None) | (CallLog.ai_summary == ""))
        .order_by(CallLog.created_at.desc())
        .limit(20)
        .all()
    )

    processed_count = 0
    for call in recent_calls:
        base_text = f"Call with {call.contact_name or 'client'} on {call.created_at.strftime('%b %d, %Y')} — "
        notes = call.notes or "No detailed notes provided."
        prompt = f"Summarize this call and suggest next follow-up actions: {base_text} {notes}"
        socketio.emit("ai_summary_update", {"processed": processed_count}, namespace="/crm")

        try:
            ai_summary = assistant.generate_reply(prompt, "crm_call_summary")
            call.ai_summary = ai_summary
            processed_count += 1
        except Exception as e:
            print(f" AI summary failed for call {call.id}: {e}")
            call.ai_summary = "AI summary unavailable."

    db.session.commit()
    return jsonify({"processed": processed_count})

@crm_bp.route("/export_call_report", methods=["POST"])
@csrf.exempt
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def export_call_report():
    """Exports filtered call log data as CSV including AI summaries."""
    user_filter = request.form.get("user_filter", "All")
    sentiment_filter = request.form.get("sentiment_filter", "All")

    query = CallLog.query
    if user_filter != "All":
        query = query.filter(CallLog.user_id == int(user_filter))
    if sentiment_filter != "All":
        query = query.filter(CallLog.sentiment == sentiment_filter)

    calls = query.order_by(CallLog.created_at.desc()).all()

    # === Create CSV in memory ===
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID",
        "User",
        "Contact Name",
        "Phone",
        "Sentiment",
        "Direction",
        "Duration (sec)",
        "Outcome",
        "Notes",
        "AI Summary",
        "Created At"
    ])

    for call in calls:
        writer.writerow([
            call.id,
            getattr(call.user, "full_name", "N/A") if hasattr(call, "user") else "N/A",
            call.contact_name or "",
            call.contact_phone or "",
            getattr(call, "sentiment", "N/A"),
            call.direction or "",
            call.duration_seconds or 0,
            call.outcome or "",
            (call.notes or "").replace("\n", " "),
            (call.ai_summary or "").replace("\n", " ").replace("\r", " "),
            call.created_at.strftime("%Y-%m-%d %H:%M:%S") if call.created_at else ""
        ])

    output.seek(0)
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=call_report.csv"
    response.headers["Content-Type"] = "text/csv"
    return response
# ---------------------------------------------------------
# 💬 Message Center
# ---------------------------------------------------------
@crm_bp.route("/messages", methods=["GET", "POST"])
@csrf.exempt
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def messages():
    """Unified message thread across email/SMS/chat."""
    all_messages = Message.query.order_by(Message.timestamp.desc()).limit(50).all()

    if request.method == "POST":
        content = request.form.get("message", "")
        lead_id = request.form.get("lead_id")

        if not content:
            return jsonify({"reply": "⚠️ No message provided."}), 400

        new_message = Message(sender=current_user.username, content=content, lead_id=lead_id)
        db.session.add(new_message)
        db.session.commit()

        try:
            ai_reply = assistant.generate_reply(f"Generate appropriate response to: {content}", "crm_message_ai")
        except Exception:
            ai_reply = "AI response unavailable."

        ai_message = Message(sender="AI", content=ai_reply, lead_id=lead_id)
        db.session.add(ai_message)
        db.session.commit()

        return jsonify({"reply": ai_reply})

    return render_template("crm/messages.html", messages=all_messages, title="Message Center")

# ---------------------------------------------------------
# 🤝 Partner CRM
# ---------------------------------------------------------
@crm_bp.route("/partners")
@role_required("crm", "loan_officer", "processor", "executive", "admin")
def partners():
    """Displays and manages partner contacts and referral networks."""
    partner_list = Partner.query.order_by(Partner.name.asc()).all()
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize partner network performance for {len(partner_list)} partners.",
            "crm_partner_ai"
        )
    except Exception:
        ai_summary = "Partner summary unavailable."
    return render_template("crm/partner_crm.html", partners=partner_list, ai_summary=ai_summary, title="Partner CRM")

# ---------------------------------------------------------
# 📣 Campaign Management
# ---------------------------------------------------------
@crm_bp.route("/campaigns")
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def campaigns():
    """Show all campaigns created by current user."""
    campaign_list = Campaign.query.filter_by(created_by_id=current_user.id).order_by(Campaign.created_at.desc()).all()
    stats = {
        "total": len(campaign_list),
        "sent": len([c for c in campaign_list if c.status == "sent"]),
        "draft": len([c for c in campaign_list if c.status == "draft"]),
        "scheduled": len([c for c in campaign_list if c.status == "scheduled"]),
    }
    return render_template("crm/campaigns.html", campaigns=campaign_list, stats=stats, title="CRM Campaigns")

# ---------------------------------------------------------
# 🧩 Leads Management
# ---------------------------------------------------------
@crm_bp.route("/leads/<int:lead_id>", methods=["GET", "POST"])
@csrf.exempt
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def view_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    calls = CallLog.query.filter_by(related_lead_id=lead.id).order_by(CallLog.created_at.desc()).all()
    ai_followup = None

    if request.method == "POST":
        # ----- New Call Logging -----
        note = request.form.get("note")
        phone = request.form.get("phone")
        outcome = request.form.get("outcome")

        call = CallLog(
            user_id=current_user.id,
            related_lead_id=lead.id,
            contact_name=lead.name,
            contact_phone=lead.phone,
            notes=note,
            outcome=outcome,
            direction="outbound"
        )
        db.session.add(call)
        db.session.commit()

        # Auto AI summary for the call
        try:
            call.ai_summary = assistant.generate_reply(
                f"Summarize this call note and key insights: {note}",
                "crm_lead_call_summary"
            )
            db.session.commit()
        except Exception:
            call.ai_summary = "⚠️ AI summary unavailable."

        # Auto AI follow-up
        try:
            ai_followup = assistant.generate_reply(
                f"Generate next actions and follow-up plan for this lead based on recent call: {note}",
                "crm_lead_followup"
            )
        except Exception:
            ai_followup = "⚠️ AI follow-up unavailable."

        flash("📞 Call logged and AI insights updated.", "success")
        return redirect(url_for("crm.view_lead", lead_id=lead.id))

    # Auto-generate follow-up for the latest call (view only)
    if calls:
        latest_note = calls[0].notes or ""
        try:
            ai_followup = assistant.generate_reply(
                f"Provide actionable next steps for follow-up based on call note: {latest_note}",
                "crm_lead_followup"
            )
        except Exception:
            ai_followup = "⚠️ AI follow-up unavailable."

    return render_template(
        "crm/view_lead.html",
        lead=lead,
        calls=calls,
        ai_followup=ai_followup,
        title=f"Lead • {lead.name}"
    )

@crm_bp.route("/leads/<int:lead_id>/ai_followup", methods=["GET"])
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def lead_ai_followup(lead_id):
    """Returns updated AI follow-up text for the latest call (AJAX)."""
    lead = Lead.query.get_or_404(lead_id)
    latest_call = CallLog.query.filter_by(related_lead_id=lead.id).order_by(CallLog.created_at.desc()).first()

    if not latest_call or not latest_call.notes:
        return {"message": "No recent call notes found."}

    try:
        ai_text = assistant.generate_reply(
            f"Provide actionable next steps for follow-up based on call note: {latest_call.notes}",
            "crm_lead_followup"
        )
    except Exception:
        ai_text = "⚠️ AI follow-up unavailable."

    return {"message": ai_text}

@crm_bp.route("/add_lead", methods=["GET", "POST"])
@csrf.exempt
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def add_lead():
    """Add a new lead record."""
    officers = _crm_company_loan_officers()
    if request.method == "GET":
        return render_template("crm/add_lead.html", officers=officers, title="Add Lead")

    name = (request.form.get("name") or request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip() or None
    phone = (request.form.get("phone") or "").strip() or None
    source_name = (request.form.get("source") or "Manual Entry").strip()
    notes = (request.form.get("notes") or "").strip() or None
    status = (request.form.get("status") or "New").strip()
    assigned_officer_id = request.form.get("assigned_officer_id", type=int)

    if not name:
        flash("Lead name is required.", "danger")
        return render_template("crm/add_lead.html", officers=officers, title="Add Lead")

    selected_officer = next((officer for officer in officers if officer.id == assigned_officer_id), None)
    source = _lead_source_record(source_name)
    new_lead = Lead(
        name=name,
        email=email,
        phone=phone,
        message=notes,
        source_id=source.id if source else None,
        assigned_officer_id=selected_officer.id if selected_officer else None,
        assigned_to=selected_officer.user_id if selected_officer else None,
        status=status,
        created_at=datetime.utcnow()
    )
    db.session.add(new_lead)
    db.session.commit()
    flash(f"Lead '{name}' added successfully.", "success")
    return redirect(url_for("crm.leads"))


@crm_bp.route("/ai_leads", methods=["GET", "POST"])
@csrf.exempt
@role_required("crm", "loan_officer", "executive", "admin")
def ai_leads():
    officers = _crm_company_loan_officers()
    generated = []

    if request.method == "POST":
        market = (request.form.get("market") or "").strip()
        audience = (request.form.get("audience") or "").strip()
        product_focus = (request.form.get("product_focus") or "").strip()
        count = min(max(request.form.get("count", type=int) or 5, 1), 20)
        assigned_officer_id = request.form.get("assigned_officer_id", type=int)
        selected_officer = next((officer for officer in officers if officer.id == assigned_officer_id), None)
        source = _lead_source_record("AI Lead Engine")

        prompt = f"""
Generate {count} realistic mortgage prospect leads for a lending business.
Target market: {market or 'United States'}.
Audience: {audience or 'homebuyers and refinance borrowers'}.
Product focus: {product_focus or 'residential mortgage products'}.
Return only valid JSON as an array.
Each object must include: name, email, phone, message.
Keep the message to one short sentence explaining the prospect's likely need.
Use plausible sample contact info, not existing famous people.
"""

        try:
            raw = assistant.generate_reply(prompt, "crm_ai_leads")
            generated = _parse_ai_leads(raw)
        except Exception:
            generated = []

        if not generated:
            flash("AI could not generate lead records this time.", "warning")
        else:
            for item in generated:
                lead = Lead(
                    name=item["name"],
                    email=item["email"],
                    phone=item["phone"],
                    message=item["message"],
                    source_id=source.id if source else None,
                    assigned_officer_id=selected_officer.id if selected_officer else None,
                    assigned_to=selected_officer.user_id if selected_officer else None,
                    status="New",
                    created_at=datetime.utcnow(),
                )
                db.session.add(lead)
            db.session.commit()
            flash(f"{len(generated)} AI-generated leads were added to the CRM queue.", "success")

    return render_template(
        "crm/ai_leads.html",
        officers=officers,
        generated=generated,
        title="AI Leads",
    )

@crm_bp.route("/leads/<int:lead_id>", methods=["GET", "POST"])
@csrf.exempt
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def update_lead(lead_id):
    """Update or assign a lead."""
    lead = Lead.query.get_or_404(lead_id)
    borrower = BorrowerProfile.query.filter_by(lead_id=lead_id).first()

    if request.method == "POST":
        lead.status = request.form.get("status") or lead.status
        lead.notes = request.form.get("notes") or lead.notes
        assigned_to = request.form.get("assigned_to")
        if assigned_to:
            lead.assigned_to = int(assigned_to)
        lead.updated_at = datetime.utcnow()
        db.session.commit()
        flash("✅ Lead updated successfully.", "success")
        return redirect(url_for("crm.view_leads"))

    users = User.query.all()
    return render_template("crm/lead_detail.html", lead=lead, borrower=borrower, users=users)

# ---------------------------------------------------------
# 🧭 Communication Hub + AI Summary
# ---------------------------------------------------------
@crm_bp.route("/hub")
@role_required("crm", "loan_officer", "processor", "executive", "admin", "partners")
def hub():
    """Visualizes live CRM communications between key user roles."""
    communication_data = [
        {"source": "Borrower Portal", "target": "Loan Officer", "volume": 64},
        {"source": "CRM AI", "target": "Processor", "volume": 18},
        {"source": "Partner CRM", "target": "Executive", "volume": 9},
    ]
    try:
        ai_summary = assistant.generate_reply(f"Summarize communication activity: {communication_data}", "crm_hub_ai")
    except Exception:
        ai_summary = "AI hub summary unavailable."
    return render_template("crm/communication_hub.html", data=communication_data, ai_summary=ai_summary, title="Communication Hub")

@crm_bp.route("/ai_summary")
@role_required("crm")
def ai_summary():
    """Generates AI summary of CRM activity and engagement patterns."""
    leads = Lead.query.order_by(Lead.created_at.desc()).limit(20).all()
    tasks = Task.query.order_by(Task.due_date.asc()).limit(10).all()

    total_leads = len(leads)
    active_leads = sum(1 for l in leads if l.status and l.status.lower() in ["active", "new", "engaged"])
    closed_leads = sum(1 for l in leads if l.status and l.status.lower() in ["closed", "converted"])

    avg_age = 0
    if leads:
        avg_age = round(sum((datetime.utcnow() - l.created_at).days for l in leads) / len(leads), 1)

    pending_tasks = [t for t in tasks if t.status != "Completed"]
    overdue_tasks = [t for t in tasks if t.due_date and t.due_date < datetime.utcnow()]

    prompt = f"""
    CRM Summary:
    - Total Leads: {total_leads}
    - Active Leads: {active_leads}
    - Closed Leads: {closed_leads}
    - Average Age: {avg_age} days
    - Pending Tasks: {len(pending_tasks)}
    - Overdue Tasks: {len(overdue_tasks)}
    """

    try:
        ai_summary_text = assistant.generate_reply(prompt, "crm_summary")
    except Exception:
        ai_summary_text = "AI summary unavailable."

    return jsonify({
        "summary": ai_summary_text,
        "stats": {
            "total_leads": total_leads,
            "active_leads": active_leads,
            "closed_leads": closed_leads,
            "avg_age_days": avg_age,
            "pending_tasks": len(pending_tasks),
            "overdue_tasks": len(overdue_tasks)
        }
    })

@crm_bp.route("/dialer_results")
@role_required("crm", "loan_officer", "processor", "executive", "admin")
def dialer_results():
    leads = Lead.query.order_by(Lead.created_at.desc()).limit(15).all()
    return render_template("crm/leads.html", leads=leads, title="Dialer Results")

@crm_bp.route("/call_log/delete/<int:call_id>", methods=["POST"])
@csrf.exempt
@role_required("crm", "loan_officer", "processor", "executive", "admin")
def delete_call(call_id):
    call = CallLog.query.get_or_404(call_id)
    db.session.delete(call)
    db.session.commit()
    flash("🗑 Call deleted successfully.", "info")
    return redirect(url_for("crm.dialer"))

from sqlalchemy import func



# ==========================================================
# 🧭 Lead Engine (Search / Filter / Analytics)
# ==========================================================
@crm_bp.route("/lead_engine")
@role_required("crm", "admin")
def lead_engine():
    query = request.args.get("q", "")
    leads = Lead.query.filter(Lead.name.ilike(f"%{query}%")).all() if query else []
    return render_template("crm/leads.html", leads=leads, query=query, title="Lead Engine")

# ==========================================================
# 📋 View All Leads
# ==========================================================
@crm_bp.route("/leads")
@role_required("crm", "admin")
def leads():
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    return render_template("crm/leads.html", leads=leads, title="All Leads")

# ==========================================================
# 🧠 Lead Detail (Full View with AI + Communication)
# ==========================================================
@crm_bp.route("/details/<int:lead_id>")
@role_required("crm", "admin")
def lead_details(lead_id):
    """
    Detailed view for a single lead including AI insights,
    tasks, communication logs, and related loans.
    """
    lead = Lead.query.get_or_404(lead_id)

    # Optional relationships (if you have them)
    tasks = getattr(lead, "tasks", [])
    messages = getattr(lead, "messages", [])
    loans = getattr(lead, "loans", [])

    # Simple placeholder AI summary (can replace with your AI assistant)
    ai_summary = f"🤖 Lead '{lead.name}' is currently marked as {lead.status}. Based on recent trends, " \
                 f"leads from {lead.source or 'organic sources'} show a {round(72.5, 1)}% chance of conversion."

    return render_template(
        "crm/lead_details.html",
        lead=lead,
        tasks=tasks,
        messages=messages,
        loans=loans,
        ai_summary=ai_summary,
        title=f"Lead Details - {lead.name}"
    )

# -----------------------------------------------------
# 🤝 Partner Detail View
# -----------------------------------------------------
@crm_bp.route("/partners/<int:partner_id>", methods=["GET"])
@role_required("crm", "admin")
def partner_detail(partner_id):
    from LoanMVP.models.crm_models import Partner, PartnerNote
    partner = Partner.query.get_or_404(partner_id)
    notes = PartnerNote.query.filter_by(partner_id=partner.id).order_by(PartnerNote.created_at.desc()).all()
    activities = []  # placeholder for system activity
    deals = []  # placeholder for connected deals

    ai_summary = assistant.generate_reply(
        f"Provide a professional AI summary for partner {partner.name} of type {partner.type}. Include deal trends and engagement level.",
        "crm"
    )

    return render_template("crm/partner_detail.html", partner=partner, ai_summary=ai_summary, notes=notes, activities=activities, deals=deals)

@crm_bp.route("/partners/<int:partner_id>/note", methods=["POST"])
@csrf.exempt
@role_required("crm" , "admin")
def add_partner_note(partner_id):
    from LoanMVP.models.crm_models import PartnerNote
    content = request.form.get("content")
    if not content:
        flash("⚠️ Note content cannot be empty.", "warning")
        return redirect(url_for("crm.partner_detail", partner_id=partner_id))

    note = PartnerNote(partner_id=partner_id, author=current_user.username, content=content)
    db.session.add(note)
    db.session.commit()
    flash("✅ Note added successfully.", "success")
    return redirect(url_for("crm.partner_detail", partner_id=partner_id))

# ---------------------------------------------------------
# 🧠 Quick AI Tip Endpoint
# ---------------------------------------------------------
@crm_bp.route("/ai_tip")
@role_required("crm", "admin")
def ai_tip():
    """Quick AI tip or query endpoint for CRM components."""
    query = request.args.get("query", "")
    context = request.args.get("context", "crm")
    try:
        reply = assistant.generate_reply(query, context)
    except Exception:
        reply = "AI tip unavailable."
    return jsonify({"reply": reply})



