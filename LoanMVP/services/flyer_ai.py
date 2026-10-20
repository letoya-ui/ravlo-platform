"""Natural-language flyer requests -- "create me an open house flyer for
123 Main St for Sat at 12" -- parsed into structured fields a flyer
builder can use. The model only extracts entities; date math (resolving
"Sat" to an actual calendar date) is done in plain Python so a model
arithmetic slip never puts the wrong day on a flyer.
"""
import json
import os
from datetime import date, timedelta

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class FlyerRequestParseError(Exception):
    pass


def resolve_event_date(day_of_week, explicit_date, today=None):
    """Return a date for the requested event, or None if neither a
    weekday name nor an explicit date was given. A bare weekday name
    always resolves to its next upcoming occurrence -- today counts as
    "next week", not "today" -- since that's how people actually mean
    it when scheduling an open house."""
    today = today or date.today()
    if explicit_date:
        try:
            return date.fromisoformat(explicit_date)
        except (TypeError, ValueError):
            pass
    if day_of_week:
        try:
            target = _WEEKDAYS.index(day_of_week.strip().lower())
        except (AttributeError, ValueError):
            return None
        delta = (target - today.weekday()) % 7
        delta = delta or 7
        return today + timedelta(days=delta)
    return None


def parse_flyer_request(text: str) -> dict:
    """Extract structured flyer fields from a freeform request like
    "create me an open house flyer for 123 main st for sat at 12".
    Every field the model couldn't find comes back None. Raises
    FlyerRequestParseError if the model call itself fails."""
    prompt = f"""
Extract flyer details from this real estate partner's request. Return ONLY
a JSON object with these keys:
- flyer_type: one of "open_house", "just_listed", or "business"
- address: street address only, e.g. "123 Main St" (null if not given)
- city: null if not given
- state: null if not given
- zip: null if not given
- day_of_week: the full weekday name if one was mentioned (e.g. "Saturday"),
  else null. Do NOT compute an actual date yourself.
- explicit_date: an ISO date "YYYY-MM-DD" ONLY if the user gave an actual
  calendar date (e.g. "September 20th"), else null.
- time: the event start time normalized like "12:00 PM". A bare hour under
  8 with no AM/PM given should be assumed PM (open houses aren't held at
  1 AM). Null if no time was given.
- time_end: the event end time if a range was given (e.g. "12 to 2" means
  "2:00 PM"), else null.

Request: "{text}"
""".strip()

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You extract structured real estate flyer details as JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        raw = completion.choices[0].message.content or "{}"
        obj = json.loads(raw)
    except Exception as exc:
        raise FlyerRequestParseError(str(exc)) from exc

    return {
        "flyer_type": (obj.get("flyer_type") or "just_listed").strip().lower(),
        "address": (obj.get("address") or "").strip() or None,
        "city": (obj.get("city") or "").strip() or None,
        "state": (obj.get("state") or "").strip() or None,
        "zip": (obj.get("zip") or "").strip() or None,
        "day_of_week": (obj.get("day_of_week") or "").strip() or None,
        "explicit_date": (obj.get("explicit_date") or "").strip() or None,
        "time": (obj.get("time") or "").strip() or None,
        "time_end": (obj.get("time_end") or "").strip() or None,
    }
