from datetime import datetime
from LoanMVP.extensions import db

class Contractor(db.Model):
    __tablename__ = "contractors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    website = db.Column(db.String(255))
    location = db.Column(db.String(120))
    description = db.Column(db.Text)
    approved = db.Column(db.Boolean, default=False)
    featured = db.Column(db.Boolean, default=False)
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    payments = db.relationship("ContractorPayment", backref="contractor", lazy=True)

class ContractorPayment(db.Model):
    __tablename__ = "contractor_payments"
    id = db.Column(db.Integer, primary_key=True)
    contractor_id = db.Column(db.Integer, db.ForeignKey("contractors.id"))
    amount = db.Column(db.Float)
    status = db.Column(db.String(20), default="pending")  # pending, paid, expired
    transaction_id = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ContractorBidOpportunity(db.Model):
    """Tracks external/self-sourced jobs Jamaine is pursuing from any channel."""
    __tablename__ = "contractor_bid_opportunities"

    id         = db.Column(db.Integer, primary_key=True)
    partner_id = db.Column(db.Integer, db.ForeignKey("partners.id"), nullable=False, index=True)

    project_name    = db.Column(db.String(255), nullable=False)
    source          = db.Column(db.String(120), nullable=True)   # where it came from
    category        = db.Column(db.String(100), nullable=True)   # Demo, Renovation, etc.
    location        = db.Column(db.String(255), nullable=True)
    estimated_value = db.Column(db.Float,       nullable=True)
    bid_deadline    = db.Column(db.DateTime,    nullable=True)
    notes           = db.Column(db.Text,        nullable=True)

    # reviewing → bid_submitted → won / lost / no_bid
    status     = db.Column(db.String(50), default="reviewing", nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    partner = db.relationship("Partner", backref=db.backref("bid_opportunities", lazy="dynamic"))

    def __repr__(self):
        return f"<ContractorBidOpportunity {self.id} {self.project_name} {self.status}>"
