from enum import Enum


class TemplateType(str, Enum):
    # Flyers
    JUST_LISTED = "just_listed"
    JUST_SOLD = "just_sold"
    COMING_SOON = "coming_soon"
    OPEN_HOUSE = "open_house"
    PRICE_DROP = "price_drop"
    BUYER_NEED = "buyer_need"
    MARKET_UPDATE = "market_update"

    # Emails
    FOLLOWUP_GENERAL = "followup_general"
    FOLLOWUP_AFTER_SHOWING = "followup_after_showing"
    FOLLOWUP_NEW_LEAD = "followup_new_lead"
    FOLLOWUP_INACTIVE = "followup_inactive"

    # Social
    SOCIAL_JUST_LISTED = "social_just_listed"
    SOCIAL_JUST_SOLD = "social_just_sold"
    SOCIAL_OPEN_HOUSE = "social_open_house"
    SOCIAL_MARKET_UPDATE = "social_market_update"


TEMPLATES = {
    # ---------------- FLYERS ----------------
    TemplateType.JUST_LISTED: """
You are writing a JUST LISTED real estate flyer.

Agent: Elena James (Keller Williams Hudson Valley)
Address: {address}
City: {city}, {state} {zip_code}
Beds: {beds}
Baths: {baths}
Sqft: {sqft}
Price: {price}

Instructions:
- Create a compelling headline (max 10 words)
- Write a 2–3 sentence lifestyle-focused description
- Add 4–6 bullet points highlighting features, upgrades, and neighborhood
- Tone: warm, professional, Hudson Valley lifestyle, service-first
""",

    TemplateType.JUST_SOLD: """
You are writing a JUST SOLD real estate flyer.

Agent: Elena James
Address: {address}
City: {city}, {state} {zip_code}
Sale Price: {price}
Days on Market: {days_on_market}
Offer Details: {offer_details}

Instructions:
- Create a celebratory headline (max 10 words)
- Mention that the home is sold and the area
- Highlight 3–5 key features that made it attractive
- Add a call-to-action for homeowners considering selling
- Tone: confident, warm, professional
""",

    TemplateType.COMING_SOON: """
You are writing a COMING SOON real estate flyer.

Agent: Elena James
Address: {address}
City: {city}, {state} {zip_code}
Beds: {beds}
Baths: {baths}
Sqft: {sqft}
Price (if available): {price}

Instructions:
- Create a teaser-style headline (max 10 words)
- Write a short 2–3 sentence teaser description
- Add 3–5 bullet points about features and location
- Emphasize "more details coming soon" and "schedule early access"
- Tone: anticipatory, inviting, professional
""",

    TemplateType.OPEN_HOUSE: """
You are writing an OPEN HOUSE flyer.

Agent: Elena James
Address: {address}
City: {city}, {state} {zip_code}
Date: {date}
Time: {time}
Beds: {beds}
Baths: {baths}
Sqft: {sqft}
Price: {price}

Instructions:
- Create an inviting headline (max 10 words)
- Write a short 2–3 sentence description of the home
- Add 3–5 bullet points about features and neighborhood
- Clearly restate the open house date and time
- Add a call-to-action to attend or schedule a private showing
- Tone: friendly, welcoming, professional
""",

    TemplateType.PRICE_DROP: """
You are writing a PRICE IMPROVEMENT flyer.

Agent: Elena James
Address: {address}
City: {city}, {state} {zip_code}
Old Price: {old_price}
New Price: {new_price}
Beds: {beds}
Baths: {baths}
Sqft: {sqft}

Instructions:
- Create a headline emphasizing the new price (max 10 words)
- Write a 2–3 sentence description focusing on value
- Add 3–5 bullet points about features and lifestyle
- Mention that the price has been improved and invite showings
- Tone: optimistic, value-focused, professional
""",

    TemplateType.BUYER_NEED: """
You are writing a BUYER NEED flyer.

Agent: Elena James
Buyer Type: {buyer_type}
Budget: {budget}
Beds: {beds}
Baths: {baths}
Preferred Areas: {areas}

Instructions:
- Create a headline about an active, qualified buyer (max 10 words)
- Write a 2–3 sentence description of what the buyer is seeking
- Add 3–5 bullet points with specific criteria
- Add a call-to-action for homeowners considering selling
- Tone: respectful, professional, opportunity-focused
""",

    TemplateType.MARKET_UPDATE: """
You are writing a local MARKET UPDATE flyer.

Agent: Elena James
Area: {area}
Timeframe: {timeframe}
Key Stats: {stats}

Instructions:
- Create a headline about the current market (max 10 words)
- Write a 2–3 sentence overview of the market conditions
- Add 4–6 bullet points with specific stats and insights
- Add a call-to-action for buyers and sellers to reach out
- Tone: informative, calm, expert, service-first
""",

    # ---------------- EMAILS ----------------
    TemplateType.FOLLOWUP_GENERAL: """
Write a follow-up email.

Agent: Elena James
Client Name: {client_name}
Pipeline Stage: {pipeline_stage}
Context: {context}

Instructions:
- Include a subject line
- Write a warm, professional 3–6 sentence email
- Focus on checking in, offering help, and next steps
- Tone: service-first, friendly, not pushy
""",

    TemplateType.FOLLOWUP_AFTER_SHOWING: """
Write a follow-up email after a home showing.

Agent: Elena James
Client Name: {client_name}
Property Address: {address}
City: {city}, {state} {zip_code}
Context: {context}

Instructions:
- Include a subject line
- Reference the specific property they viewed
- Ask for their thoughts and reactions
- Offer to answer questions or schedule another showing
- 3–6 sentences, warm and professional
""",

    TemplateType.FOLLOWUP_NEW_LEAD: """
Write a follow-up email to a NEW LEAD.

Agent: Elena James
Client Name: {client_name}
Lead Source: {source}
Context: {context}

Instructions:
- Include a subject line
- Acknowledge how they came into contact
- Introduce Elena briefly and her approach
- Invite a quick call or meeting
- 3–6 sentences, friendly and confident
""",

    TemplateType.FOLLOWUP_INACTIVE: """
Write a re-engagement email to an INACTIVE client.

Agent: Elena James
Client Name: {client_name}
Last Contact Context: {context}

Instructions:
- Include a subject line
- Gently acknowledge it has been a while
- Offer value (market update, new listings, strategy)
- Invite them to reconnect if timing is better now
- 3–6 sentences, warm and low-pressure
""",

    # ---------------- SOCIAL ----------------
    TemplateType.SOCIAL_JUST_LISTED: """
Write a short social media post for a JUST LISTED property.

Platform: Instagram + Facebook
Agent: Elena James
Address: {address}
City: {city}, {state}
Beds: {beds}
Baths: {baths}
Price: {price}

Instructions:
- 2–4 short sentences
- Include a hook in the first line
- Mention key features and location
- Add a soft call-to-action to schedule a showing
- No hashtags
- Tone: warm, excited, professional
""",

    TemplateType.SOCIAL_JUST_SOLD: """
Write a short social media post for a JUST SOLD property.

Platform: Instagram + Facebook
Agent: Elena James
Address: {address}
City: {city}, {state}
Sale Price: {price}
Buyer/Seller Context: {context}

Instructions:
- 2–4 short sentences
- Celebrate the sale and congratulate the clients
- Mention the area and any notable detail
- Add a soft call-to-action for homeowners thinking about selling
- No hashtags
- Tone: celebratory, grateful, professional
""",

    TemplateType.SOCIAL_OPEN_HOUSE: """
Write a short social media post for an OPEN HOUSE.

Platform: Instagram + Facebook
Agent: Elena James
Address: {address}
City: {city}, {state}
Date: {date}
Time: {time}

Instructions:
- 2–4 short sentences
- Invite people to the open house
- Mention one or two key features
- Clearly restate date and time
- No hashtags
- Tone: inviting, friendly, professional
""",

    TemplateType.SOCIAL_MARKET_UPDATE: """
Write a short social media post for a MARKET UPDATE.

Platform: Instagram + Facebook
Agent: Elena James
Area: {area}
Timeframe: {timeframe}
Key Stats: {stats}

Instructions:
- 2–4 short sentences
- Summarize the market in plain language
- Mention 2–3 key stats or trends
- Add a soft call-to-action for buyers/sellers to reach out
- No hashtags
- Tone: calm, expert, reassuring
""",
}


def render_template(template_type: TemplateType, **kwargs) -> str:
    template = TEMPLATES.get(template_type)
    if not template:
        raise ValueError(f"Template not found: {template_type}")
    return template.format(**kwargs)
    
def _template_defaults():
    """Default values for all supported Elena template variables."""
    return {
        "address": "",
        "city": "",
        "state": "",
        "zip_code": "",
        "beds": "",
        "baths": "",
        "sqft": "",
        "price": "",
        "description": "",
        "status": "",
        "days_on_market": "",
        "offer_details": "",
        "date": "",
        "time": "",
        "old_price": "",
        "new_price": "",
        "buyer_type": "",
        "budget": "",
        "areas": "",
        "area": "",
        "timeframe": "",
        "stats": "",
        "client_name": "",
        "pipeline_stage": "",
        "context": "",
        "source": "",
        "email": "",
        "phone": "",
        "title": "",
        "cta": "",
    }


def _get_template_enum(template_type_value):
    if not template_type_value:
        return None
    try:
        return TemplateType(template_type_value)
    except ValueError:
        return None
