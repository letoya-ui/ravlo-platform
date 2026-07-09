"""Portfolio AI: aggregate summary across an investor's whole tracked deal
portfolio — total value/ARV, aggregate projected ROI, and risk flags rolled
up across every deal.

Mirrors borrower_ai_service.py's pattern: a real LLM call (Claude) with a
deterministic, non-LLM template fallback so the feature never hard-fails.
"""

from __future__ import annotations

from LoanMVP.models.borrowers import Deal
from LoanMVP.services.llm_studio_service import claude_portfolio_analysis


def _query_raw(user_id):
    """DB read scoped to this investor's own deals. Untestable without an
    app/DB context, kept separate from the pure shaping logic in
    _shape_context. Reuses the exact same query as command_center()."""
    deals = (
        Deal.query
        .filter_by(user_id=user_id)
        .order_by(Deal.updated_at.desc())
        .all()
    )
    return {"deals": deals}


def _deal_label(deal):
    """Best-effort human label for a deal: title -> address -> 'Deal #<id>'."""
    return deal.title or deal.address or f"Deal #{deal.id}"


def _deal_risk_flags(deal):
    """Replicates run_analysis()'s inline per-deal risk-flag rules
    (investor_routes.py ~line 6070), tagged with which deal they belong to.
    Field access is duck-typed (works with SimpleNamespace in tests)."""
    label = _deal_label(deal)
    purchase_price = deal.purchase_price or 0
    arv = deal.arv or 0
    rehab_cost = deal.rehab_cost or 0
    estimated_rent = deal.estimated_rent or 0
    strategy = (deal.strategy or "").strip().lower()

    flags = []

    if not (arv and purchase_price and float(arv) > float(purchase_price)):
        flags.append(f"{label}: ARV needs validation or is not above purchase price.")

    if not estimated_rent and strategy in ("rental", "airbnb"):
        flags.append(f"{label}: rental strategy selected without rent support.")

    if rehab_cost and purchase_price:
        rehab_ratio = float(rehab_cost) / max(float(purchase_price), 1)
        if rehab_ratio > 0.5:
            flags.append(f"{label}: rehab cost exceeds 50% of purchase price.")

    return flags


def _shape_context(deals) -> dict:
    """Pure function: plain-primitive dict in/out, no DB/app context needed.
    Duck-typed on attributes so SimpleNamespace stand-ins work in tests."""
    deals = deals or []

    if not deals:
        return {
            "has_deals": False,
            "total_deals": 0,
        }

    total_purchase_price = sum((d.purchase_price or 0) for d in deals)
    total_arv = sum((d.arv or 0) for d in deals)
    total_rehab_cost = sum((d.rehab_cost or 0) for d in deals)
    total_project_cost = total_purchase_price + total_rehab_cost
    total_profit = total_arv - total_project_cost
    portfolio_roi_percent = (
        round((total_profit / total_project_cost) * 100, 2)
        if total_project_cost > 0 else 0
    )

    scored = [d.deal_score for d in deals if d.deal_score is not None]
    average_deal_score = round(sum(scored) / len(scored), 1) if scored else 0

    ready_for_funding_count = len([
        d for d in deals
        if not d.submitted_for_funding
        and ((d.recommended_strategy or d.strategy) is not None)
        and (d.purchase_price or 0) > 0
    ])
    funding_requested_count = len([d for d in deals if d.submitted_for_funding])

    deal_flags = []
    for d in deals:
        deal_flags.extend(_deal_risk_flags(d))

    deals_summary = [
        {
            "id": d.id,
            "label": _deal_label(d),
            "strategy": d.recommended_strategy or d.strategy,
            "purchase_price": d.purchase_price or 0,
            "arv": d.arv or 0,
            "rehab_cost": d.rehab_cost or 0,
            "estimated_profit": (d.arv or 0) - ((d.purchase_price or 0) + (d.rehab_cost or 0)),
            "deal_score": d.deal_score,
            "submitted_for_funding": bool(d.submitted_for_funding),
        }
        for d in deals
    ]

    return {
        "has_deals": True,
        "total_deals": len(deals),
        "total_purchase_price": total_purchase_price,
        "total_arv": total_arv,
        "total_rehab_cost": total_rehab_cost,
        "total_project_cost": total_project_cost,
        "total_profit": total_profit,
        "portfolio_roi_percent": portfolio_roi_percent,
        "average_deal_score": average_deal_score,
        "ready_for_funding_count": ready_for_funding_count,
        "funding_requested_count": funding_requested_count,
        "deal_flags": deal_flags,
        "deals": deals_summary,
    }


def gather_investor_portfolio_context(user_id) -> dict:
    raw = _query_raw(user_id)
    return _shape_context(raw.get("deals"))


def _template_portfolio_explanation(context: dict) -> dict:
    """Deterministic, non-LLM fallback built directly from context — the
    feature must never hard-fail for the investor."""
    if not context.get("has_deals"):
        return {
            "summary": "You don't have any tracked deals yet. Save or create a deal to build your portfolio.",
            "next_steps": ["Open Deal Finder and save your first property to start tracking a deal."],
            "flags": [],
            "highlight": "",
        }

    total_deals = context["total_deals"]
    total_arv = context["total_arv"]
    roi = context["portfolio_roi_percent"]
    summary = (
        f"You're tracking {total_deals} deal{'s' if total_deals != 1 else ''} "
        f"with a combined ARV of ${total_arv:,.0f} and an aggregate projected "
        f"ROI of {roi:.1f}%."
    )

    next_steps = []
    if context["ready_for_funding_count"] > 0:
        next_steps.append(
            f"{context['ready_for_funding_count']} deal(s) look ready for funding — review and submit them."
        )
    if context["deal_flags"]:
        next_steps.append("Resolve the flagged risks below before moving deals further along.")
    if not next_steps:
        next_steps.append("Your portfolio has no outstanding flags right now — keep building your pipeline.")

    best_deal = max(context["deals"], key=lambda d: d["estimated_profit"], default=None)
    highlight = (
        f"{best_deal['label']} shows the strongest projected profit at ${best_deal['estimated_profit']:,.0f}."
        if best_deal else ""
    )

    return {
        "summary": summary,
        "next_steps": next_steps,
        "flags": context["deal_flags"],
        "highlight": highlight,
    }


def explain_investor_portfolio(user_id, question: str | None = None) -> dict:
    context = gather_investor_portfolio_context(user_id)

    result = claude_portfolio_analysis({"context": context, "question": question})
    if result.get("error"):
        return {
            "result": _template_portfolio_explanation(context),
            "provider": "template",
            "context": context,
        }

    return {
        "result": {
            "summary": result.get("summary", ""),
            "next_steps": result.get("next_steps", []),
            "flags": result.get("flags", []),
            "highlight": result.get("highlight", ""),
        },
        "provider": "anthropic/claude",
        "context": context,
    }
