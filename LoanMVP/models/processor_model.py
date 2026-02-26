# ====================================
# ⚙️ PROCESSOR PROFILE MODEL
# ====================================
from datetime import datetime
from LoanMVP.extensions import db

class ProcessorProfile(db.Model):
    __tablename__ = "processor_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", name="fk_processor_user_id"),
        nullable=False
    )
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(50))
    department = db.Column(db.String(100))
    assigned_loans = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ Relationship back to LoanApplication
    loans = db.relationship(
        "LoanApplication",
        back_populates="processor",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ProcessorProfile {self.full_name} ({self.email})>"
