"""One-command demo reset.

What it does:
1) Ensures platform admin exists (default: letoya@ravlohq.com)
2) Removes non-admin users when possible
3) Falls back to deactivating non-admin users if hard-delete fails
"""

from LoanMVP.app import app
from LoanMVP.extensions import db
from LoanMVP.models.user_model import User
from LoanMVP.create_platform_admin import ensure_platform_admin, DEFAULT_EMAIL

ADMIN_ROLES = {"admin", "platform_admin", "master_admin", "lending_admin"}


def _is_protected(user: User, protected_email: str) -> bool:
    email = (user.email or "").strip().lower()
    role = (user.role or "").strip().lower()
    return email == protected_email.lower().strip() or role in ADMIN_ROLES


def reset_demo_users(protected_email: str = DEFAULT_EMAIL):
    ensure_platform_admin(email=protected_email)

    with app.app_context():
        users = User.query.all()
        targets = [u for u in users if not _is_protected(u, protected_email)]

        if not targets:
            print("ℹ️ No non-admin users found to remove.")
            return

        # Attempt hard-delete first.
        try:
            for user in targets:
                db.session.delete(user)
            db.session.commit()
            print(f"✅ Deleted {len(targets)} non-admin users.")
            return
        except Exception as exc:
            db.session.rollback()
            print(f"⚠️ Hard-delete failed ({exc}). Falling back to deactivation.")

        # Fallback: deactivate + anonymize email.
        updated = 0
        for user in targets:
            user.is_active = False
            user.email = f"archived+{user.id}@ravlohq.local"
            updated += 1

        db.session.commit()
        print(f"✅ Deactivated/anonymized {updated} non-admin users.")


if __name__ == "__main__":
    reset_demo_users()
