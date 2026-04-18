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

## Testing Tips

- Logout is POST-only (`/auth/logout`). Use the Logout button in the UI, not a GET request.
- `executive.py` is aliased to `executive_new.py` at runtime via `app.py` module_aliases.
- The sidebar selection in `ravlo_employee_base.html` checks email before role, so admin-role users with executive emails see the executive sidebar.
- When testing sidebar changes, make sure to scroll the sidebar to verify all sections are visible since the sidebar may be taller than the viewport.
- Admin routes like `admin.ai_dashboard`, `admin.verify_data`, `admin.messages`, `admin.reports` use `@role_required("admin")` or `@role_required("admin_group")`, so users with role=admin can access them even when routed through the executive sidebar.
