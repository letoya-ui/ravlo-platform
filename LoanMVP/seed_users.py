# LoanMVP/seed_users.py
import os
from LoanMVP.app import app
from LoanMVP.extensions import db
from LoanMVP.models import User
from werkzeug.security import generate_password_hash

# ----------------------------
# 🌱 Seed Default Users
# ----------------------------
def seed_users():
    with app.app_context():
        # Prevent duplicates
        if User.query.first():
            print("⚠️ Users already exist — skipping seed.")
            return

        users = [
            {
                "full_name": "Admin User",
                "email": "admin@loanmvp.com",
                "password": "admin123",
                "role": "admin"
            },
            {
                "full_name": "Loan Officer User",
                "email": "officer@loanmvp.com",
                "password": "officer123",
                "role": "loan_officer"
            },
            {
                "full_name": "Processor User",
                "email": "processor@loanmvp.com",
                "password": "processor123",
                "role": "processor"
            },
            {
                "full_name": "Underwriter User",
                "email": "underwriter@loanmvp.com",
                "password": "underwriter123",
                "role": "underwriter"
            },
            {
                "full_name": "Borrower User",
                "email": "borrower@loanmvp.com",
                "password": "borrower123",
                "role": "borrower"
            },
            {
                "full_name": "Property User",
                "email": "property@loanmvp.com",
                "password": "property123",
                "role": "property"
            },
            {
                "full_name": "System User",
                "email": "system@loanmvp.com",
                "password": "system123",
                "role": "system"
            },
            {
                "full_name": "Intelligence User",
                "email": "intelligence@loanmvp.com",
                "password": "intelligence123",
                "role": "intelligence"
            },
            {
                "full_name": "Executive User",
                "email": "exec@loanmvp.com",
                "password": "executive123",
                "role": "executive"
            },
            {
                "full_name": "CRM User",
                "email": "crm@loanmvp.com",
                "password": "crm123",
                "role": "crm"
            },
            {
                "full_name": "ai User",
                "email": "ai@loanmvp.com",
                "password": "ai123",
                "role": "ai"
            },
            {
                "full_name": "Compliance User",
                "email": "compliance@loanmvp.com",
                "password": "compliance123",
                "role": "compliance"
            },

        ]

        for u in users:
            user = User(
                full_name=u["full_name"],
                email=u["email"],
                password_hash=generate_password_hash(u["password"]),
                role=u["role"]
            )
            db.session.add(user)

        db.session.commit()
        print("✅ Seed users created successfully!")
        print("\n--- Default Login Accounts ---")
        for u in users:
            print(f"{u['role'].capitalize():<15} | {u['email']} | {u['password']}")

if __name__ == "__main__":
    seed_users()
