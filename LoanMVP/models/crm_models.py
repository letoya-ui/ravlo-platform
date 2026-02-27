# LoanMVP/models/crm_models.py
from datetime import datetime, timedelta
from LoanMVP.extensions import db
from sqlalchemy.sql import func

# ====================================
# 📋 LEAD MANAGEMENT
# ====================================
class Lead(db.Model):
    __tablename__ = "lead"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    message = db.Column(db.Text)
    source_id = db.Column(db.Integer, db.ForeignKey("lead_source.id"))
    property_id = db.Column(db.Integer, db.ForeignKey("property.id"))
    assigned_officer_id = db.Column(db.Integer, db.ForeignKey("loan_officer_profile.id"))
    status = db.Column(db.String(50), default="New")
    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    property = db.relationship("Property", backref="leads")
    calls = db.relationship("CallLog", backref="lead", lazy="dynamic")
    source = db.relationship("LeadSource", back_populates="leads")
    assigned_officer = db.relationship("LoanOfficerProfile", backref="leads")
    borrowers = db.relationship("BorrowerProfile", backref="lead", lazy=True)
    # inside class Lead(db.Model):
    loan_quotes = db.relationship(
    "LoanQuote",
    secondary="borrower_profile",
    primaryjoin="Lead.id==BorrowerProfile.lead_id",
    secondaryjoin="BorrowerProfile.id==LoanQuote.borrower_profile_id",
    viewonly=True,
    lazy="dynamic"
)

    def __repr__(self):
        return f"<Lead {self.name} - {self.status}>"


# ====================================
# 🧠 BEHAVIORAL INSIGHTS (AI Analytics)
# ====================================
class BehavioralInsight(db.Model):
    __tablename__ = "behavioral_insights"

    id = db.Column(db.Integer, primary_key=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"))
    officer_id = db.Column(db.Integer, db.ForeignKey("loan_officer_profile.id"), nullable=True)

    # Core metrics
    total_messages = db.Column(db.Integer, default=0)
    avg_response_time = db.Column(db.Float, default=0.0)  # hours
    sentiment_score = db.Column(db.Float, default=0.0)    # -1 → +1
    follow_up_rate = db.Column(db.Float, default=0.0)
    engagement_level = db.Column(db.String(50), default="Low")

    # AI summary + recommendations
    ai_summary = db.Column(db.Text)
    ai_suggestions = db.Column(db.Text)

    # Derived metrics
    conversion_rate = db.Column(db.Float, default=0.0)
    loan_success_score = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    borrower = db.relationship("BorrowerProfile", backref="behavioral_insights")
    officer = db.relationship("LoanOfficerProfile", backref="behavioral_insights")

    def __repr__(self):
        return f"<BehavioralInsight borrower={self.borrower_id} officer={self.officer_id}>"

    def update_metrics(self, total_messages, avg_response_time, sentiment_score, follow_up_rate, conversion_rate):
        """Recalculate AI and engagement metrics dynamically"""
        self.total_messages = total_messages
        self.avg_response_time = avg_response_time
        self.sentiment_score = sentiment_score
        self.follow_up_rate = follow_up_rate
        self.conversion_rate = conversion_rate

        # Weighted success score
        self.loan_success_score = round(
            (follow_up_rate * 0.3)
            + ((1 - avg_response_time / 24) * 0.2)
            + ((sentiment_score + 1) / 2 * 0.2)
            + (conversion_rate * 0.3),
            2,
        )

        if self.loan_success_score >= 0.8:
            self.engagement_level = "High"
        elif self.loan_success_score >= 0.5:
            self.engagement_level = "Moderate"
        else:
            self.engagement_level = "Low"

        db.session.commit()



class Message(db.Model):
    """
    Message model handles all internal communications between users
    (borrowers, loan officers, processors, underwriters, etc.).
    """

    __tablename__ = "message"

    id = db.Column(db.Integer, primary_key=True)

    # 🔗 Core sender/receiver relationship
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # 💬 Message content
    subject = db.Column(db.String(255), nullable=True)
    content = db.Column(db.Text, nullable=False)

    # 🧭 Role context (optional)
    sender_role = db.Column(db.String(50), nullable=True)
    receiver_role = db.Column(db.String(50), nullable=True)

    # 🕒 Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 📌 Flags
    system_generated = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)

    # ===============================
    # 🔗 Relationships
    # ===============================
    sender = db.relationship(
        "User",
        foreign_keys=[sender_id],
        back_populates="messages_sent"
    )
    receiver = db.relationship(
        "User",
        foreign_keys=[receiver_id],
        back_populates="messages_received"
    )

    # ===============================
    # 🧩 Methods
    # ===============================
    def mark_read(self):
        """Mark message as read."""
        self.is_read = True
        db.session.commit()

    def to_dict(self):
        """Return a simple dictionary for JSON APIs or templates."""
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "subject": self.subject,
            "content": self.content,
            "sender_role": self.sender_role,
            "receiver_role": self.receiver_role,
            "timestamp": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "is_read": self.is_read,
        }

    def __repr__(self):
        return f"<Message {self.id} from {self.sender_id} to {self.receiver_id}>"

# ====================================
# 🗒️ CRM NOTE SYSTEM
# ====================================
class CRMNote(db.Model):
    __tablename__ = "crm_note"

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"), nullable=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship("User", back_populates="crm_notes")
    lead = db.relationship("Lead", backref="notes")
    borrower = db.relationship("BorrowerProfile", backref="notes")

    def __repr__(self):
        return f"<CRMNote {self.id} by User:{self.user_id}>"


