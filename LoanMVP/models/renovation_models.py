# LoanMVP/models/renovation_models.py
from datetime import datetime
from LoanMVP.extensions import db

class RenovationMockup(db.Model):
    __tablename__ = "renovation_mockup"
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    borrower_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=True)

    property_id = db.Column(db.String(64), nullable=True)  # your "property_id" string
    saved_property_id = db.Column(db.Integer, db.ForeignKey("saved_properties.id"), nullable=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("deal.id"), nullable=True)

    before_url = db.Column(db.Text, nullable=False)
    after_url = db.Column(db.Text, nullable=False)

    style_prompt = db.Column(db.Text, nullable=True)
    style_preset = db.Column(db.String(40), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
