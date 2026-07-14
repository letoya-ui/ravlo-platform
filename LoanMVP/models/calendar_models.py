import uuid
from datetime import datetime

from LoanMVP.extensions import db


def _new_confirmation_token() -> str:
    return uuid.uuid4().hex


class DemoAvailability(db.Model):
    """A recurring weekly block of time a staff member (executive or
    account executive) is open to take demo bookings. Actual open slots
    for the public booking page are computed on the fly from these
    templates minus any already-booked DemoBooking rows -- there is no
    per-slot row generated ahead of time.

    All times are company-local (see scheduling.py's COMPANY_TIMEZONE),
    not per-visitor timezone-converted -- the public booking page labels
    times with the company timezone so this stays honest rather than
    silently wrong.
    """

    __tablename__ = "demo_availability"

    id = db.Column(db.Integer, primary_key=True)
    host_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    day_of_week = db.Column(db.Integer, nullable=False)  # 0 = Monday ... 6 = Sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    slot_minutes = db.Column(db.Integer, nullable=False, default=30)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    host = db.relationship("User", foreign_keys=[host_user_id])

    def __repr__(self):
        return f"<DemoAvailability host={self.host_user_id} dow={self.day_of_week} {self.start_time}-{self.end_time}>"


class DemoBooking(db.Model):
    """A prospect's booked demo slot with a specific host."""

    __tablename__ = "demo_bookings"

    id = db.Column(db.Integer, primary_key=True)
    host_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    # Random, unguessable -- looked up on the public confirmation page
    # instead of the sequential id, so one prospect can't enumerate
    # another's booking (name/email/notes) by guessing nearby ids.
    confirmation_token = db.Column(db.String(32), nullable=False, unique=True, index=True, default=_new_confirmation_token)

    starts_at = db.Column(db.DateTime, nullable=False, index=True)  # company-local, naive
    ends_at = db.Column(db.DateTime, nullable=False)

    prospect_name = db.Column(db.String(255), nullable=False)
    prospect_email = db.Column(db.String(255), nullable=False, index=True)
    prospect_company = db.Column(db.String(255), nullable=True)
    prospect_phone = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), nullable=False, default="scheduled")  # scheduled, canceled
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    canceled_at = db.Column(db.DateTime, nullable=True)

    host = db.relationship("User", foreign_keys=[host_user_id])

    def __repr__(self):
        return f"<DemoBooking host={self.host_user_id} starts_at={self.starts_at} status={self.status}>"
