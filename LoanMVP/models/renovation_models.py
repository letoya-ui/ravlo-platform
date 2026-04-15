# LoanMVP/models/renovation_models.py
from datetime import datetime
from LoanMVP.extensions import db

class RenovationMockup(db.Model):
    __tablename__ = "renovation_mockup"
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    borrower_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=True)
    investor_profile_id = db.Column(db.Integer, db.ForeignKey("investor_profile.id"), nullable=True)
    property_id = db.Column(db.String(64), nullable=True)  # your "property_id" string
    saved_property_id = db.Column(db.Integer, db.ForeignKey("saved_properties.id"), nullable=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("deals.id"), nullable=True)

    before_url = db.Column(db.Text, nullable=False)
    after_url = db.Column(db.Text, nullable=False)

    style_prompt = db.Column(db.Text, nullable=True)
    style_preset = db.Column(db.String(40), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RehabJob(db.Model):
    __tablename__ = "rehab_jobs"

    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    plan_url = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(20), default="pending")  
    # pending → processing → complete → failed

    result_plan = db.Column(db.Text)
    result_cost_low = db.Column(db.Integer)
    result_cost_high = db.Column(db.Integer)
    result_arv = db.Column(db.Integer)
    result_images = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BuildProject(db.Model):
    __tablename__ = "build_projects"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    project_name = db.Column(db.String(255))
    property_type = db.Column(db.String(100))
    description = db.Column(db.Text)
    lot_size = db.Column(db.String(100))
    zoning = db.Column(db.String(100))
    location = db.Column(db.String(255))
    notes = db.Column(db.Text)

    land_image_path = db.Column(db.String(500))
    concept_render_url = db.Column(db.String(500))
    blueprint_url = db.Column(db.String(500))
    site_plan_url = db.Column(db.String(500))
    presentation_url = db.Column(db.String(500))
    development_type = db.Column(db.String(64))  # condos, townhomes, apartments, single_family_subdivision
    exterior_url = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    budgets = db.relationship(
        "ProjectBudget",
        back_populates="build_project",
        cascade="all, delete-orphan",
        lazy=True,
    )
