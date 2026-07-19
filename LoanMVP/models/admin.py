from datetime import datetime, timedelta
from decimal import Decimal
import secrets

from LoanMVP.extensions import db


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

    # These fields exist in your database but were missing in your model
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(255), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    zip = db.Column(db.String(20), nullable=True)

    email_domain = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    subscription_tier = db.Column(db.String(50), nullable=True)
    max_users = db.Column(db.Integer, nullable=True)
    
    is_blocked = db.Column(db.Boolean, default=False, nullable=False)
    blocked_at = db.Column(db.DateTime, nullable=True)
    blocked_reason = db.Column(db.String(100), nullable=True)
    blocked_note = db.Column(db.Text, nullable=True)
    blocked_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    billing_status = db.Column(db.String(50), default="active", nullable=True)
    grace_period_ends_at = db.Column(db.DateTime, nullable=True)
    stripe_customer_id = db.Column(db.String(255), nullable=True)

    # -- White Label branding (the Enterprise/"white_label" tier add-on) --
    # only ever displayed in place of Ravlo's own branding when
    # subscription_tier == "white_label" AND brand_name is actually set
    # (see LoanMVP/utils/branding.py's effective_brand()) -- every other
    # company keeps seeing "Ravlo" regardless of what's stored here.
    brand_name = db.Column(db.String(120), nullable=True)
    brand_logo_initials = db.Column(db.String(4), nullable=True)
    brand_primary_color = db.Column(db.String(9), nullable=True)
    brand_secondary_color = db.Column(db.String(9), nullable=True)
    brand_accent_color = db.Column(db.String(9), nullable=True)
    brand_tagline = db.Column(db.String(160), nullable=True)

    users = db.relationship("User", back_populates="company", foreign_keys="User.company_id", lazy=True)
    invites = db.relationship("UserInvite", back_populates="company", lazy=True)
    access_requests = db.relationship("AccessRequest", backref="company", lazy=True)
    blocked_by_user = db.relationship(
        "User",
        foreign_keys=[blocked_by],
        back_populates="blocked_companies",
        lazy=True
    )

    def seats_used(self) -> int:
        from LoanMVP.models.user_model import User
        return User.query.filter_by(company_id=self.id).count()

    def has_seat_available(self) -> bool:
        """max_users=None means an uncapped plan (e.g. white_label/Enterprise)."""
        if self.max_users is None:
            return True
        return self.seats_used() < self.max_users

    def is_billing_current(self) -> bool:
        """True if billing_status is active, or past_due but still inside the grace period.

        Not enforced anywhere yet -- this just reports the state Stripe has
        put the company in. A follow-up (tier-based feature gating) is what
        will actually act on this.
        """
        if self.billing_status == "active":
            return True
        if self.billing_status == "past_due":
            return self.grace_period_ends_at is not None and datetime.utcnow() < self.grace_period_ends_at
        return False


class AccessRequest(db.Model):
    __tablename__ = "access_requests"

    id = db.Column(db.Integer, primary_key=True)

    company_name = db.Column(db.String(255), nullable=True)
    contact_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(50), nullable=True)

    request_type = db.Column(db.String(50), nullable=False, default="company_setup")
    requested_role = db.Column(db.String(50), nullable=True)

    status = db.Column(db.String(50), nullable=False, default="pending")
    notes = db.Column(db.Text, nullable=True)

    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)

    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewer = db.relationship("User", foreign_keys=[reviewed_by], back_populates="access_requests")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserInvite(db.Model):
    __tablename__ = "user_invites"

    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)

    email = db.Column(db.String(255), nullable=False, index=True)
    first_name = db.Column(db.String(120), nullable=True)
    last_name = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(50), nullable=False)

    token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False, default="pending")

    invited_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    inviter = db.relationship("User", foreign_keys=[invited_by], back_populates="invites_sent")

    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    company = db.relationship("Company", back_populates="invites")

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(32)

    @staticmethod
    def default_expiration(days=7):
        return datetime.utcnow() + timedelta(days=days)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

