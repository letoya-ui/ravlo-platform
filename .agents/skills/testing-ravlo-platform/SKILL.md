# Testing Ravlo Platform

## Local Dev Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Environment variables
export FLASK_ENV=development
export FLASK_DEBUG=true
export DATABASE_URL="sqlite:///local.db"
export SOCKETIO_ASYNC_MODE=threading
export OPENAI_API_KEY="sk-dummy"  # dummy key, not used in local testing

# Start the server
python3 -c "from LoanMVP.app import create_app, socketio; app = create_app(); socketio.run(app, host='0.0.0.0', port=5050, debug=True, use_reloader=False)"
```

The app runs on `http://localhost:5050`. SQLite database is at `instance/local.db`.

## Partner Subscription Bypass Flags (IMPORTANT)

The `development` profile in `LoanMVP/config.py` defaults **both** of these to `true`:

- `BYPASS_PARTNER_SUBSCRIPTION`
- `FREE_PARTNER_MODE`

When either is `true`, every partner-tier gate is bypassed:

- `partner_has_vip_access()` in `LoanMVP/routes/vip.py` returns `True` regardless of `subscription_tier`.
- `partner_vip_tier_unlocked()` in `LoanMVP/routes/partners.py` returns `True` regardless of tier.
- Partner feature-access and locked-tool counters will show every feature as unlocked.

**If you are testing anything that depends on Free vs. Premium/Enterprise tiering** (VIP Realtor Workspace gate, `/partners/upgrade` flash, `partners.dashboard` CTA flipping between "Upgrade to VIP" and "Open My VIP Workspace", `/elena/*` access, etc.), you **must** start the server with these explicitly off:

```bash
FLASK_ENV=development FLASK_DEBUG=true \
  DATABASE_URL="sqlite:///local.db" \
  SOCKETIO_ASYNC_MODE=threading \
  OPENAI_API_KEY="sk-dummy" \
  FREE_PARTNER_MODE=false \
  BYPASS_PARTNER_SUBSCRIPTION=false \
  python3 -c "from LoanMVP.app import create_app, socketio; app = create_app(); socketio.run(app, host='0.0.0.0', port=5050, debug=True, use_reloader=False)"
```

Symptom if you forget: a Free realtor can browse `/vip/realtor` without redirect and the `partners.dashboard` hero says "Open My VIP Workspace" instead of "Upgrade to VIP Workspace" — making it look like the gating PR is broken when it's really the dev config silently disabling it.

## Creating Test Users

The app uses Flask-Login with a `User` model. To create test users:

```python
import sys; sys.path.insert(0, '.')
from LoanMVP.app import create_app
from LoanMVP.extensions import db
from LoanMVP.models import User

app = create_app()
with app.app_context():
    # Create tables if they don't exist
    db.create_all()
    
    # Create a test user
    u = User(email="test@example.com", username="test", first_name="Test", last_name="User", role="admin", company_id=1)
    u.set_password("TestPass123!")
    db.session.add(u)
    db.session.commit()
```

To reset passwords for existing users:
```python
with app.app_context():
    u = User.query.filter_by(email="test@example.com").first()
    u.set_password("NewPassword123!")
    db.session.commit()
```

## Creating Test Partner Accounts (realtor / contractor / etc.)

The `User` model does NOT have a `partner_category` field. Partner classification lives on the `Partner` row via `Partner.category` (display string like `"Realtor"`, `"Contractor"`) and `Partner.type`. `User.role` only needs to be one of the `PARTNER_ROLES` set in `LoanMVP/utils/decorators.py` (`partner`, `realtor`, `contractor`, `designer`, `loan_officer`, `lender`).

