# Testing Rehab Studio

## Local Dev Server

```bash
# Start the Flask dev server (requires OPENAI_API_KEY even if dummy)
PYENV_VERSION=3.10.16 OPENAI_API_KEY=sk-dummy FLASK_ENV=development python run.py
# Server runs on port 5050
```

## Test Accounts

- **Investor**: test_investor@test.com / TestPass123! (role=investor)
- **Admin**: sandra@ravlohq.com / $SANDRA_ADMIN_PASSWORD (role=admin)
- See environment config notes for additional test accounts

## Rehab Studio Routes

- **Rehab Studio page**: `/investor/deals/<deal_id>/rehab` (GET)
- **Generate endpoint**: `/investor/deal-studio/rehab-studio/generate` (POST)
- **Workspace page**: `/investor/deals/workspace` (GET)
- Deal ID 1 ("123 Test St") has workspace images for testing

## Renovation Engine

- Configured via `RENOVATION_ENGINE_URL` in `LoanMVP/config.py` (default: ngrok tunnel)
- Helper function `_renovation_engine_url()` in `LoanMVP/services/investor/investor_engine_helpers.py` reads from Flask config via `_engine_base_url()`
- Engine must be reachable for generation to work; verify with: `curl -s -o /dev/null -w '%{http_code}' -H 'ngrok-skip-browser-warning: true' <ENGINE_URL>/`
- Generation timeout: 240 seconds

## External Dependencies for Full Generation

- **DigitalOcean Spaces**: Required for uploading generated images. Needs `DO_SPACES_ENDPOINT`, `DO_SPACES_KEY`, `DO_SPACES_SECRET` env vars.
- Without DO Spaces credentials, generation reaches the engine but fails at the upload step with `ValueError: Invalid endpoint:`

## Key Files

- `LoanMVP/templates/investor/deal_rehab_studio.html` — Rehab Studio UI and JS form handler
- `LoanMVP/routes/investor_routes.py` — Backend routes for rehab studio (deal_rehab, deal_rehab_generate)
- `LoanMVP/services/investor/investor_engine_helpers.py` — Renovation engine API helpers
- `LoanMVP/services/investor/investor_media_helpers.py` — Image upload helpers (DO Spaces)
- `LoanMVP/config.py` — App configuration including engine URLs
