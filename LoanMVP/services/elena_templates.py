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

    # ── Insurance Flyers ────────────────────────────────────────────────────
    INSURANCE_COVERAGE_FLYER = "insurance_coverage_flyer"
    INSURANCE_QUOTE_OFFER = "insurance_quote_offer"

    # ── Insurance Emails ────────────────────────────────────────────────────
    INSURANCE_POLICY_REVIEW = "insurance_policy_review"
    INSURANCE_CLAIMS_SUPPORT = "insurance_claims_support"
    INSURANCE_FOLLOWUP_QUOTE = "insurance_followup_quote"
    INSURANCE_FOLLOWUP_RENEWAL = "insurance_followup_renewal"
    INSURANCE_REFERRAL_ASK = "insurance_referral_ask"

    # ── Insurance Social ────────────────────────────────────────────────────
    SOCIAL_INSURANCE_TIP = "social_insurance_tip"
    SOCIAL_INSURANCE_TESTIMONIAL = "social_insurance_testimonial"

    # ── Lending Flyers ──────────────────────────────────────────────────────
    LENDING_RATE_ALERT = "lending_rate_alert"
    LENDING_PRE_APPROVAL = "lending_pre_approval"
    LENDING_FIRST_TIME_BUYER = "lending_first_time_buyer"
    LENDING_REFINANCE = "lending_refinance"
    LENDING_INVESTMENT_LOAN = "lending_investment_loan"

    # ── Lending Emails ──────────────────────────────────────────────────────
    LENDING_FOLLOWUP_APPLICATION = "lending_followup_application"
    LENDING_FOLLOWUP_RATE_LOCK = "lending_followup_rate_lock"
    LENDING_REFERRAL_ASK = "lending_referral_ask"

    # ── Lending Social ──────────────────────────────────────────────────────
    SOCIAL_RATE_UPDATE = "social_rate_update"
    SOCIAL_LOAN_CLOSED = "social_loan_closed"


