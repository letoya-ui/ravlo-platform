"""Natural-language flyer requests -- "create me an open house flyer for
123 main st for sat at 12" -- get parsed into structured fields. Date
math (resolving "Sat" to a real calendar date) is plain Python, not
model output, so it's tested on its own without touching the network.
"""
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from LoanMVP.services.flyer_ai import FlyerRequestParseError, parse_flyer_request, resolve_event_date


def _fake_completion(payload: dict):
    message = SimpleNamespace(content=json.dumps(payload))
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


# ─── resolve_event_date ──────────────────────────────────────────────

def test_resolve_event_date_prefers_explicit_date_over_day_of_week():
    result = resolve_event_date("Monday", "2026-12-25", today=date(2026, 9, 14))
    assert result == date(2026, 12, 25)


def test_resolve_event_date_resolves_a_weekday_later_this_week():
    # Monday, Sep 14 2026 -> next Saturday is Sep 19.
    result = resolve_event_date("Saturday", None, today=date(2026, 9, 14))
    assert result == date(2026, 9, 19)


def test_resolve_event_date_rolls_over_to_next_week_when_today_matches():
    # If today itself is Saturday, "Saturday" means the *next* one, not today.
    result = resolve_event_date("Saturday", None, today=date(2026, 9, 19))
    assert result == date(2026, 9, 26)


def test_resolve_event_date_returns_none_without_any_date_info():
    assert resolve_event_date(None, None, today=date(2026, 9, 14)) is None


def test_resolve_event_date_ignores_unparseable_explicit_date():
    result = resolve_event_date("Saturday", "not-a-date", today=date(2026, 9, 14))
    assert result == date(2026, 9, 19)


# ─── parse_flyer_request ─────────────────────────────────────────────

def test_parse_flyer_request_normalizes_fields():
    payload = {
        "flyer_type": "OPEN_HOUSE",
        "address": "123 Main St",
        "city": None,
        "state": None,
        "zip": None,
        "day_of_week": "Saturday",
        "explicit_date": None,
        "time": "12:00 PM",
        "time_end": None,
    }
    with patch("LoanMVP.services.flyer_ai.client.chat.completions.create", return_value=_fake_completion(payload)):
        result = parse_flyer_request("create me an open house flyer for 123 main st for sat at 12")

    assert result["flyer_type"] == "open_house"
    assert result["address"] == "123 Main St"
    assert result["day_of_week"] == "Saturday"
    assert result["time"] == "12:00 PM"
    assert result["city"] is None


def test_parse_flyer_request_raises_on_api_failure():
    with patch("LoanMVP.services.flyer_ai.client.chat.completions.create", side_effect=RuntimeError("boom")):
        with pytest.raises(FlyerRequestParseError):
            parse_flyer_request("open house flyer for 123 main st")
