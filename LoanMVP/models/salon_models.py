# LoanMVP/models/salon_models.py
"""Salon / beauty-business vertical (Stylist role).

Mirrors the LoanOfficerProfile pattern: one profile row per stylist User,
with company_id denormalized directly onto every child table (clients,
appointments, sales, reviews) for the same tenant-isolation reasons
LoanApplication/BorrowerProfile carry company_id rather than relying on
joins through the profile -- every dashboard/list query filters on it
directly.
"""
from datetime import datetime

from LoanMVP.extensions import db


class StylistProfile(db.Model):
    __tablename__ = "stylist_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", name="fk_stylist_user_id"), nullable=False, unique=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", name="fk_stylist_company_id"), nullable=True, index=True)

    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    specialty = db.Column(db.String(255))
    bio = db.Column(db.Text)
    avatar_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="stylist_profile", foreign_keys=[user_id])
    clients = db.relationship("SalonClient", back_populates="stylist", cascade="all, delete-orphan", lazy=True)
    appointments = db.relationship("Appointment", back_populates="stylist", cascade="all, delete-orphan", lazy=True)


class SalonClient(db.Model):
    __tablename__ = "salon_clients"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", name="fk_salonclient_company_id"), nullable=False, index=True)
    stylist_id = db.Column(db.Integer, db.ForeignKey("stylist_profile.id", name="fk_salonclient_stylist_id"), nullable=False, index=True)

    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    notes = db.Column(db.Text)
    loyalty_points = db.Column(db.Integer, default=0, nullable=False)
    last_visit_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    stylist = db.relationship("StylistProfile", back_populates="clients")
    appointments = db.relationship("Appointment", back_populates="client", cascade="all, delete-orphan", lazy=True)
    formulas = db.relationship("ClientFormula", back_populates="client", cascade="all, delete-orphan", lazy=True)
    photos = db.relationship("ClientPhoto", back_populates="client", cascade="all, delete-orphan", lazy=True)
    loyalty_transactions = db.relationship(
        "LoyaltyTransaction", back_populates="client", cascade="all, delete-orphan", lazy=True
    )


class Appointment(db.Model):
    __tablename__ = "salon_appointments"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", name="fk_appt_company_id"), nullable=False, index=True)
    stylist_id = db.Column(db.Integer, db.ForeignKey("stylist_profile.id", name="fk_appt_stylist_id"), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("salon_clients.id", name="fk_appt_client_id"), nullable=False, index=True)

    service_type = db.Column(db.String(150), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False, index=True)
    duration_minutes = db.Column(db.Integer, default=60)
    price = db.Column(db.Numeric(10, 2), nullable=True)
    status = db.Column(db.String(20), default="scheduled", nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    stylist = db.relationship("StylistProfile", back_populates="appointments")
    client = db.relationship("SalonClient", back_populates="appointments")


class ClientFormula(db.Model):
    __tablename__ = "salon_client_formulas"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("salon_clients.id", name="fk_formula_client_id"), nullable=False, index=True)
    stylist_id = db.Column(db.Integer, db.ForeignKey("stylist_profile.id", name="fk_formula_stylist_id"), nullable=False, index=True)

    title = db.Column(db.String(150), nullable=False)
    notes = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = db.relationship("SalonClient", back_populates="formulas")
    stylist = db.relationship("StylistProfile")


class ClientPhoto(db.Model):
    __tablename__ = "salon_client_photos"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("salon_clients.id", name="fk_photo_client_id"), nullable=False, index=True)
    appointment_id = db.Column(
        db.Integer, db.ForeignKey("salon_appointments.id", name="fk_photo_appointment_id"), nullable=True, index=True
    )

    photo_type = db.Column(db.String(10), default="after", nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship("SalonClient", back_populates="photos")
    appointment = db.relationship("Appointment")


class ProductSale(db.Model):
    __tablename__ = "salon_product_sales"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", name="fk_productsale_company_id"), nullable=False, index=True)
    stylist_id = db.Column(db.Integer, db.ForeignKey("stylist_profile.id", name="fk_productsale_stylist_id"), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("salon_clients.id", name="fk_productsale_client_id"), nullable=True, index=True)

    product_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    sold_at = db.Column(db.DateTime, default=datetime.utcnow)

    stylist = db.relationship("StylistProfile")
    client = db.relationship("SalonClient")


class SalonReview(db.Model):
    __tablename__ = "salon_reviews"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", name="fk_review_company_id"), nullable=False, index=True)
    stylist_id = db.Column(db.Integer, db.ForeignKey("stylist_profile.id", name="fk_review_stylist_id"), nullable=True, index=True)

    client_name = db.Column(db.String(120), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    source = db.Column(db.String(50), default="direct")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    stylist = db.relationship("StylistProfile")


class LoyaltyTransaction(db.Model):
    __tablename__ = "salon_loyalty_transactions"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("salon_clients.id", name="fk_loyalty_client_id"), nullable=False, index=True)

    points = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship("SalonClient", back_populates="loyalty_transactions")
