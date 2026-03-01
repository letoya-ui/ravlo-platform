from datetime import datetime
from LoanMVP.extensions import db
from sqlalchemy.dialects import postgresql


# =========================================================
# 👤 BORROWER PROFILE MODEL
# =========================================================
class BorrowerProfile(db.Model):
    __tablename__ = "borrower_profile"

    id = db.Column(db.Integer, primary_key=True)

    # 🔑 Foreign Keys
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", name="fk_borrower_user"), nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id", name="fk_borrower_assigned_to"), nullable=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("lead.id", name="fk_borrower_lead"))
    assigned_officer_id = db.Column(db.Integer, db.ForeignKey("loan_officer_profile.id", name="fk_borrower_officer"))

    # 📋 Borrower Basic Info
    full_name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))

    # 🏠 Address
    address = db.Column(db.String(255))
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    zip = db.Column(db.String(20))

    # 💼 Employment
    employment_status = db.Column(db.String(50))
    employer_name = db.Column(db.String(150))
    employer_phone = db.Column(db.String(50))
    job_title = db.Column(db.String(150))
    years_at_job = db.Column(db.Integer)

    # 💰 Income
    annual_income = db.Column(db.Float)
    income = db.Column(db.Float)
    monthly_income_secondary = db.Column(db.Float)

    # 🏦 Assets & Liabilities
    bank_balance = db.Column(db.Float)
    assets_description = db.Column(db.Text)
    liabilities_description = db.Column(db.Text)

    # 🏚️ Housing
    housing_status = db.Column(db.String(50))   # rent / own / other
    monthly_housing_payment = db.Column(db.Float)

    # 🧩 Key 1003 Personal Info
    dob = db.Column(db.Date)
    ssn = db.Column(db.String(20))
    citizenship = db.Column(db.String(50))
    marital_status = db.Column(db.String(50))
    dependents = db.Column(db.Integer)

    # 🏠 Real Estate Owned (JSON)
    reo_properties = db.Column(postgresql.JSONB)

    # ⚠️ Declarations (JSON)
    declarations_flags = db.Column(postgresql.JSONB)

    # 📄 Loan Info (legacy)
    credit_score = db.Column(db.Integer)
    loan_type = db.Column(db.String(50), nullable=True)

    # 🕒 Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    profile_pic = db.Column(db.String(255), nullable=True)
    company = db.Column(db.String(120), nullable=True)
    subscription_plan = db.Column(db.String(20), default="Free")
    has_seen_dashboard_tour = db.Column(db.Boolean, default=False)
    email_notifications = db.Column(db.Boolean, default=True)
    sms_notifications = db.Column(db.Boolean, default=False)
    
    # 🔗 Relationships
    user = db.relationship("User", back_populates="borrower_profile", foreign_keys=[user_id])
    assigned_user = db.relationship("User", backref="assigned_borrowers", foreign_keys=[assigned_to])
    assigned_officer = db.relationship("LoanOfficerProfile", back_populates="borrowers")

    # 📎 Related Entities
    loans = db.relationship("LoanApplication", back_populates="borrower_profile", cascade="all, delete-orphan")
    credit_profiles = db.relationship("CreditProfile", back_populates="borrower_profile", cascade="all, delete-orphan")
    loan_quotes = db.relationship("LoanQuote", back_populates="borrower_profile", cascade="all, delete-orphan")
    property_analyses = db.relationship("PropertyAnalysis", back_populates="borrower_profile", cascade="all, delete-orphan")
    documents = db.relationship("LoanDocument", back_populates="borrower_profile", cascade="all, delete-orphan")
    loan_intake_sessions = db.relationship("LoanIntakeSession", back_populates="borrower")
    underwriting_conditions = db.relationship("UnderwritingCondition", back_populates="borrower_profile", cascade="all, delete-orphan")
    condition_requests = db.relationship("ConditionRequest", back_populates="borrower_profile", cascade="all, delete-orphan")
    document_requests = db.relationship("DocumentRequest", back_populates="borrower", cascade="all, delete-orphan")
    budgets = db.relationship("ProjectBudget", back_populates="borrower", cascade="all, delete-orphan")
    ai_conversations = db.relationship("LoanAIConversation", back_populates="borrower", cascade="all, delete-orphan")
    tasks = db.relationship("Task", back_populates="borrower", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BorrowerProfile {self.full_name}>"


# =========================================================
# 🏦 LOAN APPLICATION MODEL
# =========================================================
class LoanApplication(db.Model):
    __tablename__ = "loan_application"

    id = db.Column(db.Integer, primary_key=True)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id", name="fk_loanapp_borrower"))
    loan_officer_id = db.Column(db.Integer, db.ForeignKey("loan_officer_profile.id", name="fk_loanapp_officer"))
    processor_id = db.Column(db.Integer, db.ForeignKey("processor_profile.id", name="fk_loanapp_processor"))
    underwriter_id = db.Column(db.Integer, db.ForeignKey("underwriter_profile.id", name="fk_loanapp_underwriter"))
    property_id = db.Column(db.Integer, db.ForeignKey("property.id", name="fk_loanapp_property"))

    # --- Core Loan Data ---
    lender_name = db.Column(db.String(120))
    amount = db.Column(db.Float)
    loan_type = db.Column(db.String(50))
    term_months = db.Column(db.Integer)
    rate = db.Column(db.Float)
    ltv = db.Column(db.Float)
    property_value = db.Column(db.Float)
    property_address = db.Column(db.String(255))
    description = db.Column(db.String(255))
    ai_summary = db.Column(db.Text)
    risk_score = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(50), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    is_active = db.Column(db.Boolean, default=True)
    processor_notes = db.Column(db.Text, nullable=True)
    risk_level = db.Column(db.String(50), default="Medium")
    ltv_ratio = db.Column(db.Float, nullable=True)
    decision_notes = db.Column(db.Text, nullable=True)
    decision_date = db.Column(db.DateTime, nullable=True)
    monthly_housing_payment = db.Column(db.Float, nullable=True)
    front_end_dti = db.Column(db.Float, nullable=True)
    back_end_dti = db.Column(db.Float, nullable=True)
    monthly_debt_total = db.Column(db.Float, nullable=True)
    progress_percent = db.Column(db.Integer, default=0)
    milestone_stage = db.Column(db.String(50), default="Application Started")


    

    # --- Relationships ---
    borrower_profile = db.relationship("BorrowerProfile", back_populates="loans")
    loan_officer = db.relationship("LoanOfficerProfile", back_populates="loans")
    processor = db.relationship("ProcessorProfile", back_populates="loans")
    underwriter = db.relationship("UnderwriterProfile", backref="loan_applications")
    property = db.relationship("Property", back_populates="loan_applications")
    tasks = db.relationship("Task", back_populates="loan", cascade="all, delete-orphan")

    # --- Related Entities ---
    loan_quotes = db.relationship("LoanQuote", back_populates="loan_application", cascade="all, delete-orphan")
    lender_quotes = db.relationship("LenderQuote", back_populates="loan_application", cascade="all, delete-orphan")
    credit_profiles = db.relationship("CreditProfile", back_populates="loan_application", cascade="all, delete-orphan")
    property_analyses = db.relationship("PropertyAnalysis", back_populates="loan_application", cascade="all, delete-orphan")
    loan_documents = db.relationship("LoanDocument", back_populates="loan_application", cascade="all, delete-orphan")
    underwriting_conditions = db.relationship("UnderwritingCondition", back_populates="loan", cascade="all, delete-orphan")
    condition_requests = db.relationship("ConditionRequest", back_populates="loan", cascade="all, delete-orphan")
    ai_summary_record = db.relationship("LoanOfficerAISummary", back_populates="loan", uselist=False)
    ai_conversations = db.relationship("LoanAIConversation", back_populates="loan", cascade="all, delete-orphan")
    document_requests = db.relationship("DocumentRequest", back_populates="loan", cascade="all, delete-orphan")
    project_budgets = db.relationship(
        "ProjectBudget",
        back_populates="loan_application",
        cascade="all, delete-orphan"
    )
    scenarios = db.relationship(
        "LoanScenario",
         back_populates="loan",
         cascade="all, delete-orphan"
    )

    def calculate_ltv(self):
        """Calculate Loan-to-Value Ratio."""
        if self.amount and self.property_value:
            return round((self.amount / self.property_value) * 100, 2)
        return None


    def calculate_dti(self, borrower, credit_report=None):
        """Calculate both front-end and back-end DTI ratios."""
        income = float(borrower.income or 0)
        secondary_income = float(getattr(borrower, "monthly_income_secondary", 0) or 0)
        total_income = income + secondary_income

        housing_payment = float(self.monthly_housing_payment or 0)
        monthly_debts = float(
            credit_report.monthly_debt_total if credit_report else 0
        )

        if total_income > 0:
            self.front_end_dti = round((housing_payment / total_income) * 100, 2)
            self.back_end_dti = round(((housing_payment + monthly_debts) / total_income) * 100, 2)
        else:
            self.front_end_dti = None
            self.back_end_dti = None

        self.monthly_debt_total = monthly_debts

        db.session.commit()

        return self.front_end_dti, self.back_end_dti
   
    def calculate_risk_score(self):
        """Lightweight demo: derive a risk score from credit score + LTV."""
        credit = self.borrower_profile.credit_profile if self.borrower_profile else None
        credit_score = credit.score if credit else 650
        ltv = getattr(self, "ltv_ratio", 70)
        score = max(0.1, min(1.0, (100 - credit_score / 10 + ltv / 100)))
        return round(score / 10, 2)

    def __repr__(self):
        return f"<LoanApplication ID={self.id} Borrower={self.borrower_profile_id} Status={self.status}>"

class LoanNotification(db.Model):
    __tablename__ = "loan_notification"

    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"), nullable=False)
    borrower_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"))
    role = db.Column(db.String(50))  # "borrower", "processor", "underwriter", "admin"
    message = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    channel = db.Column(db.String(20))  # sms / email / inapp
    title = db.Column(db.String(255))
    message = db.Column(db.String(800))

    loan = db.relationship("LoanApplication", backref="notifications")
    borrower = db.relationship("BorrowerProfile", backref="notifications")

    def to_dict(self):
        return {
            "id": self.id,
            "loan_id": self.loan_id,
            "role": self.role,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "is_read": self.is_read,
        }

# =========================================================
# 💰 LOAN QUOTE MODEL
# =========================================================
class LoanQuote(db.Model):
    __tablename__ = "loan_quote"

    id = db.Column(db.Integer, primary_key=True)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id", name="fk_quote_borrower"))
    loan_application_id = db.Column(db.Integer, db.ForeignKey("loan_application.id", name="fk_quote_loanapp"))

    lender_name = db.Column(db.String(120))
    rate = db.Column(db.Float)
    max_ltv = db.Column(db.Float)
    term_months = db.Column(db.Integer)
    loan_amount = db.Column(db.Float)
    loan_type = db.Column(db.String(120))
    property_address = db.Column(db.String(255))
    property_type = db.Column(db.String(120))
    purchase_price = db.Column(db.Float)
    purchase_date = db.Column(db.String(120))
    as_is_value = db.Column(db.Float)
    after_repair_value = db.Column(db.Float)
    fico_score = db.Column(db.Integer)
    loan_category = db.Column(db.String(50))
    construction_budget = db.Column(db.Float)
    capex_amount = db.Column(db.Float)
    experience = db.Column(db.String(255))
    requested_terms = db.Column(db.Text)
    status = db.Column(db.String(50), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    photos = db.Column(db.String(255))
    response_json = db.Column(db.Text)
    selected = db.Column(db.Boolean, default=False)
    documents_uploaded = db.Column(db.Boolean, default=False)
    deal_type = db.Column(db.String(50))
    data = db.Column(db.JSON)
    ai_suggestion = db.Column(db.Text)

    assigned_officer_id = db.Column(db.Integer, db.ForeignKey("loan_officer_profile.id", name="fk_quote_officer"))
    assigned_underwriter_id = db.Column(db.Integer, db.ForeignKey("underwriter_profile.id", name="fk_quote_underwriter"))

    borrower_profile = db.relationship("BorrowerProfile", back_populates="loan_quotes")
    loan_application = db.relationship("LoanApplication", back_populates="loan_quotes", foreign_keys=[loan_application_id])

    def __repr__(self):
        return f"<LoanQuote ID={self.id} Borrower={self.borrower_profile_id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "borrower_profile_id": self.borrower_profile_id,
            "loan_type": self.loan_type,
            "property_address": self.property_address,
            "loan_amount": self.loan_amount,
            "deal_type": self.deal_type,
            "status": self.status,
            "ai_suggestion": self.ai_suggestion,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# =========================================================
# 🧩 LOAN INTAKE SESSION MODEL
# =========================================================
class LoanIntakeSession(db.Model):
    __tablename__ = "loan_intake_session"

    id = db.Column(db.Integer, primary_key=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"))
    assigned_officer_id = db.Column(db.Integer, db.ForeignKey("loan_officer_profile.id"))
    status = db.Column(db.String(50), default="in_progress")
    data = db.Column(db.JSON, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    borrower = db.relationship("BorrowerProfile", back_populates="loan_intake_sessions")
    assigned_officer = db.relationship("LoanOfficerProfile", back_populates="loan_intakes")

    def __repr__(self):
        return f"<LoanIntakeSession Borrower={self.borrower_id} Status={self.status}>"


# =========================================================
# 📊 CREDIT PROFILE MODEL
# =========================================================
class CreditProfile(db.Model):
    __tablename__ = "credit_profile"

    id = db.Column(db.Integer, primary_key=True)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"))
    loan_app_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"))
    credit_score = db.Column(db.Integer)
    report_date = db.Column(db.DateTime, default=datetime.utcnow)
    score = db.Column(db.Integer)
    report_json = db.Column(db.Text)
    pulled_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50))
    public_records = db.Column(db.Integer, default=0)
    delinquencies = db.Column(db.Integer)
    total_accounts = db.Column(db.Integer)
    total_debt = db.Column(db.Numeric(12, 2), default=0)
    pulled_at = db.Column(db.DateTime, default=datetime.utcnow)

    borrower_profile = db.relationship("BorrowerProfile", back_populates="credit_profiles")
    loan_application = db.relationship("LoanApplication", back_populates="credit_profiles")

    def __repr__(self):
        return f"<CreditProfile Borrower={self.borrower_profile_id} Score={self.credit_score}>"

class Upload(db.Model):
    __tablename__ = "upload"

    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(100), nullable=True)  # pdf, image, docx, etc.
    category = db.Column(db.String(100), nullable=True)   # income, id, property, credit, etc.
    size_kb = db.Column(db.Float, nullable=True)

    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=True)
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"), nullable=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Status and review workflow
    status = db.Column(db.String(30), default="pending")  # pending, verified, rejected
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_notes = db.Column(db.Text, nullable=True)

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    borrower_profile = db.relationship("BorrowerProfile", backref="uploads", lazy=True)
    loan_application = db.relationship("LoanApplication", backref="uploads", lazy=True)
    uploaded_by_user = db.relationship("User", foreign_keys=[uploaded_by_id])
    reviewed_by_user = db.relationship("User", foreign_keys=[reviewed_by_id])

    def __repr__(self):
        return f"<Upload {self.file_name} [{self.status}]>"

