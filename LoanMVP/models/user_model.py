from flask_login import UserMixin
from LoanMVP.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import func


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)

    # Identity
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    username = db.Column(db.String(120), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)

    # Auth
    password_hash = db.Column(db.String(255), nullable=True)

    # Role system
    role = db.Column(db.String(50), nullable=True)  # admin, borrower, loan_officer, investor, partner, etc.

    # Company assignment
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)

    # Activation + onboarding
    is_active = db.Column(db.Boolean, default=True)
    invite_accepted = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=None)

    # Borrower timeline
    timeline_status = db.Column(db.String(50), default="application_submitted")

    # ===============================
    # 🔗 Relationships
    # ===============================

    # Company relationship
    company = db.relationship("Company", back_populates="users")

    # Borrower
    borrower_profile = db.relationship(
        "BorrowerProfile",
        back_populates="user",
        foreign_keys="[BorrowerProfile.user_id]"
    )

    # Loan officer
    loan_officer_profile = db.relationship(
        "LoanOfficerProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete"
    )

    # Investor
    investor_profile = db.relationship(
        "InvestorProfile",
        back_populates="user",
        foreign_keys="[InvestorProfile.user_id]"
    )

    # Messaging
    messages_sent = db.relationship(
        "Message",
        foreign_keys="Message.sender_id",
        back_populates="sender",
        lazy=True
    )

    messages_received = db.relationship(
        "Message",
        foreign_keys="Message.receiver_id",
        back_populates="receiver",
        lazy=True
    )

    # CRM
    crm_notes = db.relationship(
        "CRMNote",
        back_populates="user",
        lazy=True
    )

    # Admin: invites sent
    invites_sent = db.relationship(
        "UserInvite",
        back_populates="inviter",
        lazy=True
    )

    # Admin: access requests reviewed
    access_requests = db.relationship(
        "AccessRequest",
        back_populates="reviewer",
        lazy=True
    )

    # ===============================
    # 🧩 Methods
    # ===============================

    def __repr__(self):
        return f"<User {self.username or self.email} ({self.role})>"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Full name hybrid property
    @hybrid_property
    def full_name(self):
        if self.first_name or self.last_name:
            return f"{self.first_name or ''} {self.last_name or ''}".strip()
        return self.username or self.email

    @full_name.expression
    def full_name(cls):
        return func.trim(
            func.concat(
                func.coalesce(cls.first_name, ""),
                " ",
                func.coalesce(cls.last_name, "")
            )
        )
