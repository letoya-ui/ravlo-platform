import os
import requests
import logging

from LoanMVP.utils.safe_http import safe_call

class EquifaxAPI:
    def __init__(self):
        self.api_key = os.getenv("EQUIFAX_SANDBOX_KEY")
        self.endpoint = "https://api.equifax.com/personal/consumer-data-suite/v1/creditReport"

    def pull_credit(self, borrower):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        full_name = (getattr(borrower, "full_name", "") or "").strip()
        name_parts = full_name.split(" ", 1)
        first = name_parts[0] if name_parts else ""
        last = name_parts[1] if len(name_parts) > 1 else ""

        payload = {
            "consumer": {
                "ssn": getattr(borrower, "ssn", None),
                "name": {
                    "first": first,
                    "last": last,
                },
                "address": {
                    "street": getattr(borrower, "address", None),
                    "city": getattr(borrower, "city", None),
                    "state": getattr(borrower, "state", None),
                    "zip": getattr(borrower, "zip", None),
                }
            }
        }

        try:
            response = safe_call(
                requests.post,
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=20
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logging.error(f"Equifax API Error: {e}")
            return {"error": str(e)}
