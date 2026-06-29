# Ravlo Team Routing Guide

This guide explains how Ravlo should decide where internal team members, company users, partners, and customers go after login.

## Core rule

A user's dashboard is controlled by two things:

1. `role` — what kind of user they are.
2. `company_id` — which team/company workspace they belong to.

A user can have the right role but still not appear in the right team if `company_id` is missing.

---

## Role language vs technical role

Ravlo can use a human title that is different from the technical role stored in the database.

Example:

- Human title: Ravlo Operations Lead
- Technical role: `platform_admin`
- Company: Ravlo
- Dashboard: Admin Operations Desk

This helps Ravlo stay simple in code while still giving team members a title that matches the work they are doing.

---

## Ravlo internal team

### Letoya

Recommended setup:

- Email: `letoya@ravlohq.com`
- Human title: Founder / CEO
- Technical role: `executive`
- Company: Ravlo
- Expected dashboard: Executive Mission Control

Purpose:

- founder / CEO view
- Mission Control
- user activity
- subscriptions
- platform health
- growth and operations
- final decisions

### Sandra

Recommended setup:

- Email: `sandra@ravlohq.com`
- Human title: Ravlo Operations Lead
- Technical role: `platform_admin`
- Company: Ravlo
- Expected dashboard: Admin Operations Desk

Why this is the best fit:

Sandra is trusted internal team and is open to helping wherever Ravlo needs support. She should not be treated like an outside partner or a limited customer/company admin. Her role should let her help with operations, users, messages, CRM, requests, and general platform coordination.

Sandra's job is not to make founder-level decisions. Her job is to keep the work moving and flag anything that needs Letoya.

Sandra's daily dashboard purpose:

- welcome new users
- review access requests
- review invites
- update CRM notes
- monitor messages
- check Ravlo Capital / Lending follow-ups
- review partner requests
- help keep user records clean
- send end-of-day report
- escalate anything sensitive to Letoya

Recommended access boundary:

- Sandra can help operate Ravlo.
- Sandra should not replace Letoya's executive dashboard.
- Sandra should not approve major strategy, pricing, legal, investor, or partnership decisions without Letoya.
- Sandra can prepare, organize, follow up, and report.

If Ravlo later adds a dedicated custom role, it should be called:

- `operations_admin`

Until then, use:

- `platform_admin`
- Company: Ravlo

---

## Partner users

Recommended setup:

- Role: `partner`
- Company: optional, depending on whether they are internal or external
- Partner profile: required for a personalized partner dashboard
- Expected dashboard: Partner Dashboard

A partner account should not be treated like an internal admin unless they are actively helping operate Ravlo.

Partner dashboard purpose:

- receive referrals
- manage partner requests
- update profile
- respond to jobs/opportunities
- use partner tools

If a partner is inactive, keep the dashboard ready but do not give them admin access.

For an absent or inconsistent partner:

- keep role as `partner`
- keep the dashboard ready
- do not add admin permissions
- do not assign internal operations responsibility
- use CRM/follow-up notes to track whether they are active

---

## Lending team users

### Loan Officer

- Role: `loan_officer`
- Company: Ravlo Capital or client company
- Expected dashboard: Loan Officer Dashboard

### Processor

- Role: `processor`
- Company: Ravlo Capital or client company
- Expected dashboard: Processor Dashboard

### Underwriter

- Role: `underwriter`
- Company: Ravlo Capital or client company
- Expected dashboard: Underwriter Dashboard

---

## Investor users

- Role: `investor`
- Company: usually Caughman Mason Loan Service or investor workspace
- Expected dashboard: Investor Command Center

Investor dashboard purpose:

- property search
- saved properties
- Deal Architect
- Budget Studio
- Academy
- capital request path

---

## Borrower users

- Role: `borrower`
- Company: lending company or borrower workspace
- Expected dashboard: Borrower profile / borrower portal

Borrower dashboard purpose:

- application
- document upload
- loan status
- communication

---

## Quick decision tree

Ask these questions before changing a user:

1. Are they Ravlo internal team?
   - Use Ravlo company.
   - Use `executive`, `admin`, or `platform_admin`.
   - If they are trusted and helping across the platform, use `platform_admin`.

2. Are they helping operate Ravlo day to day?
   - Use Ravlo company.
   - Use Admin Operations Desk.
   - Human title should be Operations Lead, Operations Assistant, or Operations Admin.

3. Are they a company customer/team member?
   - Use that company's `company_id`.
   - Use role based on their job.

4. Are they an external partner?
   - Use `partner`.
   - Create/confirm partner profile.
   - Do not give admin access unless they help operate Ravlo.

5. Are they an investor or borrower?
   - Keep them out of internal team dashboards.
   - Route them to Investor OS or Borrower Portal.

---

## Current recommended correction

Sandra is part of Ravlo's internal team and is open to helping wherever needed. Make sure her user record has:

- email normalized to lowercase: `sandra@ravlohq.com`
- company set to Ravlo
- technical role set to `platform_admin`
- human title treated as Ravlo Operations Lead
- expected dashboard: Admin Operations Desk

For the absent partner, keep them as:

- role: `partner`
- partner profile enabled
- no admin privileges unless they become active in operations

This keeps Ravlo clean:

- Letoya runs Mission Control.
- Sandra runs Operations Desk as Ravlo Operations Lead.
- Partners stay in Partner Dashboard.
- Lending staff go to Lending OS dashboards.
- Investors and borrowers stay in their customer experiences.
