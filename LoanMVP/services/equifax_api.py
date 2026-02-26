import os
import requests

class EquifaxAPI:
    def __init__(self):
        self.api_key = os.getenv("EQUIFAX_SANDBOX_KEY")
        self.endpoint = "https://api.equifax.com/personal/consumer-data-suite/v1/creditReport"

    def pull_credit(self, ssn, last_name, first_name, address, city, state, zip):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "consumer": {
                "ssn": ssn,
                "name": {"first": first_name, "last": last_name},
                "address": {"street": address, "city": city, "state": state, "zip": zip},
            }
        }
        try:
            response = requests.post(self.endpoint, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print("Equifax API Error:", e)
            return {"error": str(e)}
