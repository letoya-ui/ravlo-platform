from datetime import datetime, timedelta
import secrets

from LoanMVP.extensions import db


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email_domain = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship("User", back_populates="company", lazy=True)
    invites = db.relationship("UserInvite", backref="company", lazy=True)


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
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])

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
    inviter = db.relationship("User", foreign_keys=[invited_by])

    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(32)

    @staticmethod
    def default_expiration(days=7):
        return datetime.utcnow() + timedelta(days=days)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at
