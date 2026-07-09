from datetime import datetime
from LoanMVP.extensions import db


# ====================================
# 🧍 Loan Officer Profile
# ====================================
class LoanOfficerProfile(db.Model):
    __tablename__ = "loan_officer_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    nmls = db.Column(db.String(20), nullable=True)
    region = db.Column(db.String(100))
    specialization = db.Column(db.String(150))
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    signature_image = db.Column(db.String(255), nullable=True)

    # State MLO licensing -- comma-separated state codes (e.g. "FL,GA,TX").
    # Self-reported by whoever fills the form; license_verified only means a
    # company/Ravlo admin has reviewed and confirmed it, not that Ravlo has
    # independently checked the NMLS registry.
    licensed_states = db.Column(db.String(255), nullable=True)
    license_verified = db.Column(db.Boolean, default=False, nullable=False)
    license_verified_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    license_verified_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship("User", back_populates="loan_officer_profile", foreign_keys=[user_id])
    license_verifier = db.relationship("User", foreign_keys=[license_verified_by])
    loans = db.relationship("LoanApplication", back_populates="loan_officer", cascade="all, delete-orphan")
    ai_summaries = db.relationship("LoanOfficerAISummary", back_populates="loan_officer", cascade="all, delete-orphan")
    analytics = db.relationship("LoanOfficerAnalytics", back_populates="loan_officer", cascade="all, delete-orphan")
    portfolio = db.relationship("LoanOfficerPortfolio", back_populates="loan_officer", cascade="all, delete-orphan")
    loan_intakes = db.relationship("LoanIntakeSession", back_populates="assigned_officer", cascade="all, delete-orphan")

    # ✅ Fix: Add reverse link for BorrowerProfile (required by your Borrower model)
    borrowers = db.relationship("BorrowerProfile", back_populates="assigned_officer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LoanOfficerProfile {self.name}>"


# ====================================
# 📊 Performance Analytics
# ====================================
class LoanOfficerAnalytics(db.Model):
    __tablename__ = "loan_officer_analytics"

    id = db.Column(db.Integer, primary_key=True)
    officer_id = db.Column(db.Integer, db.ForeignKey("loan_officer_profile.id"))
    total_loans = db.Column(db.Integer, default=0)
    approved_loans = db.Column(db.Integer, default=0)
    declined_loans = db.Column(db.Integer, default=0)
    active_loans = db.Column(db.Integer, default=0)
    average_processing_time = db.Column(db.Float, default=0.0)
    performance_score = db.Column(db.Float, default=0.0)
    month = db.Column(db.String(15))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    loan_officer = db.relationship("LoanOfficerProfile", back_populates="analytics")

    def __repr__(self):
        return f"<LoanOfficerAnalytics Officer={self.officer_id} Month={self.month}>"


# ====================================
# 💵 Lender Quote
# ====================================
class LenderQuote(db.Model):
    __tablename__ = "lender_quote"

    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"))
    property_id = db.Column(db.Integer, db.ForeignKey("property.id"))
    lender_name = db.Column(db.String(100))
    quote_details = db.Column(db.JSON)
    rate = db.Column(db.Float)
    term_months = db.Column(db.Integer)
    status = db.Column(db.String(50), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    loan_application = db.relationship("LoanApplication", back_populates="lender_quotes")
    property = db.relationship("Property", back_populates="lender_quotes")

    def __repr__(self):
        return f"<LenderQuote {self.lender_name} Loan:{self.loan_id}>"


# ====================================
# 🧾 Loan Officer Portfolio
# ====================================
class LoanOfficerPortfolio(db.Model):
    __tablename__ = "loan_officer_portfolio"

    id = db.Column(db.Integer, primary_key=True)
    officer_id = db.Column(db.Integer, db.ForeignKey("loan_officer_profile.id"))
    total_clients = db.Column(db.Integer, default=0)
    avg_loan_amount = db.Column(db.Numeric(12, 2), default=0.00)
    avg_credit_score = db.Column(db.Integer, default=0)
    avg_closing_time = db.Column(db.Float, default=0.0)
    rating = db.Column(db.Float, default=5.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    loan_officer = db.relationship("LoanOfficerProfile", back_populates="portfolio")

    def __repr__(self):
        return f"<LoanOfficerPortfolio Officer:{self.officer_id}>"