TEMPLATES = {

    # ── Realtor Flyers ───────────────────────────────────────────────────────

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

    # ── Realtor Emails ───────────────────────────────────────────────────────

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

    # ── Realtor Social ───────────────────────────────────────────────────────

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

    # ── Insurance Flyers ─────────────────────────────────────────────────────

    TemplateType.INSURANCE_COVERAGE_FLYER: """
You are writing a HOME & PROPERTY COVERAGE flyer for {agent_name} of {agent_company}.

Agent: {agent_name}
Company: {agent_company}
Coverage Types: {coverage_type}
Service Area: {service_area}
Phone: {phone}
Key Benefits: {offer_details}

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
- Headline must speak to protection and peace of mind (3 to 8 words)
- Subheadline must be one short sentence about what they protect
- Body must be 2 short sentences on why coverage matters now
- Bullets must list 3 to 5 coverage types or key benefits
- CTA should invite a free quote or a coverage review call
- Tone: reassuring, trustworthy, straightforward
- No hashtags
""",

    TemplateType.INSURANCE_QUOTE_OFFER: """
You are writing a FREE QUOTE offer flyer for insurance agent {agent_name} of {agent_company}.

Agent: {agent_name}
Company: {agent_company}
Coverage Types: {coverage_type}
Quote Offer: {offer_details}
Service Area: {service_area}
Phone: {phone}

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
- Headline must lead with the free quote offer
- Subheadline must be one short reassuring sentence
- Body must be 2 short sentences on what the quote process looks like
- Bullets must highlight 3 to 5 types of coverage or reasons to get a quote
- CTA must include the phone number or next step clearly
- Tone: approachable, helpful, no-pressure
- No hashtags
""",

    # ── Insurance Emails ─────────────────────────────────────────────────────

    TemplateType.INSURANCE_POLICY_REVIEW: """
Write a policy review outreach email from insurance agent {agent_name}.

Client Name: {client_name}
Policy Type: {policy_type}
Context / Reason for Review: {context}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Email must be 4 to 6 sentences
- Frame the review as a benefit, not a sales call
- Mention one or two reasons a review is timely (rate changes, life events, etc.)
- Include a clear next step (reply, call, or book a time)
- Tone: helpful, professional, proactive
""",

    TemplateType.INSURANCE_CLAIMS_SUPPORT: """
Write a post-claim support email from insurance agent {agent_name}.

Client Name: {client_name}
Claim Type: {policy_type}
Context: {context}
Notes: {notes}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Open with empathy and acknowledgment of the situation
- Reassure the client about the process
- Offer to be a direct resource and advocate
- Email must be 4 to 6 sentences
- Tone: warm, calm, genuinely supportive
""",

    TemplateType.INSURANCE_FOLLOWUP_QUOTE: """
Write a follow-up email from insurance agent {agent_name} after sending a quote.

Client Name: {client_name}
Quote Type: {policy_type}
Quote Date: {estimate_date}
Notes: {notes}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Reference the quote naturally without pressure
- Offer to clarify coverage options or adjust the quote
- Include a clear next step
- Email must be 4 to 6 sentences
- Tone: helpful, patient, professional
""",

    TemplateType.INSURANCE_FOLLOWUP_RENEWAL: """
Write a policy renewal reminder email from insurance agent {agent_name}.

Client Name: {client_name}
Policy Type: {policy_type}
Renewal Date: {renewal_date}
Notes: {notes}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Reference the upcoming renewal date clearly
- Frame it as a service reminder, not a hard sell
- Offer to review the policy for any needed updates
- Email must be 4 to 6 sentences
- Tone: helpful, timely, low-pressure
""",

    TemplateType.INSURANCE_REFERRAL_ASK: """
Write a referral request email from insurance agent {agent_name}.

Client Name: {client_name}
Policy Type: {policy_type}
Referral Incentive: {incentive}
Notes: {notes}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Express genuine appreciation for the client's trust
- Make the referral ask feel natural and easy
- Briefly describe who you help (homeowners, renters, families, businesses, etc.)
- Mention any referral incentive if provided
- Email must be 4 to 6 sentences
- Tone: grateful, warm, easy to forward
""",

    # ── Insurance Social ─────────────────────────────────────────────────────

    TemplateType.SOCIAL_INSURANCE_TIP: """
Write a short social post sharing a home or property INSURANCE TIP.

Platform: Instagram + Facebook
Agent: {agent_name}
Tip Topic: {tip}
Coverage Type: {coverage_type}

Return the result in exactly this format:

HOOK:
CAPTION:
CTA:

Rules:
- Hook must be one short, attention-grabbing line about the tip
- Caption must deliver 1 to 2 practical, useful sentences on the tip
- CTA must invite a question, reply, or free quote request
- No hashtags
- Tone: knowledgeable, friendly, genuinely helpful
""",

    TemplateType.SOCIAL_INSURANCE_TESTIMONIAL: """
Write a short social caption sharing a CLIENT TESTIMONIAL for insurance agent {agent_name}.

Platform: Instagram + Facebook
Client Name: {client_name}
Coverage Type: {coverage_type}
Testimonial: {testimonial}

Return the result in exactly this format:

HOOK:
CAPTION:
CTA:

Rules:
- Hook must highlight the client outcome or relief
- Caption must quote or paraphrase the testimonial naturally
- CTA must invite others to get covered or reach out
- No hashtags
- Tone: warm, trust-building, social-proof-driven
""",

    # ── Lending Flyers ───────────────────────────────────────────────────────

    TemplateType.LENDING_RATE_ALERT: """
You are writing a RATE ALERT flyer for loan officer {agent_name} of {agent_company}.

Loan Officer: {agent_name}
Company: {agent_company}
Current Rate: {current_rate}
Loan Type: {loan_type}
Max Loan Amount: {max_loan_amount}
Phone: {phone}

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
- Headline must highlight the rate opportunity (3 to 8 words)
- Subheadline must be one short sentence on why now is the time
- Body must be 2 short sentences on what this rate means for buyers
- Bullets must include 3 to 5 quick facts (rate, loan types, who qualifies, etc.)
- CTA must invite a call, text, or pre-approval application
- Tone: urgent-but-helpful, credible, action-oriented
- No hashtags
""",

    TemplateType.LENDING_PRE_APPROVAL: """
You are writing a PRE-APPROVAL OFFER flyer for loan officer {agent_name} of {agent_company}.

Loan Officer: {agent_name}
Company: {agent_company}
Loan Type: {loan_type}
Max Loan Amount: {max_loan_amount}
Program Name: {program_name}
Phone: {phone}

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
- Headline must position pre-approval as the first step to homeownership
- Subheadline must be one short reassuring sentence
- Body must be 2 short sentences on how fast and easy the process is
- Bullets must list 3 to 5 benefits of getting pre-approved now
- CTA must invite an application or quick call
- Tone: empowering, straightforward, encouraging
- No hashtags
""",

    TemplateType.LENDING_FIRST_TIME_BUYER: """
You are writing a FIRST-TIME BUYER PROGRAM flyer for loan officer {agent_name} of {agent_company}.

Loan Officer: {agent_name}
Company: {agent_company}
Program Name: {program_name}
Loan Type: {loan_type}
Max Loan Amount: {max_loan_amount}
Key Benefits: {offer_details}
Phone: {phone}

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
- Headline must speak directly to first-time buyers
- Subheadline must make the program feel accessible
- Body must be 2 short sentences explaining what the program offers
- Bullets must highlight 3 to 5 program benefits (low down payment, grants, etc.)
- CTA must invite a call or application to get started
- Tone: welcoming, educational, empowering
- No hashtags
""",

    TemplateType.LENDING_REFINANCE: """
You are writing a REFINANCE OPPORTUNITY flyer for loan officer {agent_name} of {agent_company}.

Loan Officer: {agent_name}
Company: {agent_company}
Current Rate: {current_rate}
Loan Type: {loan_type}
Key Benefit: {offer_details}
Phone: {phone}

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
- Headline must create a sense of opportunity around refinancing
- Subheadline must be one short sentence on potential savings
- Body must be 2 short sentences on who should refinance and why now
- Bullets must highlight 3 to 5 refinance benefits (lower payment, cash out, shorter term, etc.)
- CTA must invite a free refinance consultation
- Tone: opportunistic, helpful, credible
- No hashtags
""",

    TemplateType.LENDING_INVESTMENT_LOAN: """
You are writing an INVESTMENT PROPERTY LOAN flyer for loan officer {agent_name} of {agent_company}.

Loan Officer: {agent_name}
Company: {agent_company}
Loan Type: {loan_type}
Max Loan Amount: {max_loan_amount}
Program Name: {program_name}
Key Benefits: {offer_details}
Phone: {phone}

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
- Headline must appeal to investors and wealth builders
- Subheadline must position the loan as a strategic tool
- Body must be 2 short sentences on what properties or strategies qualify
- Bullets must highlight 3 to 5 loan features (terms, LTV, cash-out, DSCR, etc.)
- CTA must invite a strategy call or pre-qualification
- Tone: sophisticated, results-focused, investor-minded
- No hashtags
""",

    # ── Lending Emails ───────────────────────────────────────────────────────

    TemplateType.LENDING_FOLLOWUP_APPLICATION: """
Write a follow-up email from loan officer {agent_name} after receiving a loan application.

Borrower Name: {client_name}
Loan Type: {loan_type}
Application Date: {estimate_date}
Context: {context}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Confirm receipt of the application and set expectations
- Explain the next step in the process clearly
- Offer to answer any questions
- Email must be 4 to 6 sentences
- Tone: professional, reassuring, organized
""",

    TemplateType.LENDING_FOLLOWUP_RATE_LOCK: """
Write a rate lock follow-up email from loan officer {agent_name}.

Borrower Name: {client_name}
Loan Type: {loan_type}
Rate Lock Deadline: {renewal_date}
Context: {context}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Reference the rate lock window with urgency but not pressure
- Explain what locking in means for the borrower
- Offer to walk through options or answer questions
- Email must be 4 to 6 sentences
- Tone: helpful, timely, credible
""",

    TemplateType.LENDING_REFERRAL_ASK: """
Write a referral request email from loan officer {agent_name}.

Client Name: {client_name}
Loan Type: {loan_type}
Referral Incentive: {incentive}
Notes: {notes}

Return the result in exactly this format:

SUBJECT:
EMAIL:

Rules:
- Express genuine appreciation for the client's business
- Make the referral ask feel natural and warm
- Briefly describe who you help (first-time buyers, investors, move-up buyers, etc.)
- Mention any referral incentive if provided
- Email must be 4 to 6 sentences
- Tone: grateful, relationship-focused, easy to forward
""",

    # ── Lending Social ───────────────────────────────────────────────────────

    TemplateType.SOCIAL_RATE_UPDATE: """
Write a short social post sharing a MORTGAGE RATE UPDATE.

Platform: Instagram + Facebook
Loan Officer: {agent_name}
Current Rate: {current_rate}
Loan Type: {loan_type}
Context: {context}

Return the result in exactly this format:

HOOK:
CAPTION:
CTA:

Rules:
- Hook must grab attention with the rate news
- Caption must explain what this means for buyers or homeowners in 2 to 3 sentences
- CTA must invite a DM, call, or pre-approval
- No hashtags
- Tone: informative, timely, accessible
""",

    TemplateType.SOCIAL_LOAN_CLOSED: """
Write a short social caption celebrating a CLOSED LOAN.

Platform: Instagram + Facebook
Loan Officer: {agent_name}
Borrower First Name: {client_name}
Loan Type: {loan_type}
Context: {context}

Return the result in exactly this format:

HOOK:
CAPTION:
CTA:

Rules:
- Hook must celebrate the milestone
- Caption must highlight the borrower's achievement in 2 to 3 short sentences
- Keep the borrower anonymous or use first name only if provided
- CTA must invite others who are ready to start their journey
- No hashtags
- Tone: celebratory, warm, inspiring
""",
}


