# LoanMVP/models/property.py
from LoanMVP.extensions import db
from datetime import datetime
from sqlalchemy import Text

# ====================================
# 🏠 PROPERTY MODEL
# ====================================
class Property(db.Model):
    __tablename__ = "property"

    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    zip = db.Column(db.String(20))
    price = db.Column(db.Float)
    beds = db.Column(db.Integer)
    baths = db.Column(db.Float)
    sqft = db.Column(db.Integer)
    image_url = db.Column(db.String(255))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    loan_applications = db.relationship(
        "LoanApplication",
        back_populates="property",
        cascade="all, delete-orphan",
        lazy=True
    )

    lender_quotes = db.relationship(
        "LenderQuote",
        back_populates="property",
        cascade="all, delete-orphan",
        lazy=True
    )

    analyses = db.relationship(
        "PropertyAnalysis",
        back_populates="property",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return f"<Property {self.address}, {self.city}, {self.state}>"

    def to_dict(self):
        return {
            "id": self.id,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "zip": self.zip,
            "price": self.price,
            "beds": self.beds,
            "baths": self.baths,
            "sqft": self.sqft,
            "image_url": self.image_url,
            "description": self.description,
        }


class SavedProperty(db.Model):
    __tablename__ = "saved_properties"

    id = db.Column(db.Integer, primary_key=True)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=False)
    property_id = db.Column(db.String(50))
    address = db.Column(db.String(255))
    price = db.Column(db.String(50))
    sqft = db.Column(db.Integer, nullable=True)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    zipcode = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ NEW
    resolved_json = db.Column(db.Text, nullable=True)   # stores unified property payload
    resolved_at = db.Column(db.DateTime, nullable=True)

    borrower = db.relationship("BorrowerProfile", backref=db.backref("saved_properties", lazy=True))