class BusinessInquiry(db.Model):
    """Unified inbox for inbound submissions: license applications, plain
    contact-us messages, lending OS leads, investor challenge signups,
    referrals, and feedback. `inquiry_type` distinguishes the submission
    channel; `business_type` is only meaningful for inquiry_type ==
    'license_application' (broker, lender, fund, brokerage, enterprise)."""
    __tablename__ = "business_inquiries"

    id = db.Column(db.Integer, primary_key=True)
    inquiry_type = db.Column(db.String(50), nullable=False, default="license_application")
    # license_application, contact, lending_os_lead, challenge_signup, referral, feedback

    company_name = db.Column(db.String(255), nullable=False, default="—")
    contact_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(50))
    website = db.Column(db.String(255))

    business_type = db.Column(db.String(100))  # broker, lender, fund, brokerage, enterprise
    team_size = db.Column(db.String(50))
    plan_interest = db.Column(db.String(100))  # individual, team, lender, white_label

    monthly_loan_volume = db.Column(db.String(100))
    current_tools = db.Column(db.Text)
    goals = db.Column(db.Text)
    notes = db.Column(db.Text)

    status = db.Column(db.String(50), default="new", nullable=False)  # new, contacted, approved, declined
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # -- Account Executive pipeline (sales-rep-facing; independent of the
    # admin-facing `status` above, which drives the existing Company/invite
    # creation workflow in admin.py and must keep its own new/contacted/
    # approved/declined meaning unchanged). `ae_stage` is the AE's own view
    # of the deal's progress toward a signed license.
    assigned_ae_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    ae_stage = db.Column(db.String(30), default="prospect", nullable=True)
    # prospect, contacted, demo_scheduled, demo_completed, contract_sent, signed, lost

    contract_value = db.Column(db.Numeric(12, 2), nullable=True)
    billing_cycle = db.Column(db.String(20), nullable=True)  # monthly, annual

    # -- Commission structure (Ravlo Pricing Playbook) -- setup fee and
    # first-year monthly commission are paid separately, and at different
    # rates, so the AE is rewarded for closing new business without
    # committing Ravlo to that same rate indefinitely on recurring
    # revenue. The actual payout schedule is AECommissionEntry rows
    # (see below); these are just the rates/amounts locked in at signing.
    signed_setup_fee = db.Column(db.Numeric(12, 2), nullable=True)
    signed_monthly_fee = db.Column(db.Numeric(12, 2), nullable=True)
    setup_commission_rate = db.Column(db.Numeric(5, 4), nullable=True)  # 0.10-0.20
    monthly_commission_rate = db.Column(db.Numeric(5, 4), nullable=True)  # 0.05-0.10, first 12 months
    renewal_commission_rate = db.Column(db.Numeric(5, 4), nullable=True)  # optional, 0.01-0.03, after month 12

    signed_at = db.Column(db.DateTime, nullable=True)
    lost_reason = db.Column(db.Text, nullable=True)

    # Set manually once a Ravlo admin has completed the existing
    # approve-and-onboard flow for this deal -- ties the AE's commission
    # record to the resulting live Company for reporting.
    linked_company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)

    # -- Ravlo Pricing Playbook quote (LoanMVP/services/ae_pricing.py) --
    # populated by the AE's quote calculator, not typed free-hand, so
    # every deal's numbers come from the same standard/enterprise rate
    # card and the same discount-approval rules.
    pricing_plan = db.Column(db.String(30), nullable=True)
    # solo, professional, business, individual_lo, branch, regional, enterprise
    enterprise_user_count = db.Column(db.Integer, nullable=True)
    list_setup_fee = db.Column(db.Numeric(12, 2), nullable=True)
    list_monthly_fee = db.Column(db.Numeric(12, 2), nullable=True)
    discount_percent = db.Column(db.Numeric(5, 2), nullable=True)
    setup_fee_waived = db.Column(db.Numeric(12, 2), nullable=True)
    is_white_label = db.Column(db.Boolean, default=False, nullable=True)
    is_custom_development = db.Column(db.Boolean, default=False, nullable=True)
    is_multi_year = db.Column(db.Boolean, default=False, nullable=True)
    is_strategic_partnership = db.Column(db.Boolean, default=False, nullable=True)

    # ae, sales_manager, executive -- computed by required_approval_level()
    # each time the quote is (re)built.
    approval_level_required = db.Column(db.String(20), nullable=True)
    # not_required, pending, approved -- gates marking the deal "signed".
    approval_status = db.Column(db.String(20), default="not_required", nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)

    # -- Quote Worksheet (Ravlo Pricing Playbook, section 4) -- discovery
    # answers captured before a plan is picked, so every AE follows the
    # same repeatable process instead of relying on instinct. Company/
    # contact info already lives on this row; "Recommended Package" and
    # the setup/monthly numbers are the Quote Calculator's own output
    # above, not duplicated here.
    worksheet_industry = db.Column(db.String(120), nullable=True)
    worksheet_user_count = db.Column(db.Integer, nullable=True)
    worksheet_workspace_count = db.Column(db.Integer, nullable=True)
    worksheet_branding = db.Column(db.String(20), nullable=True)  # ravlo, co_branded, white_label
    worksheet_implementation_complexity = db.Column(db.String(20), nullable=True)  # standard, advanced, enterprise
    worksheet_training_required = db.Column(db.Boolean, nullable=True)

    assigned_ae = db.relationship("User", foreign_keys=[assigned_ae_id])
    linked_company = db.relationship("Company", foreign_keys=[linked_company_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])

    @property
    def commission_amount(self):
        """Total commission across every ledger entry (setup + every
        monthly/renewal entry generated so far) -- not just the first
        year, so this grows as renewal entries get added over time."""
        if not self.commission_entries:
            return None
        return sum((e.amount for e in self.commission_entries), Decimal("0.00"))

    @property
    def commission_status(self):
        """pending: nothing paid yet. partial: some entries paid, some
        not (the common case -- setup pays out immediately, the 12
        monthly entries pay out over the year). paid: every entry paid."""
        if not self.commission_entries:
            return None
        statuses = {e.status for e in self.commission_entries}
        if statuses == {"paid"}:
            return "paid"
        if "paid" in statuses:
            return "partial"
        return "pending"


