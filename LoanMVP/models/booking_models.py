# LoanMVP/models/booking_models.py
"""Booking capability: a public "schedule a visit" calendar any
VIP-style workspace can turn on (contractor quote visits, realtor
showings, insurance consultations, ...).

Deliberately does NOT touch the existing Salon/Stylist booking system
(StylistProfile/SalonAvailability/Appointment) -- that vertical already
has its own live, working booking flow with client formulas, photos, and
product-sale history hanging off Appointment, and migrating it onto a
generic table would be a risky rewrite of something that already works
for a real paying customer. This is for the workspaces that have no
booking system at all today (VIPProfile-based: realtor/insurance/
contractor), starting with Mason-Fultz's quote-visit scheduling.

Same owner-agnostic pattern as PaymentAccount/PaymentRequest in
payment_models.py: the owner is referenced via (owner_type, owner_id)
rather than a foreign key into any one vertical's profile table, resolved
by LoanMVP/services/payments_service.py's resolve_current_owner() (reused
here rather than duplicated).
"""
import uuid
from datetime import datetime

from LoanMVP.extensions import db


def _new_confirmation_token() -> str:
    return uuid.uuid4().hex


class BookingAvailability(db.Model):
    """A recurring weekly block of time a workspace is open for public
    booking. Actual open slots are computed on the fly from these
    templates minus already-booked Booking rows -- no pre-generated
    per-slot row, same approach as DemoAvailability/SalonAvailability."""

    __tablename__ = "booking_availabilities"

    id = db.Column(db.Integer, primary_key=True)

    owner_type = db.Column(db.String(50), nullable=False)
    owner_id = db.Column(db.Integer, nullable=False, index=True)

    day_of_week = db.Column(db.Integer, nullable=False)  # 0 = Monday ... 6 = Sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    slot_minutes = db.Column(db.Integer, nullable=False, default=60)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BookingAvailability {self.owner_type}:{self.owner_id} dow={self.day_of_week}>"


class Booking(db.Model):
    """A client's scheduled visit with a workspace (a quote visit, a
    showing, a consultation, ...)."""

    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)

    owner_type = db.Column(db.String(50), nullable=False)
    owner_id = db.Column(db.Integer, nullable=False, index=True)

    title = db.Column(db.String(255), nullable=True)
    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    ends_at = db.Column(db.DateTime, nullable=False)

    client_name = db.Column(db.String(255), nullable=False)
    client_email = db.Column(db.String(255), nullable=True)
    client_phone = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # scheduled -> canceled
    status = db.Column(db.String(20), nullable=False, default="scheduled")

    # Random, unguessable -- looked up on the public confirmation page
    # instead of the sequential id.
    confirmation_token = db.Column(
        db.String(32), nullable=False, unique=True, index=True, default=_new_confirmation_token
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Booking {self.owner_type}:{self.owner_id} starts_at={self.starts_at}>"
