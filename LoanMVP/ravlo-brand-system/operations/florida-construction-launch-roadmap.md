# Florida Construction Launch Roadmap

## Purpose

This roadmap explains what Ravlo is building for the Florida move and the Caughman Mason Construction launch.

The goal is to help Jamaine hit the ground running in Florida while keeping the office side organized through Sandra and visible to Letoya.

Ravlo should support the business instead of forcing everyone to operate the same way.

---

## Business structure

Caughman Mason LLC is the parent company.

Ravlo operates under Caughman Mason LLC as the technology platform and operating system brand.

Caughman Mason Construction is the hands-on construction lane powered by Ravlo.

Recommended language:

- Caughman Mason LLC: parent company
- Ravlo: real estate operating system
- Caughman Mason Construction: construction operations, powered by Ravlo

---

## Team roles

### Letoya

Role: Founder / CEO

Responsibilities:

- company vision
- Ravlo platform growth
- Ravlo Capital strategy
- executive oversight
- final business decisions
- product direction
- team accountability

Workspace:

- Executive Dashboard / Mission Control

### Jamaine

Role: Construction Partner / Construction Operations Lead

Background:

- certified ironworker
- hands-on field operator
- not expected to operate like an office manager

Responsibilities:

- find and review construction opportunities
- walk sites
- take field photos and notes
- confirm scope and field risks
- estimate labor and material assumptions
- approve final construction numbers
- pursue demo jobs, small GC jobs, repair jobs, ironwork opportunities, and construction relationships
- keep the pipeline moving

Workspace:

- Construction Command Center

### Sandra

Role: Operations Lead

Responsibilities:

- onboarding support
- lending operations learning path
- bid-support learning path
- prepare bid packages after Jamaine handoff
- organize contact details, due dates, notes, documents, and follow-ups
- update CRM / operations notes
- prepare end-of-day reports for Letoya

Workspace:

- Operations Center

---

## Current workflow being built

### Bid Search and Handoff

The intended workflow is:

1. Jamaine opens Construction Command Center.
2. Jamaine uses bid search links or finds opportunities manually.
3. Jamaine saves a bid opportunity into Ravlo.
4. Jamaine clicks Send to Sandra.
5. The opportunity status becomes bid_package_needed.
6. Sandra sees it in her Bid Support Queue.
7. Sandra prepares the office side of the bid package.
8. Jamaine reviews final field scope, labor, materials, timeline, and bid number.
9. The bid is sent.
10. Ravlo tracks follow-up, awarded/lost status, project progress, invoice, and payment.

---

## What is already done

### 1. Company structure documented

File:

- LoanMVP/ravlo-brand-system/operations/company-structure.md

Purpose:

- documents Caughman Mason LLC as parent company
- documents Ravlo as the platform brand
- documents Caughman Mason Construction as the construction lane powered by Ravlo

### 2. Team Academy paths updated

File:

- LoanMVP/ravlo-brand-system/operations/team-academy-paths.md

Purpose:

- Sandra primary learning path: Lending
- Sandra secondary learning path: Bid Support / Construction Office Operations
- Jamaine learning path: Contractor / Construction
- defines boundaries between Sandra's office support and Jamaine's field judgment

### 3. Bid Search and Handoff system documented

File:

- LoanMVP/ravlo-brand-system/operations/bid-search-handoff-system.md

Purpose:

- defines the complete field-to-office bid workflow
- defines Jamaine, Sandra, and Letoya responsibilities
- defines bid pipeline stages
- defines dashboard expectations

### 4. Backend bid handoff routes added

File:

- LoanMVP/routes/construction_bids.py

Purpose:

- create bid opportunity
- save opportunity as saved_opportunity
- send opportunity to Sandra by changing status to bid_package_needed
- update bid status through the construction pipeline

### 5. Existing bid opportunity model reused

File:

- LoanMVP/models/contractor_models.py

Existing model:

- ContractorBidOpportunity

Purpose:

- tracks external or self-sourced construction opportunities
- avoids creating a duplicate data model

### 6. Construction Command Center updated

File:

