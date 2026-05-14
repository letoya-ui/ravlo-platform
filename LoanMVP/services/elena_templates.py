from enum import Enum


class TemplateType(str, Enum):
    # ── Realtor Flyers ──────────────────────────────────────────────────────
    JUST_LISTED = "just_listed"
    JUST_SOLD = "just_sold"
    COMING_SOON = "coming_soon"
    OPEN_HOUSE = "open_house"
    PRICE_DROP = "price_drop"
    BUYER_NEED = "buyer_need"
    MARKET_UPDATE = "market_update"

    # ── Realtor Emails ──────────────────────────────────────────────────────
    FOLLOWUP_GENERAL = "followup_general"
    FOLLOWUP_AFTER_SHOWING = "followup_after_showing"
    FOLLOWUP_NEW_LEAD = "followup_new_lead"
    FOLLOWUP_INACTIVE = "followup_inactive"

    # ── Realtor Social ──────────────────────────────────────────────────────
    SOCIAL_JUST_LISTED = "social_just_listed"
    SOCIAL_JUST_SOLD = "social_just_sold"
    SOCIAL_OPEN_HOUSE = "social_open_house"
    SOCIAL_MARKET_UPDATE = "social_market_update"

    # ── Contractor Flyers ───────────────────────────────────────────────────
    PROJECT_SHOWCASE = "project_showcase"
    PROJECT_BEFORE_AFTER = "project_before_after"
    FREE_ESTIMATE = "free_estimate"
    SERVICES_FLYER = "services_flyer"
    NEW_SERVICE = "new_service"

    # ── Contractor Emails ───────────────────────────────────────────────────
    CONTRACTOR_FOLLOWUP_ESTIMATE = "contractor_followup_estimate"
    CONTRACTOR_FOLLOWUP_COMPLETE = "contractor_followup_complete"
    CONTRACTOR_REFERRAL_ASK = "contractor_referral_ask"

    # ── Contractor Social ───────────────────────────────────────────────────
    SOCIAL_PROJECT_HIGHLIGHT = "social_project_highlight"
    SOCIAL_BEFORE_AFTER = "social_before_after"
    SOCIAL_TESTIMONIAL = "social_testimonial"


