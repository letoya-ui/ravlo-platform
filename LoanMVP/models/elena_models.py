from LoanMVP.extensions import db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship


# ---------------------------------------------------------
# BASE MODEL
# ---------------------------------------------------------
class BaseModel(db.Model):
    __abstract__ = True

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---------------------------------------------------------
# CLIENT MODEL (CRM)
# ---------------------------------------------------------
class ElenaClient(BaseModel):
    __tablename__ = "elena_clients"

    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    # Contact type inside Elena's CRM:
    # realtor, investor, contractor, partner, student, buyer, seller, etc.
    role = Column(String(50), nullable=True)

    # Free-form comma-separated tags used for filtering and segmentation.
    tags = Column(String(255), nullable=True)

    pipeline_stage = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    preferred_areas = Column(String, nullable=True)
    budget = Column(String, nullable=True)

    # Relationships
    interactions = relationship("ElenaInteraction", back_populates="client", lazy=True)
    listings = relationship("ElenaListing", back_populates="client", lazy=True)

    def __repr__(self):
        return f"<ElenaClient {self.id} - {self.name}>"


# ---------------------------------------------------------
# LISTING MODEL (MLS IMPORT)
# ---------------------------------------------------------
class ElenaListing(BaseModel):
    __tablename__ = "elena_listings"

    mls_number = Column(String, nullable=True)

    address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    zip_code = Column(String, nullable=False)

    beds = Column(Integer, nullable=True)
    baths = Column(Integer, nullable=True)
    sqft = Column(Integer, nullable=True)
    price = Column(Integer, nullable=True)

    description = Column(Text, nullable=True)
    photos_json = Column(Text, nullable=True)

    # Lifecycle status: active, pending, sold, withdrawn.
    status = Column(String(20), nullable=False, default="active")

    # ⭐ REQUIRED — this was missing
    client_id = Column(Integer, ForeignKey("elena_clients.id"), nullable=True)
    client = relationship("ElenaClient", back_populates="listings")

    flyers = relationship("ElenaFlyer", backref="listing", lazy=True)

    def __repr__(self):
        return f"<ElenaListing {self.id} - {self.address}>"


# ---------------------------------------------------------
# FLYER MODEL
# ---------------------------------------------------------
class ElenaFlyer(BaseModel):
    __tablename__ = "elena_flyers"

    flyer_type = Column(String, nullable=False)

    property_address = Column(String, nullable=False)
    property_id = Column(String, nullable=True)
    listing_id = Column(Integer, ForeignKey("elena_listings.id"), nullable=True)

    # Optional display-facing title and call-to-action so flyers can be
    # rendered without re-parsing the full body each time.
    title = Column(String(255), nullable=True)
    cta = Column(String(255), nullable=True)

    body = Column(Text, nullable=False)

    def __repr__(self):
        return f"<ElenaFlyer {self.id} - {self.flyer_type}>"


# ---------------------------------------------------------
# INTERACTION MODEL
# ---------------------------------------------------------
class InteractionType:
    EMAIL = "email"
    NOTE = "note"
    SHOWING = "showing"
    CALL = "call"
    TEXT = "text"
    MEETING = "meeting"
    FOLLOW_UP = "follow_up"


class ElenaInteraction(BaseModel):
    __tablename__ = "elena_interactions"

    client_id = Column(Integer, ForeignKey("elena_clients.id"), nullable=False)
    interaction_type = Column(String, nullable=False)

    content = Column(Text, nullable=False)
    meta = Column(String, nullable=True)

    # Optional scheduled time for follow-ups and meetings.
    due_at = Column(DateTime, nullable=True)

    client = relationship("ElenaClient", back_populates="interactions")

    def __repr__(self):
        return f"<ElenaInteraction {self.id} - {self.interaction_type}>"
