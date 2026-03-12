from LoanMVP.services.notify import notify
from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile
from LoanMVP.models.investor_models import InvestorProfile


def send_notification(loan_id, role, message):

    loan = LoanApplication.query.get(loan_id)
    if not loan:
        return

    borrower = BorrowerProfile.query.get(loan.borrower_profile_id)

    investor = None
    if getattr(loan, "investor_profile_id", None):
        investor = InvestorProfile.query.get(loan.investor_profile_id)

    notify(
        borrower=borrower,
        investor=investor,
        loan=loan,
        role=role,
        title="Loan Update",
        message=message,
        channels=["socket", "inapp"]  # optional: "email", "sms"
    )

def notify_underwriter(loan_id, message):
    send_notification(loan_id, "underwriter", message)


def notify_processor(loan_id, message):
    send_notification(loan_id, "processor", message)


def notify_loan_officer(loan_id, message):
    send_notification(loan_id, "loan_officer", message)


def notify_investor(loan_id, message):
    send_notification(loan_id, "investor", message)


def notify_borrower(loan_id, message):
    send_notification(loan_id, "borrower", message)