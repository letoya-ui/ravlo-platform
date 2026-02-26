"""
Rehab Service
-------------
Handles:
- Rehab cost estimation
- Rehab optimization (budget, ROI, timeline, ARV)
- Rehab risk flags
- Rehab timeline
- Material costs
- Rehab notes
"""

def _to_number(x, default=0.0):
    """Convert ints/floats and common numeric strings ('$250,000') to float."""
    if x is None:
        return default
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip().replace("$", "").replace(",", "")
        if s == "":
            return default
        try:
            return float(s)
        except ValueError:
            return default
    return default


def estimate_rehab_cost(property_sqft, scope="medium", items=None):
    base_costs = {"light": 15, "medium": 30, "heavy": 50}
    base = base_costs.get(scope, 30)

    sqft = _to_number(property_sqft, 0.0)
    base_total = sqft * base

    breakdown = {
        "base_rehab": base_total,
        "items": {},
        "total": base_total,
        "cost_per_sqft": base,   # per-sqft baseline rate
        "scope": scope,
    }

    default_items = {
        "kitchen": {"light": 8000, "medium": 15000, "heavy": 25000},
        "bathroom": {"light": 4000, "medium": 8000, "heavy": 15000},
        "flooring": {"light": 3000, "medium": 6000, "heavy": 12000},
        "paint": {"light": 2000, "medium": 4000, "heavy": 8000},
        "roof": {"light": 3000, "medium": 7000, "heavy": 12000},
        "hvac": {"light": 2000, "medium": 5000, "heavy": 9000},
    }

    total = base_total

    if items:
        for key, level in items.items():
            if key in default_items and level:
                cost = _to_number(default_items[key].get(level, 0), 0.0)
                breakdown["items"][key] = {"level": level, "cost": cost}
                total += cost

    breakdown["total"] = total
    breakdown["cost_per_sqft"] = (total / sqft) if sqft else 0.0

    return breakdown


def generate_rehab_risk_flags(results, comps):
    flags = []

    rehab = (results or {}).get("rehab_summary")
    if not rehab:
        return flags

    total = _to_number(rehab.get("total", 0), 0.0)
    cpsf  = _to_number(rehab.get("cost_per_sqft", 0), 0.0)
    scope = rehab.get("scope")
    items = rehab.get("items", {}) or {}

    purchase_price = _to_number((comps or {}).get("property", {}).get("price", 0), 0.0)
    arv = _to_number((comps or {}).get("arv_estimate", 0), 0.0)

    if arv and total > arv * 0.4:
        flags.append("Rehab cost exceeds 40% of ARV.")

    if purchase_price and total > purchase_price * 0.5:
        flags.append("Rehab cost exceeds 50% of purchase price.")

    if cpsf > 60:
        flags.append("Cost per sqft is unusually high.")

    heavy_items = [k for k, v in items.items() if isinstance(v, dict) and v.get("level") == "heavy"]
    if len(heavy_items) >= 2:
        flags.append("Multiple heavy items — major renovation.")

    if scope != "light":
        if "kitchen" not in items and "bathroom" not in items:
            flags.append("Medium/heavy rehab usually includes kitchen or bathroom updates.")

    return flags


def estimate_rehab_timeline(items, scope):
    base_weeks = {"light": 2, "medium": 4, "heavy": 8}
    timeline = _to_number(base_weeks.get(scope, 4), 0.0)

    item_weeks = {
        "kitchen": {"light": 1, "medium": 2, "heavy": 4},
        "bathroom": {"light": 1, "medium": 2, "heavy": 3},
        "flooring": {"light": 1, "medium": 1, "heavy": 2},
        "paint": {"light": 1, "medium": 1, "heavy": 2},
        "roof": {"light": 1, "medium": 2, "heavy": 3},
        "hvac": {"light": 1, "medium": 2, "heavy": 3},
    }

    breakdown = {}
    items = items or {}

    for key, level in items.items():
        if key in item_weeks and level:
            weeks = _to_number(item_weeks[key].get(level, 0), 0.0)
            breakdown[key] = weeks
            timeline += weeks

    # Return ints for nicer display if you prefer
    return {"total_weeks": timeline, "breakdown": breakdown}


def estimate_material_costs(property_sqft, items):
    sqft = _to_number(property_sqft, 0.0)

    material_rates = {
        "flooring": {"light": 1.50, "medium": 2.50, "heavy": 5.00},
        "paint": {"light": 0.50, "medium": 1.00, "heavy": 1.50},
        "tile": {"light": 2.00, "medium": 4.00, "heavy": 7.00},
    }

    fixed_materials = {
        "kitchen": {"light": 1500, "medium": 3500, "heavy": 8000},
        "bathroom": {"light": 800, "medium": 2000, "heavy": 4500},
    }

    breakdown = {}
    total = 0.0
    items = items or {}

    for key, level in items.items():
        if key in material_rates and level:
            rate = _to_number(material_rates[key].get(level, 0), 0.0)
            cost = sqft * rate
            breakdown[key] = cost
            total += cost

    for key, level in items.items():
        if key in fixed_materials and level:
            cost = _to_number(fixed_materials[key].get(level, 0), 0.0)
            breakdown[key] = breakdown.get(key, 0.0) + cost
            total += cost

    return {"total_material_cost": total, "breakdown": breakdown}


