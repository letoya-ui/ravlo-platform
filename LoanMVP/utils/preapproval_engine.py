import math

class PreapprovalEngine:

    def __init__(self, borrower, loan, credit):
        self.borrower = borrower
        self.loan = loan
        self.credit = credit

    # ---------------------------------------------------------
    # Debt-to-Income (DTI)
    # ---------------------------------------------------------
    def calc_dti(self):
        # Income
        income = float(self.borrower.income or 0)
        income2 = float(getattr(self.borrower, "monthly_income_secondary", 0) or 0)
        total_income = income + income2

        # Housing payment
        housing = getattr(self.borrower, "monthly_housing_payment", 0) or 0
        housing = float(housing)

        # Total debts
        debts = float(self.credit.monthly_debt_total if self.credit else 0)

        if total_income <= 0:
            return None, None

        fe = housing / total_income
        be = (housing + debts) / total_income
        return round(fe, 3), round(be, 3)

    # ---------------------------------------------------------
    # Loan-to-Value (LTV)
    # ---------------------------------------------------------
    def calc_ltv(self):
        if not self.loan or not self.loan.property_value:
            return None
        try:
            return round(self.loan.amount / self.loan.property_value, 4)
        except Exception:
            return None

    # ---------------------------------------------------------
    # Program Fit Logic
    # ---------------------------------------------------------
    def program_fit(self):
        cs = self.credit.credit_score if self.credit else 660
        ltv = self.calc_ltv()
        fe, be = self.calc_dti()

        programs = []

        # ---- FHA ----
        if ltv is not None and cs >= 580 and ltv <= 0.965:
            if be is not None and be <= 0.50:
                programs.append("FHA")

        # ---- Conventional ----
        if ltv is not None and cs >= 620 and ltv <= 0.97:
            if be is not None and be <= 0.45:
                programs.append("Conventional")

        # ---- VA ----
        if getattr(self.borrower, "veteran_status", False):
            if be is not None and be <= 0.55:
                programs.append("VA")

        # ---- DSCR ----
        if self.loan.loan_type and self.loan.loan_type.lower() == "dscr":
            rent = getattr(self.loan, "monthly_rent", 0)
            if rent > 0 and getattr(self.loan, "estimated_payment", 0) > 0:
                dscr = rent / self.loan.estimated_payment
                if dscr >= 1.0:
                    programs.append("DSCR")

        # ---- Non-QM ----
        if cs >= 500:
            programs.append("Non-QM")

        return programs

    # ---------------------------------------------------------
    # Red Flags
    # ---------------------------------------------------------
    def red_flags(self):
        flags = []
        fe, be = self.calc_dti()
        ltv = self.calc_ltv()
        cs = self.credit.credit_score if self.credit else 660

        if cs < 580:
            flags.append("Low credit score")

        if be is not None and be > 0.55:
            flags.append("High back-end DTI")

        if ltv is not None and ltv > 0.97:
            flags.append("LTV exceeds program limits")

        if not self.borrower.income:
            flags.append("Missing income documentation")

        if (
            self.loan.loan_type.lower() == "dscr"
            and getattr(self.loan, "monthly_rent", 0) <= 0
        ):
            flags.append("Missing rent / DSCR calculation")

        return flags

    # ---------------------------------------------------------
    # Required Conditions
    # ---------------------------------------------------------
    def required_conditions(self):
        c = []

        if not self.borrower.income:
            c.append("Provide income documentation (W-2, paystubs, or bank statements).")

        if not getattr(self.borrower, "employment_name", None):
            c.append("Employment verification required.")

        if not getattr(self.loan, "property_value", None):
            c.append("Property valuation / appraisal needed.")

        if not self.credit:
            c.append("Credit report required.")

        return c
