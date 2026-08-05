from datetime import datetime
from LoanMVP.extensions import db
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint

class PaymentRecord(db.Model):
    __tablename__ = "payment_record"

    id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    
    user = db.relationship("User", backref=db.backref("payment_records", lazy=True))

    borrower_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("borrower_profile.id", name="fk_payment_borrower")
    )
    
    investor_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("investor_profile.id", name="fk_payment_investor")
    )

    loan_id = db.Column(
        db.Integer,
        db.ForeignKey("loan_application.id", name="fk_payment_loan")
    )

    payment_type = db.Column(db.String(100))  # Appraisal, Credit Pull, App Fee, etc.
    amount = db.Column(db.Float)
    status = db.Column(db.String(20), default="Pending")  # Pending / Paid
    stripe_payment_intent = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    borrower = db.relationship("BorrowerProfile", backref="payments")
    loan = db.relationship("LoanApplication", backref="payments")
    investor_profile = db.relationship("InvestorProfile", backref="payments")


# ---------------------------------------------------------------------------
# PAYMENTS CAPABILITY (Stripe Connect deposits/invoices)
# ---------------------------------------------------------------------------
# Unrelated to PaymentRecord above (that's internal loan-process fees --
# appraisal, credit pull, app fee -- tied to a specific loan/borrower).
# PaymentAccount/PaymentRequest back the "request a deposit" capability any
# VIP-style workspace can turn on. A realtor and an insurance agent are both
# VIPProfile rows; a stylist is a StylistProfile row (a fully separate
# table -- see salon_models.py, it has its own sidebar/base layout and no
# relation to VIPProfile at all). Rather than duplicating Connect columns
# onto every vertical's profile table, the owner is referenced
# polymorphically via (owner_type, owner_id); LoanMVP/services/
# payments_service.py is the one place that maps an owner_type string to
# its real model. Adding a new workspace type here later means teaching
# that one function a new owner_type, not touching this schema again.
# ---------------------------------------------------------------------------

class PaymentAccount(db.Model):
    """One row per (owner_type, owner_id) workspace that has connected --
    or started connecting -- its own Stripe account. Ravlo is never the
    merchant of record for the money itself; funds move straight to the
    workspace's own connected account via a destination charge."""

    __tablename__ = "payment_accounts"
    __table_args__ = (
        UniqueConstraint("owner_type", "owner_id", name="uq_payment_accounts_owner"),
    )

    id = db.Column(db.Integer, primary_key=True)

    owner_type = db.Column(db.String(50), nullable=False)
    owner_id   = db.Column(db.Integer,    nullable=False)

    stripe_connect_account_id      = db.Column(db.String(255), nullable=True)
    stripe_connect_charges_enabled = db.Column(db.Boolean, nullable=False, default=False)
    stripe_connect_payouts_enabled = db.Column(db.Boolean, nullable=False, default=False)
    stripe_connect_onboarded_at    = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payment_requests = relationship(
        "PaymentRequest",
        back_populates="payment_account",
        lazy=True,
        order_by="PaymentRequest.created_at.desc()",
    )

    @property
    def is_ready_for_payments(self) -> bool:
        return bool(self.stripe_connect_account_id) and self.stripe_connect_charges_enabled

    def __repr__(self):
        return f"<PaymentAccount {self.id} - {self.owner_type}:{self.owner_id}>"


class PaymentRequest(db.Model):
    """A deposit/invoice request a workspace sends to a client to pay.
    Same shape regardless of workspace type (salon deposit, contractor
    invoice, insurance binder fee, etc.)."""

    __tablename__ = "payment_requests"

    id = db.Column(db.Integer, primary_key=True)

    payment_account_id = db.Column(db.Integer, db.ForeignKey("payment_accounts.id"), nullable=False)

    title        = db.Column(db.String(255), nullable=False)
    description  = db.Column(db.Text,        nullable=True)
    amount_cents = db.Column(db.Integer,     nullable=False)

    client_name  = db.Column(db.String(255), nullable=True)
    client_email = db.Column(db.String(255), nullable=True)
    client_phone = db.Column(db.String(50),  nullable=True)

    # pending -> paid | canceled | expired
    status = db.Column(db.String(20), nullable=False, default="pending")

    stripe_checkout_session_id = db.Column(db.String(255), nullable=True)
    stripe_payment_intent_id   = db.Column(db.String(255), nullable=True)

    # Opaque token used in the public payer URL so the request isn't
    # guessable/enumerable off its integer id.
    confirmation_token = db.Column(db.String(64), nullable=False, unique=True)

    paid_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payment_account = relationship("PaymentAccount", back_populates="payment_requests")

    def __repr__(self):
        return f"<PaymentRequest {self.id} - {self.title} (${self.amount_cents / 100:.2f})>"
