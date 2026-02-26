from openai import OpenAI

client = OpenAI()

def generate_property_summary(payload: dict) -> str:
    address = payload.get("address")
    price = payload.get("price")
    beds = payload.get("beds")
    baths = payload.get("baths")
    sqft = payload.get("sqft")
    zestimate = payload.get("zestimate")
    source = payload.get("source")

    prompt = f"""
You are a premium real estate analyst writing for a savvy homebuyer.

Property:
- Address: {address}
- Price: {price}
- Beds/Baths: {beds} bd / {baths} ba
- Square Feet: {sqft}
- Zestimate / Est. Value: {zestimate}
- Data Source: {source}

Using this info plus any comps/price history/tax history (if present), write:

1. A 2–3 sentence high-level overview of the property.
2. A bullet list of:
   - Strengths (location, layout, condition, value)
   - Potential concerns or red flags
   - Investment / appreciation potential
3. A one-line “bottom line” recommendation.

Be concise, confident, and buyer-focused.
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
   
    return resp.choices[0].message.content

