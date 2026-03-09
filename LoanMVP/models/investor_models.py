# LoanMVP/models/investor_models.py
from datetime import datetime
from LoanMVP.extensions import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class InvestorProfile(db.Model, TimestampMixin):
    __tablename__ = "investor_profile"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        unique=True,
        index=True
    )

    # Basic identity
    full_name = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    address = db.Column(db.String(255))
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    zip_code = db.Column(db.String(20))

    employment_status = db.Column(db.String(100))
    annual_income = db.Column(db.Integer)
    credit_score = db.Column(db.Integer)
    # Preferences
    strategy = db.Column(db.String(50), nullable=True)
    experience_level = db.Column(db.String(30), nullable=True)

    # Buy box
    target_markets = db.Column(db.Text, nullable=True)
    property_types = db.Column(db.Text, nullable=True)
    min_price = db.Column(db.Integer, nullable=True)
    max_price = db.Column(db.Integer, nullable=True)
    min_sqft = db.Column(db.Integer, nullable=True)
    max_sqft = db.Column(db.Integer, nullable=True)

    # Capital + returns
    capital_available = db.Column(db.Integer, nullable=True)
    min_cash_on_cash = db.Column(db.Float, nullable=True)
    min_roi = db.Column(db.Float, nullable=True)

    # Risk + timeline
    timeline_days = db.Column(db.Integer, nullable=True)
    risk_tolerance = db.Column(db.String(30), nullable=True)

    is_verified = db.Column(db.Boolean, default=False, nullable=False)

    # ----------------------------
    # Relationships
    # ----------------------------
    user = db.relationship("User", back_populates="investor_profile", uselist=False)

    investments = db.relationship(
        "Investment",
        back_populates="investor_profile",
        cascade="all, delete-orphan",
        lazy=True
    )

    saved_properties = db.relationship(
        "SavedProperty",
        back_populates="investor_profile",
        cascade="all, delete-orphan",
        lazy=True
    )

    # 🔥 THIS IS THE FIX: LoanApplication expects back_populates="capital_requests"
    capital_requests = db.relationship(
        "LoanApplication",
        back_populates="investor_profile",
        cascade="all, delete-orphan",
        lazy=True
    )

    documents = db.relationship(
        "LoanDocument",
        back_populates="investor_profile",
        cascade="all, delete-orphan",
        lazy=True
    )

    conditions = db.relationship(
        "UnderwritingCondition",
        back_populates="investor_profile",
        cascade="all, delete-orphan",
        lazy=True
    )

    # 🔥 NEW: ConditionRequest expects back_populates="investor_profile"
    condition_requests = db.relationship(
        "ConditionRequest",
        back_populates="investor_profile",
        cascade="all, delete-orphan",
        lazy=True
    )

    esigned_documents = db.relationship(
        "ESignedDocument",   # or the exact model name in document_models.py
         back_populates="investor_profile",
         cascade="all, delete-orphan",
         lazy=True
    )


        
    credit_profiles = db.relationship(
        "CreditProfile",
        back_populates="investor_profile",
        cascade="all, delete-orphan",
        lazy=True
    )

    loan_quotes = db.relationship(
        "LoanQuote",
        back_populates="investor_profile",
        cascade="all, delete-orphan",
        lazy=True
    )

    property_analysis= db.relationship(
        "PropertyAnalysis",
        back_populates="investor_profile",
        cascade="all, delete-orphan",
        lazy=True
    )

    loan_intake_sessions= db.relationship(
        "LoanIntakeSession",
        back_populates="investor_profile",
        cascade="all, delete-orphan",
        lazy=True
    )
     
    document_requests= db.relationship(
        "DocumentRequest",
        back_populates="investor_profile",
        cascade="all, delete-orphan",
        lazy=True
    )

    budgets= db.relationship(
        "ProjectBudget",
        back_populates="investor_profile",
        cascade="all, delete-orphan",
        lazy=True
    )

    ai_conversations= db.relationship(
        "LoanAIConversation",
        back_populates="investor_profile",
        cascade="all, delete-orphan",
        lazy=True
    )

    tasks= db.relationship(
        "Task",
        back_populates="investor_profile",
        cascade="all, delete-orphan",
        lazy=True
    )
    def __repr__(self):
        return f"<InvestorProfile id={self.id} user_id={self.user_id}>"



