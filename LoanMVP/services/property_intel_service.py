"""
Property Intelligence Service
-----------------------------
Handles:
- Unified property resolver (Zillow → Redfin → Realtor fallback)
- AI property summary
- Property comps wrapper
"""

from LoanMVP.ai.base_ai import AIAssistant


def unified_property_resolver(address):
    """
    Placeholder for a real property resolver.
    """
    return {
        "address": address,
        "beds": 3,
        "baths": 2,
        "sqft": 1500,
        "photos": [],
        "zestimate": None,
    }


def generate_property_ai_summary(resolved):
    """
    AI summary of property details.
    """
    return assistant.generate_reply(
        f"Analyze property details: {resolved}",
        "property_ai_summary",
    )


def get_property_comps(resolved):
    """
    Placeholder for property comps.
    """
    return {
        "sales": [],
        "rentals": [],
        "airbnb": [],
    }