def generate_rehab_notes(results, comps, strategy="flip"):
    notes = []

    rehab = (results or {}).get("rehab_summary")
    timeline = (results or {}).get("rehab_timeline")

    if not rehab:
        return notes

    items = rehab.get("items", {}) or {}
    scope = rehab.get("scope")
    cpsf = _to_number(rehab.get("cost_per_sqft", 0), 0.0)

    if scope == "light":
        notes.append("Light rehab — quick cosmetic improvements.")
    elif scope == "medium":
        notes.append("Medium rehab — balanced upgrades.")
    elif scope == "heavy":
        notes.append("Heavy rehab — long timeline, major work.")

    for key, data in items.items():
        if not isinstance(data, dict):
            continue
        level = data.get("level")
        if level:
            notes.append(f"{key.capitalize()} renovation: {str(level).capitalize()}.")

    if scope != "light":
        if "kitchen" not in items and "bathroom" not in items:
            notes.append("Consider updating kitchen or bathroom.")

    if strategy == "flip":
        notes.append("For flips, prioritize kitchens, bathrooms, flooring.")
        if cpsf > 50:
            notes.append("High cost per sqft — ensure ARV supports it.")

    if strategy == "rental":
        notes.append("For rentals, use durable, low-maintenance materials.")

    if strategy == "airbnb":
        notes.append("For Airbnb, focus on guest experience upgrades.")

    if timeline and isinstance(timeline, dict) and _to_number(timeline.get("total_weeks", 0), 0.0) > 10:
        notes.append("Long rehab timeline — consider holding costs.")

    return notes


# --- Optimization Engines ---

def optimize_rehab_to_budget(target_budget, items, scope, sqft):
    """
    Downgrades items until total cost fits target budget.
    """
    optimized = (items or {}).copy()
    current_scope = scope
    target_budget = _to_number(target_budget, 0.0)
    sqft = _to_number(sqft, 0.0)

    def calc():
        rehab = estimate_rehab_cost(sqft, current_scope, optimized)
        return _to_number(rehab["total"], 0.0), rehab

    total, rehab_data = calc()

    if target_budget and total <= target_budget:
        return optimized, rehab_data

    downgrade_order = [
        ("kitchen", ["heavy", "medium", "light", ""]),
        ("bathroom", ["heavy", "medium", "light", ""]),
        ("flooring", ["heavy", "medium", "light", ""]),
        ("paint", ["heavy", "medium", "light", ""]),
        ("roof", ["heavy", "medium", "light", ""]),
        ("hvac", ["heavy", "medium", "light", ""]),
    ]

    for key, levels in downgrade_order:
        if key in optimized:
            current_level = optimized[key]
            if current_level in levels:
                idx = levels.index(current_level)
                if idx + 1 < len(levels):
                    optimized[key] = levels[idx + 1]
                    total, rehab_data = calc()
                    if target_budget and total <= target_budget:
                        return optimized, rehab_data

    if current_scope == "heavy":
        current_scope = "medium"
    elif current_scope == "medium":
        current_scope = "light"

    total, rehab_data = calc()
    return optimized, rehab_data


def optimize_rehab_for_roi(items, scope, sqft, comps):
    optimized = (items or {}).copy()
    current_scope = scope
    sqft = _to_number(sqft, 0.0)

    comps = comps or {}
    arv = _to_number(comps.get("arv_estimate", 0), 0.0)
    price = _to_number(comps.get("property", {}).get("price", 0), 0.0)

    for key in ["kitchen", "bathroom"]:
        optimized[key] = "medium"

    optimized["flooring"] = "medium"
    optimized["paint"] = "medium"

    margin = arv - price
    if margin > 80000:
        optimized["kitchen"] = "heavy"
        optimized["bathroom"] = "heavy"

    rehab = estimate_rehab_cost(sqft, current_scope, optimized)
    return optimized, rehab


def optimize_rehab_for_timeline(items, scope, sqft):
    optimized = (items or {}).copy()
    current_scope = "light"
    sqft = _to_number(sqft, 0.0)

    for key in optimized:
        optimized[key] = "light"

    for key in ["roof", "hvac"]:
        optimized[key] = ""

    rehab = estimate_rehab_cost(sqft, current_scope, optimized)
    return optimized, rehab


def optimize_rehab_for_arv(items, scope, sqft):
    optimized = (items or {}).copy()
    current_scope = "heavy"
    sqft = _to_number(sqft, 0.0)

    optimized["kitchen"] = "heavy"
    optimized["bathroom"] = "heavy"
    optimized["flooring"] = "medium"
    optimized["paint"] = "medium"

    rehab = estimate_rehab_cost(sqft, current_scope, optimized)
    return optimized, rehab