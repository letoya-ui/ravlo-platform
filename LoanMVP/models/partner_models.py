# LoanMVP/models/partner_models.py

from datetime import datetime
from LoanMVP.extensions import db

class PartnerConnectionRequest(db.Model):
    __tablename__ = "partner_connection_requests"

    id = db.Column(db.Integer, primary_key=True)

    borrower_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    investor_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=True)
    investor_profile_id = db.Column(db.Integer, db.ForeignKey("investor_profile.id"), nullable=True)

    property_id = db.Column(db.Integer, db.ForeignKey("property.id"), nullable=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"), nullable=True)

    deal_id = db.Column(db.Integer, db.ForeignKey("deals.id"), nullable=True)
    saved_property_id = db.Column(db.Integer, db.ForeignKey("saved_properties.id"), nullable=True)

    partner_id = db.Column(db.Integer, db.ForeignKey("partners.id"), nullable=True)
    external_partner_lead_id = db.Column(db.Integer, db.ForeignKey("external_partner_leads.id"), nullable=True)

    category = db.Column(db.String(100), nullable=True)
    message = db.Column(db.Text, nullable=True)

    source = db.Column(db.String(30), default="internal")
    # internal / external / fallback_search

    status = db.Column(db.String(20), default="pending")
    # pending | accepted | declined | canceled | completed | awaiting_match

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)

    partner = db.relationship("Partner", backref=db.backref("connection_requests", lazy=True))
    external_partner_lead = db.relationship("ExternalPartnerLead", foreign_keys=[external_partner_lead_id])

    borrower = db.relationship("BorrowerProfile", foreign_keys=[borrower_profile_id])
    investor_profile = db.relationship("InvestorProfile", foreign_keys=[investor_profile_id])
    property = db.relationship("Property", foreign_keys=[property_id])



class PartnerJob(db.Model):
    __tablename__ = "partner_jobs"

    id = db.Column(db.Integer, primary_key=True)
    partner_id = db.Column(db.Integer, db.ForeignKey("partners.id"), nullable=False)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=True)
    investor_profile_id = db.Column(db.Integer, db.ForeignKey("investor_profile.id"), nullable=True)
    property_id = db.Column(db.Integer, db.ForeignKey("property.id"), nullable=True)

    title = db.Column(db.String(200), nullable=False)
    scope = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(30), default="Open")  # Open/In Progress/Blocked/Complete
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    partner = db.relationship("Partner", backref=db.backref("jobs", lazy=True))
    borrower = db.relationship("BorrowerProfile", backref=db.backref("partner_jobs", lazy=True))
    investor_profile = db.relationship("InvestorProfile", backref=db.backref("partner_jobs", lazy=True))
    property = db.relationship("Property", foreign_keys=[property_id])

class PartnerPhoto(db.Model):
    __tablename__ = "partner_photos"

    id = db.Column(db.Integer, primary_key=True)

    partner_id = db.Column(
        db.Integer,
        db.ForeignKey("partners.id", ondelete="CASCADE"),
        nullable=False
    )

    url = db.Column(db.String(500), nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    partner = db.relationship(
        "Partner",
        back_populates="photos"
    )

class ExternalPartnerLead(db.Model):
    __tablename__ = "external_partner_leads"

    id = db.Column(db.Integer, primary_key=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    investor_profile_id = db.Column(db.Integer, db.ForeignKey("investor_profile.id"), nullable=True)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=True)

    partner_id = db.Column(db.Integer, db.ForeignKey("partners.id"), nullable=True)

    name = db.Column(db.String(255), nullable=False)
    business_name = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(100), nullable=True)

    source = db.Column(db.String(50), nullable=True)       # google / yelp / manual
    external_id = db.Column(db.String(255), nullable=True) # Google place_id etc.

    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    website = db.Column(db.String(255), nullable=True)

    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    state = db.Column(db.String(20), nullable=True)
    zip_code = db.Column(db.String(20), nullable=True)

    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)

    invite_status = db.Column(db.String(30), default="new")
    # new / saved / invited / contacted / joined / ignored

    notes = db.Column(db.Text, nullable=True)
    raw_json = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = db.relationship("User", foreign_keys=[created_by_user_id])
    investor_profile = db.relationship("InvestorProfile", foreign_keys=[investor_profile_id])
    borrower_profile = db.relationship("BorrowerProfile", foreign_keys=[borrower_profile_id])
    partner = db.relationship("Partner", foreign_keys=[partner_id])
