"""Auto-discovery of public procurement bid opportunities.

Pluggable adapters fetch open solicitations from public sources, normalize
them to a common shape, and the orchestrator writes new ones into
``bid_suggestions`` (deduped by ``external_ref``) so opportunities surface on
the construction dashboard without anyone manually searching.

Ships a SAM.gov adapter today (federal Contract Opportunities API,
https://open.gsa.gov/api/get-opportunities-public-api/). Add DemandStar or a
portal scraper by writing another ``BidSource`` subclass and listing it in
``default_sources()``.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
import os

from flask import current_app

from LoanMVP.extensions import db
from LoanMVP.models.contractor_models import BidSuggestion
from LoanMVP.utils.safe_http import safe_call

# ── Construction relevance filters ──────────────────────────────────────────
# NAICS codes that map to the kind of work Caughman Mason Construction bids.
CONSTRUCTION_NAICS = [
    "236118",  # Residential remodelers
    "236220",  # Commercial & institutional building construction
    "238190",  # Other foundation, structure & building exterior
    "238910",  # Site preparation (demolition, excavation)
    "562910",  # Remediation / environmental cleanup (demo & abatement)
]

# Applied to every fetched record so we only keep constructiony, Tampa-area
# work regardless of what a given source returns.
KEYWORDS = [
    "demo", "demolition", "renovat", "remodel", "construct", "repair",
    "rehab", "build", "general contract", "roof", "concrete", "site work",
    "site prep", "grading", "clean out", "cleanout", "turnover", "iron",
    "weld", "structural", "maintenance", "restoration", "abatement", "paint",
]
TAMPA_AREA = [
    "tampa", "hillsborough", "pinellas", "pasco", "clearwater",
    "st. petersburg", "st petersburg", "brandon", "riverview", "plant city",
]

DEFAULT_LOOKBACK_DAYS = 30
DISCOVERY_THROTTLE_HOURS = 6


@dataclass
class DiscoveredBid:
    """Normalized opportunity produced by a source adapter."""
    external_ref: str            # stable per-source id, e.g. "samgov:<noticeId>"
    title: str
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    due_date: Optional[datetime] = None
    estimated_value: Optional[float] = None
    contact: Optional[str] = None
    summary: Optional[str] = None
    naics: Optional[str] = None
    state: Optional[str] = None


def _matches_construction(bid: "DiscoveredBid") -> bool:
    """Keep the bid only if it looks like Tampa-area construction work."""
    if bid.naics and bid.naics in CONSTRUCTION_NAICS:
        naics_ok = True
    else:
        naics_ok = False

    haystack = " ".join(
        p for p in (bid.title, bid.category, bid.summary) if p
    ).lower()
    keyword_ok = any(k in haystack for k in KEYWORDS)

    loc = " ".join(p for p in (bid.location, bid.state) if p).lower()
    # Statewide FL is acceptable; otherwise require a Tampa-area locale.
    geo_ok = ("fl" in loc.split() or "florida" in loc
              or any(c in loc for c in TAMPA_AREA))

    return (naics_ok or keyword_ok) and geo_ok


# ── Source adapters ──────────────────────────────────────────────────────────
class BidSource:
    name = "base"

    def available(self) -> bool:
        """Whether this source is configured (e.g. has an API key)."""
        return True

    def fetch(self) -> List[DiscoveredBid]:
        raise NotImplementedError


class SamGovBidSource(BidSource):
    """Federal Contract Opportunities via the SAM.gov public API."""
    name = "samgov"
    API_URL = "https://api.sam.gov/opportunities/v2/search"

    def __init__(self, lookback_days: int = DEFAULT_LOOKBACK_DAYS):
        self.api_key = (os.getenv("SAM_GOV_API_KEY") or "").strip()
        self.lookback_days = lookback_days

    def available(self) -> bool:
        return bool(self.api_key)

    def fetch(self) -> List[DiscoveredBid]:
        import requests

        now = datetime.utcnow()
        params = {
            "api_key": self.api_key,
            "postedFrom": (now - timedelta(days=self.lookback_days)).strftime("%m/%d/%Y"),
            "postedTo": now.strftime("%m/%d/%Y"),
            "ptype": "o,p,k",   # solicitation, presolicitation, combined synopsis
            "state": "FL",      # place-of-performance state
            "limit": "100",
        }
        resp = safe_call(requests.get, self.API_URL, params=params, timeout=25)
        resp.raise_for_status()
        payload = resp.json() or {}
        return [
            b for b in (self._normalize(rec) for rec in payload.get("opportunitiesData", []) or [])
            if b is not None
        ]

    @staticmethod
    def _normalize(rec: dict) -> Optional["DiscoveredBid"]:
        notice_id = rec.get("noticeId") or rec.get("solicitationNumber")
        title = (rec.get("title") or "").strip()
        if not notice_id or not title:
            return None

        pop = rec.get("placeOfPerformance") or {}
        city = ((pop.get("city") or {}).get("name") or "").strip()
        state = ((pop.get("state") or {}).get("code") or "").strip()
        location = ", ".join(p for p in (city, state) if p) or None

        contact = None
        pocs = rec.get("pointOfContact") or []
        if pocs:
            poc = pocs[0] or {}
            contact = " · ".join(
                p for p in (poc.get("fullName"), poc.get("email"), poc.get("phone")) if p
            ) or None

        due = SamGovBidSource._parse_dt(rec.get("responseDeadLine"))
        agency = (rec.get("fullParentPathName") or "").split(".")[0].strip() or None
        naics = (rec.get("naicsCode") or "").strip() or None
        summary_bits = [b for b in (
            rec.get("type"),
            f"NAICS {naics}" if naics else None,
            agency,
        ) if b]

        return DiscoveredBid(
            external_ref=f"samgov:{notice_id}",
            title=title,
            source_name="SAM.gov" + (f" — {agency}" if agency else ""),
            source_url=rec.get("uiLink"),
            category=(rec.get("classificationCode") or naics or None),
            location=location,
            due_date=due,
            contact=contact,
            summary=" · ".join(summary_bits) or None,
            naics=naics,
            state=state,
        )

    @staticmethod
    def _parse_dt(value) -> Optional[datetime]:
        if not value:
            return None
        raw = str(value).strip().replace("Z", "")
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.replace(tzinfo=None)
            except ValueError:
                continue
        return None


def default_sources() -> List[BidSource]:
    return [SamGovBidSource()]


def any_source_available(sources: Optional[List[BidSource]] = None) -> bool:
    return any(s.available() for s in (sources or default_sources()))


# ── Orchestration ────────────────────────────────────────────────────────────
def discovery_is_stale(partner, throttle_hours: int = DISCOVERY_THROTTLE_HOURS) -> bool:
    """True if we haven't auto-imported for this partner recently."""
    latest = (
        BidSuggestion.query
        .filter(BidSuggestion.partner_id == partner.id)
        .filter(BidSuggestion.origin != "manual")
        .order_by(BidSuggestion.created_at.desc())
        .first()
    )
    if latest is None or latest.created_at is None:
        return True
    return latest.created_at < datetime.utcnow() - timedelta(hours=throttle_hours)


