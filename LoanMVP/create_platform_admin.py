"""Create or update a platform admin account for demos."""

import argparse
import os
from LoanMVP.app import app
from LoanMVP.extensions import db
from LoanMVP.models.user_model import User

DEFAULT_EMAIL = "letoya@ravlohq.com"
DEFAULT_PASSWORD = os.environ.get("DEFAULT_PLATFORM_ADMIN_PASSWORD", "ChangeMeNow!2026")
DEFAULT_FIRST_NAME = "Letoya"
DEFAULT_LAST_NAME = "Ravlo"
DEFAULT_ROLE = "platform_admin"


def ensure_platform_admin(email: str = DEFAULT_EMAIL, password: str = DEFAULT_PASSWORD):
    with app.app_context():
        user = User.query.filter_by(email=email.lower().strip()).first()
        created = False

        if not user:
            user = User(
                email=email.lower().strip(),
                first_name=DEFAULT_FIRST_NAME,
                last_name=DEFAULT_LAST_NAME,
                username=f"{DEFAULT_FIRST_NAME} {DEFAULT_LAST_NAME}",
                role=DEFAULT_ROLE,
                is_active=True,
                invite_accepted=True,
            )
            created = True
            db.session.add(user)

        user.role = DEFAULT_ROLE
        user.is_active = True
        user.set_password(password)

        db.session.commit()

        if created:
            print(f"✅ Created platform admin: {user.email}")
        else:
            print(f"✅ Updated existing user as platform admin: {user.email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create/update a platform admin user.")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Admin email")
    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help="Admin password (or set DEFAULT_PLATFORM_ADMIN_PASSWORD)",
    )
    args = parser.parse_args()
    ensure_platform_admin(email=args.email, password=args.password)
