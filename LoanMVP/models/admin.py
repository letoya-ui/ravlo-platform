from datetime import datetime, timedelta
import secrets

from LoanMVP.extensions import db


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

    # These fields exist in your database but were missing in your model
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(255), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    zip = db.Column(db.String(20), nullable=True)

    email_domain = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    subscription_tier = db.Column(db.String(50), nullable=True)
    max_users = db.Column(db.Integer, nullable=True)
    
    is_blocked = db.Column(db.Boolean, default=False, nullable=False)
    blocked_at = db.Column(db.DateTime, nullable=True)
    blocked_reason = db.Column(db.String(100), nullable=True)
    blocked_note = db.Column(db.Text, nullable=True)
    blocked_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    billing_status = db.Column(db.String(50), default="active", nullable=True)
    grace_period_ends_at = db.Column(db.DateTime, nullable=True)

    users = db.relationship("User", back_populates="company", foreign_keys="User.company_id", lazy=True)
    invites = db.relationship("UserInvite", back_populates="company", lazy=True)
    access_requests = db.relationship("AccessRequest", backref="company", lazy=True)
    blocked_by_user = db.relationship(
        "User",
        foreign_keys=[blocked_by],
        back_populates="blocked_companies",
        lazy=True
    )

    def seats_used(self) -> int:
        from LoanMVP.models.user_model import User
        return User.query.filter_by(company_id=self.id).count()

    def has_seat_available(self) -> bool:
        """max_users=None means an uncapped plan (e.g. white_label/Enterprise)."""
        if self.max_users is None:
            return True
        return self.seats_used() < self.max_users


class AccessRequest(db.Model):
    __tablename__ = "access_requests"

    id = db.Column(db.Integer, primary_key=True)

    company_name = db.Column(db.String(255), nullable=True)
    contact_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(50), nullable=True)

    request_type = db.Column(db.String(50), nullable=False, default="company_setup")
    requested_role = db.Column(db.String(50), nullable=True)

    status = db.Column(db.String(50), nullable=False, default="pending")
    notes = db.Column(db.Text, nullable=True)

    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)

    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewer = db.relationship("User", foreign_keys=[reviewed_by], back_populates="access_requests")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserInvite(db.Model):
    __tablename__ = "user_invites"

    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)

    email = db.Column(db.String(255), nullable=False, index=True)
    first_name = db.Column(db.String(120), nullable=True)
    last_name = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(50), nullable=False)

    token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False, default="pending")

    invited_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    inviter = db.relationship("User", foreign_keys=[invited_by], back_populates="invites_sent")

    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    company = db.relationship("Company", back_populates="invites")

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(32)

    @staticmethod
    def default_expiration(days=7):
        return datetime.utcnow() + timedelta(days=days)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

class BusinessInquiry(db.Model):
    """Unified inbox for inbound submissions: license applications, plain
    contact-us messages, lending OS leads, investor challenge signups,
    referrals, and feedback. `inquiry_type` distinguishes the submission
    channel; `business_type` is only meaningful for inquiry_type ==
    'license_application' (broker, lender, fund, brokerage, enterprise)."""
    __tablename__ = "business_inquiries"

    id = db.Column(db.Integer, primary_key=True)
    inquiry_type = db.Column(db.String(50), nullable=False, default="license_application")
    # license_application, contact, lending_os_lead, challenge_signup, referral, feedback

    company_name = db.Column(db.String(255), nullable=False, default="—")
    contact_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(50))
    website = db.Column(db.String(255))

    business_type = db.Column(db.String(100))  # broker, lender, fund, brokerage, enterprise
    team_size = db.Column(db.String(50))
    plan_interest = db.Column(db.String(100))  # individual, team, lender, white_label

    monthly_loan_volume = db.Column(db.String(100))
    current_tools = db.Column(db.Text)
    goals = db.Column(db.Text)
    notes = db.Column(db.Text)

    status = db.Column(db.String(50), default="new", nullable=False)  # new, contacted, approved, declined
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class LicenseInviteEvent(db.Model):
    __tablename__ = "license_invite_events"

    id = db.Column(db.Integer, primary_key=True)

    invite_token = db.Column(db.String(255))
    email = db.Column(db.String(255))

    event_type = db.Column(db.String(50))  # opened
    user_agent = db.Column(db.String(255))
    ip_address = db.Column(db.String(50))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SubscriptionRequest(db.Model):
    __tablename__ = "subscription_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False, default="pending")
    plan_requested = db.Column(db.String(50), nullable=True, default="Core")
    # Which self-service upgrade flow this came from: "investor_preview",
    # "partner_tier", or "borrower_plan". Lets one shared pending-request
    # queue serve all of them without a separate table per flow.
    context = db.Column(db.String(50), nullable=True, default="investor_preview")
    message = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id], lazy=True)
    reviewer = db.relationship("User", foreign_keys=[reviewed_by], lazy=True)