TEMPLATES = {
    TemplateType.JUST_LISTED: """
You are writing a JUST LISTED real estate flyer for {agent_name} of {agent_company}.

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
You are writing a JUST SOLD real estate flyer for {agent_name}.

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
You are writing a COMING SOON flyer for {agent_name}.

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
You are writing an OPEN HOUSE flyer for {agent_name}.

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
You are writing a PRICE IMPROVEMENT flyer for {agent_name}.

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
You are writing a BUYER NEED flyer for {agent_name}.

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
You are writing a local MARKET UPDATE flyer for {agent_name}.

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
Write a follow-up email from {agent_name}.

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
Write a post-showing follow-up email from {agent_name}.

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
Write a new lead follow-up email from {agent_name}.

Client Name: {client_name}
Lead Source: {source}
Context: {context}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Acknowledge how they came in
- Briefly introduce the agent's approach
- Invite a call or reply
- Email must be 4 to 7 sentences
- Tone: warm, confident, approachable
""",

    TemplateType.FOLLOWUP_INACTIVE: """
Write a re-engagement email from {agent_name}.

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


    # ── Contractor Flyers ────────────────────────────────────────────────────

    TemplateType.PROJECT_SHOWCASE: """
You are writing a PROJECT SHOWCASE flyer for {contractor_name}, a {trade} contractor.

Project:
Address: {address}
Project Type: {project_type}
Scope: {scope}
Completion Date: {completion_date}
Key Materials: {materials}

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
- Headline must be 3 to 8 words highlighting the transformation
- Subheadline must be one short sentence
- Body must be 2 short sentences max describing the result
- Bullets must highlight 3 to 5 standout features of the work
- CTA should invite neighbors or investors to request a quote
- Tone: confident, professional, quality-first
- No hashtags
""",

    TemplateType.PROJECT_BEFORE_AFTER: """
You are writing a BEFORE & AFTER flyer for {contractor_name}, a {trade} contractor.

Project:
Address: {address}
Project Type: {project_type}
Before Condition: {before_description}
After Result: {after_description}
Timeline: {timeline}
Budget Range: {budget_range}

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
- Headline must emphasize the transformation
- Subheadline must be one short sentence
- Body must contrast before vs. after in 2 sentences max
- Bullets must highlight 3 to 5 improvements made
- CTA should invite a free consultation or estimate
- Tone: results-driven, professional, trustworthy
- No hashtags
""",

    TemplateType.FREE_ESTIMATE: """
You are writing a FREE ESTIMATE offer flyer for {contractor_name}, a {trade} contractor.

Business:
Contractor: {contractor_name}
Trade / Specialty: {trade}
Service Area: {service_area}
Phone: {phone}
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
- Headline must lead with the free estimate offer
- Subheadline must be one short sentence about the service
- Body must be 2 short sentences explaining value and process
- Bullets must list 3 to 5 services or specialties offered
- CTA must include a clear call to action (call, text, or book online)
- Tone: approachable, trustworthy, action-oriented
- No hashtags
""",

    TemplateType.SERVICES_FLYER: """
You are writing a SERVICES OVERVIEW flyer for {contractor_name}, a {trade} contractor.

Business:
Contractor: {contractor_name}
Trade / Specialty: {trade}
Years of Experience: {years_experience}
Service Area: {service_area}
Services Offered: {services}
Licenses / Certifications: {certifications}

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
- Headline must position the contractor's expertise
- Subheadline must be one short sentence
- Body must be 2 short sentences establishing trust and credibility
- Bullets must list 3 to 6 core services or differentiators
- CTA should invite a quote or consultation
- Tone: professional, experienced, quality-focused
- No hashtags
""",

    TemplateType.NEW_SERVICE: """
You are writing a NEW SERVICE announcement flyer for {contractor_name}.

Announcement:
Contractor: {contractor_name}
New Service: {new_service}
Service Details: {service_details}
Why Now: {reason}
Service Area: {service_area}

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
- Headline must announce the new service with excitement
- Subheadline must be one short sentence
- Body must be 2 short sentences explaining why it matters
- Bullets must highlight 3 to 5 benefits of the new service
- CTA should invite early bookings or inquiries
- Tone: enthusiastic, professional, forward-looking
- No hashtags
""",

    # ── Contractor Emails ────────────────────────────────────────────────────

    TemplateType.CONTRACTOR_FOLLOWUP_ESTIMATE: """
Write an estimate follow-up email from {contractor_name}.

Client Name: {client_name}
Estimate Sent: {estimate_date}
Project Type: {project_type}
Estimate Amount: {estimate_amount}
Notes: {notes}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Email must be 4 to 6 sentences
- Reference the estimate naturally without being pushy
- Offer to answer questions or adjust the scope
- Include a clear next step
- Tone: professional, helpful, confident
""",

    TemplateType.CONTRACTOR_FOLLOWUP_COMPLETE: """
Write a project completion follow-up email from {contractor_name}.

Client Name: {client_name}
Project Type: {project_type}
Address: {address}
Completion Date: {completion_date}
Notes: {notes}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Thank the client for their business
- Briefly recap the work completed
- Ask for a review or testimonial
- Mention referral program or future availability
- Email must be 4 to 6 sentences
- Tone: warm, proud of the work, relationship-focused
""",

    TemplateType.CONTRACTOR_REFERRAL_ASK: """
Write a referral request email from {contractor_name}.

Client Name: {client_name}
Previous Project: {project_type}
Referral Incentive: {incentive}
Notes: {notes}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Express genuine appreciation for their past business
- Make the referral ask feel natural, not transactional
- Briefly describe the types of clients you work with
- Mention any referral incentive if provided
- Email must be 4 to 6 sentences
- Tone: grateful, warm, easy to forward
""",

    # ── Contractor Social ────────────────────────────────────────────────────

    TemplateType.SOCIAL_PROJECT_HIGHLIGHT: """
Write a short social caption for a COMPLETED PROJECT.

Platform: Instagram + Facebook
Contractor: {contractor_name}
Trade: {trade}
Project Type: {project_type}
Address / Area: {area}
Highlight: {highlight}

Return the result in exactly this format:

HOOK:
CAPTION:
CTA:

Rules:
- Hook must be one short punchy line
- Caption must be 2 to 3 short sentences about the project
- CTA must invite inquiries or a quote request
- No hashtags
- Tone: proud, professional, results-focused
""",

    TemplateType.SOCIAL_BEFORE_AFTER: """
Write a short social caption for a BEFORE & AFTER transformation.

Platform: Instagram + Facebook
Contractor: {contractor_name}
Project Type: {project_type}
Area: {area}
Before: {before_description}
After: {after_description}

Return the result in exactly this format:

HOOK:
CAPTION:
CTA:

Rules:
- Hook must tease the transformation
- Caption must contrast before and after in 2 to 3 sentences
- CTA must invite a quote or consultation
- No hashtags
- Tone: excited, confident, results-first
""",

    TemplateType.SOCIAL_TESTIMONIAL: """
Write a short social caption sharing a CLIENT TESTIMONIAL.

Platform: Instagram + Facebook
Contractor: {contractor_name}
Client Name: {client_name}
Project Type: {project_type}
Testimonial: {testimonial}

Return the result in exactly this format:

HOOK:
CAPTION:
CTA:

Rules:
- Hook must lead with the client result or praise
- Caption must quote or paraphrase the testimonial naturally
- CTA must invite others to book or inquire
- No hashtags
- Tone: grateful, social-proof-driven, warm
""",
}


# Role-to-template mapping — used by the template_studio route to filter
# the dropdown to role-appropriate options only.
REALTOR_TEMPLATES = {
    TemplateType.JUST_LISTED, TemplateType.JUST_SOLD, TemplateType.COMING_SOON,
    TemplateType.OPEN_HOUSE, TemplateType.PRICE_DROP, TemplateType.BUYER_NEED,
    TemplateType.MARKET_UPDATE, TemplateType.FOLLOWUP_GENERAL,
    TemplateType.FOLLOWUP_AFTER_SHOWING, TemplateType.FOLLOWUP_NEW_LEAD,
    TemplateType.FOLLOWUP_INACTIVE, TemplateType.SOCIAL_JUST_LISTED,
    TemplateType.SOCIAL_JUST_SOLD, TemplateType.SOCIAL_OPEN_HOUSE,
    TemplateType.SOCIAL_MARKET_UPDATE,
}

CONTRACTOR_TEMPLATES = {
    TemplateType.PROJECT_SHOWCASE, TemplateType.PROJECT_BEFORE_AFTER,
    TemplateType.FREE_ESTIMATE, TemplateType.SERVICES_FLYER,
    TemplateType.NEW_SERVICE, TemplateType.CONTRACTOR_FOLLOWUP_ESTIMATE,
    TemplateType.CONTRACTOR_FOLLOWUP_COMPLETE, TemplateType.CONTRACTOR_REFERRAL_ASK,
    TemplateType.SOCIAL_PROJECT_HIGHLIGHT, TemplateType.SOCIAL_BEFORE_AFTER,
    TemplateType.SOCIAL_TESTIMONIAL,
}

# Roles that share both realtor + contractor templates (hybrid roles)
CONTRACTOR_REALTOR_TEMPLATES = REALTOR_TEMPLATES | CONTRACTOR_TEMPLATES


def templates_for_role(role_type: str) -> list:
    """Return ordered list of TemplateType values for the given VIP role."""
    role = (role_type or "realtor").lower()
    if role in ("contractor",):
        allowed = CONTRACTOR_TEMPLATES
    elif role in ("contractor_realtor",):
        allowed = CONTRACTOR_REALTOR_TEMPLATES
    elif role in ("insurance", "insurance_realtor", "loan_officer", "lender"):
        # Insurance and loan officers get the general/social templates from
        # the contractor set (useful for business promotion) plus realtor ones
        allowed = CONTRACTOR_TEMPLATES | REALTOR_TEMPLATES
    else:
        allowed = REALTOR_TEMPLATES
    return [t.value for t in TemplateType if t in allowed]


def render_template(template_type: TemplateType, **kwargs) -> str:
    template = TEMPLATES.get(template_type)
    if not template:
        raise ValueError(f"Template not found: {template_type}")
    kwargs.setdefault("agent_name", "Agent")
    kwargs.setdefault("agent_company", "")
    return template.format(**kwargs)