"""Read-only diagnostic for why Keyona isn't receiving quote-request emails.

    python -m LoanMVP.diagnose_keyona_notifications

Prints (no secrets, no writes):
  - Every "insurance"-role VIPProfile in production and the User row (if
    any) it's actually linked to -- production logs show quote requests
    hitting /vip/insurance/18/get-quote, not the /10/ id everyone assumed
    was hers, so the first thing to confirm is which profile id is
    actually live and whether its user_id resolves to a real, emailable
    User row.
  - Whether MAIL_USERNAME/MAIL_PASSWORD/MAIL_DEFAULT_SENDER are configured
    in this environment (booleans/sender address only, never the
    password) -- a missing SMTP credential would make every outbound
    email silently fail (caught and only logged as a warning).
  - The most recent InsuranceQuoteRequest rows, so we can see whether her
    test submission was actually saved to the DB at all (isolating "the
    route never really ran" from "the row saved but the email failed").
"""
from LoanMVP.app import app
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile, InsuranceQuoteRequest


def main():
    with app.app_context():
        print()
        print("=" * 70)
        print("  Insurance VIP profiles")
        print("=" * 70)
        profiles = VIPProfile.query.filter(VIPProfile.role_type.ilike("%insurance%")).all()
        if not profiles:
            print("  No VIPProfile rows with role_type containing 'insurance' found.")
        for p in profiles:
            user = User.query.get(p.user_id)
            print(f"  VIPProfile id={p.id}  slug={p.public_slug!r}  role_type={p.role_type!r}")
            print(f"    business_name={p.business_name!r}  display_name={p.display_name!r}")
            if user:
                print(f"    -> User id={user.id}  email={user.email!r}  role={user.role!r}  active={user.is_active}")
            else:
                print(f"    -> NO USER FOUND for user_id={p.user_id} (orphaned profile -- emails have nowhere to go)")
            print()

        print("=" * 70)
        print("  Mail configuration (this environment)")
        print("=" * 70)
        cfg = app.config
        print(f"  MAIL_SERVER          = {cfg.get('MAIL_SERVER')!r}")
        print(f"  MAIL_PORT            = {cfg.get('MAIL_PORT')!r}")
        print(f"  MAIL_USE_TLS         = {cfg.get('MAIL_USE_TLS')!r}")
        print(f"  MAIL_USERNAME set?   = {bool(cfg.get('MAIL_USERNAME'))}")
        print(f"  MAIL_PASSWORD set?   = {bool(cfg.get('MAIL_PASSWORD'))}")
        print(f"  MAIL_DEFAULT_SENDER  = {cfg.get('MAIL_DEFAULT_SENDER')!r}")
        print(f"  MAIL_SUPPRESS_SEND   = {cfg.get('MAIL_SUPPRESS_SEND')!r}")
        print()

        print("=" * 70)
        print("  Most recent insurance quote requests")
        print("=" * 70)
        recent = InsuranceQuoteRequest.query.order_by(InsuranceQuoteRequest.created_at.desc()).limit(10).all()
        if not recent:
            print("  No InsuranceQuoteRequest rows exist at all.")
        for qr in recent:
            print(f"  #{qr.id}  vip_profile_id={qr.vip_profile_id}  client={qr.client_name!r}  "
                  f"email={qr.client_email!r}  source={qr.source!r}  created_at={qr.created_at}")
        print()


if __name__ == "__main__":
    main()