class LoanStatusEvent(db.Model):
    __tablename__ = "loan_status_event"

    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(
        db.Integer,
        db.ForeignKey("loan_application.id", name="fk_status_loan")
    )
    event_name = db.Column(db.String(120))
    description = db.Column(db.String(400))
    status = db.Column(db.String(50), default="completed")  # completed | pending
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    loan = db.relationship("LoanApplication", backref="status_events")

class DocumentEvent(db.Model):
    __tablename__ = "document_event"

    id = db.Column(db.Integer, primary_key=True)

    loan_id = db.Column(
        db.Integer,
        db.ForeignKey("loan_application.id"),
        nullable=False
    )
    borrower_id = db.Column(
        db.Integer,
        db.ForeignKey("borrower_profile.id"),
        nullable=False
    )

    document_name = db.Column(db.String(200))
    event_type = db.Column(db.String(50))  
    # values: "opened", "viewed", "downloaded", "emailed"

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user_agent = db.Column(db.String(300), nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)

    loan = db.relationship("LoanApplication", backref="doc_events")
    borrower = db.relationship("BorrowerProfile", backref="doc_events")

class LoanScenario(db.Model):
    __tablename__ = "loan_scenario"

    id = db.Column(db.Integer, primary_key=True)

    loan_id = db.Column(
        db.Integer,
        db.ForeignKey("loan_application.id", name="fk_scenario_loan")
    )

    # Scenario Details
    title = db.Column(db.String(120))     # "FHA Option", "Conv 20%", etc.
    amount = db.Column(db.Float)
    rate = db.Column(db.Float)
    term_months = db.Column(db.Integer)
    loan_type = db.Column(db.String(50))
    down_payment = db.Column(db.Float)
    closing_costs = db.Column(db.Float)
    monthly_payment = db.Column(db.Float)

    # Optional fields

    dti = db.Column(db.Float)
    ltv = db.Column(db.Float)
    apr = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=db.func.now())

    # Relationship
    loan = db.relationship("LoanApplication", back_populates="scenarios")

    def __repr__(self):
        return f"<LoanScenario {self.title} Loan={self.loan_id}>"


from LoanMVP.models.ai_models import LoanAIConversation