class AECommissionEntry(db.Model):
    """One line of an AE's commission payout schedule for a signed deal.
    Generated automatically at signing: one 'setup' entry, then 12
    'monthly' entries (the first-year recurring-revenue commission).
    'renewal' entries are added one at a time, on demand, for as long as
    the customer keeps renewing -- there's no fixed end date for those,
    unlike the guaranteed first 12 months.
    """
    __tablename__ = "ae_commission_entries"

    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("business_inquiries.id"), nullable=False, index=True)

    entry_type = db.Column(db.String(20), nullable=False)  # setup, monthly, renewal
    period_number = db.Column(db.Integer, nullable=True)  # 1-12 for monthly; 13+ for renewal; null for setup
    amount = db.Column(db.Numeric(12, 2), nullable=False)

    status = db.Column(db.String(20), default="pending", nullable=False)  # pending, paid
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    deal = db.relationship(
        "BusinessInquiry",
        backref=db.backref("commission_entries", lazy=True, order_by="AECommissionEntry.id"),
    )


class LicenseInviteEvent(db.Model):
    __tablename__ = "license_invite_events"

    id = db.Column(db.Integer, primary_key=True)

    invite_token = db.Column(db.String(255))
    email = db.Column(db.String(255))

    event_type = db.Column(db.String(50))  # opened
    user_agent = db.Column(db.String(255))
    ip_address = db.Column(db.String(50))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SubscriptionRequest(db.Model):
    __tablename__ = "subscription_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False, default="pending")
    plan_requested = db.Column(db.String(50), nullable=True, default="Core")
    # Which self-service upgrade flow this came from: "investor_preview",
    # "partner_tier", or "borrower_plan". Lets one shared pending-request
    # queue serve all of them without a separate table per flow.
    context = db.Column(db.String(50), nullable=True, default="investor_preview")
    message = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id], lazy=True)
    reviewer = db.relationship("User", foreign_keys=[reviewed_by], lazy=True)
