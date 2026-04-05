import requests
import os

ATTOM_API_KEY = os.getenv("ATTOM_API_KEY")

def get_property_data(address, city, state, zip_code):
    url = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/detail"

    headers = {
        "apikey": ATTOM_API_KEY
    }

    params = {
        "address": address,
        "city": city,
        "state": state
    }

    res = requests.get(url, headers=headers, params=params)
    res.raise_for_status()
    return res.json()
