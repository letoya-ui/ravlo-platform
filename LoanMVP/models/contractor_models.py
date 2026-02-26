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
