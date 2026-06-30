from datetime import datetime
from LoanMVP.extensions import db


DIVISIONS = [
    ("construction",      "Construction"),
    ("lending",           "Lending"),
    ("brokerage",         "Real Estate Brokerage"),
    ("janitorial",        "Janitorial"),
    ("property_mgmt",     "Property Management"),
    ("development",       "Development"),
    ("corporate",         "Corporate / Admin"),
]

INCOME_CATEGORIES = [
    "Contract Revenue",
    "Deposit Received",
    "Change Order",
    "Referral Fee",
    "Commission",
    "Management Fee",
    "Loan Origination Fee",
    "Other Income",
]

EXPENSE_CATEGORIES = [
    "Materials",
    "Labor",
    "Subcontractors",
    "Equipment",
    "Equipment Rental",
    "Insurance",
    "Licenses & Permits",
    "Marketing",
    "Office / Admin",
    "Software / Tools",
    "Travel",
    "Fuel",
    "Taxes & Fees",
    "Professional Services",
    "Other Expense",
]


class CMFinanceEntry(db.Model):
    """Single income or expense entry for any Caughman Mason division."""
    __tablename__ = "cm_finance_entries"

    id              = db.Column(db.Integer, primary_key=True)
    created_by_id   = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    division        = db.Column(db.String(50),  nullable=False, default="construction")
    entry_type      = db.Column(db.String(10),  nullable=False)   # income | expense
    category        = db.Column(db.String(100), nullable=True)
    description     = db.Column(db.String(255), nullable=True)
    amount          = db.Column(db.Float,       nullable=False)
    entry_date      = db.Column(db.Date,        nullable=False, default=datetime.utcnow)
    project_name    = db.Column(db.String(255), nullable=True)   # optional job reference
    notes           = db.Column(db.Text,        nullable=True)

    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    created_by = db.relationship("User", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<CMFinanceEntry {self.id} {self.division} {self.entry_type} ${self.amount}>"


class ChallengeEnrollment(db.Model):
    """Tracks who has signed up for each challenge (investor, lending, etc.)."""
    __tablename__ = "challenge_enrollments"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    slug        = db.Column(db.String(50), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("challenge_enrollments", lazy="dynamic"))

    def __repr__(self):
        return f"<ChallengeEnrollment {self.user_id} {self.slug}>"


class FeedbackSurvey(db.Model):
    """NPS + qualitative feedback submitted via /feedback."""
    __tablename__ = "feedback_surveys"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(150), nullable=True)
    email       = db.Column(db.String(255), nullable=True)
    nps_score   = db.Column(db.Integer,     nullable=False)   # 0–10
    liked       = db.Column(db.Text,        nullable=True)
    improve     = db.Column(db.Text,        nullable=True)
    source      = db.Column(db.String(50),  nullable=True)    # e.g. "email", "platform"
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<FeedbackSurvey {self.id} NPS={self.nps_score} {self.email}>"


class UserEmailConnection(db.Model):
    """Stores OAuth tokens for a user's connected email account (Gmail, Outlook)."""
    __tablename__ = "user_email_connections"

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    provider        = db.Column(db.String(20), nullable=False, default="gmail")  # gmail | outlook
    email_address   = db.Column(db.String(255), nullable=True)
    access_token    = db.Column(db.Text, nullable=True)
    refresh_token   = db.Column(db.Text, nullable=True)
    token_expiry    = db.Column(db.DateTime, nullable=True)
    connected_at    = db.Column(db.DateTime, default=datetime.utcnow)
    last_synced_at  = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref=db.backref("email_connection", uselist=False))

    def __repr__(self):
        return f"<UserEmailConnection {self.user_id} {self.provider} {self.email_address}>"
