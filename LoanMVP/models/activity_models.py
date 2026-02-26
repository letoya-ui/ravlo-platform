from LoanMVP.extensions import db
from datetime import datetime

class BorrowerActivity(db.Model):
    __tablename__ = "borrower_activity"

    id = db.Column(db.Integer, primary_key=True)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text)
    category = db.Column(db.String(50))  # e.g., "upload", "loan", "ai", "message"
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    borrower = db.relationship("BorrowerProfile", backref=db.backref("activities", lazy=True))

    def __repr__(self):
        return f"<BorrowerActivity {self.action} @ {self.timestamp:%Y-%m-%d}>"
