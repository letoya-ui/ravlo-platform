import math

# ======================================================
# 📌 RATE ENGINE
# ======================================================
def estimate_rate(credit_score, ltv, loan_type):
    """Simple illustrative rate model."""

    base_rates = {
        "conventional": 6.25,
        "fha": 5.75,
        "va": 5.65,
        "usda": 5.60,
        "dscr": 7.50,
        "non_qm": 8.25
    }

    rate = base_rates.get(str(loan_type).lower(), 6.99)

    # Credit adjustments
    if credit_score:
        if credit_score < 620:
            rate += 1.00
        elif credit_score < 660:
            rate += 0.50
        elif credit_score < 700:
            rate += 0.25
        elif credit_score > 760:
            rate -= 0.25

    # LTV adjustments
    if ltv is not None:
        if ltv > 0.90:
            rate += 1.00
        elif ltv > 0.80:
            rate += 0.50
        elif ltv < 0.70:
            rate -= 0.25

    return round(rate, 3)


# ======================================================
# 📌 PAYMENT CALCULATION
# ======================================================
def calc_payment(amount, rate, term=30):
    """Monthly mortgage payment using amortization formula."""
    r = (rate / 100) / 12
    n = term * 12

    if r == 0:
        return round(amount / n, 2)

    return round(amount * (r * (1 + r)**n) / ((1 + r)**n - 1), 2)


# ======================================================
# 📌 DSCR CALCULATION
# ======================================================
def calc_dscr(rent, payment):
    if not payment:
        return None
    try:
        return round(rent / payment, 3)
    except:
        return None


# ======================================================
# 📌 DTI + LTV ENGINE (UNIFIED)
# ======================================================
def calculate_dti_ltv(borrower, loan, credit):
    """
    Universal DTI + LTV calculator used across:
    - Loan Officer engines
    - Processor engines
    - Underwriter engines
    - Master AI
    - Preapproval engine
    """

    # -------------------------------
    # Income
    # -------------------------------
    primary_income = float(borrower.income or 0)
    secondary_income = float(getattr(borrower, "monthly_income_secondary", 0) or 0)
    total_income = primary_income + secondary_income

    # -------------------------------
    # Housing Expense
    # -------------------------------
    housing_payment = float(getattr(borrower, "monthly_housing_payment", 0) or 0)

    # -------------------------------
    # Revolving Debts (Credit Report)
    # -------------------------------
    monthly_debts = float(getattr(credit, "monthly_debt_total", 0) or 0)

    # -------------------------------
    # Calculate DTI
    # -------------------------------
    if total_income > 0:
        front_dti = housing_payment / total_income
        back_dti = (housing_payment + monthly_debts) / total_income
    else:
        front_dti = None
        back_dti = None

    # -------------------------------
    # Calculate LTV
    # -------------------------------
    if loan and loan.amount and loan.property_value:
        try:
            ltv = float(loan.amount) / float(loan.property_value)
        except:
            ltv = None
    else:
        ltv = None

    # -------------------------------
    # Return dictionary
    # -------------------------------
    return {
        "front_end_dti": front_dti,
        "back_end_dti": back_dti,
        "ltv": ltv,
        "income_total": total_income,
        "monthly_debts": monthly_debts,
        "housing_payment": housing_payment
    }
