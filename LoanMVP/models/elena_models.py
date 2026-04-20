from LoanMVP.extensions import db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship


class BaseModel(db.Model):
    __abstract__ = True

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ElenaClient(BaseModel):
    __tablename__ = "elena_clients"

    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    role = Column(String(50), nullable=True)
    tags = Column(String(255), nullable=True)
    pipeline_stage = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    preferred_areas = Column(String, nullable=True)
    budget = Column(String, nullable=True)

    assigned_member_id = Column(Integer, nullable=True)
    market = Column(String(100), nullable=True)

    interactions = relationship("ElenaInteraction", back_populates="client", lazy=True)
    listings = relationship("ElenaListing", back_populates="client", lazy=True)

    def __repr__(self):
        return f"<ElenaClient {self.id} - {self.name}>"


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
    status = Column(String(20), nullable=False, default="active")

    market = Column(String(100), nullable=True)

    client_id = Column(Integer, ForeignKey("elena_clients.id"), nullable=True)
    client = relationship("ElenaClient", back_populates="listings")

    flyers = relationship("ElenaFlyer", backref="listing", lazy=True)

    def __repr__(self):
        return f"<ElenaListing {self.id} - {self.address}>"


class ElenaFlyer(db.Model):
    __tablename__ = "elena_flyers"

    id = db.Column(db.Integer, primary_key=True)
    flyer_type = db.Column(db.String(100), nullable=False)
    property_address = db.Column(db.String(255))
    property_id = db.Column(db.String(64))
    body = db.Column(db.Text)
    listing_id = db.Column(db.Integer, db.ForeignKey("elena_listings.id"), nullable=True)

    canva_design_id = db.Column(db.String(128), nullable=True, index=True)
    canva_edit_url = db.Column(db.Text, nullable=True)
    canva_export_job_id = db.Column(db.String(128), nullable=True)
    canva_export_url = db.Column(db.Text, nullable=True)
    canva_status = db.Column(db.String(50), nullable=True, default="draft")
    canva_last_synced_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    due_at = Column(DateTime, nullable=True)

    client = relationship("ElenaClient", back_populates="interactions")

    def __repr__(self):
        return f"<ElenaInteraction {self.id} - {self.interaction_type}>"