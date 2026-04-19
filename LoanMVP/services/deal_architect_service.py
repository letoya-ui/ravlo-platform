try:
    from LoanMVP.services.cost_index import describe_learned_index
except Exception:  # pragma: no cover - defensive: never break this module
    describe_learned_index = None


def _to_money(value):
    return "${:,.0f}".format(value)


def _safe_float_from_text(text, default=0):
    if not text:
        return default
    cleaned = "".join(ch for ch in str(text) if ch.isdigit() or ch in ["."])
    try:
        return float(cleaned) if cleaned else default
    except Exception:
        return default


def generate_deal_architect_strategies(payload):
    property_address = payload.get("property_address") or ""
    zip_code = payload.get("zip_code") or ""
    state = payload.get("state") or ""
    property_type = (payload.get("property_type") or "").lower()
    lot_size = payload.get("lot_size") or ""
    zoning = (payload.get("zoning") or "").upper()
    strategy_goal = payload.get("strategy_goal") or ""
    budget = payload.get("budget") or ""
    notes = payload.get("notes") or ""

    context_label = property_address or zip_code or "This opportunity"
    numeric_budget = _safe_float_from_text(budget, default=0)

    # Local cost index (RSMeans seed blended with real CostObservations).
    # Ground-up build numbers get the new_build category; rehab/flip numbers
    # get the rehab category. Seed-only until the observation table fills in.
    # describe_learned_index may be None if cost_index failed to import at
    # module load time; in that case we degrade to national averages.
    if describe_learned_index is not None:
        try:
            build_index = describe_learned_index(
                zip_code=zip_code, state=state,
                category="new_build", scope=None,
            )
            rehab_index = describe_learned_index(
                zip_code=zip_code, state=state,
                category="rehab", scope="medium",
            )
        except Exception:
            build_index = {"factor": 1.0}
            rehab_index = {"factor": 1.0}
    else:
        build_index = {"factor": 1.0}
        rehab_index = {"factor": 1.0}
    build_factor = float(build_index.get("factor") or 1.0)
    rehab_factor = float(rehab_index.get("factor") or 1.0)

    strategies = []

    # LAND / LOT / DEVELOPMENT
    if property_type in ["land", "lot", "vacant land", "development site"]:
        strategies.append({
            "name": "Single-Family Build",
            "tag": "Lower complexity",
            "description": "A simpler ground-up strategy with a faster path to concepting, pricing, and funding.",
            "build_cost": 425000,
            "arv": 690000,
            "profit": 265000,
            "roi": "38%",
            "recommended_workspace": "build",
            "buttons": [
                {"label": "Open Build Studio", "url": "/investor/deal-studio/build-studio"},
                {"label": "Send to Funding", "url": "#"}
            ]
        })

        strategies.append({
            "name": "Duplex Development",
            "tag": "Income-focused",
            "description": "A strong option when zoning and lot shape support 2 units and higher total value creation.",
            "build_cost": 560000,
            "arv": 860000,
            "profit": 300000,
            "roi": "35%",
            "recommended_workspace": "build",
            "buttons": [
                {"label": "Generate Concept", "url": "/investor/deal-studio/build-studio"},
                {"label": "Open Deal Copilot", "url": "/investor/deal-studio/copilot"}
            ]
        })

        strategies.append({
            "name": "Townhome / Small Development Concept",
            "tag": "Higher upside",
            "description": "A more aggressive approach for parcels with stronger zoning flexibility and exit potential.",
            "build_cost": 890000,
            "arv": 1325000,
            "profit": 435000,
            "roi": "33%",
            "recommended_workspace": "build",
            "buttons": [
                {"label": "Open Build Studio", "url": "/investor/deal-studio/build-studio"},
                {"label": "Create Presentation", "url": "#"}
            ]
        })

        summary = (
            f"{context_label} looks best suited for a build-focused strategy. "
            f"My recommendation is to compare a lower-complexity single-family concept against a duplex or small development path, "
            f"then narrow the choice based on zoning, lot layout, and funding appetite."
        )

    # EXISTING HOUSE / FIXER
    else:
        strategies.append({
            "name": "Value-Add Flip",
            "tag": "Fastest reposition",
            "description": "Best when the property has clear cosmetic or layout upside and a strong resale ceiling.",
            "build_cost": 85000,
            "arv": 355000,
            "profit": 70000,
            "roi": "28%",
            "recommended_workspace": "rehab",
            "buttons": [
                {"label": "Open Rehab Studio", "url": "/investor/deal-studio/rehab-studio"},
                {"label": "Create Funding Summary", "url": "#"}
            ]
        })

        strategies.append({
            "name": "BRRRR / Rental Hold",
            "tag": "Cash-flow path",
            "description": "A better fit when the area supports rents, moderate rehab, and long-term hold performance.",
            "build_cost": 65000,
            "arv": 320000,
            "profit": 52000,
            "roi": "22%",
            "recommended_workspace": "rehab",
            "buttons": [
                {"label": "Open Rehab Studio", "url": "/investor/deal-studio/rehab-studio"},
                {"label": "Open Deal Copilot", "url": "/investor/deal-studio/copilot"}
            ]
        })

        strategies.append({
            "name": "Tear-Down + New Build",
            "tag": "Highest change",
            "description": "Worth comparing when the existing structure limits upside and the lot supports a stronger new product.",
            "build_cost": 490000,
            "arv": 760000,
            "profit": 270000,
            "roi": "31%",
            "recommended_workspace": "build",
            "buttons": [
                {"label": "Open Build Studio", "url": "/investor/deal-studio/build-studio"},
                {"label": "Generate Concept", "url": "/investor/deal-studio/build-studio"}
            ]
        })

        summary = (
            f"{context_label} looks like a strategy-comparison deal. "
            f"The smartest move is to test a rehab-first scenario against a hold strategy and a tear-down / rebuild scenario, "
            f"then choose the path with the strongest margin and execution fit."
        )

    # simple budget influence
    if numeric_budget and numeric_budget < 100000:
        summary += " Based on the budget entered, lighter rehab or phased execution may be more realistic than full-scale redevelopment."

    if zoning:
        summary += f" Zoning noted: {zoning}."

    if lot_size:
        summary += f" Lot size noted: {lot_size}."

    if strategy_goal:
        summary += f" Primary goal: {strategy_goal}."

    if notes:
        summary += " Ravlo should keep the notes in mind when refining the final recommendation."

    # Apply the local cost index to every strategy's cost side. We multiply
    # build_cost (and rehab_cost if present) by the appropriate category
    # factor, leave ARV alone (ARV is a market/comps figure, not a cost),
    # and recompute profit + ROI off the adjusted numbers. Each strategy
    # carries its own ``local_index`` so the UI can surface the factor.
    for strategy in strategies:
        is_build = strategy.get("recommended_workspace") == "build"
        factor = build_factor if is_build else rehab_factor
        index_info = build_index if is_build else rehab_index

        national_build_cost = _to_number(strategy.get("build_cost"), 0.0)
        local_build_cost = national_build_cost * factor

        arv = _to_number(strategy.get("arv"), 0.0)
        profit = arv - local_build_cost
        roi_pct = (profit / local_build_cost * 100.0) if local_build_cost else 0.0

        strategy["national_build_cost"] = national_build_cost
        strategy["build_cost"] = local_build_cost
        strategy["profit"] = profit
        strategy["roi"] = f"{roi_pct:.0f}%"

        strategy["build_cost_label"]  = _to_money(local_build_cost)
        strategy["arv_label"]         = _to_money(arv)
        strategy["profit_label"]      = _to_money(profit)
        strategy["local_factor"]      = round(factor, 3)
        strategy["local_index"]       = index_info
        strategy["local_index_label"] = index_info.get("signed_label")
        strategy["local_index_detail"] = index_info.get("detail")

    return {
        "context_label": context_label,
        "summary": summary,
        "strategies": strategies,
        "local_index": {
            "build": build_index,
            "rehab": rehab_index,
        },
    }


def _to_number(x, default=0.0):
    """Local fallback for numeric coercion (matches rehab_service)."""
    if x is None:
        return default
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip().replace("$", "").replace(",", "")
        if not s:
            return default
        try:
            return float(s)
        except ValueError:
            return default
    return default