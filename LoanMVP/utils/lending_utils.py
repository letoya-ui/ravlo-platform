# LoanMVP/utils/lending_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Shared utilities for loan_officer, processor, underwriter, borrower, and vip
# Import from here instead of defining locally in each blueprint
# ─────────────────────────────────────────────────────────────────────────────

from datetime import datetime
from LoanMVP.extensions import db


# ── DTI / LTV ────────────────────────────────────────────────────────────────

def calculate_dti_ltv(borrower, loan, credit):
    """
    Canonical DTI/LTV calculator used across all blueprints.
    Replaces the duplicate defined in processor.py and imported
    from pricing_engine in underwriter.py and loan_officer.py.

    Returns dict with front_end_dti, back_end_dti, ltv,
    monthly_debts, income_total.
    """
    primary    = float(getattr(borrower, "income", 0) or 0)
    secondary  = float(getattr(borrower, "monthly_income_secondary", 0) or 0)
    total_income = primary + secondary

    housing_payment = float(getattr(borrower, "monthly_housing_payment", 0) or 0)
    monthly_debts   = float(getattr(credit,   "monthly_debt_total",      0) or 0)

    if total_income > 0:
        front = round(housing_payment / total_income, 4)
        back  = round((housing_payment + monthly_debts) / total_income, 4)
    else:
        front = None
        back  = None

    if loan and getattr(loan, "amount", None) and getattr(loan, "property_value", None):
        ltv = round(float(loan.amount) / float(loan.property_value), 4)
    else:
        ltv = None

    return {
        "front_end_dti": front,
        "back_end_dti":  back,
        "ltv":           ltv,
        "monthly_debts": monthly_debts,
        "income_total":  total_income,
    }


# ── Credit profile resolver ───────────────────────────────────────────────────

def get_credit_profile(borrower):
    """
    Resolves the latest credit profile regardless of whether the model
    uses .credit_profiles (loan_officer) or .credit_reports (underwriter/processor).
    Returns None if neither exists.
    """
    if borrower is None:
        return None

    if getattr(borrower, "credit_profiles", None):
        profiles = borrower.credit_profiles
        return profiles[-1] if profiles else None

    if getattr(borrower, "credit_reports", None):
        reports = borrower.credit_reports
        return reports[-1] if reports else None

    return None


# ── Notification stub ─────────────────────────────────────────────────────────

def send_notification(loan_id, recipient_role, message, sender_id=None):
    """
    Central notification dispatcher.
    Currently logs to LoanStatusEvent and can be extended to push/email/SMS.

    recipient_role: 'borrower' | 'processor' | 'underwriter' | 'loan_officer'
    """
    try:
        from LoanMVP.models.loan_models import LoanStatusEvent

        event = LoanStatusEvent(
            loan_id=loan_id,
            event_name=f"Notification → {recipient_role.title()}",
            description=message,
        )
        db.session.add(event)
        db.session.commit()
    except Exception as e:
        # Never let a notification failure crash a route
        print(f"[send_notification] failed for loan {loan_id}: {e}")


# ── Task extraction from AI output ───────────────────────────────────────────

def extract_tasks(ai_text):
    """
    Pulls lines beginning with 'TASK:' from AI-generated text.
    Returns a list of task title strings.
    """
    tasks = []
    for line in (ai_text or "").splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("TASK:"):
            task_title = stripped[5:].strip()
            if task_title:
                tasks.append(task_title)
    return tasks


def extract_and_create_tasks(ai_text, borrower, loan):
    """
    Extracts TASK: lines from AI output and persists them as Task records.
    Returns list of created task titles.
    Used by followup_ai and communication_ai in loan_officer.py
    """
    from LoanMVP.models.crm_models import Task
    from flask_login import current_user

    task_titles = extract_tasks(ai_text)
    created = []

    for title in task_titles:
        task = Task(
            borrower_id=getattr(borrower, "id", None),
            loan_id=getattr(loan, "id", None),
            assigned_to=current_user.id,
            title=title,
            status="open",
        )
        db.session.add(task)
        created.append(title)

    if created:
        db.session.commit()

    return created


# ── Document keyword detection ────────────────────────────────────────────────

_DOC_KEYWORDS = [
    "bank statement", "pay stub", "paystub", "w-2", "w2", "tax return",
    "1099", "id", "driver's license", "passport", "lease agreement",
    "purchase contract", "insurance", "scope of work", "appraisal",
    "title commitment", "entity docs", "operating agreement",
]

def detect_documents(text):
    """
    Scans AI-generated text for document keywords.
    Returns list of detected document names.
    Used by upload_call and communication_ai in loan_officer.py
    """
    found = []
    lower = (text or "").lower()
    for keyword in _DOC_KEYWORDS:
        if keyword in lower and keyword.title() not in found:
            found.append(keyword.title())
    return found


# ── Sentiment stub ────────────────────────────────────────────────────────────

def analyze_sentiment(text):
    """
    Basic keyword-based sentiment for call transcripts.
    Returns 'positive' | 'neutral' | 'negative'
    Replace with a real NLP call if needed.
    """
    lower = (text or "").lower()
    positive_words = ["great", "perfect", "approved", "ready", "excited", "yes", "definitely"]
    negative_words = ["can't", "won't", "frustrated", "denied", "problem", "issue", "no", "never"]

    pos = sum(1 for w in positive_words if w in lower)
    neg = sum(1 for w in negative_words if w in lower)

    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


# ── Pricing stubs ─────────────────────────────────────────────────────────────

def estimate_rate(credit_score, ltv, loan_type):
    """
    Simple rule-based rate estimate.
    Replace with your actual pricing engine when ready.
    """
    base = 7.5

    if credit_score:
        if credit_score >= 760:
            base -= 0.75
        elif credit_score >= 720:
            base -= 0.5
        elif credit_score >= 680:
            base -= 0.25
        elif credit_score < 620:
            base += 1.0

    if ltv:
        if ltv > 0.85:
            base += 0.5
        elif ltv > 0.80:
            base += 0.25

    type_lower = (loan_type or "").lower()
    if "dscr" in type_lower or "rental" in type_lower:
        base += 0.5
    elif "fix" in type_lower or "flip" in type_lower:
        base += 0.75
    elif "construction" in type_lower:
        base += 1.0

    return round(base, 3)


def calc_payment(loan_amount, annual_rate, term=30):
    """Monthly P&I payment."""
    if not loan_amount or not annual_rate:
        return 0.0
    monthly_rate = annual_rate / 100 / 12
    n = term * 12
    if monthly_rate == 0:
        return round(loan_amount / n, 2)
    payment = loan_amount * (monthly_rate * (1 + monthly_rate) ** n) / ((1 + monthly_rate) ** n - 1)
    return round(payment, 2)


def calc_dscr(monthly_rent, monthly_payment):
    """Debt Service Coverage Ratio."""
    if not monthly_payment or monthly_payment == 0:
        return None
    return round(float(monthly_rent or 0) / float(monthly_payment), 3)
