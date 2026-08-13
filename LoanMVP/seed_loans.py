from LoanMVP.extensions import db
from LoanMVP.models.user_model import User
from LoanMVP.models.loan_models import BorrowerProfile, LoanApplication, LoanQuote
from LoanMVP.models.document_models import LoanDocument
from LoanMVP.models.underwriter_model import UnderwritingCondition, ConditionRequest, UnderwriterProfile
from sqlalchemy import text
from LoanMVP.models.loan_officer_model import LoanOfficerProfile
from LoanMVP.models.processor_model import ProcessorProfile
app = create_app()

with app.app_context():
    officer_user = User.query.filter_by(email="officer@loanmvp.com").first()
    borrower_user = User.query.filter_by(email="borrower@loanmvp.com").first()

# --- 2️⃣ PROFILES ---

# Loan Officer Profile
loan_officer_profile = LoanOfficerProfile(
    user_id=User.id,
    name="Jonathan Fultz",
    email="officer@loanmvp.com",
    phone="555-123-6789",
    region="Caughman Mason Loan Services HQ",
    joined_at=datetime.now(timezone.utc),
)
db.session.add(loan_officer_profile)
db.session.commit()
print(f"🏦 Loan Officer Profile (ID={loan_officer_profile.id})")

# Processor Profile
processor_profile = ProcessorProfile(
    user_id=processor.id,
    full_name="Alex Rivera",
    email="processor@loanmvp.com",
    department="Processing",
    phone="555-222-3456",
    created_at=datetime.now(timezone.utc),
)
db.session.add(processor_profile)
db.session.commit()
print(f"📂 Processor Profile (ID={processor_profile.id})")

# Underwriter Profile
underwriter_profile = UnderwriterProfile(
    user_id=underwriter.id,
    full_name="Letoya Washington",
    email="underwriter@loanmvp.com",
    phone="555-444-7777",
    department="Underwriting",
    created_at=datetime.now(timezone.utc),
)
db.session.add(underwriter_profile)
db.session.commit()
print(f"📋 Underwriter Profile (ID={underwriter_profile.id})")


# Borrower Profile
borrower_profile = BorrowerProfile(
    user_id=borrower_user.id,
    full_name="Letoya Washington",
    email="borrower@loanmvp.com",
    phone="555-987-6543",
    address="158 Whitlock Rd",
    city="Otisville",
    state="NY",
    zip="10963",
    employer_name="Caughman Mason Realty Group",
    income=98000.00,
    credit_score=720,
    created_at=datetime.now(timezone.utc),
)
db.session.add(borrower_profile)
db.session.commit()
print(f"🏠 Borrower Profile (ID={borrower_profile.id})")


# --- 3️⃣ LOAN APPLICATION ---
loan = LoanApplication(
    borrower_profile_id=borrower_profile.id,
    loan_officer_id=loan_officer_profile.id,
    processor_id=processor_profile.id,
    underwriter_id=underwriter_profile.id,
    lender_name="Caughman Mason Loan Services",
    amount=350000,
    loan_type="Bridge",
    term_months=12,
    rate=8.5,
    ltv=70.0,
    property_value=500000,
    property_address="158 Whitlock Rd, Otisville, NY 10963",
    ai_summary="Initial underwriting assessment indicates strong borrower with stable income and moderate credit.",
    status="Pending",
    risk_score=0.23,
    created_at=datetime.now(timezone.utc),

)
db.session.add(loan)
db.session.commit()
print(f"💼 Loan Application (ID={loan.id})")


# --- 4️⃣ LOAN QUOTE ---
quote = LoanQuote(
    borrower_profile_id=borrower_profile.id,
    loan_application_id=loan.id,
    lender_name="Prestige Pointe Lending",
    rate=8.25,
    max_ltv=75.0,
    term_months=12,
    loan_amount=350000,
    loan_type="Bridge",
    property_address="158 Whitlock Rd, Otisville, NY 10963",
    status="offered",
    created_at=datetime.now(timezone.utc),
)
db.session.add(quote)
db.session.commit()
print(f"💰 Loan Quote (ID={quote.id})")


# --- 5️⃣ DOCUMENTS ---
docs = [
    ("bank_statements.pdf", "/uploads/borrower_docs/bank_statements.pdf"),
    ("tax_returns.pdf", "/uploads/borrower_docs/tax_returns.pdf"),
]

for name, path in docs:
    doc = LoanDocument(
        borrower_profile_id=borrower_profile.id,
        loan_id=loan.id,
        file_name=name,
        file_path=path,
        status="Pending",
        uploaded_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(doc)

db.session.commit()
print("📎 Loan Documents created.")


# --- 6️⃣ UNDERWRITING CONDITIONS ---
condition = UnderwritingCondition(
    loan_id=loan.id,
    borrower_profile_id=borrower_profile.id,
    condition_type="Income Verification",
    status="Pending",
    notes="Verify income and employer prior to conditional approval.",
    created_at=datetime.now(timezone.utc),
)
db.session.add(condition)
db.session.commit()
print("📋 Underwriting Condition added.")


# --- 7️⃣ REQUEST UNDERWRITING ---
request = ConditionRequest(
    loan_id=loan.id,
    borrower_profile_id=borrower_profile.id,
    document_name="Underwriting Review Form",
    requested_by=loan_officer.id,
    status="Open",
    notes="Request full underwriting review for bridge loan scenario.",
    created_at=datetime.now(timezone.utc),
)
db.session.add(request)
db.session.commit()
print("🧾 Underwriting Request logged.")


print("\n🎉 LoanMVP Database seeded successfully! 🚀")
