def build_deal_copilot_context(
    property_address=None,
    zip_code=None,
    strategy_hint=None,
    lot_size=None,
    zoning=None,
    notes=None,
    workspace="deal",
    user_id=None
):
    """
    Starter context builder for Ravlo Deal Copilot.
    Later you can pull from:
      - saved deals
      - rehab studio outputs
      - build studio outputs
      - deal finder results
      - funding data
      - property intelligence
    """
    return {
        "workspace": workspace,
        "property_address": property_address or "",
        "zip_code": zip_code or "",
        "strategy_hint": strategy_hint or "",
        "lot_size": lot_size or "",
        "zoning": zoning or "",
        "notes": notes or "",
        "user_id": user_id
    }


def generate_deal_copilot_response(user_message, context):
    """
    Placeholder response logic.
    Replace this with OpenAI / AI orchestration later.
    """

    msg = user_message.lower()
    workspace = context.get("workspace", "deal")
    property_address = context.get("property_address", "")
    zip_code = context.get("zip_code", "")
    zoning = context.get("zoning", "")
    lot_size = context.get("lot_size", "")
    strategy_hint = context.get("strategy_hint", "")
    notes = context.get("notes", "")

    location_label = property_address or zip_code or "this opportunity"

    context_summary_parts = []
    if property_address:
        context_summary_parts.append(f"Address: {property_address}")
    if zip_code:
        context_summary_parts.append(f"ZIP: {zip_code}")
    if lot_size:
        context_summary_parts.append(f"Lot Size: {lot_size}")
    if zoning:
        context_summary_parts.append(f"Zoning: {zoning}")
    if strategy_hint:
        context_summary_parts.append(f"Strategy Hint: {strategy_hint}")
    if notes:
        context_summary_parts.append(f"Notes: {notes}")

    context_summary = " • ".join(context_summary_parts) if context_summary_parts else "No deal context provided yet."

    # --- basic intent routing ---
    if "flip" in msg and "rental" in msg:
        reply = (
            f"Here’s how I’d frame {location_label}: compare the resale spread against the long-term cash flow. "
            f"If the renovation upside is strong and the neighborhood supports a higher after-repair value, a flip may be the stronger play. "
            f"If the area supports stable rents and the rehab scope is moderate, rental may be more durable.\n\n"
            f"My recommendation is to run two scenarios next:\n"
            f"1. a flip scenario with estimated rehab + ARV\n"
            f"2. a rental scenario with projected rent + holding costs\n\n"
            f"Once those numbers are side by side, Ravlo can recommend the stronger strategy with much more confidence."
        )
        actions = [
            {"label": "Open Rehab Studio", "url": "/investor/deal-studio/rehab-studio"},
            {"label": "Analyze Build Option", "url": "/investor/deal-studio/build-studio"},
            {"label": "Create Funding Summary", "url": "#"}
        ]

    elif "what can i build" in msg or "build on this lot" in msg or workspace == "build":
        reply = (
            f"For {location_label}, the strongest next step is to evaluate build options against lot size, zoning, access, and exit strategy. "
            f"Based on the information provided, Ravlo should compare a single-family concept, duplex concept, and small development concept if allowed.\n\n"
            f"My recommendation is to open Build Studio and generate a concept package. "
            f"That will give you a render, draft blueprint, site layout, and presentation sheet you can use for architects, builders, or lenders."
        )
        actions = [
            {"label": "Open Build Studio", "url": "/investor/deal-studio/build-studio"},
            {"label": "Run AI Deal Architect", "url": "/investor/deal-studio/architect"},
            {"label": "Send to Funding", "url": "#"}
        ]

    elif "lender" in msg or "summary" in msg or "partner" in msg:
        reply = (
            f"Here is the best way to frame {location_label} for a lender or partner:\n\n"
            f"- clearly define the project type\n"
            f"- explain the business plan\n"
            f"- summarize the opportunity\n"
            f"- outline expected improvements or build scope\n"
            f"- present the exit strategy\n\n"
            f"Ravlo should turn this into a concise presentation sheet with visuals, numbers, and next-step requirements."
        )
        actions = [
            {"label": "Generate Presentation", "url": "#"},
            {"label": "Open Build Studio", "url": "/investor/deal-studio/build-studio"},
            {"label": "Open Rehab Studio", "url": "/investor/deal-studio/rehab-studio"}
        ]

    elif "risk" in msg or "risks" in msg:
        reply = (
            f"The top risks for {location_label} likely fall into four areas:\n\n"
            f"1. scope risk — the work required may exceed expectations\n"
            f"2. margin risk — resale or rent may not support the total project cost\n"
            f"3. zoning/site risk — development limits may reduce options\n"
            f"4. timeline risk — delays can impact carrying costs and profitability\n\n"
            f"The next move is to validate the deal through project scope, market comps, and a realistic exit scenario."
        )
        actions = [
            {"label": "Open Deal Finder", "url": "/borrower/property_tool"},
            {"label": "Open Rehab Studio", "url": "/investor/deal-studio/rehab-studio"},
            {"label": "Open Build Studio", "url": "/investor/deal-studio/build-studio"}
        ]

    else:
        reply = (
            f"I’m looking at {location_label} as an opportunity that needs a clear strategy, realistic numbers, and a strong next step. "
            f"Ravlo can help you decide whether this should be approached as a flip, rental, or ground-up development play.\n\n"
            f"The smartest next move is to choose one of three paths:\n"
            f"- Rehab Studio for improvement scenarios\n"
            f"- Build Studio for land or new construction concepts\n"
            f"- AI Deal Architect for strategy comparison\n\n"
            f"Once you pick the path, I can help shape the deal into something lender-ready and execution-ready."
        )
        actions = [
            {"label": "Open Rehab Studio", "url": "/investor/deal-studio/rehab-studio"},
            {"label": "Open Build Studio", "url": "/investor/deal-studio/build-studio"},
            {"label": "Run AI Deal Architect", "url": "/investor/deal-studio/architect"}
        ]

    return {
        "reply": reply,
        "actions": actions,
        "context_summary": context_summary
    }