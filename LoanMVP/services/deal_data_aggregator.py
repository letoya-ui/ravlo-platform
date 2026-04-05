from services.attom_service import get_property_data
from services.mashvisor_service import get_investment_data

def build_deal_profile(address, city, state, zip_code):
    attom = get_property_data(address, city, state, zip_code)
    mashvisor = get_investment_data(zip_code)

    deal = {
        "address": address,
        "price": attom.get("property", {}).get("assessment", {}).get("market", {}).get("mktttlvalue"),
        "beds": attom.get("property", {}).get("building", {}).get("rooms", {}).get("beds"),
        "baths": attom.get("property", {}).get("building", {}).get("rooms", {}).get("bathstotal"),
        "sqft": attom.get("property", {}).get("building", {}).get("size", {}).get("universalsize"),

        "rent_estimate": mashvisor.get("traditional_rent"),
        "airbnb_estimate": mashvisor.get("airbnb_rent"),
        "cap_rate": mashvisor.get("cap_rate"),
    }

    return deal
