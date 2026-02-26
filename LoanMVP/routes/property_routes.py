from flask import (
    Blueprint, render_template, request, jsonify,
    redirect, url_for, flash, current_app
)
from flask_login import login_required, current_user
from datetime import datetime
from LoanMVP.utils.decorators import role_required
from LoanMVP.models import db, PropertyAnalysis
from LoanMVP.services.unified_property_resolver import resolve_property_unified
from LoanMVP.services.property_dto import to_property_card_dto
from LoanMVP.services.resolver_metrics import get_metrics_snapshot
from LoanMVP.ai import AIAssistant
import requests

property_bp = Blueprint("property", __name__, url_prefix="/property")

# =========================================================
# 📊 PROPERTY DASHBOARD (Borrower‑style structure)
# =========================================================
@property_bp.route("/dashboard")
@role_required("property")
def dashboard():
    """Property OS Dashboard (Borrower‑style structure)."""

    properties = PropertyAnalysis.query.order_by(
        PropertyAnalysis.created_at.desc()
    ).all()

    total_value = sum([(p.after_repair_value or 0) for p in properties])
    total_count = len(properties)

    # AI Summary (Borrower‑style)
    try:
        ai_summary = assistant.generate_reply(
            f"Summarize a portfolio of {total_count} properties valued at ${total_value:,.0f}.",
            "property_dashboard"
        )
    except Exception as e:
        ai_summary = f"AI summary unavailable ({str(e)[:60]})"

    stats = {
        "total_properties": total_count,
        "portfolio_value": total_value,
    }

    return render_template(
        "property/dashboard.html",
        properties=properties,
        stats=stats,
        ai_summary=ai_summary,
        title="Property Intelligence"
    )


# =========================================================
# 🔍 GOOGLE PLACES AUTOCOMPLETE (Borrower‑style)
# =========================================================
@property_bp.route("/autocomplete", methods=["POST"])
def autocomplete():
    data = request.get_json() or {}
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"predictions": []})

    api_key = current_app.config.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        return jsonify({"predictions": []})

    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": query,
        "key": api_key,
        "types": "address",
        "components": "country:us"
    }

    try:
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
    except Exception:
        return jsonify({"predictions": []})

    predictions = [
        {
            "description": p.get("description", ""),
            "place_id": p.get("place_id", "")
        }
        for p in data.get("predictions", [])
    ]

    return jsonify({"predictions": predictions})


# =========================================================
# 🧠 UNIFIED PROPERTY RESOLVER (Borrower‑style)
# =========================================================
@property_bp.route("/resolve", methods=["POST"])
def resolve():
    address = request.json.get("address")
    if not address:
        return jsonify({"error": "Missing address"}), 400

    unified = resolve_property_unified(address)

    if unified.get("status") != "ok":
        return jsonify(unified), 200

    return jsonify({
        "status": "ok",
        "card": to_property_card_dto(unified),
        "raw": unified,
    })


# =========================================================
# 📈 RESOLVER METRICS
# =========================================================
@property_bp.route("/resolver/metrics")
def resolver_metrics():
    return jsonify(get_metrics_snapshot())


# =========================================================
# 🔎 PROPERTY SEARCH PAGE
# =========================================================
@property_bp.route("/search")
def search_page():
    return render_template("property/search.html")


# =========================================================
# 📋 PROPERTY LIST
# =========================================================
@property_bp.route("/list")
@role_required("property")
def property_list():
    properties = PropertyAnalysis.query.order_by(
        PropertyAnalysis.created_at.desc()
    ).all()
    return render_template(
        "property/list.html",
        properties=properties,
        title="Property List"
    )


# =========================================================
# 🧾 VIEW PROPERTY
# =========================================================
@property_bp.route("/view/<int:property_id>")
def view(property_id):
    prop = PropertyAnalysis.query.get_or_404(property_id)
    return render_template(
        "property/view.html",
        property=prop,
        title="View Property"
    )


# =========================================================
# ✏️ EDIT PROPERTY
# =========================================================
@property_bp.route("/edit/<int:property_id>", methods=["GET", "POST"])
@role_required("property")
def edit(property_id):
    prop = PropertyAnalysis.query.get_or_404(property_id)

    if request.method == "POST":
        prop.property_address = request.form.get("address")
        prop.property_value = request.form.get("value")
        prop.status = request.form.get("status")
        prop.updated_at = datetime.utcnow()

        db.session.commit()
        flash("✅ Property updated successfully.", "success")
        return redirect(url_for("property.view", property_id=prop.id))

    return render_template(
        "property/edit.html",
        property=prop,
        title="Edit Property"
    )


