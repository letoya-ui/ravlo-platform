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

    # saved_opportunity → bid_package_needed → missing_information → draft_bid_prepared →
    # jamaine_review_needed → ready_to_send → bid_submitted → follow_up_needed → won / lost / no_bid
    status     = db.Column(db.String(50), default="reviewing", nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    partner = db.relationship("Partner", backref=db.backref("bid_opportunities", lazy="dynamic"))

    def __repr__(self):
        return f"<ContractorBidOpportunity {self.id} {self.project_name} {self.status}>"


class ConstructionProject(db.Model):
    """Active construction job converted from a won bid opportunity.

    Created automatically when a ContractorBidOpportunity is marked 'won'.
    The unique constraint on bid_opportunity_id prevents duplicate projects
    from the same bid — idempotent creation is safe to call multiple times.
    """
    __tablename__ = "construction_projects"

    id                   = db.Column(db.Integer, primary_key=True)
    # unique=True enforces one project per bid — the duplicate-prevention mechanism
    bid_opportunity_id   = db.Column(
        db.Integer, db.ForeignKey("contractor_bid_opportunities.id"),
        unique=True, nullable=True, index=True,
    )
    partner_id           = db.Column(db.Integer, db.ForeignKey("partners.id"), nullable=False, index=True)

    # Carried over from the bid
    project_name         = db.Column(db.String(255), nullable=False)
    location             = db.Column(db.String(255), nullable=True)
    category             = db.Column(db.String(100), nullable=True)
    source               = db.Column(db.String(120), nullable=True)
    estimated_value      = db.Column(db.Float,       nullable=True)  # original bid estimate
    contract_amount      = db.Column(db.Float,       nullable=True)  # negotiated final amount
    notes                = db.Column(db.Text,        nullable=True)
    bid_date             = db.Column(db.DateTime,    nullable=True)  # bid_deadline from opportunity

    # Default team — overrideable per-project
    project_manager      = db.Column(db.String(120), default="Jamaine Caughman")
    office_coordinator   = db.Column(db.String(120), default="Sandra")
    executive            = db.Column(db.String(120), default="Letoya")

    # pre_construction → active → on_hold → punch_list → completed → invoiced → paid / cancelled
    status               = db.Column(db.String(50), default="pre_construction", nullable=False)
    start_date           = db.Column(db.DateTime, nullable=True)
    estimated_completion = db.Column(db.DateTime, nullable=True)
    actual_completion    = db.Column(db.DateTime, nullable=True)

    created_at           = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at           = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    partner = db.relationship("Partner",                  backref=db.backref("construction_projects", lazy="dynamic"))
    bid     = db.relationship("ContractorBidOpportunity", backref=db.backref("project", uselist=False))

    def __repr__(self):
        return f"<ConstructionProject {self.id} {self.project_name} {self.status}>"


class BidSuggestion(db.Model):
    """A suggested opportunity surfaced on the Bid Search page.

    Stays in the suggestion layer until Jamaine acts on it: Save or Send to
    Sandra converts it into a ContractorBidOpportunity; Not Interested hides
    it; Follow Up Later keeps it visible but de-prioritised.
    """
    __tablename__ = "bid_suggestions"

    id              = db.Column(db.Integer, primary_key=True)
    partner_id      = db.Column(db.Integer, db.ForeignKey("partners.id"), nullable=False, index=True)

    title           = db.Column(db.String(255), nullable=False)
    category        = db.Column(db.String(100), nullable=True)
    source_name     = db.Column(db.String(120), nullable=True)
    source_url      = db.Column(db.String(500), nullable=True)
    location        = db.Column(db.String(255), nullable=True)
    due_date        = db.Column(db.DateTime,    nullable=True)
    estimated_value = db.Column(db.Float,       nullable=True)
    contact         = db.Column(db.String(255), nullable=True)
    summary         = db.Column(db.Text,        nullable=True)

    # active → saved / not_interested / follow_up
    status          = db.Column(db.String(30), default="active", nullable=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    partner = db.relationship("Partner", backref=db.backref("bid_suggestions", lazy="dynamic"))

    def __repr__(self):
        return f"<BidSuggestion {self.id} {self.title} {self.status}>"
