from LoanMVP.extensions import db
from datetime import datetime

class Campaign(db.Model):
    __tablename__ = "campaign"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(50), nullable=False, default="email")  # email, sms, ad, ai
    description = db.Column(db.Text, nullable=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)

    status = db.Column(db.String(30), default="draft")  # draft, active, paused, completed

    # targeting
    audience_type = db.Column(db.String(50), nullable=True)  # e.g. 'borrower', 'lead', 'realtor'
    audience_segment = db.Column(db.String(100), nullable=True)  # e.g. 'High LTV Borrowers'

    # delivery
    channel = db.Column(db.String(50), nullable=True)  # 'email', 'sms', 'phone', 'social'
    message_subject = db.Column(db.String(255), nullable=True)
    message_body = db.Column(db.Text, nullable=True)
    ai_generated = db.Column(db.Boolean, default=False)

    # metrics
    sent_count = db.Column(db.Integer, default=0)
    open_count = db.Column(db.Integer, default=0)
    click_count = db.Column(db.Integer, default=0)
    response_count = db.Column(db.Integer, default=0)
    conversion_count = db.Column(db.Integer, default=0)

    last_run = db.Column(db.DateTime, nullable=True)
    
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_by_user = db.relationship("User", backref="campaigns", lazy=True)  # 👈 optional but useful

    def __repr__(self):
        return f"<Campaign {self.name} - {self.type} - {self.status}>"

class CampaignRecipient(db.Model):
    __tablename__ = "campaign_recipient"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaign.id"), nullable=False)
    lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"), nullable=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(50), default="pending")  # pending, sent, opened, responded
    sent_at = db.Column(db.DateTime, nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<CampaignRecipient {self.email or self.phone} - {self.status}>"



class CampaignMessage(db.Model):
    __tablename__ = "campaign_messages"
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"), nullable=True)
    subject = db.Column(db.String(255))
    body = db.Column(db.Text)
    channel = db.Column(db.String(50), default="email")  # email or sms
    status = db.Column(db.String(50), default="draft")   # draft, sent, scheduled
    scheduled_for = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<CampaignMessage {self.subject or self.body[:30]}>"
