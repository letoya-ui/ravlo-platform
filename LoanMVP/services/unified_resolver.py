import time
import hashlib
from LoanMVP.services.rentcast_resolver import resolve_rentcast_investor_bundle
from LoanMVP.services.ai_summary import generate_property_summary

_CACHE = {}
_TTL = 60 * 60 * 6  # 6 hours


def resolve_property_unified(address: str = None, zipcode: str = None, **kwargs) -> dict:
    """
    Unified property resolver.

    Backward compatible:
      - accepts zipcode (ignored for now)
      - accepts extra kwargs from older callers without crashing
    """

    address = (address or "").strip()
    if not address:
        return {"status": "error", "provider": "rentcast", "error": "address_required", "stage": "input"}

    # ---- cache ----
    key = _ck(address)
    cached = _cache_get(key)
    if cached:
        return cached

    # ---- rentcast bundle ----
    result = resolve_rentcast_investor_bundle(address)

    if result.get("status") != "ok":
        out = {
            "status": "error",
            "provider": "rentcast",
            "error": result.get("error"),
            "stage": result.get("stage"),
        }
        _cache_set(key, out)
        return out

    prop = result.get("property") or {}
    prop["valuation"] = result.get("valuation")
    prop["rent_estimate"] = result.get("rent_estimate")
    prop["comps"] = result.get("comps")

    summary = generate_property_summary({
        "property": prop,
        "valuation": result.get("valuation"),
        "rent_estimate": result.get("rent_estimate"),
        "comps": result.get("comps"),
        "source": "rentcast",
    })

    out = {
        "status": "ok",
        "property": prop,
        "ai_summary": summary,
        "primary_source": "rentcast",
    }

    _cache_set(key, out)
    return out


def _ck(address: str) -> str:
    normalized = " ".join((address or "").strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _cache_get(key: str):
    row = _CACHE.get(key)
    if not row:
        return None
    if time.time() - row["ts"] > _TTL:
        _CACHE.pop(key, None)
        return None
    return row["val"]


def _cache_set(key: str, val):
    _CACHE[key] = {"ts": time.time(), "val": val}