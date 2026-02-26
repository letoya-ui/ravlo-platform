# =========================================================
# 🤖 AI MODELS — LoanMVP Unified AI Models (Clean 2025)
# =========================================================

from datetime import datetime
from LoanMVP.extensions import db


# =========================================================
# 🧠 Loan AI Conversations
# =========================================================
class LoanAIConversation(db.Model):
    __tablename__ = "loan_ai_conversation"

    id = db.Column(db.Integer, primary_key=True)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"))
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"))
    user_role = db.Column(db.String(50))
    topic = db.Column(db.String(120))
    user_message = db.Column(db.Text, nullable=False)
    ai_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ✅ Relationships
    loan = db.relationship("LoanApplication", back_populates="ai_conversations")
    borrower = db.relationship("BorrowerProfile", back_populates="ai_conversations")

    def __repr__(self):
        return f"<LoanAIConversation Loan={self.loan_id} Role={self.user_role}>"


# =========================================================
# 🧩 AI Audit Log — tracks AI actions and system events
# =========================================================
class AIAuditLog(db.Model):
    __tablename__ = "ai_audit_log"

    id = db.Column(db.Integer, primary_key=True)
    module = db.Column(db.String(100))        # e.g. borrower_ai, processor_ai
    action = db.Column(db.String(100))        # e.g. "generate_summary", "risk_analysis"
    details = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"), nullable=True)

    # === 🔥 New Shared Insight Fields ===
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"), nullable=True)
    context = db.Column(db.String(100), nullable=True)   # e.g. "borrower_dashboard", "crm_view_lead"
    role_view = db.Column(db.String(50), nullable=True)  # e.g. "borrower", "crm", "processor"

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AIAuditLog {self.module}:{self.action}>"

# =========================================================
# 📊 AI Summary — stores generated analytics or summaries
# =========================================================
# LoanMVP/models/ai_models.py

class LoanOfficerAISummary(db.Model):
    __tablename__ = "loan_officer_ai_summary"

    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"))
    officer_id = db.Column(db.Integer, db.ForeignKey("loan_officer_profile.id"))
    summary_text = db.Column(db.Text)
    confidence_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ✅ Correct relationship name
    loan = db.relationship("LoanApplication", back_populates="ai_summary_record")
    loan_officer = db.relationship("LoanOfficerProfile", back_populates="ai_summaries")

    def __repr__(self):
        return f"<LoanOfficerAISummary Loan={self.loan_id}>"


    def __repr__(self):
        return f"<LoanOfficerAISummary loan={self.loan_id}>"

class AIIntakeSummary(db.Model):
    """Stores AI-generated borrower summaries for Loan Officers."""
    __tablename__ = "ai_intake_summary"

    id = db.Column(db.Integer, primary_key=True)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default="pending")  # pending / reviewed / approved / flagged
    reviewer_notes = db.Column(db.Text, nullable=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    borrower = db.relationship("BorrowerProfile", backref="ai_intake_summaries")
    reviewer = db.relationship("User", backref="ai_reviews", foreign_keys=[reviewer_id])

    def __repr__(self):
        return f"<AIIntakeSummary #{self.id} for Borrower {self.borrower_id}>"

class AIAssistantInteraction(db.Model):
    __tablename__ = "ai_assistant_interactions"

    id = db.Column(db.Integer, primary_key=True)

    # Who is chatting
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    loan_officer_id = db.Column(db.Integer, db.ForeignKey("loan_officer_profile.id"), nullable=True)

    # Context
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"))
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"), nullable=True)

    # Threading
    parent_id = db.Column(db.Integer, db.ForeignKey("ai_assistant_interactions.id"), nullable=True)

    # Chat content
    question = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text)
    context_tag = db.Column(db.String(100))  # e.g., 'general', 'borrower', 'loan'

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    borrower = db.relationship("BorrowerProfile", backref=db.backref("ai_interactions", lazy=True))
    loan = db.relationship("LoanApplication", backref=db.backref("ai_interactions", lazy=True))
    parent = db.relationship("AIAssistantInteraction", remote_side=[id], backref="followups")

    def __repr__(self):
        return f"<AIInteraction {self.id} LO={self.loan_officer_id} Borrower={self.borrower_profile_id} Loan={self.loan_id}>"