# ── Role-to-template sets ────────────────────────────────────────────────────

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

INSURANCE_TEMPLATES = {
    TemplateType.INSURANCE_COVERAGE_FLYER, TemplateType.INSURANCE_QUOTE_OFFER,
    TemplateType.INSURANCE_POLICY_REVIEW, TemplateType.INSURANCE_CLAIMS_SUPPORT,
    TemplateType.INSURANCE_FOLLOWUP_QUOTE, TemplateType.INSURANCE_FOLLOWUP_RENEWAL,
    TemplateType.INSURANCE_REFERRAL_ASK, TemplateType.SOCIAL_INSURANCE_TIP,
    TemplateType.SOCIAL_INSURANCE_TESTIMONIAL,
}

LENDING_TEMPLATES = {
    TemplateType.LENDING_RATE_ALERT, TemplateType.LENDING_PRE_APPROVAL,
    TemplateType.LENDING_FIRST_TIME_BUYER, TemplateType.LENDING_REFINANCE,
    TemplateType.LENDING_INVESTMENT_LOAN, TemplateType.LENDING_FOLLOWUP_APPLICATION,
    TemplateType.LENDING_FOLLOWUP_RATE_LOCK, TemplateType.LENDING_REFERRAL_ASK,
    TemplateType.SOCIAL_RATE_UPDATE, TemplateType.SOCIAL_LOAN_CLOSED,
}