- LoanMVP/templates/executive/construction_center.html

Purpose:

- added Bid Search + Handoff section
- added quick Tampa-area search links
- added manual Save Opportunity form
- added Send to Sandra button in bid pipeline rows
- added bid status dropdown controls
- updated language to Caughman Mason Construction, powered by Ravlo

### 7. Schema self-heal updated

File:

- LoanMVP/app.py

Purpose:

- added contractor_bid_opportunities to schema self-heal table list
- helps create the table on deploy if migrations have not already run

---

## What is partially done

### Sandra Bid Support Queue

The backend status exists:

- bid_package_needed

The Construction Command Center can send an opportunity to Sandra.

What is not fully wired yet:

- Sandra's Operations Center does not yet visibly show the Bid Support Queue
- Sandra cannot yet update bid-support statuses from her dashboard

Reason:

- GitHub connector blocked the attempted write for the Sandra queue route/template in the prior run

---

## What still needs to be done

### Phase 1: Finish Sandra's Bid Support Queue

Needed:

1. Query ContractorBidOpportunity records with these statuses:
   - bid_package_needed
   - missing_information
   - draft_bid_prepared
   - jamaine_review_needed
   - ready_to_send
   - follow_up_needed

2. Pass the queue into admin/dashboard.html as bid_support_queue.

3. Add a visible card in the Operations Center:
   - Bid Support Queue
   - New handoffs
   - Missing information
   - Draft package needed
   - Waiting on Jamaine
   - Ready to send
   - Follow-up needed

4. Add status update forms for Sandra.

Recommended statuses for Sandra:

- missing_information
- draft_bid_prepared
- jamaine_review_needed
- ready_to_send
- bid_submitted
- follow_up_needed

### Phase 2: Improve bid opportunity data fields

Current model is simple and usable.

Future fields to add:

- source_url
- contact_name
- contact_email
- contact_phone
- property_address
- walk_through_date
- sent_to_sandra_at
- assigned_to_user_id
- created_by_user_id
- due_date
- documents_url
- photos_url

### Phase 3: Add true internal bid search

Current Phase 1 search uses external quick links and manual saving.

Future search can support:

- saved searches by location
- public procurement portal links
- Google Custom Search or external search API
- opportunity scraping where allowed
- lead source integrations
- AI summary of search results

Ravlo should not auto-submit bids.

Ravlo should find, save, organize, hand off, and track opportunities.

### Phase 4: Add Letoya executive visibility

Add Construction Bid Pipeline card to Executive Dashboard.

Letoya should see:

- opportunities found this week
- sent to Sandra
- waiting on Jamaine
- ready to send
- bids sent
- awarded
- estimated value in play
- stuck items

### Phase 5: Add notifications

Recommended notifications:

- Jamaine sends opportunity to Sandra
- Sandra marks missing information
- Sandra marks ready for Jamaine review
- Jamaine marks bid sent
- bid needs follow-up

### Phase 6: Add Academy alignment

Sandra's Operations Center should link to:

- Lending Academy
- Bid Support checklist

Jamaine's Construction Command Center should link to:

- Contractor / Construction Academy

---

## Operating rule

Jamaine should not be turned into an office manager.

Sandra should not be asked to make field judgment calls.

Letoya should not have to chase every detail manually.

The system should create accountability by showing status.

Simple accountability question:

Where is this opportunity in the pipeline?

---

## Weekly launch goals for Florida

Jamaine weekly targets:

- save at least 5 construction opportunities
- send qualified opportunities to Sandra
- visit or contact local contractors, builders, investors, or property owners
- identify demo, repair, small GC, and ironwork opportunities
- update status before end of day

Sandra weekly targets:

- keep every handoff organized
- prepare bid packets
- follow up on missing information
- mark what is waiting on Jamaine
- include bid activity in end-of-day reports

Letoya weekly targets:

- review what moved
- review what is stuck
- decide what needs business approval
- keep Ravlo Capital and Ravlo platform growth moving

---

## Product principle

Field work by Jamaine.

Office organization by Sandra.

Executive oversight by Letoya.

Ravlo holds the system together.