```python
from LoanMVP.app import create_app
from LoanMVP.extensions import db
from LoanMVP.models import User
from LoanMVP.models.crm_models import Partner

app = create_app()
with app.app_context():
    db.create_all()

    u = User.query.filter_by(email="test.realtor@ravlo.dev").first()
    if not u:
        u = User(
            email="test.realtor@ravlo.dev",
            username="testrealtor",
            first_name="Test",
            last_name="Realtor",
            role="realtor",  # must be in PARTNER_ROLES
            company_id=1,
        )
        u.set_password("TestPass123!")
        db.session.add(u)
        db.session.commit()

    p = Partner.query.filter_by(user_id=u.id).first()
    if not p:
        p = Partner(
            user_id=u.id,
            name="Test Realtor",
            email=u.email,
            category="Realtor",   # source-of-truth for partner_is_realtor(); case-insensitive
            type="Realtor",
            subscription_tier="Free",  # tiers: Free | Featured | Premium | Enterprise
            approved=True,
            active=True,
            status="Active",
        )
        db.session.add(p)
        db.session.commit()
```

For contractor / designer / loan_officer test accounts, change `User.role` and `Partner.category` accordingly.

## Devin Secrets Needed

No external secrets are needed for local testing. The app uses a dummy OpenAI key and SQLite database.

## Sidebar Architecture

- **Base template**: `LoanMVP/templates/layouts/ravlo_employee_base.html`
  - Selects sidebar based on `current_user.role`
  - Has email-based override for executive dashboard users
- **Sidebar templates**: `LoanMVP/templates/layouts/_sidebar_*.html`
  - `_sidebar_admin.html` — Platform admin / company admin sidebar
  - `_sidebar_executive.html` — Executive sidebar (full platform visibility)
  - `_sidebar_loan_officer.html`, `_sidebar_processor.html`, `_sidebar_underwriter.html`

## Role-Based Routing

- Login routing is in `LoanMVP/routes/auth.py` → `post_login_redirect()`
- Executive email override: `_EXECUTIVE_DASHBOARD_EMAILS` set in `auth.py` and `executive_new.py`
- The `_is_executive_dashboard_user()` function checks email first, then role
- Route guards use `@role_required()` decorator from `LoanMVP/utils/decorators.py`
  - `"admin"` matches users with role=admin
  - `"admin_group"` expands to all admin roles (admin, platform_admin, master_admin, etc.)
  - `"partner_group"` expands to all partner roles (partner, realtor, contractor, designer, loan_officer, lender)

## VIP Workspace Access Gate

The VIP Realtor Workspace (`/vip/realtor*` and `/elena/*`) is gated by `partner_has_vip_access()` in `LoanMVP/routes/vip.py`:

- Admins always pass.
- `FREE_PARTNER_MODE` or `BYPASS_PARTNER_SUBSCRIPTION` config flag bypasses the gate.
- Otherwise `Partner.subscription_tier` must be in `VIP_ACCESS_TIERS = {"premium", "enterprise"}` (case-insensitive).

Elena routes (`/elena/*`) additionally require the partner to be a realtor (`Partner.category`/`type` contains "realtor"). Non-realtor premium partners hitting `/elena/*` get bounced to `/vip/` index.

`partners.confirm_subscription` redirects upgraded realtors straight to `vip.realtor_dashboard` (not `partners.billing`) when the new tier is Premium/Enterprise.

## Testing Tips

- Logout is POST-only (`/auth/logout`). Use the Logout button in the UI, not a GET request.
- `executive.py` is aliased to `executive_new.py` at runtime via `app.py` module_aliases.
- The sidebar selection in `ravlo_employee_base.html` checks email before role, so admin-role users with executive emails see the executive sidebar.
- When testing sidebar changes, make sure to scroll the sidebar to verify all sections are visible since the sidebar may be taller than the viewport.
- Admin routes like `admin.ai_dashboard`, `admin.verify_data`, `admin.messages`, `admin.reports` use `@role_required("admin")` or `@role_required("admin_group")`, so users with role=admin can access them even when routed through the executive sidebar.
- When testing partner-tier behavior, always double-check `FREE_PARTNER_MODE` / `BYPASS_PARTNER_SUBSCRIPTION` are off (see top of this file).