# Hybrid roles get both sets
CONTRACTOR_REALTOR_TEMPLATES = REALTOR_TEMPLATES | CONTRACTOR_TEMPLATES
INSURANCE_REALTOR_TEMPLATES = REALTOR_TEMPLATES | INSURANCE_TEMPLATES


def templates_for_role(role_type: str) -> list:
    """Return ordered list of TemplateType values for the given VIP role."""
    role = (role_type or "realtor").lower()
    if role == "contractor":
        allowed = CONTRACTOR_TEMPLATES
    elif role == "contractor_realtor":
        allowed = CONTRACTOR_REALTOR_TEMPLATES
    elif role == "insurance":
        allowed = INSURANCE_TEMPLATES
    elif role == "insurance_realtor":
        allowed = INSURANCE_REALTOR_TEMPLATES
    elif role in ("loan_officer", "lender"):
        allowed = LENDING_TEMPLATES
    else:
        allowed = REALTOR_TEMPLATES
    return [t.value for t in TemplateType if t in allowed]


def render_template(template_type: TemplateType, **kwargs) -> str:
    template = TEMPLATES.get(template_type)
    if not template:
        raise ValueError(f"Template not found: {template_type}")
    # Provide safe defaults for every known placeholder so .format() never
    # raises a KeyError when a user leaves a field blank.
    defaults = {
        # shared / realtor
        "agent_name": "Agent", "agent_company": "", "address": "", "city": "",
        "state": "", "zip_code": "", "beds": "", "baths": "", "sqft": "",
        "price": "", "description": "", "days_on_market": "", "offer_details": "",
        "date": "", "time": "", "old_price": "", "new_price": "", "buyer_type": "",
        "budget": "", "areas": "", "area": "", "timeframe": "", "stats": "",
        "client_name": "", "pipeline_stage": "", "context": "", "source": "",
        "email": "", "phone": "", "title": "", "cta": "",
        # contractor
        "contractor_name": "", "trade": "", "project_type": "", "scope": "",
        "completion_date": "", "materials": "", "before_description": "",
        "after_description": "", "timeline": "", "budget_range": "",
        "service_area": "", "years_experience": "", "services": "",
        "certifications": "", "new_service": "", "service_details": "",
        "reason": "", "estimate_date": "", "estimate_amount": "",
        "notes": "", "incentive": "", "highlight": "", "testimonial": "",
        # insurance
        "coverage_type": "", "policy_type": "", "renewal_date": "", "tip": "",
        # lending
        "current_rate": "", "loan_type": "", "max_loan_amount": "",
        "program_name": "", "rate_lock_deadline": "",
    }
    defaults.update(kwargs)
    return template.format(**defaults)
