import os
import requests
import logging

class EquifaxAPI:
    def __init__(self):
        self.api_key = os.getenv("EQUIFAX_SANDBOX_KEY")
        self.endpoint = "https://api.equifax.com/personal/consumer-data-suite/v1/creditReport"

    def pull_credit(self, borrower):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "consumer": {
                "ssn": borrower.ssn,
                "name": {
                    "first": borrower.first_name,
                    "last": borrower.last_name
                },
                "address": {
                    "street": borrower.address,
                    "city": borrower.city,
                    "state": borrower.state,
                    "zip": borrower.zip_code
                }
            }
        }

        try:
            response = requests.post(
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
