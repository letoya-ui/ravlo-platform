from datetime import datetime
from LoanMVP.extensions import db

class ChatHistory(db.Model):
    __tablename__ = "chat_history"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(50))
    user_message = db.Column(db.Text, nullable=False)
    ai_response = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Chat {self.role} {self.timestamp}>"
