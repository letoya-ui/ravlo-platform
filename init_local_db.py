from werkzeug.security import generate_password_hash

from LoanMVP.app import create_app
from LoanMVP.extensions import db
from LoanMVP.models import User

# Import all models that need tables created
from LoanMVP.models.loan_models import BorrowerProfile, LoanNotification

app = create_app()

with app.app_context():
    db.create_all()

    user = User.query.filter_by(email="officer@loanmvp.com").first()
    if not user:
        user = User(
            first_name="Loan",
            last_name="Officer",
            username="officer",
            email="officer@loanmvp.com",
            role="loan_officer",
            password_hash=generate_password_hash("Password123!")
        )
        db.session.add(user)
        db.session.commit()
        print("Created local loan officer user.")
    else:
        print("Loan officer user already exists.")

    print("local.db initialized successfully.")