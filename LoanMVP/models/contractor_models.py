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


# ─────────────────────────────────────────────────────────────────────────────
# VIP Contractor workspace models
#
# These are owned by VIPProfile (role_type="contractor"). They power the
# day-to-day jobs board, bid CRUD, change-order requests, before/after photo
# tracking and the generated job report.
# ─────────────────────────────────────────────────────────────────────────────


class ContractorJob(db.Model):
    """A contractor's active / scheduled / completed job.

    Separate from ``PartnerJob`` (investor-initiated) so the contractor can
    own their own pipeline — direct clients, referrals, and accepted bids
    all land here.
    """

    __tablename__ = "contractor_jobs"

    id              = db.Column(db.Integer, primary_key=True)
    vip_profile_id  = db.Column(db.Integer,
                                db.ForeignKey("vip_profiles.id"),
                                nullable=False, index=True)

    title        = db.Column(db.String(200), nullable=False)
    client_name  = db.Column(db.String(200), nullable=True)
    client_email = db.Column(db.String(255), nullable=True)
    client_phone = db.Column(db.String(50),  nullable=True)

    address     = db.Column(db.String(255), nullable=True)
    scope_text  = db.Column(db.Text,        nullable=True)

    status = db.Column(db.String(30), nullable=False, default="scheduled")
    # scheduled | in_progress | blocked | completed | cancelled

    agreed_price = db.Column(db.Float, nullable=True)

    start_date   = db.Column(db.Date,     nullable=True)
    end_date     = db.Column(db.Date,     nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    # "bid" — linked to an accepted ContractorBid
    # "direct" — contractor-created
    # "referral" — from PartnerJob etc.
    source      = db.Column(db.String(30), nullable=True)
    source_ref  = db.Column(db.String(100), nullable=True)

    notes       = db.Column(db.Text, nullable=True)

    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow,
                            onupdate=datetime.utcnow)

    photos         = db.relationship(
        "ContractorJobPhoto",
        backref="job",
        lazy=True,
        cascade="all, delete-orphan",
    )
    change_orders  = db.relationship(
        "ContractorChangeOrder",
        backref="job",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def summary(self):
        return {
            "id":     self.id,
            "title":  self.title,
            "status": self.status,
            "price":  self.agreed_price,
            "client": self.client_name,
        }


class ContractorBid(db.Model):
    """A bid the contractor sends out to a prospect.

    Lives independently of a ``ContractorJob`` — when a bid is accepted, a
    new job is created and `job_id` is backfilled.
    """

    __tablename__ = "contractor_bids"

    id              = db.Column(db.Integer, primary_key=True)
    vip_profile_id  = db.Column(db.Integer,
                                db.ForeignKey("vip_profiles.id"),
                                nullable=False, index=True)
    job_id          = db.Column(db.Integer,
                                db.ForeignKey("contractor_jobs.id"),
                                nullable=True)

    prospect_name  = db.Column(db.String(200), nullable=False)
    prospect_email = db.Column(db.String(255), nullable=True)
    prospect_phone = db.Column(db.String(50),  nullable=True)

    address    = db.Column(db.String(255), nullable=True)
    scope_text = db.Column(db.Text,        nullable=True)

    labor_cost     = db.Column(db.Float, nullable=True, default=0)
    materials_cost = db.Column(db.Float, nullable=True, default=0)
    other_cost     = db.Column(db.Float, nullable=True, default=0)
    total_cost     = db.Column(db.Float, nullable=True, default=0)

    timeline       = db.Column(db.String(120), nullable=True)

    status = db.Column(db.String(30), nullable=False, default="draft")
    # draft | sent | accepted | declined | expired

    sent_at      = db.Column(db.DateTime, nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)
    expires_at   = db.Column(db.DateTime, nullable=True)

    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    def recalc_total(self):
        self.total_cost = (
            float(self.labor_cost or 0)
            + float(self.materials_cost or 0)
            + float(self.other_cost or 0)
        )
        return self.total_cost


class ContractorChangeOrder(db.Model):
    """A change-order request the contractor raises against an active job."""

    __tablename__ = "contractor_change_orders"

    id              = db.Column(db.Integer, primary_key=True)
    vip_profile_id  = db.Column(db.Integer,
                                db.ForeignKey("vip_profiles.id"),
                                nullable=False, index=True)
    job_id          = db.Column(db.Integer,
                                db.ForeignKey("contractor_jobs.id"),
                                nullable=False, index=True)

    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text,        nullable=True)

    added_cost  = db.Column(db.Float,   nullable=True, default=0)
    added_days  = db.Column(db.Integer, nullable=True, default=0)

    status = db.Column(db.String(20), nullable=False, default="pending")
    # pending | approved | declined

    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)


class ContractorJobPhoto(db.Model):
    """Before / during / after photos on a contractor job.

    Drives the generated job report.
    """

    __tablename__ = "contractor_job_photos"

    id              = db.Column(db.Integer, primary_key=True)
    vip_profile_id  = db.Column(db.Integer,
                                db.ForeignKey("vip_profiles.id"),
                                nullable=False, index=True)
    job_id          = db.Column(db.Integer,
                                db.ForeignKey("contractor_jobs.id"),
                                nullable=False, index=True)

    phase = db.Column(db.String(20), nullable=False, default="before")
    # before | during | after

    file_path = db.Column(db.String(500), nullable=False)
    caption   = db.Column(db.String(500), nullable=True)

    taken_at   = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# VIP Lender workspace — rate sheet
#
# Lives next to the contractor models because it's the parallel "VIP dashboard
# upgrade" surface. A rate sheet is a product the lender is currently quoting.
# ─────────────────────────────────────────────────────────────────────────────


class LenderRateSheet(db.Model):
    """A loan product the lender is actively quoting."""

    __tablename__ = "lender_rate_sheets"

    id             = db.Column(db.Integer, primary_key=True)
    vip_profile_id = db.Column(db.Integer,
                               db.ForeignKey("vip_profiles.id"),
                               nullable=False, index=True)

    product_name = db.Column(db.String(200), nullable=False)
    loan_type    = db.Column(db.String(100), nullable=True)
    # e.g. "DSCR", "Fix & Flip", "Conventional", "HELOC", "Bridge"

    base_rate   = db.Column(db.Float,   nullable=True)   # e.g. 7.25 = 7.25%
    max_ltv     = db.Column(db.Float,   nullable=True)   # e.g. 80.0 = 80%
    min_credit  = db.Column(db.Integer, nullable=True)   # FICO
    term_months = db.Column(db.Integer, nullable=True)
    points      = db.Column(db.Float,   nullable=True)   # origination points
    fees_text   = db.Column(db.Text,    nullable=True)

    notes       = db.Column(db.Text, nullable=True)

    is_active      = db.Column(db.Boolean,  nullable=False, default=True)
    effective_date = db.Column(db.Date,     nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)
