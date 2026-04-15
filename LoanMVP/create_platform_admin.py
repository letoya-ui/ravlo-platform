"""Create or update platform admin accounts for demos."""

import argparse
import os
from LoanMVP.app import app
from LoanMVP.extensions import db
from LoanMVP.models.user_model import User

DEFAULT_EMAIL = "letoya@ravlohq.com"
DEFAULT_PASSWORD = os.environ.get("DEFAULT_PLATFORM_ADMIN_PASSWORD", "")
DEFAULT_FIRST_NAME = "Letoya"
DEFAULT_LAST_NAME = "Ravlo"
DEFAULT_ROLE = "platform_admin"

# Sandra — admin account for user management
SANDRA_EMAIL = "sandra@ravlohq.com"
SANDRA_PASSWORD = os.environ.get("SANDRA_ADMIN_PASSWORD", "")
SANDRA_FIRST_NAME = "Sandra"
SANDRA_LAST_NAME = ""
SANDRA_ROLE = "admin"


def ensure_platform_admin(email: str = DEFAULT_EMAIL, password: str = DEFAULT_PASSWORD):
    if not password:
        raise ValueError(
            "Password must be provided via --password or the "
            "DEFAULT_PLATFORM_ADMIN_PASSWORD environment variable."
        )

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


def ensure_sandra_admin(email: str = SANDRA_EMAIL, password: str = SANDRA_PASSWORD):
    if not password:
        raise ValueError(
            "Password must be provided via --sandra-password or the "
            "SANDRA_ADMIN_PASSWORD environment variable."
        )

    with app.app_context():
        user = User.query.filter_by(email=email.lower().strip()).first()
        created = False

        if not user:
            user = User(
                email=email.lower().strip(),
                first_name=SANDRA_FIRST_NAME,
                last_name=SANDRA_LAST_NAME,
                username=SANDRA_FIRST_NAME,
                role=SANDRA_ROLE,
                is_active=True,
                invite_accepted=True,
            )
            created = True
            db.session.add(user)

        user.role = SANDRA_ROLE
        user.is_active = True
        user.set_password(password)

        db.session.commit()

        if created:
            print(f"\u2705 Created admin: {user.email}")
        else:
            print(f"\u2705 Updated existing user as admin: {user.email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create/update platform admin users.")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Platform admin email")
    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help="Platform admin password (or set DEFAULT_PLATFORM_ADMIN_PASSWORD)",
    )
    parser.add_argument(
        "--sandra-password",
        default=SANDRA_PASSWORD,
        help="Sandra admin password (or set SANDRA_ADMIN_PASSWORD)",
    )
    args = parser.parse_args()
    ensure_platform_admin(email=args.email, password=args.password)
    if args.sandra_password:
        ensure_sandra_admin(password=args.sandra_password)
