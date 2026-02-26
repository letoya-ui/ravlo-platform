import time

_cache = {}
TTL_SECONDS = 60 * 10  # 10 minutes

def get_cached_property(address: str):
    key = address.strip().lower()
    entry = _cache.get(key)
    if not entry:
        return None
    if time.time() > entry["expires_at"]:
        _cache.pop(key, None)
        return None
    return entry["value"]

def set_cached_property(address: str, value: dict):
    key = address.strip().lower()
    _cache[key] = {
        "value": value,
        "expires_at": time.time() + TTL_SECONDS,
    }
