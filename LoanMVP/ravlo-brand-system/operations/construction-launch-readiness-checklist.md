# Construction Launch Readiness Checklist

## Purpose

This checklist confirms that the construction side of Caughman Mason can run inside Ravlo alongside Ravlo OS.

The goal is to make sure a Tampa construction opportunity can move from lead discovery to bid follow-up without relying on scattered texts, memory, or verbal handoff.

---

## Core workflow to test

1. Jamaine finds a construction opportunity.
2. Jamaine saves the opportunity in the Construction Command Center.
3. Jamaine sends the opportunity to Sandra for bid package support.
4. Sandra sees the opportunity in the Bid Support Queue.
5. Sandra organizes the package and marks the correct status.
6. Jamaine reviews field scope, labor, materials, timeline, and price.
7. The bid is marked ready to send or submitted.
8. Follow-up is tracked until the job is won, lost, or no-bid.

---

## Jamaine readiness

### Construction Command Center

Confirm Jamaine can:

- log in successfully
- access the Construction Command Center
- search or open the bid search section
- save a new opportunity
- enter project name
- enter category or trade type
- enter location
- add source/contact details
- add estimated value if known
- add bid deadline if known
- add notes
- see the saved opportunity in the pipeline
- send the opportunity to Sandra

### Field responsibility

Confirm Jamaine understands he owns:

- site walks
- field photos
- field notes
- scope judgment
- labor assumptions
- material assumptions
- timeline assumptions
- safety concerns
- final field review before bid submission

---

## Sandra readiness

### Operations Center

Confirm Sandra can:

- log in successfully
- access the Operations Center
- see the Bid Support Queue section
- open construction packages that were sent from Jamaine
- review project name, category, location, deadline, value, and notes
- update bid status from the Operations Center

### Construction Office Packages page

Confirm Sandra can access:

- `/construction-office/packages`

Confirm the page shows:

- open package count
- project details
- notes
- current status
- status update dropdown

Confirm Sandra can mark:

- Missing Info
- Draft Prepared
- Waiting on Field Review
- Ready to Send
- Bid Sent
- Follow-Up Needed
- Awarded
- Lost
- No Bid

---

## Bid package requirements

Every bid package should collect or confirm:

- project name
- property address or service area
- contact name
- contact email
- contact phone
- project category
- scope notes
- photos
- documents
- bid deadline
- site visit requirement
- licensing/insurance requirement if provided
- field questions for Jamaine
- follow-up date

---

## Status rules

Use these statuses consistently:

- saved_opportunity: found but not yet sent to office support
- bid_package_needed: sent to Sandra for organization
- missing_information: package cannot move until details are collected
- draft_bid_prepared: office package is assembled
- jamaine_review_needed: field review is required
- ready_to_send: reviewed and ready for submission
- bid_submitted: bid has been sent
- follow_up_needed: waiting on response or next contact
- negotiating: terms or price are being discussed
- won: job was awarded
- lost: job was not awarded
- no_bid: team decided not to pursue

---

## Executive visibility

The Executive Dashboard should eventually show:

- saved opportunities
- packages waiting on Sandra
- packages waiting on field review
- ready-to-send bids
- submitted bids
- follow-ups needed
- awarded jobs
- estimated pipeline value
- blocked items

---

## First live test

Create one test opportunity:

```text
Project Name: Tampa Demo Test
Category: Demo / Small GC
Location: Tampa, FL
Source: Manual Test
Estimated Value: 10000
Deadline: next Friday
Notes: Test handoff from Jamaine to Sandra.
```

Test steps:

1. Save opportunity.
2. Confirm it appears as saved_opportunity.
3. Send to Sandra.
4. Confirm status changes to bid_package_needed.
5. Open Operations Center.
6. Confirm it appears in Bid Support Queue.
7. Open `/construction-office/packages`.
8. Change status to missing_information.
9. Change status to draft_bid_prepared.
10. Change status to jamaine_review_needed.
11. Change status to ready_to_send.
12. Change status to bid_submitted.
13. Change status to follow_up_needed.
14. Confirm no page crashes during the workflow.

---

## Launch definition

Construction side is ready for Florida launch when:

- Jamaine can save and send opportunities without help
- Sandra can see and update bid packages without help
- bid status is visible in Ravlo
- every open opportunity has a next step
- no bid is tracked only by text message or memory
- executive review can identify what is moving, what is stuck, and what needs a decision
