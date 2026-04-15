# Testing Ravlo Platform Locally

## Prerequisites

- Python 3.10+
- pip with packages from `requirements.txt`

## Devin Secrets Needed

None required for basic local testing. The app runs with SQLite and dummy API keys.

## Local Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

The app needs a few env vars to start. The `OPENAI_API_KEY` is required at import time (not just at runtime) because `LoanMVP/services/ai_summary.py` instantiates the OpenAI client at module level.

```bash
export FLASK_ENV=development
export FLASK_DEBUG=true
export DATABASE_URL="sqlite:///local.db"
export SOCKETIO_ASYNC_MODE=threading
export OPENAI_API_KEY="sk-dummy-key-for-local-testing"
```

### 3. Initialize Database

Create the SQLite database and seed test users:

```python
from werkzeug.security import generate_password_hash
from LoanMVP.app import create_app
from LoanMVP.extensions import db
from LoanMVP.models.user_model import User
from LoanMVP.models.admin import Company

app = create_app()
with app.app_context():
    db.create_all()
    # Create companies and users as needed
    # Default password for test users: generate_password_hash('TestPass123!')
```

Important user model fields:
- `invite_accepted=True` and `onboarding_complete=True` are required to skip onboarding redirects
- `company_id` must be set for admin users to test company-scoped dashboards

### 4. Start the Dev Server

```bash
python3 -c "
from LoanMVP.app import create_app, socketio
app = create_app()
socketio.run(app, host='0.0.0.0', port=5050, debug=True, use_reloader=False)
"
```

The app runs on `http://localhost:5050`.

## Key URLs

| URL | Description |
|-----|-------------|
| `/auth/login` | Login page (form fields: `email`, `password`) |
| `/auth/post-login-redirect` | Post-login redirect handler (determines dashboard) |
| `/executive/dashboard` | Executive dashboard |
| `/admin/company/<id>/dashboard` | Company admin dashboard |
| `/admin/dashboard` | Global admin dashboard |

## Architecture Notes

### Dashboard Routing

The post-login redirect logic lives in `LoanMVP/routes/auth.py` → `post_login_redirect()`. The order of checks matters:
1. Onboarding incomplete → complete profile
2. Executive dashboard user check (email override + role=executive)
3. Admin with company_id → admin company dashboard
4. Admin-level roles → admin dashboard
5. Fallback → role-based dashboard

### Executive Access

Two separate checks control executive dashboard access:
- `_is_executive_dashboard_user()` in `auth.py` — controls the login redirect
- `_can_access_executive_dashboard()` in `executive_new.py` — controls route guard (bounces unauthorized users)

Both must allow a user for them to stay on the executive dashboard.

### Blueprint Loading

`executive.py` is aliased to load from `executive_new.py` via `app.py` line ~360:
```python
module_aliases = {"executive.py": "LoanMVP.routes.executive_new"}
```
So `executive_new.py` is the active module at runtime, but `executive.py` still exists in the codebase.

### Sidebar Templates

The sidebar is selected in `templates/layouts/ravlo_employee_base.html` (lines 26-38) based on `current_user.role`, NOT the current route. This means users with role="admin" will see the admin sidebar even when viewing executive dashboard pages. The executive sidebar (`_sidebar_executive.html`) only renders for users with `role="executive"`.

### Logout

The `/auth/logout` route requires POST (not GET). To log out between tests, either:
- Open a new browser tab (new session) to `/auth/login`
- Clear cookies via browser console
- Use the Logout button in the UI (which submits a POST form with CSRF token)

## Common Issues

- **OpenAI import error**: Must set `OPENAI_API_KEY` env var before importing the app, even with a dummy value
- **405 on logout**: The logout route is POST-only; use a new tab or clear cookies to switch users
- **`run.py` refuses to start**: In production mode with `SOCKETIO_ASYNC_MODE=threading`, `run.py` raises RuntimeError. Use `FLASK_ENV=development` or start directly with `socketio.run()`
