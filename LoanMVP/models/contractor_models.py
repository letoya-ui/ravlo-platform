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

    # Where this suggestion came from. "manual" for hand-entered rows;
    # otherwise the discovery adapter name (e.g. "samgov"). external_ref is a
    # stable per-source id ("samgov:<noticeId>") used to dedupe auto-imports.
    origin          = db.Column(db.String(30), default="manual", nullable=False)
    external_ref    = db.Column(db.String(255), nullable=True, index=True)

    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    partner = db.relationship("Partner", backref=db.backref("bid_suggestions", lazy="dynamic"))

    def __repr__(self):
        return f"<BidSuggestion {self.id} {self.title} {self.status}>"


class BidProposal(db.Model):
    """Client-facing proposal generated from a ContractorBidOpportunity.

    One proposal per bid (unique FK). Stores draft content, client contact
    info, and submission tracking (sent_at / sent_by / follow_up_date).
    """
    __tablename__ = "bid_proposals"

    id                 = db.Column(db.Integer, primary_key=True)
    bid_opportunity_id = db.Column(
        db.Integer, db.ForeignKey("contractor_bid_opportunities.id"),
        unique=True, nullable=False, index=True,
    )
    partner_id = db.Column(db.Integer, db.ForeignKey("partners.id"), nullable=False, index=True)

    client_name    = db.Column(db.String(255), nullable=True)
    client_email   = db.Column(db.String(255), nullable=True)
    client_phone   = db.Column(db.String(50),  nullable=True)
    client_address = db.Column(db.String(500), nullable=True)

    scope_of_work    = db.Column(db.Text, nullable=True)
    line_items       = db.Column(db.JSON, nullable=True)   # [{desc, qty, unit, unit_cost}]
    terms            = db.Column(db.Text, nullable=True)
    notes_for_client = db.Column(db.Text, nullable=True)
    prepared_by      = db.Column(db.String(120), default="Caughman Mason Construction")

    sent_at        = db.Column(db.DateTime, nullable=True)
    sent_by        = db.Column(db.String(120), nullable=True)
    follow_up_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bid     = db.relationship("ContractorBidOpportunity", backref=db.backref("proposal", uselist=False))
    partner = db.relationship("Partner", backref=db.backref("bid_proposals", lazy="dynamic"))

    def __repr__(self):
        return f"<BidProposal {self.id} bid={self.bid_opportunity_id}>"


class ProjectDailyLog(db.Model):
    __tablename__ = "project_daily_logs"

    id         = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("construction_projects.id"), nullable=False, index=True)
    log_date   = db.Column(db.Date, nullable=False)
    crew_size  = db.Column(db.Integer, nullable=True)
    weather    = db.Column(db.String(80),  nullable=True)
    work_done  = db.Column(db.Text, nullable=True)
    issues     = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("ConstructionProject", backref=db.backref("daily_logs", lazy="dynamic"))

    def __repr__(self):
        return f"<ProjectDailyLog {self.id} project={self.project_id} {self.log_date}>"


class ProjectPhoto(db.Model):
    __tablename__ = "project_photos"

    id         = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("construction_projects.id"), nullable=False, index=True)
    url        = db.Column(db.String(1000), nullable=False)
    caption    = db.Column(db.String(255),  nullable=True)
    phase      = db.Column(db.String(50),   nullable=True)  # before / during / after
    created_by = db.Column(db.String(120),  nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("ConstructionProject", backref=db.backref("photos", lazy="dynamic"))

    def __repr__(self):
        return f"<ProjectPhoto {self.id} project={self.project_id}>"


class ProjectMilestone(db.Model):
    __tablename__ = "project_milestones"

    id           = db.Column(db.Integer, primary_key=True)
    project_id   = db.Column(db.Integer, db.ForeignKey("construction_projects.id"), nullable=False, index=True)
    title        = db.Column(db.String(255), nullable=False)
    due_date     = db.Column(db.Date, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    notes        = db.Column(db.Text, nullable=True)
    sort_order   = db.Column(db.Integer, default=0)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("ConstructionProject", backref=db.backref("milestones", lazy="dynamic"))

    def __repr__(self):
        return f"<ProjectMilestone {self.id} project={self.project_id} {self.title}>"


class ProjectExpenseItem(db.Model):
    __tablename__ = "construction_project_expenses"

    id          = db.Column(db.Integer, primary_key=True)
    project_id  = db.Column(db.Integer, db.ForeignKey("construction_projects.id"), nullable=False, index=True)
    description = db.Column(db.String(255), nullable=False)
    category    = db.Column(db.String(80),  nullable=True)  # Labor / Materials / Subcontractor / Equipment / Other
    amount      = db.Column(db.Float, nullable=False, default=0.0)
    paid_date   = db.Column(db.Date, nullable=True)
    vendor      = db.Column(db.String(120), nullable=True)
    created_by  = db.Column(db.String(120), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("ConstructionProject", backref=db.backref("expense_items", lazy="dynamic"))

    def __repr__(self):
        return f"<ProjectExpenseItem {self.id} project={self.project_id} ${self.amount}>"


class ProjectInvoice(db.Model):
    __tablename__ = "project_invoices"

    id             = db.Column(db.Integer, primary_key=True)
    project_id     = db.Column(db.Integer, db.ForeignKey("construction_projects.id"), nullable=False, index=True)
    invoice_number = db.Column(db.String(50),  nullable=True)
    description    = db.Column(db.Text, nullable=True)
    amount         = db.Column(db.Float, nullable=False, default=0.0)
    issued_date    = db.Column(db.Date, nullable=True)
    due_date       = db.Column(db.Date, nullable=True)
    paid_date      = db.Column(db.Date, nullable=True)
    status         = db.Column(db.String(30), default="draft", nullable=False)  # draft / sent / paid / overdue
    notes          = db.Column(db.Text, nullable=True)
    created_by     = db.Column(db.String(120), nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("ConstructionProject", backref=db.backref("invoices", lazy="dynamic"))

    def __repr__(self):
        return f"<ProjectInvoice {self.id} project={self.project_id} ${self.amount} {self.status}>"


class ProjectChangeOrder(db.Model):
    __tablename__ = "project_change_orders"

    id           = db.Column(db.Integer, primary_key=True)
    project_id   = db.Column(db.Integer, db.ForeignKey("construction_projects.id"), nullable=False, index=True)
    title        = db.Column(db.String(255), nullable=False)
    description  = db.Column(db.Text, nullable=True)
    amount       = db.Column(db.Float, nullable=True)   # positive = addition, negative = reduction
    status       = db.Column(db.String(30), default="pending", nullable=False)  # pending / approved / rejected
    requested_by = db.Column(db.String(120), nullable=True)
    approved_by  = db.Column(db.String(120), nullable=True)
    approved_at  = db.Column(db.DateTime, nullable=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("ConstructionProject", backref=db.backref("change_orders", lazy="dynamic"))

    def __repr__(self):
        return f"<ProjectChangeOrder {self.id} project={self.project_id} {self.title}>"
