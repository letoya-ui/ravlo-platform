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
  - Every VIPProfile with a custom_domain set -- she reported that her own
    connected website shows a "demo" account instead of her business.
    app.py's handle_custom_domain() looks up the VIPProfile whose
    custom_domain matches the request host and serves THAT profile's
    content/links (including its own /vip/insurance/<id>/get-quote link) --
    if her domain is stored on the wrong (e.g. a leftover demo) profile
    instead of her real one, this table will show exactly that.
  - VIPProfile id=10 specifically, side-by-side with whatever the
    insurance-role query above found -- production logs show her real
    logo/page also generating hits to /vip/insurance/10/get-quote, so
    it's worth seeing directly whether that id belongs to a demo account.
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

        print("=" * 70)
        print("  VIPProfiles with a custom_domain set")
        print("=" * 70)
        domained = VIPProfile.query.filter(VIPProfile.custom_domain.isnot(None)).all()
        if not domained:
            print("  No VIPProfile has custom_domain set at all.")
        for p in domained:
            user = User.query.get(p.user_id)
            print(f"  VIPProfile id={p.id}  custom_domain={p.custom_domain!r}  slug={p.public_slug!r}")
            print(f"    business_name={p.business_name!r}  role_type={p.role_type!r}  "
                  f"marketplace_enabled={p.marketplace_enabled!r}")
            print(f"    -> User email={user.email!r}" if user else "    -> NO USER FOUND")
            print()

        print("=" * 70)
        print("  VIPProfile id=10 (production logs show real logo hits also")
        print("  falling through to /vip/insurance/10/get-quote)")
        print("=" * 70)
        p10 = VIPProfile.query.get(10)
        if not p10:
            print("  No VIPProfile with id=10 exists.")
        else:
            user = User.query.get(p10.user_id)
            print(f"  id=10  slug={p10.public_slug!r}  role_type={p10.role_type!r}  "
                  f"custom_domain={p10.custom_domain!r}")
            print(f"  business_name={p10.business_name!r}  display_name={p10.display_name!r}  "
                  f"logo_url={p10.logo_url!r}")
            print(f"  -> User email={user.email!r}" if user else "  -> NO USER FOUND")
        print()


if __name__ == "__main__":
    main()
