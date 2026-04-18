from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from LoanMVP.extensions import db


# ---------------------------------------------------------
# BASE MODEL
# ---------------------------------------------------------
class VIPBaseModel(db.Model):
    __abstract__ = True

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------
# PROFILE
# ---------------------------------------------------------
class VIPProfile(VIPBaseModel):
    __tablename__ = "vip_profiles"

    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)

    display_name = Column(String(255), nullable=False)
    business_name = Column(String(255), nullable=True)
    dashboard_title = Column(String(255), nullable=True)

    role_type = Column(String(50), nullable=False, default="realtor")
    assistant_name = Column(String(100), nullable=True, default="Ravlo")

    headline = Column(String(255), nullable=True)
    bio = Column(Text, nullable=True)
    service_area = Column(String(255), nullable=True)
    specialties = Column(String(255), nullable=True)

    marketplace_enabled = Column(String(10), nullable=False, default="no")
    public_slug = Column(String(255), nullable=True)

    enabled_modules = Column(Text, nullable=True)

    brand_color = Column(String(50), nullable=True)
    logo_url = Column(String(500), nullable=True)
    profile_image_url = Column(String(500), nullable=True)
    cover_image_url = Column(String(500), nullable=True)

    contacts = relationship("VIPContact", back_populates="vip_profile", lazy=True)
    interactions = relationship("VIPInteraction", back_populates="vip_profile", lazy=True)
    expenses = relationship("VIPExpense", back_populates="vip_profile", lazy=True)
    incomes = relationship("VIPIncome", back_populates="vip_profile", lazy=True)
    budgets = relationship("VIPBudget", back_populates="vip_profile", lazy=True)
    suggestions = relationship("VIPAssistantSuggestion", back_populates="vip_profile", lazy=True)
    actions = relationship("VIPAssistantAction", back_populates="vip_profile", lazy=True)
    notifications = relationship("VIPNotification", back_populates="vip_profile", lazy=True)

    # ✅ DESIGN STUDIO
    design_projects = relationship("VIPDesignProject", lazy=True)

    def __repr__(self):
        return f"<VIPProfile {self.id} - {self.display_name}>"


# ---------------------------------------------------------
# CONTACTS
# ---------------------------------------------------------
class VIPContact(VIPBaseModel):
    __tablename__ = "vip_contacts"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)

    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)

    contact_type = Column(String(50), nullable=True)
    tags = Column(String(255), nullable=True)
    pipeline_stage = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)

    vip_profile = relationship("VIPProfile", back_populates="contacts")
    interactions = relationship("VIPInteraction", back_populates="contact", lazy=True)

    # ✅ NOW VALID (because we added FK in project)
    design_projects = relationship("VIPDesignProject", back_populates="contact", lazy=True)

    def __repr__(self):
        return f"<VIPContact {self.id} - {self.name}>"


# ---------------------------------------------------------
# INTERACTIONS
# ---------------------------------------------------------
class VIPInteraction(VIPBaseModel):
    __tablename__ = "vip_interactions"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("vip_contacts.id"), nullable=True)

    interaction_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    meta = Column(String(255), nullable=True)
    due_at = Column(DateTime, nullable=True)

    vip_profile = relationship("VIPProfile", back_populates="interactions")
    contact = relationship("VIPContact", back_populates="interactions")


# ---------------------------------------------------------
# EXPENSES
# ---------------------------------------------------------
class VIPExpense(VIPBaseModel):
    __tablename__ = "vip_expenses"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("vip_contacts.id"), nullable=True)

    category = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)

    amount = Column(Integer, nullable=True)
    miles = Column(Integer, nullable=True)

    expense_date = Column(DateTime, nullable=True)
    source = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)

    vip_profile = relationship("VIPProfile", back_populates="expenses")
    contact = relationship("VIPContact")


# ---------------------------------------------------------
# INCOME (NO DESIGN RELATIONSHIP ❌)
# ---------------------------------------------------------
class VIPIncome(VIPBaseModel):
    __tablename__ = "vip_income"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("vip_contacts.id"), nullable=True)

    category = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)

    amount = Column(Integer, nullable=False)
    income_date = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    notes = Column(Text, nullable=True)

    vip_profile = relationship("VIPProfile", back_populates="incomes")
    contact = relationship("VIPContact")


# ---------------------------------------------------------
# BUDGETS
# ---------------------------------------------------------
class VIPBudget(VIPBaseModel):
    __tablename__ = "vip_budgets"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)

    category = Column(String(50), nullable=False)
    budget_amount = Column(Integer, nullable=False)
    period_type = Column(String(20), nullable=False)
    notes = Column(Text, nullable=True)

    vip_profile = relationship("VIPProfile", back_populates="budgets")


# ---------------------------------------------------------
# AI
# ---------------------------------------------------------
class VIPAssistantSuggestion(VIPBaseModel):
    __tablename__ = "vip_assistant_suggestions"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)

    suggestion_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="pending")

    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)

    contact_id = Column(Integer, ForeignKey("vip_contacts.id"), nullable=True)

    vip_profile = relationship("VIPProfile", back_populates="suggestions")
    contact = relationship("VIPContact")


class VIPAssistantAction(VIPBaseModel):
    __tablename__ = "vip_assistant_actions"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)

    action_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="draft")

    contact_id = Column(Integer, ForeignKey("vip_contacts.id"), nullable=True)

    subject = Column(String(255), nullable=True)
    content = Column(Text, nullable=True)

    vip_profile = relationship("VIPProfile", back_populates="actions")
    contact = relationship("VIPContact")


class VIPNotification(VIPBaseModel):
    __tablename__ = "vip_notifications"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)

    notification_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)

    is_read = Column(String(10), nullable=False, default="no")
    action_url = Column(String(255), nullable=True)
    scheduled_for = Column(DateTime, nullable=True)

    vip_profile = relationship("VIPProfile", back_populates="notifications")


# ---------------------------------------------------------
# DESIGN STUDIO
# ---------------------------------------------------------
class VIPDesignProject(VIPBaseModel):
    __tablename__ = "vip_design_projects"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("vip_contacts.id"), nullable=True)

    title = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="draft")

    source_file = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    vip_profile = relationship("VIPProfile")
    contact = relationship("VIPContact", back_populates="design_projects")

    annotations = relationship(
        "VIPDesignAnnotation",
        back_populates="project",
        lazy=True,
        cascade="all, delete-orphan",
    )


class VIPDesignAnnotation(VIPBaseModel):
    __tablename__ = "vip_design_annotations"

    project_id = Column(Integer, ForeignKey("vip_design_projects.id"), nullable=False)

    annotation_type = Column(String(50), nullable=True)
    action_type = Column(String(50), nullable=True)

    label = Column(String(255), nullable=True)
    body = Column(Text, nullable=True)

    x = Column(Integer, nullable=True)
    y = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    project = relationship("VIPDesignProject", back_populates="annotations")