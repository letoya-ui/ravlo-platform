"""Fix Keyona's live VIPProfile missing its public_slug.

    python -m LoanMVP.fix_keyona_public_slug

Her live VIPProfile (id=18, linked to keyonahall@icloud.com) has
public_slug=None, confirmed via diagnose_keyona_notifications.py.
_load_realtor_context() in public_pages.py looks up a VIP's live page by
public_slug -- with it unset, her /p/key-signature-enterprise page falls
through to SLUG_STATIC_CONTEXT's hardcoded fallback content instead of
her real, editable profile, and any code path that relies directly on
profile.public_slug (e.g. handle_custom_domain() in app.py) would break
outright.

Safe to run multiple times -- only sets public_slug when it's missing,
never overwrites a value someone deliberately set.
"""
from LoanMVP.app import app
from LoanMVP.extensions import db
from LoanMVP.models.user_model import User
from LoanMVP.models.vip_models import VIPProfile

EMAIL = "keyonahall@icloud.com"
PUBLIC_SLUG = "key-signature-enterprise"


def main():
    with app.app_context():
        user = User.query.filter(db.func.lower(User.email) == EMAIL.lower()).first()
        if not user:
            raise SystemExit(f"No User found for {EMAIL!r} -- nothing to fix.")

        profile = VIPProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            raise SystemExit(f"No VIPProfile found for user_id={user.id} -- nothing to fix.")

        print(f"VIPProfile id={profile.id}  current public_slug={profile.public_slug!r}")

        if profile.public_slug:
            print("public_slug is already set -- leaving it alone.")
            return

        profile.public_slug = PUBLIC_SLUG
        db.session.commit()
        print(f"Set public_slug to {PUBLIC_SLUG!r}. Her live profile will now be used for "
              f"/p/{PUBLIC_SLUG} instead of the hardcoded fallback content.")


if __name__ == "__main__":
    main()
