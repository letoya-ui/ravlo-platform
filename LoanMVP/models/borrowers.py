# LoanMVP/models/borrowers.py
from datetime import datetime
from LoanMVP.extensions import db


# ====================================
# 🧮 PROPERTY ANALYSIS (Borrower Tool)
# ====================================
class PropertyAnalysis(db.Model):
    __tablename__ = "property_analysis"

    id = db.Column(db.Integer, primary_key=True)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=False)
    investor_profile_id = db.Column( db.Integer, db.ForeignKey("investor_profile.id"), nullable=True )
    loan_app_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"), nullable=True)
    property_id = db.Column(db.Integer, db.ForeignKey("property.id"), nullable=True)

    property_name = db.Column(db.String(255)) 
    property_value = db.Column(db.Float)
    property_type = db.Column(db.String(120))
    address = db.Column(db.String(255))
    arv = db.Column(db.Float)  # After Repair Value
    rehab_cost = db.Column(db.Float)
    purchase_price = db.Column(db.Float)
    ltv = db.Column(db.Float)
    cap_rate = db.Column(db.Float)
    cash_flow = db.Column(db.Float)
    noi = db.Column(db.Float)
    notes = db.Column(db.Text)
    profit_margin = db.Column(db.Float)
    expenses = db.Column(db.Float)
    rental_income = db.Column(db.Float)
    roi = db.Column(db.Float)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    borrower_profile = db.relationship("BorrowerProfile", back_populates="property_analyses")
    investor_profile = db.relationship( "InvestorProfile", back_populates="property_analysis")
    loan_application = db.relationship("LoanApplication", back_populates="property_analyses")
    property = db.relationship("Property", back_populates="analyses")

    def __repr__(self):
        return f"<PropertyAnalysis Loan:{self.loan_app_id} Property:{self.property_id}>"



# ====================================
# 💵 PROJECT BUDGET
# ====================================

class ProjectBudget(db.Model):
    __tablename__ = "project_budgets"

    id = db.Column(db.Integer, primary_key=True)

    borrower_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("borrower_profile.id"),
        nullable=True
    )
    investor_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("investor_profile.id"),
        nullable=True
    )
    loan_app_id = db.Column(
        db.Integer,
        db.ForeignKey("loan_application.id"),
        nullable=True
    )
    deal_id = db.Column(
        db.Integer,
        db.ForeignKey("deals.id"),
        nullable=True
    )
    build_project_id = db.Column(
        db.Integer,
        db.ForeignKey("build_projects.id"),
        nullable=True
    )

    budget_type = db.Column(db.String(50), nullable=False, default="rehab")

    name = db.Column(db.String(100), nullable=False)
    project_name = db.Column(db.String(120))

    total_amount = db.Column(db.Numeric(12, 2), nullable=True)
    total_budget = db.Column(db.Numeric(12, 2), nullable=True)

    total_cost = db.Column(db.Float, default=0.0)
    materials_cost = db.Column(db.Float, default=0.0)
    labor_cost = db.Column(db.Float, default=0.0)
    contingency = db.Column(db.Float, default=0.0)
    paid_amount = db.Column(db.Float, default=0.0)

    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    budgets = db.relationship(
        "ProjectBudget",
        back_populates="build_project",
        cascade="all, delete-orphan",
        lazy=True,
    )
    borrower = db.relationship("BorrowerProfile", back_populates="budgets")
    investor_profile = db.relationship("InvestorProfile", back_populates="budgets")
    loan_application = db.relationship("LoanApplication", back_populates="project_budgets")
    deal = db.relationship("Deal", back_populates="budgets")
    build_project = db.relationship("BuildProject", back_populates="budgets")

    expenses = db.relationship(
        "ProjectExpense",
        back_populates="budget",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def __repr__(self):
        return f"<ProjectBudget {self.budget_type} #{self.id} Total:${self.total_cost}>"

        
# ====================================
# 💰 PROJECT EXPENSE
# ====================================
class ProjectExpense(db.Model):
    __tablename__ = "project_expenses"

    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(
        db.Integer,
        db.ForeignKey("project_budgets.id", ondelete="CASCADE"),
        nullable=False
    )

    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)

    vendor = db.Column(db.String(255), nullable=True)

    estimated_amount = db.Column(db.Numeric(12, 2), default=0.00)
    actual_amount = db.Column(db.Numeric(12, 2), default=0.00)
    paid_amount = db.Column(db.Numeric(12, 2), default=0.00)

    status = db.Column(db.String(50), default="planned")
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    budget = db.relationship("ProjectBudget", back_populates="expenses")

    def __repr__(self):
        return f"<ProjectExpense {self.category}: est=${self.estimated_amount} actual=${self.actual_amount}>"
        
