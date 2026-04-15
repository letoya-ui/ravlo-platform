# Testing Ravlo Platform Dashboards

Comprehensive guide for testing all 4 role-based dashboards in the Ravlo lending platform.

## Prerequisites

### Start the Flask App
```bash
cd /home/ubuntu/repos/ravlo-platform
FLASK_ENV=development FLASK_DEBUG=false OPENAI_API_KEY=sk-fake python3 -m LoanMVP.app
```
The app runs on `http://localhost:5050`. Use a stub OpenAI key (`sk-fake`) — AI features gracefully degrade with fallback responses.

### Create Test Users
Use the Flask shell or a Python script to create users with pre-set onboarding flags:
```python
from LoanMVP.app import create_app
from LoanMVP.models import db, User
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    password = generate_password_hash('Test1234!')
    users = [
        User(email='lo@test.com', password=password, role='loan_officer', first_name='Test', last_name='LoanOfficer', ica_agreed=True, nda_signed=True, onboarding_complete=True),
        User(email='proc@test.com', password=password, role='processor', first_name='Test', last_name='Processor', ica_agreed=True, nda_signed=True, onboarding_complete=True),
        User(email='borrower@test.com', password=password, role='borrower', first_name='Test', last_name='Borrower'),
        User(email='uw@test.com', password=password, role='underwriter', first_name='Test', last_name='Underwriter', ica_agreed=True, nda_signed=True, onboarding_complete=True),
    ]
    for u in users:
        db.session.add(u)
    db.session.commit()
```
Password for all test users: `Test1234!`

## Devin Secrets Needed
- `OPENAI_API_KEY` — For real AI features (optional, stub key works for basic testing)

## Route Inventory by Role

### Underwriter (uw@test.com)
Sidebar pages (8): Dashboard, Decision Queue, Pipeline, Review Loans, Risk Reports, Tasks, Messages, Contracts Hub
Dashboard buttons: Decision Queue, Pipeline, Onboarding, AI Assistant
Forms: Task creation (+ New Task modal), AI chat (Ask + quick action buttons), Review Loans filter

### Processor (proc@test.com)
Sidebar pages (9): Dashboard, Loan Queue, Documents, Verify Documents, Reports, Messages, AI Conversations, Profile, Contracts Hub
Hero buttons (4): Open Queue, Documents, Verify Docs, Contracts Hub
Operations Panel (6): Loan Queue, Document Pipeline, Verification Center, Reports & Insights, NDA & Contracts, Onboarding

### Borrower (borrower@test.com)
Top nav tabs (6): Apply, Loans, Documents, Conditions, Messages, Subscription
Dashboard actions (8): Apply for Funding, Upload Document, Start/update application, Upload docs, Review conditions, Message team, Manage subscription, View All Loans
Note: Borrower requires a profile before dashboard access — first login redirects to `/borrower/create-profile`

### Loan Officer (lo@test.com)
Sidebar pages (9+): Dashboard, Messages, Leads, Borrowers, Loans, Credit Check, Tasks, Tools, Resource Center, Campaigns
Leads buttons: Add Lead, AI Leads, Lead Engine, Dialer
Forms: New Loan, Quick Add Task, Advanced Task Form, Add Lead form, Credit Check

## Known Behaviors
- Onboarding sidebar links redirect to dashboard if onboarding is already complete (correct behavior)
- Logout requires POST request (GET returns 405 — correct CSRF protection)
- AI features show fallback responses with stub API key — not a bug
- Borrower must create profile before accessing dashboard
- Staff roles (loan_officer, processor, underwriter) require ICA agreement, NDA, and onboarding completion

## Testing Tips
- Navigate to `http://localhost:5050/auth/login` to switch between roles
- Use browser recording with annotations for visual proof
- Test sidebar/nav links first, then dashboard quick actions, then forms
- Check browser console for JavaScript errors during navigation
- Maximize browser window before recording: `wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz`