# =========================================================
# ➕ ADD PROPERTY
# =========================================================
@property_bp.route("/new", methods=["GET", "POST"])
@role_required("property")
def new():
    if request.method == "POST":
        new_prop = PropertyAnalysis(
            full_name=request.form.get("owner"),
            property_address=request.form.get("address"),
            property_city=request.form.get("city"),
            property_state=request.form.get("state"),
            property_value=request.form.get("value"),
            created_at=datetime.utcnow()
        )
        db.session.add(new_prop)
        db.session.commit()

        flash("✅ Property added successfully!", "success")
        return redirect(url_for("property.dashboard"))

    return render_template("property/new.html", title="Add Property")


# =========================================================
# 🗑️ DELETE PROPERTY
# =========================================================
@property_bp.route("/delete/<int:property_id>", methods=["POST"])
@role_required("property")
def delete(property_id):
    prop = PropertyAnalysis.query.get_or_404(property_id)
    db.session.delete(prop)
    db.session.commit()
    return jsonify({"status": "deleted"})


# =========================================================
# 🧠 AI PROPERTY VALUE
# =========================================================
@property_bp.route("/ai_property_value", methods=["POST"])
@role_required("property")
def ai_property_value():
    data = request.get_json() or {}

    prompt = (
        f"Estimate market value and investment potential for "
        f"{data.get('address')}, {data.get('city')}, {data.get('state')} "
        f"currently valued at ${data.get('value')}."
    )

    try:
        insight = assistant.generate_reply(prompt, "property_value")
        return jsonify({"status": "success", "insight": insight})
    except Exception as e:
        return jsonify({"status": "error", "insight": str(e)})


# =========================================================
# 🧠 AI PORTFOLIO REFRESH
# =========================================================
@property_bp.route("/ai_refresh")
@role_required("property")
def ai_refresh():
    total = PropertyAnalysis.query.count()
    avg_value = round(
        db.session.query(db.func.avg(PropertyAnalysis.property_value)).scalar() or 0,
        2
    )

    try:
        insight = assistant.generate_reply(
            f"Summarize portfolio of {total} properties averaging ${avg_value}.",
            "property_insight"
        )
    except Exception:
        insight = "AI refresh unavailable."

    return jsonify({"message": insight})


# =========================================================
# ⚙️ LOAN OPTIMIZATION
# =========================================================
@property_bp.route("/optimize", methods=["GET", "POST"])
@role_required("property")
def optimize():
    if request.method == "POST":
        data = request.form.to_dict()

        try:
            ai_recommendation = assistant.generate_reply(
                f"Optimize loan terms for property data {data}",
                "loan_optimize"
            )
        except Exception:
            ai_recommendation = "AI recommendation unavailable."

        flash("✅ Loan optimization complete.", "success")

        return render_template(
            "property/optimize_result.html",
            data=data,
            ai_recommendation=ai_recommendation,
            title="Optimization Result"
        )

    return render_template("property/optimize.html", title="Loan Optimization")


# =========================================================
# 🗺️ RISK MAP
# =========================================================
@property_bp.route("/risk_map")
@role_required("property")
def risk_map():
    properties = PropertyAnalysis.query.limit(50).all()
    risk_data = []

    for p in properties:
        risk_level = "Low"
        if p.after_repair_value and p.as_is_value:
            ltv = (p.as_is_value / p.after_repair_value) * 100
            risk_level = (
                "High" if ltv > 85 else
                "Medium" if ltv > 70 else
                "Low"
            )

        risk_data.append({
            "address": p.property_address,
            "as_is": p.as_is_value,
            "arv": p.after_repair_value,
            "ltv": round(ltv, 2) if p.after_repair_value else None,
            "risk": risk_level
        })

    try:
        ai_comment = assistant.generate_reply(
            f"Analyze property portfolio risk trends across {len(risk_data)} items.",
            "risk_analysis"
        )
    except Exception:
        ai_comment = "AI risk summary unavailable."

    return render_template(
        "property/risk_map.html",
        risk_data=risk_data,
        ai_comment=ai_comment,
        title="Portfolio Risk Map"
    )


# =========================================================
# 🧩 Property Management Panel
# =========================================================
@property_bp.route("/manage", methods=["GET", "POST"])
@role_required("property")
def manage():
    """CRUD management panel for all properties."""
    if request.method == "POST":
        new_prop = PropertyAnalysis(
            full_name=request.form.get("owner"),
            property_address=request.form.get("address"),
            property_city=request.form.get("city"),
            property_state=request.form.get("state"),
            property_value=request.form.get("value"),
            created_at=datetime.utcnow()
        )
        db.session.add(new_prop)
        db.session.commit()
        flash("✅ Property added successfully!", "success")
        return redirect(url_for("property.manage"))
    properties = PropertyAnalysis.query.order_by(PropertyAnalysis.created_at.desc()).all()
    return render_template("property/manage.html", properties=properties, title="Property Management")
