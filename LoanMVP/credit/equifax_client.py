import requests
import json

class EquifaxSoftPull:
    """
    Equifax Soft-Pull Credit Client
    """

    def __init__(self, api_key, api_secret, sandbox=True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = (
            "https://sandbox.api.equifax.com/v2/softpull"
            if sandbox else
            "https://api.equifax.com/v2/softpull"
        )

    def pull_credit(self, full_name, ssn, address, city, state, zip):
        url = f"{self.base_url}/credit-report"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "x-api-secret": self.api_secret
        }

        payload = {
            "consumer": {
                "fullName": full_name,
                "ssn": ssn,
                "address": {
                    "line1": address,
                    "city": city,
                    "state": state,
                    "zip": zip
                }
            }
        }

        print("Sending payload:", json.dumps(payload, indent=2))
      
        # Extract monthly debts from tradelines (if present)
        monthly_debts = 0
        tradelines = credit_json.get("tradelines", [])

       for t in tradelines:
           payment = t.get("monthlyPayment", 0)
           if payment:
               monthly_debts += float(payment)

       report.monthly_debt_total = monthly_debts


        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            return {
                "success": False,
                "error": response.text
            }

        return {
            "success": True,
            "data": response.json()
        }
