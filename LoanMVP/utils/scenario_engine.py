from utils.payment_engine import (
    calculate_monthly_payment,
    calculate_taxes,
    calculate_insurance,
    calculate_mortgage_insurance
)

class LoanScenario:

    def __init__(self, title, loan_amount, rate, term, property_value):
        self.title = title
        self.loan_amount = float(loan_amount or 0)
        self.rate = float(rate or 0)
        self.term = int(term or 360)
        self.property_value = float(property_value or 0)

        # Calculate
        self.p_and_i = calculate_monthly_payment(
            self.loan_amount, self.rate, self.term
        )
        self.taxes = calculate_taxes(self.property_value)
        self.insurance = calculate_insurance(self.property_value)
        self.pmi = calculate_mortgage_insurance(
            self.loan_amount, self.property_value
        )

        self.total_payment = self.p_and_i + self.taxes + self.insurance + self.pmi

        # LTV
        if self.property_value > 0:
            self.ltv = round((self.loan_amount / self.property_value) * 100, 2)
        else:
            self.ltv = None

    def to_dict(self):
        return {
            "title": self.title,
            "loan_amount": self.loan_amount,
            "rate": self.rate,
            "term": self.term,
            "p_and_i": self.p_and_i,
            "taxes": self.taxes,
            "insurance": self.insurance,
            "pmi": self.pmi,
            "total_payment": self.total_payment,
            "ltv": self.ltv
        }
