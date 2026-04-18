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
    TemplateType.JUST_LISTED: """
You are writing a JUST LISTED real estate flyer for Elena James of Keller Williams Hudson Valley.

Property:
Address: {address}
City: {city}, {state} {zip_code}
Beds: {beds}
Baths: {baths}
Sqft: {sqft}
Price: {price}
Description: {description}

Return the result in exactly this format:

HEADLINE:
SUBHEADLINE:
BODY:
BULLETS:
- 
- 
- 
CTA:

Rules:
- Headline must be 3 to 8 words
- Subheadline must be one short sentence
- Body must be 2 short sentences max
- Bullets must be 3 to 5 concise points
- CTA must be one sentence
- Tone: elevated, warm, polished, service-first
- No hashtags
""",

    TemplateType.JUST_SOLD: """
You are writing a JUST SOLD real estate flyer for Elena James.

Property:
Address: {address}
City: {city}, {state} {zip_code}
Sale Price: {price}
Days on Market: {days_on_market}
Offer Details: {offer_details}

Return the result in exactly this format:

HEADLINE:
SUBHEADLINE:
BODY:
BULLETS:
- 
- 
- 
CTA:

Rules:
- Celebrate the result
- Mention the area naturally
- Body must be 2 short sentences max
- Bullets must highlight 3 to 5 selling points
- CTA should invite nearby homeowners to connect
- Tone: confident, warm, polished
- No hashtags
""",

    TemplateType.COMING_SOON: """
You are writing a COMING SOON flyer for Elena James.

Property:
Address: {address}
City: {city}, {state} {zip_code}
Beds: {beds}
Baths: {baths}
Sqft: {sqft}
Price: {price}
Description: {description}

Return the result in exactly this format:

HEADLINE:
SUBHEADLINE:
BODY:
BULLETS:
- 
- 
- 
CTA:

Rules:
- Create curiosity
- Position this as early access
- Body must be 2 short sentences max
- Bullets must be 3 to 5 concise points
- CTA should encourage early inquiry
- Tone: anticipatory, inviting, polished
- No hashtags
""",

    TemplateType.OPEN_HOUSE: """
You are writing an OPEN HOUSE flyer for Elena James.

Property:
Address: {address}
City: {city}, {state} {zip_code}
Date: {date}
Time: {time}
Beds: {beds}
Baths: {baths}
Sqft: {sqft}
Price: {price}
Description: {description}

Return the result in exactly this format:

HEADLINE:
SUBHEADLINE:
BODY:
BULLETS:
- 
- 
- 
CTA:

Rules:
- Clearly reference the open house
- Include date and time naturally
- Body must be 2 short sentences max
- Bullets must be 3 to 5 concise points
- CTA should invite a visit or private showing
- Tone: welcoming, polished, professional
- No hashtags
""",

    TemplateType.PRICE_DROP: """
You are writing a PRICE IMPROVEMENT flyer for Elena James.

Property:
Address: {address}
City: {city}, {state} {zip_code}
Old Price: {old_price}
New Price: {new_price}
Beds: {beds}
Baths: {baths}
Sqft: {sqft}
Description: {description}

Return the result in exactly this format:

HEADLINE:
SUBHEADLINE:
BODY:
BULLETS:
- 
- 
- 
CTA:

Rules:
- Emphasize the new value
- Body must be 2 short sentences max
- Bullets must be 3 to 5 concise points
- CTA should encourage immediate action
- Tone: optimistic, value-driven, polished
- No hashtags
""",

    TemplateType.BUYER_NEED: """
You are writing a BUYER NEED flyer for Elena James.

Buyer:
Buyer Type: {buyer_type}
Budget: {budget}
Beds: {beds}
Baths: {baths}
Preferred Areas: {areas}

Return the result in exactly this format:

HEADLINE:
SUBHEADLINE:
BODY:
BULLETS:
- 
- 
- 
CTA:

Rules:
- Position the buyer as active and real
- Body must be 2 short sentences max
- Bullets must show 3 to 5 criteria
- CTA should invite off-market opportunities
- Tone: respectful, direct, opportunity-focused
- No hashtags
""",

    TemplateType.MARKET_UPDATE: """
You are writing a local MARKET UPDATE flyer for Elena James.

Area: {area}
Timeframe: {timeframe}
Key Stats: {stats}

Return the result in exactly this format:

HEADLINE:
SUBHEADLINE:
BODY:
BULLETS:
- 
- 
- 
CTA:

Rules:
- Make the market understandable
- Body must be 2 short sentences max
- Bullets should include 4 to 6 useful insights
- CTA should invite buyers or sellers to connect
- Tone: calm, expert, reassuring
- No hashtags
""",

    TemplateType.FOLLOWUP_GENERAL: """
Write a follow-up email from Elena James.

Client Name: {client_name}
Pipeline Stage: {pipeline_stage}
Context: {context}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Email must be 4 to 7 sentences
- Warm, polished, easy to reply to
- Suggest a practical next step
- Tone: service-first, not pushy
""",

    TemplateType.FOLLOWUP_AFTER_SHOWING: """
Write a post-showing follow-up email from Elena James.

Client Name: {client_name}
Property Address: {address}
City: {city}, {state} {zip_code}
Context: {context}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Reference the property naturally
- Ask for reaction or feedback
- Offer next steps
- Email must be 4 to 7 sentences
- Tone: warm, attentive, professional
""",

    TemplateType.FOLLOWUP_NEW_LEAD: """
Write a new lead follow-up email from Elena James.

Client Name: {client_name}
Lead Source: {source}
Context: {context}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Acknowledge how they came in
- Briefly introduce Elena’s approach
- Invite a call or reply
- Email must be 4 to 7 sentences
- Tone: warm, confident, approachable
""",

    TemplateType.FOLLOWUP_INACTIVE: """
Write a re-engagement email from Elena James.

Client Name: {client_name}
Last Contact Context: {context}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Gently acknowledge the gap
- Offer value or a reason to reconnect
- Keep pressure low
- Email must be 4 to 7 sentences
- Tone: thoughtful, low-pressure, warm
""",

    TemplateType.SOCIAL_JUST_LISTED: """
Write a short social caption for a JUST LISTED property.

Platform: Instagram + Facebook
Address: {address}
City: {city}, {state}
Beds: {beds}
Baths: {baths}
Price: {price}
Description: {description}

Return the result in exactly this format:

HOOK:
CAPTION:
CTA:

Rules:
- Hook must be one short line
- Caption must be 2 to 3 short sentences
- CTA must be one sentence
- No hashtags
- Tone: elevated, warm, exciting
""",

    TemplateType.SOCIAL_JUST_SOLD: """
Write a short social caption for a JUST SOLD property.

Platform: Instagram + Facebook
Address: {address}
City: {city}, {state}
Sale Price: {price}
Context: {context}

Return the result in exactly this format:

HOOK:
CAPTION:
CTA:

Rules:
- Celebrate the outcome
- Caption must stay concise
- CTA should invite future sellers to connect
- No hashtags
- Tone: grateful, celebratory, polished
""",

    TemplateType.SOCIAL_OPEN_HOUSE: """
Write a short social caption for an OPEN HOUSE.

Platform: Instagram + Facebook
Address: {address}
City: {city}, {state}
Date: {date}
Time: {time}

Return the result in exactly this format:

HOOK:
CAPTION:
CTA:

Rules:
- Mention date and time naturally
- Caption must be 2 to 3 short sentences
- CTA must invite attendance
- No hashtags
- Tone: upbeat, welcoming, polished
""",

    TemplateType.SOCIAL_MARKET_UPDATE: """
Write a short social caption for a MARKET UPDATE.

Platform: Instagram + Facebook
Area: {area}
Timeframe: {timeframe}
Key Stats: {stats}

Return the result in exactly this format:

HOOK:
CAPTION:
CTA:

Rules:
- Make the market feel understandable
- Mention 2 to 3 useful takeaways
- CTA should invite conversation
- No hashtags
- Tone: calm, expert, approachable
""",
}


def render_template(template_type: TemplateType, **kwargs) -> str:
    template = TEMPLATES.get(template_type)
    if not template:
        raise ValueError(f"Template not found: {template_type}")
    return template.format(**kwargs)