"""
Utility: Cleans up leftover Alembic temp tables that block migrations.
Works with Flask factory pattern (create_app()).
"""

from LoanMVP.app import create_app   # ✅ import the factory
from LoanMVP.extensions import db
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

app = create_app()  # ✅ initialize the app

def cleanup_tmp_tables():
    try:
        with app.app_context():
            result = db.session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '_alembic_tmp_%';"
            ))
            tables = [row[0] for row in result]

            if not tables:
                print("✅ No leftover _alembic_tmp_ tables found. Database is clean.")
                return

            print(f"🧹 Found {len(tables)} temporary Alembic tables:")
            for t in tables:
                print(f"   - {t}")
                db.session.execute(text(f"DROP TABLE IF EXISTS {t};"))
            db.session.commit()
            print("✅ All temporary Alembic tables removed successfully.")

    except SQLAlchemyError as e:
        print(f"⚠️ Error while cleaning up temp tables: {e}")
        db.session.rollback()


if __name__ == "__main__":
    print("Starting Alembic temporary table cleanup...")
    cleanup_tmp_tables()
    print("Done.")
