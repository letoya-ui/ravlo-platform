from datetime import datetime

from LoanMVP.extensions import db


class Referral(db.Model):
    """One row per friend who signs up through a Ravlo user's personal
    referral link (see marketing.referral_landing / /r/<code>)."""

    __tablename__ = "referrals"

    id = db.Column(db.Integer, primary_key=True)

    referrer_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    referred_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)

    referral_code = db.Column(db.String(16), nullable=False, index=True)
    referred_email = db.Column(db.String(120), nullable=True)

    # signed_up -> converted (reserved for a future billing-tied upgrade)
    status = db.Column(db.String(20), nullable=False, default="signed_up")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    converted_at = db.Column(db.DateTime, nullable=True)

    referrer = db.relationship("User", foreign_keys=[referrer_user_id])
    referred_user = db.relationship("User", foreign_keys=[referred_user_id])

    def __repr__(self):
        return f"<Referral referrer={self.referrer_user_id} referred={self.referred_user_id} status={self.status}>"
