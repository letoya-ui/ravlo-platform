# Ravlo Partner Action System

## Purpose

Partner actions should appear exactly where the user needs outside help.

Partners should not feel like a separate directory users have to remember to open. Ravlo should surface the right partner action from the current deal, property, studio, budget, or project context.

This extends the Ravlo Discovery Loop:

> Every screen should answer: what happens next?

Sometimes the next step is not another Ravlo tool.

Sometimes the next step is a Realtor, contractor, designer, lender, inspector, property manager, or another local professional.

---

## Core Rule

Every major investor object should support contextual partner actions.

The action should be specific to what the user is doing, not generic.

Bad:

- Send to Partner
- Search Partners

Better:

- Send Saved Property to Realtor
- Find Realtors Near This ZIP
- Send Build Package to Contractor
- Send Design Package to Interior Designer
- Send Budget to Contractor for Pricing
- Send Funding Package to Lender

---

## Contextual Partner Actions by Module

### Saved Property

Primary partner need: Realtor / Buyer Agent / Listing Agent / Local Operator

Actions:

- Send Property to Realtor Partner
- Find Realtors in This Area
- Ask Realtor for Comps
- Ask Realtor to Check Property Access
- Ask Realtor About Offer Strategy

Context passed:

- saved_property_id
- address
- city
- state
- zip
- price
- property type
- user notes

Default partner type:

- Realtor

Default message:

> Please review this saved property and let me know if it is worth pursuing. I would like help with local market insight, comps, access, and offer strategy.

---

### Deal Workspace

Primary partner need: team coordination

Actions:

- Build My Deal Team
- Send Deal to Realtor
- Send Deal to Contractor
- Send Deal to Lender
- Send Deal to Inspector
- Search Local Partners for This Deal

Context passed:

- deal_id
- saved_property_id
- address
- deal score
- strategy
- ARV
- rehab estimate
- rent estimate
- notes

Default partner type:

- Dynamic based on missing deal milestone.

Examples:

- No comps → Realtor
- No rehab scope → Contractor
- No inspection → Inspector
- Funding ready → Lender

---

### Deal Architect

Primary partner need: validate strategy and feasibility

Actions:

- Send Strategy to Realtor
- Send Strategy to Contractor
- Send Funding Summary to Lender
- Request Feasibility Review

Context passed:

- deal_id
- recommended strategy
- deal score
- purchase price
- ARV
- rehab/build cost
- projected profit
- ROI
- risk notes
- strategy snapshot

Default partner type:

- Contractor for rehab/build strategy
- Realtor for comps/ARV validation
- Lender for funding readiness

---

### Design Studio

Primary partner need: interior designer / contractor / stager

Actions:

- Send Design Package to Designer
- Send Design Package to Contractor
- Request Finish Pricing
- Request Staging Feedback

Context passed:

- deal_id
- room type
- style direction
- selected finishes
- design images/renders
- design budget
- notes

Default partner type:

- Contractor or Designer depending on page mode.

---

### Build Studio

Primary partner need: contractor / builder / architect / permit support

Actions:

- Send Build Package to Contractor
- Send Build Concept to Builder
- Request Construction Estimate
- Request Permit / Feasibility Review

Context passed:

- deal_id
- build_project_id
- property type
- square footage
- bedrooms
- bathrooms
- stories
- lot size
- zoning
- blueprint URLs
- exterior rendering URL
- build cost estimate

Default partner type:

- Contractor

---

### Project Studio

Primary partner need: choose the right execution team

Actions:

- Find Partners for This Project
- Send Project to Contractor
- Send Project to Property Manager
- Send Project to Lender
- Build Project Team

Context passed:

- deal_id
- project_id
- selected project path
- strategy
- budget range
- timeline
- notes

Default partner type:

- Dynamic based on project path.

---

### Budget Studio

Primary partner need: pricing, validation, and actual expense tracking

Actions:

- Send Budget to Contractor for Pricing
- Request Line Item Review
- Upload Actual Expenses
- Import Contractor Numbers
- Sync Budget Updates
- Compare Estimate vs Actual

Context passed:

- deal_id
- budget_id
- budget line items
- subtotal
- contingency
- total budget
- actual expenses
- variance
- timeline
- notes

Default partner type:

- Contractor

---

## Budget Upload / Sync Concept

Budget Studio should support user or partner-provided numbers.

### Minimum version

Allow upload/import of:

- CSV
- Excel
- PDF estimate
- photo/screenshot of estimate
- manual line item entry

### User flow

1. User opens Budget Studio.
2. User clicks **Upload Numbers** or **Import Estimate**.
3. Ravlo parses or stores the file.
4. User maps imported items to Ravlo budget categories.
5. Ravlo compares imported numbers against existing budget.
6. Ravlo shows variance.

Example:

```text
Kitchen
Ravlo Estimate: $18,000
Contractor Quote: $21,500
Variance: +$3,500
Status: Needs review
```

### Partner flow

1. User sends Budget Studio package to contractor.
2. Contractor submits numbers back through Ravlo.
3. Ravlo syncs the contractor quote into Budget Studio.
4. User accepts, rejects, or edits line items.
5. Accepted line items become the working budget.

---

## Sync Language

Use simple user-facing language.

Good labels:

- Upload Numbers
- Import Estimate
- Sync Contractor Quote
- Compare Actuals
- Update Budget

Avoid overly technical labels:

- Data ingestion
- Third-party sync pipeline
- External data mapping

---

## Partner Button Pattern

Each contextual partner action should include:

- clear action label
- default partner type
- local search using city/state/zip
- Ravlo network results first
- optional external search
- prefilled message
- attached context package

The existing reusable `send_to_partner_modal.html` already supports much of this:

- partner type chips
- local search by city/state/zip
- Ravlo and Google result sources
- selected partner
- budget and timeline
- studio package items
- saved property and deal IDs
- studio type and studio reference ID

Future work should focus on better entry buttons and richer context packages.

---

## Recommended Button Labels

### Saved Property

- Send to Realtor
- Find Realtor Near This Property
- Request Comps

### Deal Workspace

- Build Deal Team
- Send to Partner
- Find Local Help

### Deal Architect

- Validate Strategy
- Send to Contractor
- Send to Lender

### Design Studio

- Send Design to Contractor
- Request Finish Pricing
- Find Designer

### Build Studio

- Send Build Package
- Request Build Estimate
- Find Builder

### Project Studio

- Build Project Team
- Find Project Partners

### Budget Studio

- Upload Numbers
- Import Estimate
- Sync Contractor Quote
- Send Budget for Pricing

---

## Product Principle

Partner actions should make users feel supported, not redirected.

The user should feel:

> I found the opportunity, Ravlo helped me understand it, and now Ravlo is helping me bring in the right people.

That is how Partner Network becomes part of the operating system instead of a separate directory.
