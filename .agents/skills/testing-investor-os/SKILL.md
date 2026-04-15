# Testing Investor OS

How to set up and test the Investor OS portion of the Ravlo platform.

## Devin Secrets Needed

- No secrets required for local testing — the app uses SQLite and dummy API keys
- For live API testing (OpenAI, Rentcast, Attom, Mashvisor, RapidAPI), the respective API keys must be set as environment variables

## Flask Dev Server Setup

```bash
# From repo root:
FLASK_ENV=development OPENAI_API_KEY=sk-dummy-key-for-local-testing \
  python -m flask --app LoanMVP.app run --host 0.0.0.0 --port 5050 --debug
```

- The app runs on **port 5050** (not the default 5000)
- SQLite database is at `instance/local.db`
- Debug mode enables auto-reload on code changes

## Test Account

- **Email:** investor@test.com
- **Password:** Password123!
- **Role:** investor
- **User ID:** 2, **Profile ID:** 1

## Key Investor Routes to Test

These are the routes that have historically had bugs:

| Route | What It Tests |
|-------|---------------|
| `/investor/dashboard` | Main command center |
| `/investor/search` | Search results (Jinja template) |
| `/investor/deal/1/analysis` | Deal analysis (template name) |
| `/investor/deals/1/edit` | Deal edit form (GET method + layout) |
| `/investor/partners/marketplace` | Partner marketplace (model imports) |
| `/investor/deal-studio/build-studio` | Build Studio (helper function args) |
| `/investor/deal-studio/rehab-studio` | Rehab Studio (render seed function) |
| `/investor/does-not-exist` | 404 handler (should NOT return 500) |

## Systematic Route Health Check

To test all investor GET routes at once:

1. Log in via curl to get session cookies:
```bash
CSRF=$(curl -s -c /tmp/cookies.txt http://localhost:5050/auth/login | \
  python3 -c "import sys,re; html=sys.stdin.read(); m=re.search(r'name=\"csrf_token\".*?value=\"([^\"]+)\"', html); print(m.group(1) if m else 'NO_CSRF')")
curl -s -b /tmp/cookies.txt -c /tmp/cookies.txt -L -o /dev/null \
  -d "email=investor@test.com&password=Password123!&csrf_token=$CSRF" \
  http://localhost:5050/auth/login
```

2. Curl each route and check status codes:
```bash
curl -s -b /tmp/cookies.txt -o /dev/null -w "%{http_code}" http://localhost:5050/investor/dashboard
```

3. Expected results: All routes should return 200 or 302 (redirect). Zero 500 errors.

## Common Issues

- **Jinja TemplateSyntaxError:** Check for orphaned `{% endif %}` or `{% endblock %}` tags without matching openers
- **TemplateNotFoundError:** Verify template file names match what the route references. Templates are in `LoanMVP/templates/investor/`
- **Wrong base layout:** Investor templates should extend `layouts/ravlo_base.html`, NOT `layouts/borrower_base.html`
- **Wrong route references:** Investor templates should use `investor.*` blueprint names, NOT `borrower.*`
- **PartnerRequest import:** The `PartnerRequest` model may be `None` if the import fails — always check `if PartnerRequest is not None:` before using `.query`
- **SocketIO CORS:** Dev config must include port 5050 origins for WebSocket connections
- **`hash()` non-determinism:** Python's `hash()` is randomized across process restarts. Use `hashlib.md5()` for stable seeds.
- **Error handler swallowing 404s:** The global `@app.errorhandler(Exception)` must check `isinstance(e, HTTPException)` to avoid converting 404s into 500s

## Browser Testing Tips

- Login via the browser at `http://localhost:5050/auth/login`
- After login, you're redirected to `/investor/dashboard`
- The sidebar navigation covers all major sections: Command, Deals, Capital, Network, Resources, System
- AI features (deal summary, next best move) will show warnings with a dummy API key — this is expected
