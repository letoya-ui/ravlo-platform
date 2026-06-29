# Ravlo Team Routing Guide

This guide explains how Ravlo should decide where internal team members, company users, partners, and customers go after login.

## Core rule

A user's dashboard is controlled by two things:

1. `role` — what kind of user they are.
2. `company_id` — which team/company workspace they belong to.

A user can have the right role but still not appear in the right team if `company_id` is missing.

---

## Ravlo internal team

### Letoya

Recommended setup:

- Email: `letoya@ravlohq.com`
- Role: `executive`
- Company: Ravlo
- Expected dashboard: Executive Mission Control

Purpose:

- Founder / CEO view
- Mission Control
- User activity
- subscriptions
- platform health
- growth and operations

### Sandra

Recommended setup:

- Email: `Sandra@ravlohq.com`
- Role: `admin` or `platform_admin`
- Company: Ravlo
- Expected dashboard: Admin Operations Desk

If Sandra should only manage Ravlo's day-to-day operations, prefer:

- Role: `admin`
- Company: Ravlo

If Sandra should have broader platform-level access, use:

- Role: `platform_admin`
- Company: Ravlo

Sandra's dashboard purpose:

- welcome new users
- review access requests
- review invites
- update CRM
- monitor messages
- check Ravlo Capital / Lending follow-ups
- send end-of-day report

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

2. Are they a company customer/team member?
   - Use that company's `company_id`.
   - Use role based on their job.

3. Are they an external partner?
   - Use `partner`.
   - Create/confirm partner profile.
   - Do not give admin access unless they help operate Ravlo.

4. Are they an investor or borrower?
   - Keep them out of internal team dashboards.
   - Route them to Investor OS or Borrower Portal.

---

## Current recommended correction

Sandra is part of Ravlo's internal team. Make sure her user record has:

- email normalized to lowercase: `sandra@ravlohq.com`
- company set to Ravlo
- role set to `admin` for Operations Desk, or `platform_admin` for broader platform access

For the absent partner, keep them as:

- role: `partner`
- partner profile enabled
- no admin privileges unless they become active in operations

This keeps Ravlo clean:

- Letoya runs Mission Control.
- Sandra runs Operations Desk.
- Partners stay in Partner Dashboard.
- Lending staff go to Lending OS dashboards.
- Investors and borrowers stay in their customer experiences.