# ====================================
# 📢 LEAD SOURCE
# ====================================
class LeadSource(db.Model):
    __tablename__ = "lead_source"

    id = db.Column(db.Integer, primary_key=True)
    source_name = db.Column(db.String(100))
    source_type = db.Column(db.String(50))  # e.g., Website, Referral, Ad Campaign
    url = db.Column(db.String(255))
    active = db.Column(db.Boolean, default=True)

    # Relationships
    leads = db.relationship("Lead", back_populates="source")

    def __repr__(self):
        return f"<LeadSource {self.source_name}>"


# ====================================
# 📅 TASK MANAGEMENT
# ====================================
class Task(db.Model):
    __tablename__ = "task"

    id = db.Column(db.Integer, primary_key=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"))
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"))
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    due_date = db.Column(db.Date)
    priority = db.Column(db.String(50), default="Normal")
    status = db.Column(db.String(30), default="Pending")
    completed = db.Column(db.Boolean, default=False) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assigned_user = db.relationship("User", backref="tasks_assigned", lazy=True)
    borrower = db.relationship("BorrowerProfile", back_populates="tasks")
    loan = db.relationship("LoanApplication", back_populates="tasks")

    def __repr__(self):
        return f"<Task {self.description[:25]} - {self.status}>"

class MessageThread(db.Model):
    __tablename__ = "message_threads"
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    recipient_type = db.Column(db.String(50))  # 'lead', 'borrower', 'realtor'
    recipient_id = db.Column(db.Integer)
    message_type = db.Column(db.String(50), default="sms")  # sms, email, internal
    content = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    direction = db.Column(db.String(20), default="outbound")  # inbound/outbound
    status = db.Column(db.String(30), default="sent")  # sent, delivered, read

    def __repr__(self):
        return f"<Msg {self.message_type.upper()} to {self.recipient_type}:{self.recipient_id}>"

# -----------------------------
# 🤝 Partner Model
# -----------------------------


class Partner(db.Model):
    __tablename__ = "partners"

    id = db.Column(db.Integer, primary_key=True)
    # in Partner model:
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, unique=True)
    name = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(120))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    category = db.Column(db.String(100))      # Contractor, Realtor, etc.
    service_area = db.Column(db.String(255))  # e.g. "Tri-State Area"
    active = db.Column(db.Boolean, default=True)
    type = db.Column(db.String(50))  # e.g., "Lender", "Broker", "Realtor", "Vendor"
    website = db.Column(db.String(255))
    status = db.Column(db.String(50), default="Active")
    relationship_level = db.Column(db.String(50))  # e.g., "Gold", "Silver", "Preferred"
    joined_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_contacted = db.Column(db.DateTime)
    last_deal = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text)
    deals = db.Column(db.Integer, default=0)
    volume = db.Column(db.Float, default=0.0)
    rating = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # === Monetization & Resource Center ===
    listing_description = db.Column(db.Text)
    logo_url = db.Column(db.String(255))
    approved = db.Column(db.Boolean, default=False)
    featured = db.Column(db.Boolean, default=False)
    subscription_tier = db.Column(db.String(50), default="Free")  # Free, Featured, Premium

    # 🧩 Fix: datetime.utcnow should be callable (not executed at import)
    paid_until = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(days=30))

    # === Relationships ===
    leads = db.relationship(
        'Lead',
        secondary='partner_lead_link',
        backref=db.backref('partners', lazy='dynamic'),
        lazy='dynamic'
    )

    user = db.relationship("User", backref=db.backref("partner_profile", uselist=False))
    
    # === Utility Methods ===
    def is_active_listing(self):
        """Return True if the partner is active and payment is valid."""
        return self.approved and self.paid_until and self.paid_until >= datetime.utcnow()

    def last_active(self):
        """Return the most recent activity (contact or deal)."""
        return max(filter(None, [self.last_contacted, self.last_deal, self.joined_date]))

    def __repr__(self):
        return f"<Partner {self.name} ({self.type or 'N/A'})>"


# -----------------------------
# 🔗 Partner ↔ Lead Association Table (FIXED)
# -----------------------------
partner_lead_link = db.Table(
    'partner_lead_link',
    db.Column('partner_id', db.Integer, db.ForeignKey('partners.id'), primary_key=True),
    db.Column('lead_id', db.Integer, db.ForeignKey('lead.id'), primary_key=True)
)

class FollowUpItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=False)
    description = db.Column(db.String(255))
    is_done = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    borrower = db.relationship("BorrowerProfile")
    created_by_user = db.relationship("User")

class FollowUpTask(db.Model):
    __tablename__ = "followup_task"

    id = db.Column(db.Integer, primary_key=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"))
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"), nullable=True)

    created_by = db.Column(db.Integer)
    assigned_to = db.Column(db.Integer)
    title = db.Column(db.String(255))
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default="Pending")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=True)

    borrower = db.relationship("BorrowerProfile", backref="followup_tasks")
    loan = db.relationship("LoanApplication", backref="followup_tasks")


class BorrowerLastContact(db.Model):
    __tablename__ = "borrower_last_contact"

    id = db.Column(db.Integer, primary_key=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"))
    last_contact_at = db.Column(db.DateTime, default=datetime.utcnow)

    borrower = db.relationship("BorrowerProfile", backref="last_contact_record")
