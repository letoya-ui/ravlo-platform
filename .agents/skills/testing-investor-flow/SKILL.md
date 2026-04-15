# Testing Investor Flow — Ravlo Platform

## Overview
The investor flow covers the complete user journey: search properties (Deal Finder) -> analyze deals (Deal Architect/Budget Studio) -> build/renovate (Build Studio/Reno Studio) -> get financing (Capital Studio/LendingOS) -> manage portfolio.

## Devin Secrets Needed
- `OPENAI_API_KEY` — Required for AI Hub, Ravlo AI assistant, and AI-powered features. Use `sk-dummy-key-for-local-testing` for pages that don't actually call OpenAI.
- No other secrets required for basic investor flow testing.

## Local Setup

1. **Start Flask server:**
   ```bash
   cd /home/ubuntu/repos/ravlo-platform
   FLASK_ENV=development OPENAI_API_KEY=sk-dummy-key-for-local-testing python -m flask --app LoanMVP.app run --host 0.0.0.0 --port 5050
   ```

2. **Create test investor account** (if not exists):
   ```bash
   python -c "
   import sys; sys.path.insert(0, '.')
   from LoanMVP.app import create_app
   from LoanMVP.extensions import db
   from LoanMVP.models import User
   from LoanMVP.models.investor_models import InvestorProfile
   from werkzeug.security import generate_password_hash
   app = create_app()
   with app.app_context():
       u = User.query.filter_by(email='investor@test.com').first()
       if not u:
           u = User(email='investor@test.com', password_hash=generate_password_hash('Password123!'), role='investor', first_name='Test', last_name='Investor', is_approved=True)
           db.session.add(u); db.session.flush()
           ip = InvestorProfile(user_id=u.id, strategy='fix_and_flip', experience_level='beginner', target_markets='Test City, TS', capital_available=100000)
           db.session.add(ip); db.session.commit()
           print(f'Created user_id={u.id}, profile_id={ip.id}')
       else:
           print(f'Exists: user_id={u.id}')
   "
   ```

3. **Create test deal** (needed for Build Studio, Rehab Studio, Deal Architect):
   ```bash
   python -c "
   import sys; sys.path.insert(0, '.')
   from LoanMVP.app import create_app
   from LoanMVP.extensions import db
   from LoanMVP.models.investor_models import Deal
   app = create_app()
   with app.app_context():
       d = Deal.query.filter_by(user_id=2).first()
       if not d:
           d = Deal(user_id=2, address='123 Main Street', city='Test City', state='TS', zip_code='12345', asking_price=250000, score=78.0)
           db.session.add(d); db.session.commit()
           print(f'Created deal_id={d.id}')
       else:
           print(f'Exists: deal_id={d.id}')
   "
   ```

## Test Account
- **Email:** investor@test.com
- **Password:** Password123!
- **Role:** investor

## Key Investor Pages to Test

| Page | URL | Notes |
|------|-----|-------|
| Command Center | `/investor/` | Dashboard with deal stats |
| Messages | `/investor/messages` | SocketIO-powered messaging |
| Deal Finder | `/investor/deal-finder` | Property search (needs API keys for live data) |
| Project Studio | `/investor/project-studio` | Complex development projects |
| Budget Studio | `/investor/budget-studio` | Budget tracking |
| AI Hub | `/investor/ai-hub` | AI features (needs OpenAI key) |
| Compare Deals | `/investor/compare` | Deal comparison |
| Capital Studio | `/investor/capital-studio` | Financing/LendingOS |
| Documents Vault | `/investor/documents` | Document management |
| Partner Network | `/investor/partner-network` | Partner marketplace |
| Saved Properties | `/investor/saved-properties` | Saved listings |
| Resource Center | `/investor/resource-center` | Resources |
| Build Studio | `/investor/deals/{id}/build` | Needs deal_id, shows 5-step wizard |
| Rehab Studio | `/investor/deals/{id}/rehab` | Needs deal_id, shows 4-step wizard |
| Deal Architect | `/investor/deals/{id}/architect` | Needs deal_id |

## Known Issues & Gotchas

1. **SocketIO might not work with `flask run`**: Flask-SocketIO requires `socketio.run()` for full CORS/event-loop support. When testing via `flask run`, SocketIO POST requests may return 400. In production, the app uses `socketio.run()` which handles CORS correctly. For local SocketIO testing, run via `python -m LoanMVP.app` instead.

2. **Rehab Studio generation needs GPU**: The renovation engine runs locally on GPU. Without it, generation calls will fail. The page itself should still load — just the generate endpoint won't produce images.

3. **Deal-dependent pages need a deal_id**: Build Studio, Rehab Studio, and Deal Architect all require a valid deal_id in the URL. Create a test deal first (see setup above).

4. **`_stable_render_seed()` accepts `*parts`**: This function uses variadic args. If you see it being called with a fixed-param signature like `(deal_id, variant)`, that's a bug — it should be `(*parts)`.

5. **`_safe_first_related()` expects a list/queryset**: Not `(object, string)`. Correct usage: `_safe_first_related(getattr(deal, 'projects', None))`.

6. **Feature reveal route**: POST to `/investor/deals/{id}/rehab/feature` — the `_set_featured_rehab()` helper must accept `style_prompt` as a keyword argument.

7. **No CI configured**: The repo has no CI pipeline. Run `python -m py_compile <file>` manually to check syntax before committing.

## Testing Approach

1. Start Flask server locally
2. Log in as test investor via browser
3. Navigate through all investor pages, checking for 500 errors
4. Monitor Flask server logs in a separate shell for tracebacks
5. For function-level tests (like `_stable_render_seed`), use direct Python calls
6. For POST endpoints (like feature reveal), use `curl` with session cookies
7. Record browser testing with annotations for visual proof
