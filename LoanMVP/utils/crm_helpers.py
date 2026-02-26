import random
from LoanMVP.extensions import db
from LoanMVP.models.crm_models import Lead
from LoanMVP.models.ai_models import AIAuditLog
from datetime import datetime

def score_lead(lead_name):
    """Generate an AI-style lead score (demo heuristic)."""
    base_score = random.randint(50, 100)
    adjustment = -5 if "test" in lead_name.lower() else 0
    return max(0, min(base_score + adjustment, 100))

def add_lead(name, email):
    """Adds new lead into the main SQLAlchemy database."""
    score = score_lead(name)
    new_lead = Lead(name=name, email=email, score=score)
    db.session.add(new_lead)
    db.session.commit()

    # Log the addition in AI Audit
    log_ai_lead_action(
        module="crm_helper",
        action="add_lead",
        details=f"Added lead {name} ({email}) with score {score}"
    )
    return new_lead

def fetch_leads():
    """Fetch all leads from main CRM database."""
    return Lead.query.order_by(Lead.created_at.desc()).all()

def log_ai_lead_action(module, action, details):
    """Record helper activity into AI audit log."""
    log = AIAuditLog(
        module=module,
        action=action,
        details=details,
        created_at=datetime.utcnow()
    )
    db.session.add(log)
    db.session.commit()
