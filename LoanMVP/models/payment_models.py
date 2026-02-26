from datetime import datetime
from LoanMVP.extensions import db

class PaymentRecord(db.Model):
    __tablename__ = "payment_record"

    id = db.Column(db.Integer, primary_key=True)

    borrower_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("borrower_profile.id", name="fk_payment_borrower")
    )

    loan_id = db.Column(
        db.Integer,
        db.ForeignKey("loan_application.id", name="fk_payment_loan")
    )

    payment_type = db.Column(db.String(100))  # Appraisal, Credit Pull, App Fee, etc.
    amount = db.Column(db.Float)
    status = db.Column(db.String(20), default="Pending")  # Pending / Paid
    stripe_payment_intent = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    borrower = db.relationship("BorrowerProfile", backref="payments")
    loan = db.relationship("LoanApplication", backref="payments")
