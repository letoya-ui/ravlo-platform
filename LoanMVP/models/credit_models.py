from LoanMVP.extensions import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB

class SoftCreditReport(db.Model):
    __tablename__ = "soft_credit_report"

    id = db.Column(db.Integer, primary_key=True)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"))

    credit_score = db.Column(db.Integer)
    bureau = db.Column(db.String(50), default="Equifax")

    # Full JSON response from Equifax
    credit_data = db.Column(JSONB)
    monthly_debt_total = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    borrower = db.relationship("BorrowerProfile", backref="credit_reports")