# ====================================
# 💳 SUBSCRIPTION PLAN
# ====================================
class SubscriptionPlan(db.Model):
    __tablename__ = "subscription_plan"

    id = db.Column(db.Integer, primary_key=True)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=False)
    investor_profile_id = db.Column( db.Integer, db.ForeignKey("investor_profile.id"), nullable=True )
    
    plan_name = db.Column(db.String(100))
    price = db.Column(db.Float)
    features = db.Column(db.Text)
    status = db.Column(db.String(50), default="Active")
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    borrower_profile = db.relationship("BorrowerProfile", backref="subscription_plans")
    investor_profile = db.relationship( "InvestorProfile", backref="subscription_plans" )
    
    def __repr__(self):
        return f"<SubscriptionPlan {self.plan_name} for Borrower:{self.borrower_id}>"

class BorrowerInteraction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"))
    interaction_type = db.Column(db.String(50))
    question = db.Column(db.Text)
    response = db.Column(db.Text)
    timestamp = db.Column(db.DateTime)
    parent_id = db.Column(db.Integer, db.ForeignKey("borrower_interaction.id"), nullable=True)
    topic = db.Column(db.String(50))  # e.g. "budget", "loan", "documents", "general"

class BorrowerMessage(db.Model):
    __tablename__ = "borrower_message"

    id = db.Column(db.Integer, primary_key=True)

    borrower_id = db.Column(
        db.Integer,
        db.ForeignKey("borrower_profile.id", name="fk_msg_borrower"),
        nullable=False
    )

    sender_type = db.Column(db.String(20))  # borrower | staff | ai
    sender_name = db.Column(db.String(120))

    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    borrower = db.relationship("BorrowerProfile", backref="messages")

class Deal(db.Model):
    __tablename__ = "deals"

    id = db.Column(db.Integer, primary_key=True)

    # owner
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    # profiles
    investor_profile_id = db.Column(db.Integer, db.ForeignKey("investor_profile.id"), nullable=True)

    # property links
    saved_property_id = db.Column(db.Integer, db.ForeignKey("saved_properties.id"), nullable=True)
    property_id = db.Column(db.String(120), index=True)

    # display / identity
    title = db.Column(db.String(255))
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    zip_code = db.Column(db.String(20), nullable=True)

    # strategy
    strategy = db.Column(db.String(32))
    recommended_strategy = db.Column(db.String(50), nullable=True)

    # core numbers
    purchase_price = db.Column(db.Float, default=0)
    arv = db.Column(db.Float, default=0)
    estimated_rent = db.Column(db.Float, default=0)
    rehab_cost = db.Column(db.Float, default=0)
    deal_score = db.Column(db.Integer, nullable=True)

    # flexible storage
    inputs_json = db.Column(db.JSON)
    results_json = db.Column(db.JSON)
    comps_json = db.Column(db.JSON)
    resolved_json = db.Column(db.JSON)
    rehab_scope_json = db.Column(db.JSON, nullable=True)

    # notes / workflow
    notes = db.Column(db.Text)
    status = db.Column(db.String(32), default="active")
    submitted_for_funding = db.Column(db.Boolean, default=False, nullable=False)
    funding_requested_at = db.Column(db.DateTime, nullable=True)

    # public reveal / share
    reveal_public_id = db.Column(db.String(32), unique=True, index=True, nullable=True)
    reveal_is_public = db.Column(db.Boolean, default=False, nullable=False)
    reveal_published_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationships
    user = db.relationship("User", backref=db.backref("deals", lazy=True))
    investor_profile = db.relationship("InvestorProfile", backref="deals")
    budgets = db.relationship(
        "ProjectBudget",
        back_populates="deal",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Deal {self.id} {self.title or self.address or 'Untitled'}>"

    @property
    def total_project_cost(self):
        return (self.purchase_price or 0) + (self.rehab_cost or 0)

    @property
    def estimated_profit(self):
        return (self.arv or 0) - self.total_project_cost

    @property
    def estimated_roi_percent(self):
        total_cost = self.total_project_cost
        if total_cost <= 0:
            return 0
        return round((self.estimated_profit / total_cost) * 100, 2)




class DealShare(db.Model):
    __tablename__ = "deal_shares"

    id = db.Column(db.Integer, primary_key=True)

    borrower_user_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=False)
    investor_profile_id = db.Column(db.Integer, db.ForeignKey("investor_profile.id"), nullable=True)

    loan_officer_user_id = db.Column(db.Integer)
    property_id = db.Column(db.String(120))
    strategy = db.Column(db.String(32))
    title = db.Column(db.String(255))

    results_json = db.Column(db.JSON)
    comps_json = db.Column(db.JSON)
    resolved_json = db.Column(db.JSON)

    note = db.Column(db.Text)
    status = db.Column(db.String(32), default="new")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    opened_at = db.Column(db.DateTime)

    # Relationships
    investor_profile = db.relationship("InvestorProfile", backref="deal_shares")

    def __repr__(self):
        return f"<DealShare id={self.id} property_id={self.property_id} status={self.status}>"