class Investment(db.Model, TimestampMixin):
    __tablename__ = "investment"

    id = db.Column(db.Integer, primary_key=True)

    investor_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("investor_profile.id"),
        nullable=False,
        index=True
    )

    # Display
    title = db.Column(db.String(160), nullable=True)
    strategy = db.Column(db.String(50), nullable=True)            # flip | rental | brrrr | note | wholesale

    # Property
    property_address = db.Column(db.String(200), nullable=True)
    city = db.Column(db.String(80), nullable=True)
    state = db.Column(db.String(30), nullable=True)
    zipcode = db.Column(db.String(15), nullable=True)

    # Numbers
    purchase_price = db.Column(db.Integer, nullable=True)
    rehab_budget = db.Column(db.Integer, nullable=True)
    arv = db.Column(db.Integer, nullable=True)

    monthly_rent = db.Column(db.Integer, nullable=True)
    monthly_expenses = db.Column(db.Integer, nullable=True)

    # Financing snapshot
    loan_amount = db.Column(db.Integer, nullable=True)
    interest_rate = db.Column(db.Float, nullable=True)
    term_months = db.Column(db.Integer, nullable=True)
    down_payment = db.Column(db.Integer, nullable=True)

    # Status
    status = db.Column(db.String(30), default="pipeline", nullable=False)  # pipeline|active|closed|dead
    stage = db.Column(db.String(50), nullable=True)                        # sourced|UW|rehab|listed|stabilized

    notes = db.Column(db.Text, nullable=True)

    # Optional cached metrics
    projected_profit = db.Column(db.Integer, nullable=True)
    projected_roi = db.Column(db.Float, nullable=True)

    # ----------------------------
    # Relationships (back_populates)
    # ----------------------------
    investor_profile = db.relationship("InvestorProfile", back_populates="investments")

    documents = db.relationship(
        "InvestmentDocument",
        back_populates="investment",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return f"<Investment id={self.id} investor_profile_id={self.investor_profile_id} status={self.status}>"


class InvestmentDocument(db.Model, TimestampMixin):
    __tablename__ = "investment_document"

    id = db.Column(db.Integer, primary_key=True)

    investment_id = db.Column(db.Integer, db.ForeignKey("investment.id"), nullable=False, index=True)

    filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    content_type = db.Column(db.String(120), nullable=True)

    doc_type = db.Column(db.String(80), nullable=True)            # scope|contract|photos|inspection|etc.
    notes = db.Column(db.Text, nullable=True)

    investment = db.relationship("Investment", back_populates="documents")

    def __repr__(self):
        return f"<InvestmentDocument id={self.id} investment_id={self.investment_id}>"

class DealConversation(db.Model):
    __tablename__ = "deal_conversations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    deal_id = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DealMessage(db.Model):
    __tablename__ = "deal_messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("deal_conversations.id"), nullable=False)
    role = db.Column(db.String(50))  # user / assistant / system
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FundingRequest(db.Model):
    __tablename__ = "funding_requests"

    id = db.Column(db.Integer, primary_key=True)

    investor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("deals.id"), nullable=False, index=True)

    requested_amount = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(db.String(50), nullable=False, default="submitted")  # submitted / reviewing / approved / declined

    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    deal = db.relationship("Deal", backref=db.backref("funding_requests", lazy=True))

    def __repr__(self):
        return f"<FundingRequest {self.id} Deal {self.deal_id}>"

class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)

    # Relationship to Deal
    deal_id = db.Column(db.Integer, db.ForeignKey("deals.id"), nullable=False)

    # Core project info
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Renovation / Build Studio fields
    status = db.Column(db.String(50), default="draft")  # draft, planning, active, completed
    arv_estimate = db.Column(db.Float, nullable=True)
    rehab_budget = db.Column(db.Float, nullable=True)
    rehab_level = db.Column(db.String(50), nullable=True)  # light, medium, heavy
    style_preset = db.Column(db.String(100), nullable=True)

    # AI-generated content
    ai_plan = db.Column(db.Text, nullable=True)
    ai_summary = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship back to Deal
    deal = db.relationship("Deal", backref=db.backref("projects", lazy=True))

    def __repr__(self):
        return f"<Project {self.id} - {self.name}>"