def run_bid_discovery(partner, sources: Optional[List[BidSource]] = None) -> dict:
    """Fetch from every available source and insert new bid suggestions.

    Idempotent: an opportunity already stored for this partner (matched by
    ``external_ref``) is skipped, so repeated runs never create duplicates.
    Returns a summary ``{"added": int, "by_source": {...}, "errors": {...}}``.
    """
    sources = sources or default_sources()
    added = 0
    by_source: dict = {}
    errors: dict = {}

    for source in sources:
        if not source.available():
            continue
        try:
            bids = source.fetch()
        except Exception as exc:  # network / API failures must not break the page
            current_app.logger.warning("[bid_discovery] %s fetch failed: %s", source.name, exc)
            errors[source.name] = str(exc)
            continue

        source_added = 0
        for bid in bids:
            if not _matches_construction(bid):
                continue
            exists = (
                BidSuggestion.query
                .filter_by(partner_id=partner.id, external_ref=bid.external_ref)
                .first()
            )
            if exists:
                continue
            db.session.add(BidSuggestion(
                partner_id      = partner.id,
                title           = bid.title[:255],
                category        = (bid.category or None),
                source_name     = bid.source_name,
                source_url      = bid.source_url,
                location        = bid.location,
                due_date        = bid.due_date,
                estimated_value = bid.estimated_value,
                contact         = bid.contact,
                summary         = bid.summary,
                status          = "active",
                origin          = source.name,
                external_ref    = bid.external_ref,
            ))
            source_added += 1

        by_source[source.name] = source_added
        added += source_added

    if added:
        db.session.commit()
    else:
        db.session.rollback()

    return {"added": added, "by_source": by_source, "errors": errors}


def maybe_run_bid_discovery(partner, sources: Optional[List[BidSource]] = None) -> dict:
    """Run discovery on page load, but only when a source is configured and
    the throttle window has elapsed. Never raises."""
    try:
        sources = sources or default_sources()
        if not any_source_available(sources):
            return {"added": 0, "by_source": {}, "errors": {}, "skipped": "no_source"}
        if not discovery_is_stale(partner):
            return {"added": 0, "by_source": {}, "errors": {}, "skipped": "throttled"}
        return run_bid_discovery(partner, sources)
    except Exception as exc:
        current_app.logger.warning("[bid_discovery] maybe_run failed: %s", exc)
        try:
            db.session.rollback()
        except Exception:
            pass
        return {"added": 0, "by_source": {}, "errors": {"_": str(exc)}}
