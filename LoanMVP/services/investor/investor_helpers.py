from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation


def _first_non_empty(*values):
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _clean_str(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _clean_num(value):
    if value in (None, "", "None"):
        return None
    try:
        if isinstance(value, str):
            value = value.replace("$", "").replace(",", "").strip()
        return float(value)
    except Exception:
        return None


def _clean_int(value):
    num = _clean_num(value)
    if num is None:
        return None
    try:
        return int(round(num))
    except Exception:
        return None


def _safe_float(value):
    try:
        if value in (None, "", "None"):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        return float(str(value).replace("$", "").replace(",", "").strip())
    except Exception:
        return None


def _safe_int(value):
    try:
        num = _safe_float(value)
        return int(round(num)) if num is not None else None
    except Exception:
        return None


def _safe_json_list(value):
    if isinstance(value, list):
        return value
    return []


def _safe_json_loads_local(value, default=None):
    default = default if default is not None else {}
    if not value:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def safe_json_loads(data, default=None):
    if default is None:
        default = {}
    if not data:
        return default
    if isinstance(data, (dict, list)):
        return data
    try:
        return json.loads(data)
    except Exception:
        return default


def _json_default():
    return {}


def _normalize_int(value):
    try:
        return int(value) if value not in (None, "", "None") else None
    except Exception:
        return None


def _normalize_percentage(value):
    if value in (None, "", "None"):
        return None
    try:
        number = float(str(value).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if number > 1:
        number = number / 100.0
    return number


def safe_float(value, default=0.0):
    try:
        if value in (None, "", "None"):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def safe_int(value, default=0, min_v=None, max_v=None):
    try:
        x = int(value)
        if min_v is not None:
            x = max(min_v, x)
        if max_v is not None:
            x = min(max_v, x)
        return x
    except (TypeError, ValueError):
        return default


def safe_decimal(value, default="0.00"):
    try:
        if value in (None, "", "None"):
            return Decimal(default)
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def fmt_money(value, blank="—"):
    try:
        if value in (None, "", "None"):
            return blank
        return f"${Decimal(str(value)):,.2f}"
    except Exception:
        return blank


def split_ids(csv_string: str):
    if not csv_string:
        return []

    parts = csv_string.replace(";", ",").split(",")
    cleaned = []

    for p in parts:
        p = p.strip()
        if not p:
            continue
        try:
            cleaned.append(int(p))
        except Exception:
            continue

    seen = set()
    result = []
    for i in cleaned:
        if i not in seen:
            seen.add(i)
            result.append(i)

    return result