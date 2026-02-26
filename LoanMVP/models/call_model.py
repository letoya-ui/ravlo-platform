from LoanMVP.extensions import db
from datetime import datetime

class CallLog(db.Model):
    __tablename__ = "call_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # who made/received call
    contact_name = db.Column(db.String(120), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)
    related_lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"), nullable=True)
    related_loan_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"), nullable=True)

    direction = db.Column(db.String(10), nullable=False)  # 'inbound' or 'outbound'
    duration_seconds = db.Column(db.Integer, nullable=True)
    outcome = db.Column(db.String(120), nullable=True)  # e.g. "No Answer", "Left VM", "Follow-up Scheduled"
    notes = db.Column(db.Text, nullable=True)
    sentiment = db.Column(db.String(20), default="Neutral")  # Positive, Neutral, Negative

    ai_summary = db.Column(db.Text, nullable=True)  # optional — auto transcript or summary
    recording_url = db.Column(db.String(255), nullable=True)  # if Twilio or other dialer stores call recordings

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CallLog {self.id} - {self.direction} - {self.contact_name}>"

class CommunicationLog(db.Model):
    __tablename__ = "communication_log"

    id = db.Column(db.Integer, primary_key=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"))
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"), nullable=True)

    channel = db.Column(db.String(20))  # call, sms, email
    subject = db.Column(db.String(255), nullable=True)
    message = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    borrower = db.relationship("BorrowerProfile", backref="communication_logs")
    loan = db.relationship("LoanApplication", backref="communication_logs")

    def __repr__(self):
        return f"<CommLog borrower={self.borrower_id} channel={self.channel}>"