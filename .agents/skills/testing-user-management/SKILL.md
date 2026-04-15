# Testing User Management (Delete User)

## Overview
The `delete_user` route in `system_routes.py` performs comprehensive FK cleanup before deleting a user. Testing requires creating users with records across 16+ related tables.

## Local Dev Setup

```bash
export FLASK_ENV=development FLASK_DEBUG=true DATABASE_URL="sqlite:///local.db" SOCKETIO_ASYNC_MODE=threading OPENAI_API_KEY="sk-dummy"
python run.py
# Server runs on port 5050
```

- `OPENAI_API_KEY` must be set (even dummy) before importing the app
- Use `python run.py` not `flask run` for SocketIO support

## Test Accounts

- System user for admin operations: Create with role="system" to access `/system/users`
- Test passwords: Use `generate_password_hash("TestPass123!")` from `werkzeug.security`
- Staff roles need `ica_agreed=True`, `nda_signed=True`, `onboarding_complete=True` to skip onboarding

## Creating Comprehensive Test Users

To test delete user, create a user with records in ALL affected tables. Key gotchas:

1. **Model column names differ from what you'd expect:**
   - `CreditProfile` uses `loan_app_id` (not `loan_id`)
   - `LoanQuote` uses `loan_application_id` (not `loan_id`)
   - `PropertyAnalysis` uses `loan_app_id` (not `loan_id`)
   - `LoanIntakeSession` uses `borrower_id` (not `loan_id`)
   - Always inspect model schemas before creating test records

2. **NOT NULL FK tables** (require special handling):
   - `BorrowerActivity.investor_profile_id` — NOT NULL
   - `AIIntakeSummary.investor_profile_id` — NOT NULL
   - `ESignedDocument.investor_profile_id` — NOT NULL
   - These must be explicitly deleted (can't nullify)

3. **Partner models with complex required FKs:**
   - `PartnerJob` requires `partner_id` (NOT NULL)
   - `ExternalPartnerLead` requires `created_by_user_id` (NOT NULL)
   - May need to skip these or create full dependency chain

4. **Cross-user references:**
   - `PartnerConnectionRequest.deal_id` can reference deals from OTHER users
   - `RenovationMockup.deal_id` can reference deals from OTHER users
   - Both need FK nullification before deal deletion

## Testing the Delete User Flow

### Test 1: Comprehensive Delete (UI)
1. Log in as system user at `/system/users`
2. Click Delete on user with 16+ related records
3. Accept JavaScript confirm dialog
4. **Pass**: Green flash "Deleted user {email}." appears, user row gone
5. **Fail**: Red flash "Could not delete user:" with FK violation error

**Note**: JavaScript `confirm()` dialogs may need Playwright CDP handling:
```python
from playwright.async_api import async_playwright
browser = await p.chromium.connect_over_cdp("http://localhost:29229")
page.on("dialog", lambda dialog: asyncio.ensure_future(dialog.accept()))
```

### Test 2: Data Cleanup Verification (Shell)
Run Python script with app context to query all 16+ tables:
```python
from LoanMVP.app import create_app
app = create_app()
with app.app_context():
    # Query each table for investor_profile_id, user_id, deal_id
    # All should return count=0 after deletion
```

### Test 3: Regression — Bare User Delete
Delete a user with NO related data to verify the cleanup code handles empty result sets.

## SQLAlchemy Cascade Patterns

- **Bulk `.delete()` bypasses ORM cascades** — must explicitly delete/nullify child rows
- **Bulk `.update()` does NOT bypass ORM** — in-memory relationship collections still trigger cascade
- **`db.session.expire_all()`** clears ORM cache, forcing fresh DB reads. Critical after bulk FK nullification to prevent stale cascade.
- **Default FK behavior (no ondelete)** = RESTRICT on PostgreSQL, which blocks parent deletion
- **SQLite has weaker FK enforcement** — always test on PostgreSQL (Render) for production confidence

## Devin Secrets Needed

- No secrets required for local testing (uses dummy OPENAI_API_KEY)
- For Render/PostgreSQL testing: DATABASE_URL from Render dashboard
