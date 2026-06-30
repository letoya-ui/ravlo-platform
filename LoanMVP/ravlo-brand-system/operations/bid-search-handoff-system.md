# Bid Search and Handoff System

## Purpose

Ravlo needs a simple construction business development workflow so Jamaine can stay hands-on in the field while Sandra handles the office side of bid preparation.

The goal is not to turn Jamaine into an office manager.

The goal is to give him a clear field-to-office system with no room for confusion or excuses.

---

## Core workflow

1. Jamaine opens the Construction Command Center.
2. He searches for demo, rehab, small GC, repair, concrete, ironwork, or construction opportunities in a target area.
3. Ravlo shows possible opportunities or allows him to manually add one.
4. Jamaine saves the opportunity.
5. Jamaine clicks: **Send to Sandra for Bid Package**.
6. Sandra receives it in her Bid Support Queue.
7. Sandra prepares the office side of the bid package.
8. Jamaine reviews the field scope, labor, material assumptions, timeline, and final number.
9. The bid is sent.
10. Ravlo tracks follow-up until the job is awarded, declined, completed, invoiced, and paid.

---

## Dashboard language

### Jamaine button

**Search Demo / GC Jobs**

### Jamaine handoff button

**Send to Sandra for Bid Package**

### Sandra queue title

**Bid Support Queue**

### Shared status label

**Bid Package Needed**

---

## Search categories

The bid search should support searches for:

- demo jobs
- small GC jobs
- rehab jobs
- repair jobs
- concrete jobs
- ironwork jobs
- punch list work
- investor renovation work
- commercial maintenance work
- property preservation work
- permit-related work
- Tampa construction opportunities
- Hillsborough County construction opportunities
- Pinellas County construction opportunities
- Pasco County construction opportunities

---

## Jamaine responsibilities

Jamaine owns the field side.

He is responsible for:

- finding or reviewing opportunities
- deciding whether the opportunity is worth pursuing
- walking sites when needed
- taking photos and notes
- identifying field risks
- estimating labor assumptions
- confirming material assumptions
- approving the final scope and price
- deciding if the job fits Caughman Mason Construction

Jamaine should not be expected to sit at a desk all day.

He should be expected to keep the pipeline moving.

---

## Sandra responsibilities

Sandra owns the office-support side.

She is responsible for:

- receiving handoffs from Jamaine
- organizing contact details
- collecting address, due date, job description, documents, and photos
- preparing a draft bid package
- drafting follow-up emails
- updating CRM notes
- tracking bid status
- reminding Jamaine what needs his review
- marking whether the bid is waiting, sent, awarded, declined, or needs follow-up

Sandra does not approve field numbers or final scope.

---

## Letoya responsibilities

Letoya owns final business oversight when needed.

She should be able to see:

- what opportunities were found
- what was sent to Sandra
- what is waiting on Jamaine
- what bids were sent
- what is stuck
- what has revenue potential

Letoya should not have to chase every detail manually.

Ravlo should show where each opportunity stands.

---

## Recommended pipeline stages

Every opportunity should have one status:

1. Search Result
2. Saved Opportunity
3. Send to Sandra
4. Bid Package Needed
5. Missing Information
6. Site Visit Needed
7. Site Visit Scheduled
8. Estimate Needed
9. Draft Bid Prepared
10. Jamaine Review Needed
11. Ready to Send
12. Bid Sent
13. Follow-Up Needed
14. Negotiating
15. Awarded
16. In Progress
17. Completed
18. Invoice Sent
19. Paid
20. Declined / Lost

---

## Data fields for a bid opportunity

Minimum fields:

- title
- source
- source URL
- location
- category
- description
- contact name
- contact email
- contact phone
- due date
- estimated value
- status
- assigned to
- sent to Sandra at
- Jamaine review needed
- notes
- created by
- created at
- updated at

Optional fields:

- property address
- photos
- documents
- permit number
- project type
- square footage
- trade type
- bid deadline
- walk-through date
- insurance requirements
- license requirements

---

## Dashboard sections

### Jamaine Construction Command Center

Add a card called **Bid Search**.

Actions:

- Search Demo / GC Jobs
- Search Tampa Area
- Save Opportunity
- Send to Sandra for Bid Package
- Mark Site Visit Needed
- Mark Not a Fit

Jamaine dashboard queues:

- New Opportunities
- Sent to Sandra
- Needs My Review
- Site Visit Needed
- Bid Sent
- Follow-Up Needed

### Sandra Operations Center

Add a card called **Bid Support Queue**.

Sandra queues:

- New Handoffs
- Missing Information
- Draft Package Needed
- Waiting on Jamaine
- Ready to Send
- Follow-Up Needed

### Letoya Executive Dashboard

Add a summary called **Construction Bid Pipeline**.

Letoya sees:

- opportunities found this week
- sent to Sandra
- waiting on Jamaine
- bids sent
- awarded
- estimated value in play

---

## Search implementation options

### Phase 1: Manual + saved search links

Start simple.

Jamaine can use predefined search buttons that open searches for Tampa-area demo, GC, rehab, concrete, ironwork, and repair work.

If he finds a real opportunity, he manually saves it into Ravlo.

This avoids overbuilding before the workflow is proven.

### Phase 2: Internal bid opportunity table

Create a Ravlo table for saved bid opportunities.

Jamaine and Sandra can both see the same records from different dashboards.

### Phase 3: External source integrations

Later, Ravlo can connect to construction bid sources, public bid portals, Google search results, procurement sites, or lead providers.

Ravlo should not auto-submit bids.

Ravlo should help find, organize, hand off, and track opportunities.

---

## Product principle

Jamaine finds and validates the work.

Sandra organizes and prepares the bid package.

Letoya sees what is moving and what is stuck.

Ravlo holds the system together.