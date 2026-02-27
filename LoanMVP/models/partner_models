# LoanMVP/models/partner_models.py

from datetime import datetime
from LoanMVP.extensions import db

class PartnerConnectionRequest(db.Model):
    __tablename__ = "partner_connection_requests"

    id = db.Column(db.Integer, primary_key=True)

    # ✅ Correct table name for User is "user"
    borrower_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # ✅ Add these so your relationships actually work + so requests can link to a workspace context
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=True)
    property_id = db.Column(db.Integer, db.ForeignKey("property.id"), nullable=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"), nullable=True)

    partner_id = db.Column(db.Integer, db.ForeignKey("partners.id"), nullable=False)

    category = db.Column(db.String(100), nullable=True)  # match Partner.category size
    message = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), default="pending")  # pending | accepted | declined | canceled | completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    partner = db.relationship("Partner", backref=db.backref("connection_requests", lazy=True))
    borrower = db.relationship("BorrowerProfile", foreign_keys=[borrower_profile_id])
    property = db.relationship("Property", foreign_keys=[property_id])


class PartnerJob(db.Model):
    __tablename__ = "partner_jobs"

    id = db.Column(db.Integer, primary_key=True)
    partner_id = db.Column(db.Integer, db.ForeignKey("partners.id"), nullable=False)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=True)
    property_id = db.Column(db.Integer, db.ForeignKey("property.id"), nullable=True)

    title = db.Column(db.String(200), nullable=False)
    scope = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(30), default="Open")  # Open/In Progress/Blocked/Complete
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    partner = db.relationship("Partner", backref=db.backref("jobs", lazy=True))
    borrower = db.relationship("BorrowerProfile", backref=db.backref("partner_jobs", lazy=True))
    property = db.relationship("Property", foreign_keys=[property_id])
