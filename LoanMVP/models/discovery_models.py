from LoanMVP.extensions import db
from datetime import datetime


class DiscoveryEvent(db.Model):
    __tablename__ = "discovery_events"

    id         = db.Column(db.Integer, primary_key=True)
    source     = db.Column(db.String(80), nullable=False, index=True)
    user_agent = db.Column(db.Text)
    ip         = db.Column(db.String(50))
    path       = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<DiscoveryEvent {self.source} {self.path} @ {self.created_at:%Y-%m-%d %H:%M}>"
