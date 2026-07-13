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

    # Set when an investor adds this property to their managed rental
    # portfolio (Property Management tool). Independent of any loan
    # application this property may also be the subject of.
    owner_investor_id = db.Column(db.Integer, db.ForeignKey("investor_profile.id"), nullable=True, index=True)

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

    owner_investor = db.relationship(
        "InvestorProfile", foreign_keys=[owner_investor_id], backref=db.backref("managed_properties", lazy=True)
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

    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=True, index=True)
    investor_profile_id = db.Column(db.Integer, db.ForeignKey("investor_profile.id"), nullable=True, index=True)

    property_id = db.Column(db.String(50))
    address = db.Column(db.String(255))
    price = db.Column(db.String(50))
    sqft = db.Column(db.Integer, nullable=True)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    zipcode = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    resolved_json = db.Column(db.Text, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    investor_profile = db.relationship("InvestorProfile", back_populates="saved_properties")
    borrower = db.relationship("BorrowerProfile", back_populates="saved_properties")

@property
def rehab_before_url(self):
    payload = self.resolved_json or {}
    payload = payload if isinstance(payload, dict) else {}
    return (payload.get("rehab", {}) or {}).get("before_url") or ""


# ====================================
# 🏢 PROPERTY MANAGEMENT
# ====================================
# Units, tenants, rent, and maintenance for properties an investor
# actively manages as a rental (distinct from Deal/PropertyAnalysis,
# which are one-time underwriting records for a prospective purchase).

class PropertyUnit(db.Model):
    __tablename__ = "property_units"

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("property.id"), nullable=False, index=True)

    unit_label = db.Column(db.String(100), nullable=False, default="Main Unit")
    bedrooms = db.Column(db.Integer)
    bathrooms = db.Column(db.Float)
    sqft = db.Column(db.Integer)
    market_rent = db.Column(db.Numeric(10, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Named property_ref (not "property") -- assigning a class attribute
    # literally named "property" here would shadow the @property builtin
    # for the rest of this class body.
    property_ref = db.relationship(
        "Property", backref=db.backref("units", cascade="all, delete-orphan", lazy=True)
    )

    @property
    def active_tenant(self):
        return next((t for t in self.tenants if t.is_active), None)

    @property
    def is_occupied(self):
        return self.active_tenant is not None


class Tenant(db.Model):
    __tablename__ = "property_tenants"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("property_units.id"), nullable=False, index=True)

    full_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    lease_start = db.Column(db.Date)
    lease_end = db.Column(db.Date)
    monthly_rent = db.Column(db.Numeric(10, 2))
    security_deposit = db.Column(db.Numeric(10, 2))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    unit = db.relationship("PropertyUnit", backref=db.backref("tenants", cascade="all, delete-orphan", lazy=True))


class RentPayment(db.Model):
    __tablename__ = "property_rent_payments"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("property_units.id"), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("property_tenants.id"), nullable=True, index=True)

    period_month = db.Column(db.Date, nullable=False)
    amount_due = db.Column(db.Numeric(10, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(10, 2), default=0)
    paid_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default="unpaid", nullable=False)  # unpaid, partial, paid, late
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    unit = db.relationship("PropertyUnit", backref=db.backref("rent_payments", cascade="all, delete-orphan", lazy=True))
    tenant = db.relationship("Tenant", backref="rent_payments")


class MaintenanceRequest(db.Model):
    __tablename__ = "property_maintenance_requests"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("property_units.id"), nullable=False, index=True)
    reported_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(20), default="medium", nullable=False)  # low, medium, high, urgent
    status = db.Column(db.String(20), default="open", nullable=False)  # open, in_progress, resolved
    actual_cost = db.Column(db.Numeric(10, 2), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    unit = db.relationship(
        "PropertyUnit", backref=db.backref("maintenance_requests", cascade="all, delete-orphan", lazy=True)
    )
