# LoanMVP/routes/elena.py

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from enum import Enum
import json
import pandas as pd

from LoanMVP.extensions import db
from sqlalchemy import (
    Column, Integer, String, DateTime, Text,
    Enum as SAEnum, ForeignKey, Float, func
)
from sqlalchemy.orm import relationship

from LoanMVP.services.ai_service import generate_text
from LoanMVP.services.mashvisor_service import (
    get_property_by_mls,
    normalize_mls_listing,
    MashvisorServiceError,
)


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
# MODELS
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
    listings = relationship("ElenaListing", back_populates="client")


class ElenaInteraction(db.Model):
    __tablename__ = "elena_interactions"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("elena_clients.id"), nullable=False)
    interaction_type = Column(SAEnum(InteractionType), nullable=False)
    content = Column(Text, nullable=True)
    meta = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("ElenaClient", back_populates="interactions")


class ElenaListing(db.Model):
    __tablename__ = "elena_listings"

    id = Column(Integer, primary_key=True)
    mls_number = Column(String, nullable=False, index=True)

    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    zip_code = Column(String, nullable=True)

    price = Column(Float, nullable=True)
    beds = Column(Float, nullable=True)
    baths = Column(Float, nullable=True)
    sqft = Column(Integer, nullable=True)
    lot_size = Column(Float, nullable=True)
    property_type = Column(String, nullable=True)
    year_built = Column(Integer, nullable=True)

    description = Column(Text, nullable=True)
    photos_json = Column(Text, nullable=True)

    client_id = Column(Integer, ForeignKey("elena_clients.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("ElenaClient", back_populates="listings")
    flyers = relationship("ElenaFlyer", back_populates="listing")


class ElenaFlyer(db.Model):
    __tablename__ = "elena_flyers"

    id = Column(Integer, primary_key=True)
    flyer_type = Column(SAEnum(FlyerType), nullable=False)

    property_address = Column(String, nullable=True)
    property_id = Column(String, nullable=True)  # can store listing.id or external id

    title = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    export_url = Column(String, nullable=True)

    listing_id = Column(Integer, ForeignKey("elena_listings.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, default="elena")

    listing = relationship("ElenaListing", back_populates="flyers")


# ============================================================
# AI HELPERS
# ============================================================

def generate_elena_flyer_text_from_listing(listing: ElenaListing, flyer_type: FlyerType) -> str:
    photos = []
    try:
        photos = json.loads(listing.photos_json or "[]")
    except Exception:
        photos = []

    prompt = f"""
    You are writing a real estate flyer for Hudson Valley Realtor Elena James (Keller Williams).

    Flyer type: {flyer_type.value}
    Address: {listing.address}, {listing.city}, {listing.state} {listing.zip_code}
    Beds: {listing.beds or ""}
    Baths: {listing.baths or ""}
    Sqft: {listing.sqft or ""}
    Price: {listing.price or ""}

    Existing description (if any):
    {listing.description or ""}

    Photos count: {len(photos)}

    Write:
    - A compelling headline (max 10 words)
    - A 2–3 sentence lifestyle-focused description
    - 4–6 bullet highlights (features, neighborhood, lifestyle)
    Tone: warm, professional, Hudson Valley lifestyle, conversational but polished.
    """

    return generate_text(prompt)


def generate_followup_email(client: ElenaClient, template_type: str, context=None) -> str:
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
    Tone: warm, professional, helpful, service-first.
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

    listings_count = db.session.query(func.count(ElenaListing.id)).scalar()

    return jsonify({
        "new_leads": new_leads,
        "needs_followup": needs_followup,
        "active_buyers": active_buyers,
        "active_sellers": active_sellers,
        "listings_count": listings_count,
    })


# ============================================================
# MLS IMPORT VIA MASHVISOR
# ============================================================

@elena_bp.post("/mls/import")
def mls_import():
    data = request.json or {}
    mls_number = data.get("mls_number")
    client_id = data.get("client_id")
    auto_generate_flyer = bool(data.get("auto_generate_flyer", False))

    if not mls_number:
        return jsonify({"error": "mls_number is required"}), 400

    try:
        raw = get_property_by_mls(mls_number)
    except MashvisorServiceError as e:
        return jsonify({"error": f"Mashvisor error: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": f"Unexpected error fetching MLS listing: {str(e)}"}), 500

    normalized = normalize_mls_listing(raw)

    listing = ElenaListing(
        mls_number=normalized.get("mls_number") or mls_number,
        address=normalized.get("address"),
        city=normalized.get("city"),
        state=normalized.get("state"),
        zip_code=normalized.get("zip_code"),
        price=normalized.get("price"),
        beds=normalized.get("beds"),
        baths=normalized.get("baths"),
        sqft=normalized.get("sqft"),
        lot_size=normalized.get("lot_size"),
        property_type=normalized.get("property_type"),
        year_built=normalized.get("year_built"),
        description=normalized.get("description"),
        photos_json=json.dumps(normalized.get("photos") or []),
        client_id=client_id,
    )

    db.session.add(listing)
    db.session.commit()

    flyer_payload = None
    if auto_generate_flyer:
        flyer_text = generate_elena_flyer_text_from_listing(listing, FlyerType.JUST_LISTED)
        flyer = ElenaFlyer(
            flyer_type=FlyerType.JUST_LISTED,
            property_address=listing.address,
            property_id=str(listing.id),
            body=flyer_text,
            listing_id=listing.id,
        )
        db.session.add(flyer)
        db.session.commit()

        flyer_payload = {
            "id": flyer.id,
            "flyer_type": flyer.flyer_type.value,
            "property_address": flyer.property_address,
            "body": flyer.body,
        }

    return jsonify({
        "listing": {
            "id": listing.id,
            "mls_number": listing.mls_number,
            "address": listing.address,
            "city": listing.city,
            "state": listing.state,
            "zip_code": listing.zip_code,
            "price": listing.price,
            "beds": listing.beds,
            "baths": listing.baths,
            "sqft": listing.sqft,
            "lot_size": listing.lot_size,
            "property_type": listing.property_type,
            "year_built": listing.year_built,
            "description": listing.description,
        },
        "flyer": flyer_payload,
        "can_auto_generate_flyer": True,
    })


# ============================================================
# FLYER CREATE (MANUAL)
# ============================================================

@elena_bp.post("/flyers/create")
def create_flyer():
    data = request.json or {}
    flyer_type = data.get("flyer_type", FlyerType.JUST_LISTED.value)
    property_address = data.get("property_address")
    property_id = data.get("property_id")
    listing_id = data.get("listing_id")
    body = data.get("body")

    if listing_id and not body:
        listing = ElenaListing.query.get(listing_id)
        if not listing:
            return jsonify({"error": "Listing not found"}), 404
        body = generate_elena_flyer_text_from_listing(listing, FlyerType(flyer_type))
        property_address = property_address or listing.address
        property_id = property_id or str(listing.id)

    if not body:
        return jsonify({"error": "body is required if no listing_id provided"}), 400

    flyer = ElenaFlyer(
        flyer_type=FlyerType(flyer_type),
        property_address=property_address,
        property_id=property_id,
        body=body,
        listing_id=listing_id,
    )
    db.session.add(flyer)
    db.session.commit()

    return jsonify({
        "id": flyer.id,
        "flyer_type": flyer.flyer_type.value,
        "property_address": flyer.property_address,
        "body": flyer.body,
    })


# ============================================================
# FOLLOW-UP EMAIL
# ============================================================

@elena_bp.post("/followup/generate")
def followup_generate():
    data = request.json or {}
    client_id = data.get("client_id")
    template_type = data.get("template_type", "general_followup")

    if not client_id:
        return jsonify({"error": "client_id is required"}), 400

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
    data = request.json or {}
    full_name = data.get("full_name")
    if not full_name:
        return jsonify({"error": "full_name is required"}), 400

    client = ElenaClient(
        full_name=full_name,
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
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "file is required"}), 400

    df = pd.read_excel(file)

    return jsonify({
        "columns": list(df.columns),
        "sample": df.head(5).to_dict(orient="records"),
    })


@elena_bp.post("/import/commit")
def import_commit():
    payload = request.json or {}
    mapping = payload.get("mapping") or {}
    rows = payload.get("rows") or []
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
