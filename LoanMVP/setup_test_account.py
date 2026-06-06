#!/usr/bin/env python3
"""
Configure letoya@ravlohq.com for full-platform testing.

Sets role=platform_admin, university_tier=elite, all 8 Academy courses unlocked,
and marks onboarding complete so every section of the platform is accessible
without creating multiple accounts.

Run from the ravlo-platform/LoanMVP directory:
    python setup_test_account.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEST_EMAIL = "letoya@ravlohq.com"
ALL_COURSES = [
    "residential",
    "commercial",
    "mortgage",
    "realtor_growth",
    "investing",
    "deal_structuring",
    "underwriting",
    "construction",
]


def setup():
    from LoanMVP.app import app
    from LoanMVP.extensions import db
    from LoanMVP.models.user_model import User

    with app.app_context():
        user = User.query.filter_by(email=TEST_EMAIL).first()
        if not user:
            print(f"❌  User {TEST_EMAIL} not found.")
            print("    Create the account via normal signup first, then re-run this script.")
            sys.exit(1)

        # Core access flags
        user.role = "platform_admin"
        user.university_tier = "elite"
        user.is_active = True
        user.is_blocked = False
        user.invite_accepted = True
        user.onboarding_complete = True

        # Unlock all 8 Academy courses so everything shows as accessible in mobile
        # (first course with no stripe_payment_id is treated as the "chosen" subscription course)
        try:
            from LoanMVP.models.training_models import UserCourseUnlock
            existing = {
                u.course_id
                for u in UserCourseUnlock.query.filter_by(user_id=user.id).all()
            }
            added = []
            for course_id in ALL_COURSES:
                if course_id not in existing:
                    db.session.add(UserCourseUnlock(user_id=user.id, course_id=course_id))
                    added.append(course_id)
            if added:
                print(f"   Added course unlocks: {', '.join(added)}")
            else:
                print("   All 8 courses already unlocked.")
        except Exception as exc:
            print(f"   Note: could not write course unlocks — {exc}")

        db.session.commit()

        print(f"\n✅  {TEST_EMAIL} configured for full platform access:")
        print(f"    role             = platform_admin  (bypasses all role gates)")
        print(f"    university_tier  = elite           (full Academy access)")
        print(f"    chosen_course    = residential (first unlock, no payment = subscription choice)")
        print(f"    All 8 Academy courses unlocked")
        print(f"    onboarding_complete = True")
        print()
        print("    Sections now accessible:")
        print("      ✓ Academy     (elite tier, all 8 courses)")
        print("      ✓ Partners    (/partners/*)")
        print("      ✓ Lending     (/loan-officer/*)")
        print("      ✓ Investors   (/investor/*)")
        print("      ✓ Admin       (/admin/*)")
        print("      ✓ System      (/system/*)")


if __name__ == "__main__":
    setup()
