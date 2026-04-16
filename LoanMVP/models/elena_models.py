from LoanMVP.extensions import db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import uuid


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

    # Basic info
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    # CRM fields
    pipeline_stage = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    # Preferences
    preferred_areas = Column(String, nullable=True)
    budget = Column(String, nullable=True)

    # Relationships
    interactions = relationship("ElenaInteraction", backref="client", lazy=True)

    def __repr__(self):
        return f"<ElenaClient {self.id} - {self.name}>"


# ---------------------------------------------------------
# LISTING MODEL (MLS IMPORT)
# ---------------------------------------------------------
class ElenaListing(BaseModel):
    __tablename__ = "elena_listings"

    mls_number = Column(String, nullable=True)

    # Property details
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

    # Relationships
    flyers = relationship("ElenaFlyer", backref="listing", lazy=True)

    def __repr__(self):
        return f"<ElenaListing {self.id} - {self.address}>"


# ---------------------------------------------------------
# FLYER MODEL (GENERATED CONTENT)
# ---------------------------------------------------------
class ElenaFlyer(BaseModel):
    __tablename__ = "elena_flyers"

    flyer_type = Column(String, nullable=False)

    # Property reference
    property_address = Column(String, nullable=False)
    property_id = Column(String, nullable=True)  # UUID or listing ID
    listing_id = Column(Integer, ForeignKey("elena_listings.id"), nullable=True)

    # Generated content
    body = Column(Text, nullable=False)

    def __repr__(self):
        return f"<ElenaFlyer {self.id} - {self.flyer_type}>"


# ---------------------------------------------------------
# INTERACTION MODEL (EMAILS, NOTES, LOGS)
# ---------------------------------------------------------
class InteractionType:
    EMAIL = "email"
    NOTE = "note"
    SHOWING = "showing"
    CALL = "call"
    TEXT = "text"


class ElenaInteraction(BaseModel):
    __tablename__ = "elena_interactions"

    client_id = Column(Integer, ForeignKey("elena_clients.id"), nullable=False)
    interaction_type = Column(String, nullable=False)

    content = Column(Text, nullable=False)
    meta = Column(String, nullable=True)

    def __repr__(self):
        return f"<ElenaInteraction {self.id} - {self.interaction_type}>"
