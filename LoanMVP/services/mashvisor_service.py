import requests
import os

MASHVISOR_API_KEY = os.getenv("MASHVISOR_API_KEY")

def get_investment_data(zip_code):
    url = f"https://api.mashvisor.com/v1.1/client/property/zip/{zip_code}"

    headers = {
        "x-api-key": MASHVISOR_API_KEY
    }

    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return res.json()
