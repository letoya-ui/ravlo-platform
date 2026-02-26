import requests
import os

class BaseLenderAPI:
    """Base class for all lender API integrations."""
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("LENDER_API_KEY")

    def _get(self, url, params=None, headers=None):
        try:
            res = requests.get(url, params=params, headers=headers, timeout=10)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"[API Error] {url}: {e}")
            return {"error": str(e)}

    def _post(self, url, payload=None, headers=None):
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"[API Error] {url}: {e}")
            return {"error": str(e)}


# ===============================
# 🏦 Roc Capital API
# ===============================
class RocCapitalAPI(BaseLenderAPI):
    BASE_URL = "https://api.roccapital.com/v1/quotes"

    def get_quote(self, loan_amount, ltv, property_type, state):
        payload = {
            "loan_amount": loan_amount,
            "ltv": ltv,
            "property_type": property_type,
            "state": state
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        # Simulated response until live API key available
        return {
            "lender": "Roc Capital",
            "rate": 7.25,
            "ltv": ltv,
            "term": "12 months",
            "program": "Fix & Flip",
            "estimated_payment": round((loan_amount * 0.0725) / 12, 2)
        }


# ===============================
# 🏢 Lima One API
# ===============================
class LimaOneAPI(BaseLenderAPI):
    BASE_URL = "https://api.limaone.com/loans/quote"

    def get_quote(self, loan_amount, ltv, property_type, state):
        return {
            "lender": "Lima One Capital",
            "rate": 7.75,
            "ltv": ltv,
            "term": "24 months",
            "program": "Rental30 DSCR",
            "estimated_payment": round((loan_amount * 0.0775) / 12, 2)
        }


# ===============================
# 💰 New Silver API
# ===============================
class NewSilverAPI(BaseLenderAPI):
    BASE_URL = "https://api.newsilver.com/v1/quote"

    def get_quote(self, loan_amount, ltv, property_type, state):
        return {
            "lender": "New Silver",
            "rate": 8.15,
            "ltv": ltv,
            "term": "12 months",
            "program": "Bridge Loan",
            "estimated_payment": round((loan_amount * 0.0815) / 12, 2)
        }


# ===============================
# 🏗️ Lev Capital API
# ===============================
class LevCapitalAPI(BaseLenderAPI):
    BASE_URL = "https://api.lev.co/v1/loan_quote"

    def get_quote(self, loan_amount, ltv, property_type, state):
        return {
            "lender": "Lev Capital",
            "rate": 6.95,
            "ltv": ltv,
            "term": "36 months",
            "program": "Ground-Up Construction",
            "estimated_payment": round((loan_amount * 0.0695) / 12, 2)
        }
