from datetime import datetime
from sqlalchemy import Column, Integer, Text, String, DateTime, ForeignKey

from LoanMVP.extensions import db


class CanvaConnection(db.Model):
    __tablename__ = "canva_connections"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, unique=True)

    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    scope = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CanvaConnection user_id={self.user_id}>"