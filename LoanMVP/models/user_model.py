from flask_login import UserMixin
from LoanMVP.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    username = db.Column(db.String(120), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(50), nullable=True)  # admin, borrower, loan_officer, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=None)
    timeline_status = db.Column(db.String(50), default="application_submitted")

    # ===============================
    # 🔗 Relationships
    # ===============================
    borrower_profile = db.relationship(
        "BorrowerProfile",
        back_populates="user",
        foreign_keys="[BorrowerProfile.user_id]"
    )

    loan_officer_profile = db.relationship(
        "LoanOfficerProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete"
    )

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

    crm_notes = db.relationship(
        "CRMNote",
        back_populates="user",
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
    
    @hybrid_property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    @full_name.expression
    def full_name(cls):
        return func.concat(cls.first_name, " ", cls.last_name)

    @property
    def full_name(self):
        """Combine first and last name safely."""
        if self.first_name or self.last_name:
            return f"{self.first_name or ''} {self.last_name or ''}".strip()
        return self.username or self.email
