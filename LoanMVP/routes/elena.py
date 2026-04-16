# LoanMVP/routes/elena.py

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd

from LoanMVP.extensions import db
from sqlalchemy import (
    Column, Integer, String, DateTime, Text,
    Enum as SAEnum, ForeignKey, func
)
from sqlalchemy.orm import relationship

# If your AI wrapper is different, adjust this import:
from LoanMVP.services.ai_service import generate_text

# If your ATTOM wrapper is different, adjust this import:
from LoanMVP.services.attom_service import get_property_details


# ============================================================
# ENUMS
# ============================================================

class ClientType(str, Enum):
    BUYER = "buyer"
    SELLER = "seller"
    LEAD = "lead"
    REFERRAL = "referral"


class PipelineStage(str, Enum):
    NEW_LEAD = "new_lead"
    CONTACTED = "contacted"
    SHOWING_SCHEDULED = "showing_scheduled"
    OFFER_SUBMITTED = "offer_submitted"
    UNDER_CONTRACT = "under_contract"
    CLOSED = "closed"


class InteractionType(str, Enum):
    EMAIL = "email"
    CALL = "call"
    TEXT = "text"
    NOTE = "note"
    SHOWING = "showing"


class FlyerType(str, Enum):
    JUST_LISTED = "just_listed"
    JUST_SOLD = "just_sold"
    OPEN_HOUSE = "open_house"
    COMING_SOON = "coming_soon"
    PRICE_DROP = "price_drop"
    BUYER_NEED = "buyer_need"
    MARKET_UPDATE = "market_update"


# ============================================================
# MODELS (Elena-specific tables)
# ============================================================

class ElenaClient(db.Model):
    __tablename__ = "elena_clients"

    id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    client_type = Column(SAEnum(ClientType), default=ClientType.LEAD)
    pipeline_stage = Column(SAEnum(PipelineStage), default=PipelineStage.NEW_LEAD)

    tags = Column(String, nullable=True)
    source = Column(String, nullable=True)

    notes = Column(Text, nullable=True)
    last_contacted_at = Column(DateTime, nullable=True)
    next_followup_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    interactions = relationship("ElenaInteraction", back_populates="client")


class ElenaInteraction(db.Model):
    __tablename__ = "elena_interactions"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("elena_clients.id"), nullable=False)
    interaction_type = Column(SAEnum(InteractionType), nullable=False)
    content = Column(Text, nullable=True)
    meta = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("ElenaClient", back_populates="interactions")


class ElenaFlyer(db.Model):
    __tablename__ = "elena_flyers"

    id = Column(Integer, primary_key=True)
    flyer_type = Column(SAEnum(FlyerType), nullable=False)
    property_address = Column(String, nullable=True)
    property_id = Column(String, nullable=True)

    title = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    export_url = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, default="elena")


# ============================================================
# AI SERVICES
# ============================================================

def generate_elena_flyer_text(flyer_type, property_id=None, address=None):
    prop = get_property_details(property_id=property_id, address=address) if (property_id or address) else {}

    prompt = f"""
    Create a real estate flyer for Hudson Valley Realtor Elena James (Keller Williams).
    Flyer type: {flyer_type}
    Address: {prop.get('address_full', address)}
    Beds: {prop.get('beds', '')}
    Baths: {prop.get('baths', '')}
    Sqft: {prop.get('sqft', '')}
    Price: {prop.get('list_price', '')}

    Write:
    - A headline (max 10 words)
    - A 2–3 sentence description
    - 4–6 bullet highlights
    Tone: warm, professional, Hudson Valley lifestyle.
    """

    return generate_text(prompt)


def generate_followup_email(client, template_type, context=None):
    context = context or {}

    prompt = f"""
    Write a follow-up email for Hudson Valley Realtor Elena James.
    Client: {client.full_name}
    Type: {template_type}
    Pipeline: {client.pipeline_stage.value}
    Context: {context}

    Include:
    - Subject line
    - 3–6 sentence body
    Tone: warm, professional, helpful.
    """

    return generate_text(prompt)


# ============================================================
# BLUEPRINT
# ============================================================

elena_bp = Blueprint("elena", __name__, url_prefix="/elena")


# ============================================================
# DASHBOARD SUMMARY
# ============================================================

