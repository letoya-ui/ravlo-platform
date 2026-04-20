from LoanMVP.extensions import db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
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


# ==================================================================
# LISTING PRESENTATION
# ==================================================================
# A full pitch deck a realtor builds to win a listing. Attaches to an
# existing ElenaListing (already-listed property) or stands alone for
# a prospect address that hasn't been added as a listing yet.
#
# Rich-text / structured sections are kept as independent columns so we
# can render them on the wizard editor, printable view, and shareable
# public page without parsing JSON at render time. Collections that are
# genuinely list-shaped (CMA comparables, marketing plan items,
# testimonials) are stored as JSON text on the row.
# ==================================================================
class RealtorListingPresentation(BaseModel):
    __tablename__ = "realtor_listing_presentations"

    # Owner — which VIP profile built this deck.
    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=True)

    # Optional link to an existing listing. When set, we auto-copy
    # address / beds / baths / price into the cover.
    listing_id = Column(Integer, ForeignKey("elena_listings.id"), nullable=True)

    # Client the presentation is going to (optional).
    client_id = Column(Integer, ForeignKey("elena_clients.id"), nullable=True)

    # Subject property / prospect info (denormalised so the deck survives
    # if the underlying listing is deleted).
    title             = Column(String(255), nullable=False, default="Listing Presentation")
    prospect_name     = Column(String(255), nullable=True)
    prospect_email    = Column(String(255), nullable=True)
    prospect_phone    = Column(String(50),  nullable=True)
    property_address  = Column(String(255), nullable=True)
    property_city     = Column(String(120), nullable=True)
    property_state    = Column(String(50),  nullable=True)
    property_zip      = Column(String(20),  nullable=True)
    property_beds     = Column(Integer, nullable=True)
    property_baths    = Column(Integer, nullable=True)
    property_sqft     = Column(Integer, nullable=True)

    # Hero asset for the cover (URL to photo/render).
    cover_image_url   = Column(String(500), nullable=True)

    # About the agent.
    agent_tagline     = Column(String(255), nullable=True)
    agent_bio         = Column(Text,        nullable=True)
    agent_stats_json  = Column(Text,        nullable=True)  # list[{label,value}]

    # Local market snapshot (free-text + structured stats).
    market_snapshot   = Column(Text,        nullable=True)
    market_stats_json = Column(Text,        nullable=True)  # list[{label,value}]

    # Comparative Market Analysis.
    # list[{address, status, price, sqft, beds, baths, adjustments}]
    cma_rows_json     = Column(Text, nullable=True)
    cma_summary       = Column(Text, nullable=True)

    # Pricing strategy.
    suggested_list_price  = Column(Integer, nullable=True)
    pricing_range_low     = Column(Integer, nullable=True)
    pricing_range_high    = Column(Integer, nullable=True)
    pricing_rationale     = Column(Text,    nullable=True)

    # Marketing plan. list[{title, description, icon}]
    marketing_plan_json   = Column(Text, nullable=True)

    # Testimonials. list[{quote, author}]
    testimonials_json     = Column(Text, nullable=True)

    # Commission & listing terms.
    commission_rate       = Column(String(20), nullable=True)    # "6%" or "5.5%"
    listing_term_months   = Column(Integer,    nullable=True)
    listing_term_notes    = Column(Text,       nullable=True)

    # Next steps / call to action.
    next_steps            = Column(Text, nullable=True)
    signature_line        = Column(String(255), nullable=True)

    # Delivery.
    status       = Column(String(20),  nullable=False, default="draft")
    share_slug   = Column(String(64),  nullable=True, unique=True, index=True)
    share_enabled = Column(Boolean,    nullable=False, default=False)
    sent_at      = Column(DateTime, nullable=True)
    last_viewed_at = Column(DateTime, nullable=True)
    view_count   = Column(Integer, nullable=False, default=0)

    # Relationships.
    listing = relationship("ElenaListing", lazy=True)
    client  = relationship("ElenaClient", lazy=True)

    def __repr__(self):
        return f"<RealtorListingPresentation {self.id} - {self.title}>"