# =========================================================
# 👔 UNDERWRITER MODELS (Unified & Updated)
# =========================================================
from datetime import datetime
from LoanMVP.extensions import db

# =========================================================
# 👤 UNDERWRITER PROFILE
# =========================================================
class UnderwriterProfile(db.Model):
    __tablename__ = "underwriter_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", name="fk_underwriter_user_id"),
        nullable=False
    )
    full_name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    department = db.Column(db.String(120))
    region = db.Column(db.String(120))
    active = db.Column(db.Boolean, default=True)

    # Stats & Activity
    total_quotes_reviewed = db.Column(db.Integer, default=0)
    total_loans_approved = db.Column(db.Integer, default=0)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    loan_quotes = db.relationship(
        "LoanQuote",
        backref="underwriter_profile",
        lazy=True,
        foreign_keys="LoanQuote.assigned_underwriter_id"
    )

    def __repr__(self):
        return f"<UnderwriterProfile {self.full_name or self.email}>"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "department": self.department,
            "region": self.region,
            "active": self.active,
            "total_quotes_reviewed": self.total_quotes_reviewed,
            "total_loans_approved": self.total_loans_approved,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =========================================================
# 🧾 UNDERWRITING CONDITIONS
# =========================================================
class UnderwritingCondition(db.Model):
    __tablename__ = "underwriting_condition"

    id = db.Column(db.Integer, primary_key=True)

    borrower_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("borrower_profile.id", name="fk_condition_borrower_id"),
        nullable=False
    )

    loan_id = db.Column(
        db.Integer,
        db.ForeignKey("loan_application.id", name="fk_condition_loan_id"),
        nullable=False
    )

    condition_type = db.Column(db.String(120))
    description = db.Column(db.String(800))
    severity = db.Column(db.String(50), default="Standard")  # Low / Standard / High
    status = db.Column(db.String(50), default="Open")        # Open / Cleared / Waived
    notes = db.Column(db.Text, nullable=True)
    requested_by = db.Column(db.String(100))
    cleared_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=db.func.now())
    cleared_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relationships
    borrower_profile = db.relationship("BorrowerProfile", back_populates="underwriting_conditions")
    loan = db.relationship("LoanApplication", back_populates="underwriting_conditions")

    def __repr__(self):
        return f"<UnderwritingCondition ID={self.id} BorrowerProfile={self.borrower_profile_id} Status={self.status}>"


# =========================================================
# 📤 CONDITION REQUESTS (Borrower Document Requests)
# =========================================================
class ConditionRequest(db.Model):
    __tablename__ = "condition_request"

    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(
        db.Integer,
        db.ForeignKey("loan_application.id", name="fk_conditionreq_loan_id"),
        nullable=False
    )
    borrower_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("borrower_profile.id", name="fk_conditionreq_borrower_id"),
        nullable=True
    )
    document_name = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), default="pending")  # pending / received / cleared / waived
    requested_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    condition_type = db.Column(db.String(120))  # 🆕 what kind of condition (e.g., Income, Appraisal)
    description = db.Column(db.Text)         
    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relationships
    loan = db.relationship("LoanApplication", back_populates="condition_requests")
    borrower_profile = db.relationship("BorrowerProfile", back_populates="condition_requests")
    requested_by_user = db.relationship("User", foreign_keys=[requested_by])
    assigned_to_user = db.relationship("User", foreign_keys=[assigned_to])

    def __repr__(self):
        return f"<ConditionRequest {self.document_name} for Loan {self.loan_id}>"


# =========================================================
# 🧾 UNDERWRITER AUDIT LOGS
# =========================================================
class UnderwriterAuditLog(db.Model):
    __tablename__ = "underwriter_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(
        db.Integer,
        db.ForeignKey("loan_application.id", name="fk_auditlog_loan_id"),
        nullable=True
    )
    user_name = db.Column(db.String(120))
    action_type = db.Column(db.String(100))      # e.g., "AI_RISK_ANALYSIS", "DOC_VERIFICATION"
    actor = db.Column(db.String(120))            # current_user.username or "AI"
    description = db.Column(db.String(800))
    outcome = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=db.func.now())
    notes = db.Column(db.Text)

    def __repr__(self):
        return f"<UnderwriterAuditLog Loan={self.loan_id} Action={self.action_type}>"


# =========================================================
# 📋 UNDERWRITER TASKS
# =========================================================
class UnderwriterTask(db.Model):
    __tablename__ = "underwriter_task"

    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    priority = db.Column(db.String(50), default="Normal")
    status = db.Column(db.String(50), default="Pending")
    assigned_to = db.Column(
        db.Integer,
        db.ForeignKey("underwriter_profile.id", name="fk_task_underwriter_id"),
        nullable=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    underwriter = db.relationship("UnderwriterProfile", backref="tasks")

    def __repr__(self):
        return f"<UnderwriterTask {self.title}>"
