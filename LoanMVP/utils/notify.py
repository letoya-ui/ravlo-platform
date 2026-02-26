from LoanMVP.services.notify import notify
from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile

def send_notification(loan_id, role, message):
    loan = LoanApplication.query.get(loan_id)
    borrower = BorrowerProfile.query.get(loan.borrower_profile_id)

    notify(
        borrower=borrower,
        loan=loan,
        role=role,
        title="Loan Update",
        message=message,
        channels=["socket", "inapp"]  # you can add "sms", "email"
    )

def notify_underwriter(loan_id, message):
    send_notification(loan_id, "underwriter", message)
