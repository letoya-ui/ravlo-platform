def calculate_monthly_payment(loan_amount, annual_rate, term_months):
    """Calculate fixed P&I mortgage payment."""
    if not loan_amount or not annual_rate or not term_months:
        return 0

    P = float(loan_amount)
    r = float(annual_rate) / 100 / 12   # monthly interest rate
    n = int(term_months)

    if r == 0:
        return P / n  # no interest loan

    monthly_payment = (P * r) / (1 - (1 + r) ** -n)
    return round(monthly_payment, 2)


def calculate_taxes(property_value, tax_rate=1.2):
    """Property taxes as a percent (default 1.2%)."""
    if not property_value:
        return 0
    return round((float(property_value) * (tax_rate / 100)) / 12, 2)


def calculate_insurance(property_value, insurance_rate=0.35):
    """Annual homeowners insurance estimate."""
    if not property_value:
        return 0
    return round((float(property_value) * (insurance_rate / 100)) / 12, 2)


def calculate_mortgage_insurance(loan_amount, property_value, rate=0.55):
    """PMI if LTV > 80%."""
    if not loan_amount or not property_value:
        return 0

    ltv = float(loan_amount) / float(property_value)

    if ltv <= 0.80:
        return 0  # no PMI

    return round((float(loan_amount) * (rate / 100)) / 12, 2)