@elena_bp.get("/dashboard/summary")
def dashboard_summary():
    now = datetime.utcnow()
    soon = now + timedelta(days=2)

    new_leads = db.session.query(func.count(ElenaClient.id))\
        .filter(ElenaClient.pipeline_stage == PipelineStage.NEW_LEAD).scalar()

    needs_followup = db.session.query(func.count(ElenaClient.id))\
        .filter(ElenaClient.next_followup_at != None)\
        .filter(ElenaClient.next_followup_at <= soon).scalar()

    active_buyers = db.session.query(func.count(ElenaClient.id))\
        .filter(ElenaClient.client_type == ClientType.BUYER)\
        .filter(ElenaClient.pipeline_stage != PipelineStage.CLOSED).scalar()

    active_sellers = db.session.query(func.count(ElenaClient.id))\
        .filter(ElenaClient.client_type == ClientType.SELLER)\
        .filter(ElenaClient.pipeline_stage != PipelineStage.CLOSED).scalar()

    return jsonify({
        "new_leads": new_leads,
        "needs_followup": needs_followup,
        "active_buyers": active_buyers,
        "active_sellers": active_sellers,
    })


# ============================================================
# CREATE FLYER
# ============================================================

@elena_bp.post("/flyers/create")
def create_flyer():
    data = request.json
    flyer_type = data["flyer_type"]
    property_id = data.get("property_id")
    address = data.get("property_address")

    text = generate_elena_flyer_text(flyer_type, property_id, address)

    flyer = ElenaFlyer(
        flyer_type=flyer_type,
        property_id=property_id,
        property_address=address,
        body=text,
    )
    db.session.add(flyer)
    db.session.commit()

    return jsonify({
        "id": flyer.id,
        "flyer_type": flyer.flyer_type,
        "property_address": flyer.property_address,
        "body": flyer.body,
    })


# ============================================================
# FOLLOW-UP EMAIL
# ============================================================

@elena_bp.post("/followup/generate")
def followup_generate():
    data = request.json
    client_id = data["client_id"]
    template_type = data.get("template_type", "general_followup")

    client = ElenaClient.query.get(client_id)
    if not client:
        return jsonify({"error": "Client not found"}), 404

    email_text = generate_followup_email(client, template_type)

    interaction = ElenaInteraction(
        client_id=client.id,
        interaction_type=InteractionType.EMAIL,
        content=email_text,
    )
    db.session.add(interaction)
    db.session.commit()

    return jsonify({"email": email_text})


# ============================================================
# CLIENT LIST + CREATE
# ============================================================

@elena_bp.get("/clients")
def list_clients():
    clients = ElenaClient.query.order_by(ElenaClient.created_at.desc()).all()
    return jsonify([
        {
            "id": c.id,
            "full_name": c.full_name,
            "email": c.email,
            "phone": c.phone,
            "client_type": c.client_type.value,
            "pipeline_stage": c.pipeline_stage.value,
            "tags": c.tags,
            "source": c.source,
        }
        for c in clients
    ])


@elena_bp.post("/clients")
def create_client():
    data = request.json
    client = ElenaClient(
        full_name=data["full_name"],
        email=data.get("email"),
        phone=data.get("phone"),
        client_type=ClientType(data.get("client_type", "lead")),
        pipeline_stage=PipelineStage.NEW_LEAD,
        tags=data.get("tags"),
        source=data.get("source", "manual"),
    )
    db.session.add(client)
    db.session.commit()
    return jsonify({"id": client.id})


# ============================================================
# EXCEL IMPORT
# ============================================================

@elena_bp.post("/import/preview")
def import_preview():
    file = request.files["file"]
    df = pd.read_excel(file)

    return jsonify({
        "columns": list(df.columns),
        "sample": df.head(5).to_dict(orient="records"),
    })


@elena_bp.post("/import/commit")
def import_commit():
    payload = request.json
    mapping = payload["mapping"]
    rows = payload["rows"]
    source = payload.get("source", "excel_import")

    created = 0
    for row in rows:
        full_name = row.get(mapping.get("full_name"))
        if not full_name:
            continue

        client = ElenaClient(
            full_name=full_name,
            email=row.get(mapping.get("email")),
            phone=row.get(mapping.get("phone")),
            client_type=ClientType.LEAD,
            pipeline_stage=PipelineStage.NEW_LEAD,
            source=source,
        )
        db.session.add(client)
        created += 1

    db.session.commit()
    return jsonify({"created": created})
