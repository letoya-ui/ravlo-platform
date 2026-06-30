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
