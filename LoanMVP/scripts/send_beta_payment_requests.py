"""
Send payment-request emails to beta partners whose trial has expired or
expires within the next 3 days.

Run this daily (e.g. via cron or Windows Task Scheduler):

    python -m LoanMVP.scripts.send_beta_payment_requests

What it does:
  1. Finds all Partner rows where paid_until is within the next 3 days
     OR is already past, AND subscription_tier is still "Premium" (beta),
     AND beta_payment_sent is not already True.
  2. Sends each partner an email with their personal Stripe checkout link
     for the "brokerage" plan.
  3. Sets partner.beta_payment_sent = True so we don't spam them.

Safe to run multiple times — already-notified partners are skipped.
"""

import os
from datetime import datetime, timedelta

from LoanMVP.app import app
from LoanMVP.extensions import db

CHECKOUT_PLAN = "brokerage"   # maps to STRIPE_PRICE_BROKERAGE_SMALL_TEAM in checkout_routes
WARN_DAYS     = 3             # also email 3 days before expiry as a heads-up


def _checkout_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/checkout/subscribe/{CHECKOUT_PLAN}"


def _build_email(partner_name: str, expiry: datetime, checkout_link: str, days_left: int) -> tuple[str, str]:
    if days_left > 0:
        timing_line = f"Your 2-month beta period ends in <strong>{days_left} day{'s' if days_left != 1 else ''}</strong> on {expiry.strftime('%B %d, %Y')}."
        subject = f"Your Ravlo Lending OS beta ends in {days_left} day{'s' if days_left != 1 else ''} — activate to keep access"
    else:
        timing_line = f"Your 2-month beta period <strong>ended on {expiry.strftime('%B %d, %Y')}</strong>."
        subject = "Your Ravlo Lending OS beta has ended — activate your subscription to restore access"

    html = f"""
<html><body style="font-family:Arial,sans-serif;color:#1a1a1a;max-width:600px;margin:0 auto;padding:24px;">
  <img src="https://ravlo.com/static/img/ravlo-logo.png" alt="Ravlo" height="36" style="margin-bottom:24px;" />
  <h2 style="color:#3A5C7A;">Hi {partner_name},</h2>
  <p>{timing_line}</p>
  <p>
    We hope your experience with the <strong>Ravlo Lending OS</strong> has been valuable.
    To continue enjoying full access — including your white-label dashboard, CRM, AI pilot,
    deal visibility, and proposal builder — please activate your subscription below.
  </p>
  <p style="text-align:center;margin:32px 0;">
    <a href="{checkout_link}"
       style="background:#3A5C7A;color:#fff;padding:14px 32px;border-radius:6px;
              text-decoration:none;font-weight:700;font-size:16px;">
      Activate My Subscription
    </a>
  </p>
  <p style="color:#666;font-size:13px;">
    Questions? Reply to this email or contact us at
    <a href="mailto:support@ravlo.com">support@ravlo.com</a>.
  </p>
  <hr style="border:none;border-top:1px solid #eee;margin:32px 0;" />
  <p style="color:#999;font-size:11px;">
    Ravlo Platform · You are receiving this because you signed up for a beta account.
  </p>
</body></html>
"""

    text = (
        f"Hi {partner_name},\n\n"
        + (f"Your 2-month beta ends in {days_left} day(s) on {expiry.strftime('%B %d, %Y')}.\n\n"
           if days_left > 0
           else f"Your 2-month beta ended on {expiry.strftime('%B %d, %Y')}.\n\n")
        + "To keep your Ravlo Lending OS access, activate your subscription:\n"
        + f"{checkout_link}\n\n"
        + "Questions? Email support@ravlo.com\n"
    )

    return subject, html, text


def send_beta_payment_requests(base_url: str = None):
    from LoanMVP.models.crm_models import Partner
    from LoanMVP.utils.emailer import send_email

    if not base_url:
        base_url = os.environ.get("APP_BASE_URL", "https://ravlo.com")

    now = datetime.utcnow()
    warn_cutoff = now + timedelta(days=WARN_DAYS)

    # Partners whose beta is expiring soon or already expired, not yet notified
    candidates = (
        Partner.query
        .filter(Partner.paid_until != None)
        .filter(Partner.paid_until <= warn_cutoff)
        .filter(Partner.subscription_tier == "Premium")
        .filter(
            db.or_(
                Partner.beta_payment_sent == False,
                Partner.beta_payment_sent == None,
            )
        )
        .all()
    )

    if not candidates:
        print("No beta partners to notify.")
        return

    checkout_link = _checkout_url(base_url)
    sent = 0

    for partner in candidates:
        if not partner.email:
            print(f"  skip partner {partner.id} — no email address")
            continue

        days_left = max(0, (partner.paid_until - now).days)
        subject, html, text = _build_email(
            partner_name=partner.name or "there",
            expiry=partner.paid_until,
            checkout_link=checkout_link,
            days_left=days_left,
        )

        try:
            send_email(partner.email, subject, html, text)
            partner.beta_payment_sent = True
            db.session.commit()
            print(f"  ✓ Sent payment request to {partner.email} (days_left={days_left})")
            sent += 1
        except Exception as exc:
            print(f"  ✗ Failed to email {partner.email}: {exc}")

    print(f"\nDone — {sent} payment request(s) sent.")


if __name__ == "__main__":
    with app.app_context():
        send_beta_payment_requests()
