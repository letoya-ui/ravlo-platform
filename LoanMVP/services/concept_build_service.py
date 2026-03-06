"""
concept_build_service.py
------------------------------------
Handles AI-powered concept generation for:
- Concept exterior render
- Draft blueprint
- Site plan

This service is called by:
POST /investor/deals/new/concept/generate
"""

import uuid
import requests
from datetime import datetime


# ============================================================
#  CONFIG
# ============================================================

AI_ENGINE_URL = "http://localhost:5002/concept"  
# Example: Your Renovation Engine or SDXL pipeline endpoint


# ============================================================
#  HELPERS
# ============================================================

def _post_json(url, payload):
    """
    Safe wrapper for POSTing JSON to the AI engine.
    """
    try:
        res = requests.post(url, json=payload, timeout=120)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return {
            "error": True,
            "message": str(e),
            "concept_image": None,
            "blueprint_image": None,
            "site_plan_image": None
        }


def _generate_filename(prefix):
    """
    Generates a unique filename for storing AI outputs.
    """
    return f"{prefix}_{uuid.uuid4().hex}.png"


# ============================================================
#  MAIN SERVICE
# ============================================================

def run_concept_build(land_image_url: str, description: str, style: str, lot_size: str = None):
    """
    Sends the user's inputs to the AI engine and returns:
    - concept_image
    - blueprint_image
    - site_plan_image

    Parameters
    ----------
    land_image_url : str
        URL of the land photo
    description : str
        User's idea description
    style : str
        Selected architectural style
    lot_size : str, optional
        Optional lot size input

    Returns
    -------
    dict
        {
            "concept_image": <url>,
            "blueprint_image": <url>,
            "site_plan_image": <url>,
            "description": <str>,
            "style": <str>,
            "lot_size": <str>
        }
    """

    payload = {
        "land_image_url": land_image_url,
        "description": description,
        "style": style,
        "lot_size": lot_size,
    }

    ai_response = _post_json(AI_ENGINE_URL, payload)

    if ai_response.get("error"):
        return ai_response

    # Expected AI engine response:
    # {
    #   "concept_image": "https://...",
    #   "blueprint_image": "https://...",
    #   "site_plan_image": "https://..."
    # }

    return {
        "concept_image": ai_response.get("concept_image"),
        "blueprint_image": ai_response.get("blueprint_image"),
        "site_plan_image": ai_response.get("site_plan_image"),
        "description": description,
        "style": style,
        "lot_size": lot_size,
        "generated_at": datetime.utcnow().isoformat()
    }
