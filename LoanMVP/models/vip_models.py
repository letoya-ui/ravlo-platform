from LoanMVP.extensions import db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship


# ---------------------------------------------------------
# BASE MODEL
# ---------------------------------------------------------
class VIPBaseModel(db.Model):
    __abstract__ = True

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------
# PROFILE (CORE)
# ---------------------------------------------------------
class VIPProfile(VIPBaseModel):
    __tablename__ = "vip_profiles"

    user_id = Column(Integer, nullable=False)

    role_type = Column(String(50), nullable=False, default="realtor")

    business_name = Column(String(255), nullable=True)
    display_name = Column(String(255), nullable=True)

    # Relationships
    contacts = relationship("VIPContact", lazy=True)
    interactions = relationship("VIPInteraction", lazy=True)
    income = relationship("VIPIncome", lazy=True)
    expenses = relationship("VIPExpense", lazy=True)

    suggestions = relationship("VIPAssistantSuggestion", lazy=True)
    actions = relationship("VIPAction", lazy=True)
    notifications = relationship("VIPNotification", lazy=True)

    # ✅ DESIGN STUDIO (correct place)
    design_projects = relationship("VIPDesignProject", lazy=True)

    def __repr__(self):
        return f"<VIPProfile {self.id} - {self.role_type}>"


# ---------------------------------------------------------
# CONTACTS
# ---------------------------------------------------------
class VIPContact(VIPBaseModel):
    __tablename__ = "vip_contacts"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)

    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    role = Column(String(50), nullable=True)
    tags = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)


# ---------------------------------------------------------
# INTERACTIONS
# ---------------------------------------------------------
class VIPInteraction(VIPBaseModel):
    __tablename__ = "vip_interactions"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("vip_contacts.id"), nullable=True)

    interaction_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=True)
    due_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------
# INCOME (NO DESIGN RELATIONSHIP HERE ❌)
# ---------------------------------------------------------
class VIPIncome(VIPBaseModel):
    __tablename__ = "vip_income"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)

    amount = Column(Integer, nullable=False)
    source = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)


# ---------------------------------------------------------
# EXPENSES
# ---------------------------------------------------------
class VIPExpense(VIPBaseModel):
    __tablename__ = "vip_expenses"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)

    amount = Column(Integer, nullable=False)
    category = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)


# ---------------------------------------------------------
# AI / AUTOMATION
# ---------------------------------------------------------
class VIPAssistantSuggestion(VIPBaseModel):
    __tablename__ = "vip_suggestions"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)

    suggestion_type = Column(String(100))
    content = Column(Text)
    status = Column(String(50), default="pending")


class VIPAction(VIPBaseModel):
    __tablename__ = "vip_actions"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)

    action_type = Column(String(100))
    payload = Column(Text)
    status = Column(String(50), default="pending")


class VIPNotification(VIPBaseModel):
    __tablename__ = "vip_notifications"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)

    title = Column(String(255))
    body = Column(Text)
    status = Column(String(50), default="unread")


# ---------------------------------------------------------
# DESIGN STUDIO
# ---------------------------------------------------------
class VIPDesignProject(VIPBaseModel):
    __tablename__ = "vip_design_projects"

    vip_profile_id = Column(Integer, ForeignKey("vip_profiles.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("vip_contacts.id"), nullable=True)

    title = Column(String(255), nullable=False)
    status = Column(String(50), default="draft")

    source_file = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    annotations = relationship(
        "VIPDesignAnnotation",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def __repr__(self):
        return f"<VIPDesignProject {self.id} - {self.title}>"


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

    # Relationship (paired correctly)
    project = relationship("VIPDesignProject", back_populates="annotations")

    def __repr__(self):
        return f"<VIPDesignAnnotation {self.id}>"