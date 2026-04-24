try:
    from LoanMVP.services.cost_index import describe_learned_index
except Exception:  # pragma: no cover - defensive: never break this module
    describe_learned_index = None


def _to_money(value):
    # Render negatives as ``-$1,234`` instead of ``$-1,234`` (the former is
    # the convention investors expect; the latter looks like a typo). Matters
    # for Deal Architect when a high local cost factor eats the margin and
    # ``profit`` goes negative — the strategy still renders, just flagged.
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    if v < 0:
        return "-${:,.0f}".format(-v)
    return "${:,.0f}".format(v)


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
    # Fallback must match the shape downstream code (and templates) expects
    # from describe_learned_index so ``index_info.get("signed_label")`` and
    # ``index_info.get("detail")`` never surface literal 'None' in the UI.
    _NATIONAL_FALLBACK = {
        "factor": 1.0,
        "label": "U.S. average",
        "delta_pct": 0,
        "signed_label": "at national average",
        "detail": "RSMeans seed only",
        "source": "baseline",
    }
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
            build_index = dict(_NATIONAL_FALLBACK)
            rehab_index = dict(_NATIONAL_FALLBACK)
    else:
        build_index = dict(_NATIONAL_FALLBACK)
        rehab_index = dict(_NATIONAL_FALLBACK)
    build_factor = float(build_index.get("factor") or 1.0)
    rehab_factor = float(rehab_index.get("factor") or 1.0)

    strategies = []

    # LAND / LOT / DEVELOPMENT
    if property_type in ["land", "lot", "vacant land", "development site"]:
        strategies.append({
            "name": "Single-Family Build",
            "tag": "Lower complexity",
            "description": "A simpler ground-up strategy with a faster path to concepting, pricing, and funding.",
            "purchase_price": 0,
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
            "purchase_price": 0,
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
            "purchase_price": 0,
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
            "purchase_price": 200000,
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
            "purchase_price": 203000,
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
            # Tear-down targets are typically acquired cheap (land value +
            # minus demo cost). 100K keeps the strategy an existing-house
            # play (not a land-only play) while producing a realistic
            # profit/ROI off the original hardcoded build_cost and arv.
            "purchase_price": 100000,
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
    # build_cost (construction/rehab spend) by the appropriate category
    # factor, leave both ARV (market/comps figure) and purchase_price
    # (existing asset price, not a construction-cost item) alone, and
    # recompute profit + ROI off the adjusted total investment. Each
    # strategy carries its own ``local_index`` so the UI can surface it.
    #
    # ``purchase_price`` is explicit on each strategy dict: 0 for
    # ground-up builds where ``build_cost`` already represents the total
    # investment, and non-zero for existing-house rehab strategies where
    # ``build_cost`` is just the rehab spend.
    # The "Tear-Down + New Build" strategy is a mixed scope: ~15% demo /
    # site work (rehab-category labor) and ~85% ground-up construction
    # (new_build-category). Using the pure new_build factor over-adjusts
    # the demo side; using the pure rehab factor under-adjusts the build
    # side. Blend 85/15 so the number tracks the actual spend profile.
    _TEARDOWN_BUILD_WEIGHT = 0.85
    for strategy in strategies:
        is_build = strategy.get("recommended_workspace") == "build"
        is_teardown = strategy.get("name") == "Tear-Down + New Build"
        if is_teardown:
            factor = (
                _TEARDOWN_BUILD_WEIGHT * build_factor
                + (1.0 - _TEARDOWN_BUILD_WEIGHT) * rehab_factor
            )
            # Surface the build index — it's the dominant component and
            # matches what the UI already calls the strategy ("new build").
            index_info = build_index
        else:
            factor = build_factor if is_build else rehab_factor
            index_info = build_index if is_build else rehab_index

        national_build_cost = _to_number(strategy.get("build_cost"), 0.0)
        local_build_cost = national_build_cost * factor

        arv = _to_number(strategy.get("arv"), 0.0)
        purchase_price = _to_number(strategy.get("purchase_price"), 0.0)
        total_investment = purchase_price + local_build_cost
        profit = arv - total_investment
        roi_pct = (profit / total_investment * 100.0) if total_investment else 0.0

        strategy["national_build_cost"] = national_build_cost
        strategy["build_cost"] = local_build_cost
        strategy["total_investment"] = total_investment
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

def _auto_generate_build_budget_from_deal(deal, project_id=None):
    results = _deal_results(deal)
    build_project = results.get("build_project", {}) or {}

    if not build_project:
        return None

    blueprint = build_project.get("blueprint", {}) or {}
    site_plan = build_project.get("site_plan", {}) or {}
    exterior = build_project.get("exterior", {}) or {}

    lot_count = int(build_project.get("lot_count") or 1)
    property_type = build_project.get("property_type") or "single_family"

    package = {
        "deal_id": deal.id,
        "project_id": project_id or build_project.get("project_id"),
        "strategy": deal.strategy,
        "address": deal.address,
        "city": deal.city,
        "state": deal.state,
        "zip_code": deal.zip_code,
        "purchase_price": deal.purchase_price or 0,
        "arv": deal.arv or 0,
        "project_name": build_project.get("project_name") or deal.title,
        "property_type": property_type,
        "development_type": build_project.get("development_type"),
        "lot_count": lot_count,
        "description": build_project.get("description"),
        "lot_size": build_project.get("lot_size"),
        "zoning": build_project.get("zoning"),
        "location": build_project.get("location"),
        "notes": build_project.get("notes"),
        "blueprint_url": blueprint.get("image_url") or blueprint.get("blueprint_url"),
        "site_plan_url": site_plan.get("image_url") or site_plan.get("site_plan_url"),
        "exterior_url": exterior.get("image_url"),
    }

    try:
        cost_json = _post_scope_engine_json(
            "/v1/build_cost",
            package,
            timeout=90,
        ) or {}
    except Exception:
        current_app.logger.exception("Auto build-cost engine failed")
        cost_json = {}

    if not cost_json or not cost_json.get("line_items"):
        fallback_items = [
            {"category": "Sitework", "description": "Clearing, grading, access, utility prep", "estimated_amount": 35000 * lot_count},
            {"category": "Foundation", "description": "Foundation and slab / basement allowance", "estimated_amount": 45000 * lot_count},
            {"category": "Framing", "description": f"{property_type} framing and shell", "estimated_amount": 85000 * lot_count},
            {"category": "Exterior", "description": "Roofing, siding, windows, doors", "estimated_amount": 65000 * lot_count},
            {"category": "MEP", "description": "Mechanical, electrical, plumbing rough-ins", "estimated_amount": 70000 * lot_count},
            {"category": "Interior Finishes", "description": "Drywall, flooring, cabinets, fixtures, paint", "estimated_amount": 95000 * lot_count},
            {"category": "Soft Costs", "description": "Permits, design, engineering, inspections", "estimated_amount": 30000 * lot_count},
        ]

        subtotal = sum(float(i["estimated_amount"]) for i in fallback_items)
        contingency = round(subtotal * 0.10, 2)

        cost_json = {
            "source": "auto_fallback_deal_architect",
            "category": "new_build",
            "line_items": fallback_items,
            "subtotal": subtotal,
            "contingency": contingency,
            "total_budget": subtotal + contingency,
            "notes": "Auto-generated estimate from Build Studio package.",
        }

    line_items = cost_json.get("line_items") or []
    subtotal = float(cost_json.get("subtotal") or sum(float(i.get("estimated_amount") or 0) for i in line_items))
    contingency = float(cost_json.get("contingency") or round(subtotal * 0.10, 2))
    total_budget = float(cost_json.get("total_budget") or subtotal + contingency)

    budget = ProjectBudget(
        investor_profile_id=getattr(deal, "investor_profile_id", None),
        deal_id=deal.id,
        build_project_id=project_id or build_project.get("project_id"),
        budget_type=cost_json.get("category") or "new_build",
        name=f"{build_project.get('project_name') or deal.title or 'Build'} Budget",
        project_name=build_project.get("project_name") or deal.title,
        total_cost=subtotal,
        contingency=contingency,
        total_budget=total_budget,
        total_amount=total_budget,
        notes=cost_json.get("notes") or "Generated automatically from Build Studio package.",
    )
    db.session.add(budget)
    db.session.flush()

    for item in line_items:
        db.session.add(ProjectExpense(
            budget_id=budget.id,
            category=item.get("category") or "Construction",
            description=item.get("description") or item.get("name") or "Build cost item",
            vendor=item.get("vendor"),
            estimated_amount=float(item.get("estimated_amount") or item.get("amount") or 0),
            actual_amount=0,
            paid_amount=0,
            status=item.get("status") or "planned",
            notes=item.get("notes"),
        ))

    budget.recalculate_totals()

    results["deal_architect"] = results.get("deal_architect", {}) or {}
    results["deal_architect"]["build_costs"] = {
        "budget_id": budget.id,
        "source": cost_json.get("source") or "auto_deal_architect",
        "subtotal": subtotal,
        "contingency": contingency,
        "total_budget": total_budget,
        "line_items": line_items,
        "package": package,
    }

    deal.rehab_cost = total_budget
    _set_deal_results(deal, results)

    return {
        "budget_id": budget.id,
        "subtotal": subtotal,
        "contingency": contingency,
        "total_budget": total_budget,
        "budget_url": url_for("investor.budget_studio", deal_id=deal.id, budget_id=budget.id),
    }