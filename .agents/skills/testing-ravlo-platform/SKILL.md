# Testing Ravlo Platform

How to set up and test the Ravlo Platform Flask application locally.

## Environment Setup

```bash
# Start the Flask server from the repo root
cd /home/ubuntu/repos/ravlo-platform
PYTHONPATH=/home/ubuntu/repos/ravlo-platform FLASK_ENV=development FLASK_DEBUG=false OPENAI_API_KEY=sk-fake python3 LoanMVP/app.py
```

- Server runs on `http://localhost:5050`
- The `PYTHONPATH` must point to the repo root for module imports to work
- A stub `OPENAI_API_KEY` is needed to start the app; AI features will show fallback responses

## Devin Secrets Needed

- `OPENAI_API_KEY` (optional) — for real AI summary generation. Without it, AI sections show warnings but the app is fully functional.

## Test Accounts

| Role | Email | Password |
|------|-------|----------|
| Loan Officer | lo@test.com | Test1234! |
| Processor | proc@test.com | Test1234! |
| Borrower | borrower@test.com | Test1234! |
| Underwriter | uw@test.com | Test1234! |

## Login Flow

1. Navigate to `http://localhost:5050/auth/login`
2. Enter email and password
3. Click "Login" — redirects to role-specific dashboard

## Key Routes by Role

### Loan Officer
- Dashboard: `/loan_officer/dashboard`
- Loan Application: `/loan_officer/loan-application`
- Loan File: `/loan_officer/loan/<id>`
- Loan Queue: `/loan_officer/loan_queue`
- Borrowers: `/loan_officer/borrowers`
- Tasks: `/loan_officer/tasks`

### Processor
- Dashboard: `/processor/dashboard`
- Loan Queue: `/processor/loan_queue`
- Documents: `/processor/documents`

### Borrower
- Dashboard: `/borrower/dashboard`

### Underwriter
- Dashboard: `/underwriter/dashboard`
- Decision Queue: `/underwriter/decision_queue`

## Testing Tips

- The borrower role might require creating a `BorrowerProfile` on first login — the app handles this automatically via a profile creation flow.
- The onboarding check (`@loan_officer_onboarding_required`) may redirect new users. Test accounts should already be onboarded.
- When testing form submissions that create new records (e.g., loan applications), the created record will persist in the SQLite database across server restarts.
- DTI calculations depend on `borrower.income` (monthly), not `annual_income`. If testing income-related features, verify both fields are set.
- The LTV ratio on the loan file page is calculated as `loan_amount / property_value`.
- Flash messages appear at the top of the page after redirects — they confirm successful operations.
