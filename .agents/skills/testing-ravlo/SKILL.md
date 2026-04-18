# Testing Ravlo Platform

## Local App Setup

```bash
export FLASK_ENV=development FLASK_DEBUG=true DATABASE_URL="sqlite:///local.db" SOCKETIO_ASYNC_MODE=threading OPENAI_API_KEY="sk-dummy"
python run.py
# Server runs on port 5050
```

- Use `python run.py` (not `flask run`) — SocketIO requires it
- `OPENAI_API_KEY` must be set (even dummy) before importing the app
- Login page: `/auth/login`
- Local test investor: `investor@test.com` / `Password123!`

## Render Deployment

- URL: `https://ravlo-platform-1.onrender.com` (same as `ravlohq.com`)
- Admin login: `letoya@ravlohq.com` (role=admin, can access executive dashboard and user management)
- Note: `letoya@caughmanmason.com` is NOT registered in the Render database
- Admin accounts cannot access investor routes (Deal Finder, Workspace) — use an investor account
- The app auto-deploys from `main` branch on merge

## Devin Secrets Needed

- `RENTCAST_API_KEY` — for Deal Finder property search
- `ATTOM_API_KEY` — for property detail enrichment
- `MASHVISOR_API_KEY` — for STR/Airbnb data and **property photos** (the only photo source)
- These are configured on Render but not available locally

## Deal Finder Testing

### Image Pipeline Architecture
- RentCast sale listings API does **NOT** return property photos
- Mashvisor `GET /v1.1/client/property/{id}/images` is the **only** source of property photos
- The orchestrator flow: RentCast search → Mashvisor validate (get property_id) → Mashvisor get_property_images → merge into CanonicalProperty
- Frontend: `resolveCardImageSrc()` checks `listing_photos`/`photos`, falls back to OpenStreetMap tiles if empty
- Image proxy: `/investor/api/property_tool_image?src=<encoded_url>` — converts external URLs to avoid CORS/referrer issues

### Testing Without Real API Keys
Mock the orchestrator's `run_search` method to return pre-built results with photo URLs:

```python
from LoanMVP.services.investor.property_orchestrator import PropertyIntelligenceOrchestrator

def _patched_run_search(self, *, address="", city="", state="", zip_code="", limit=12):
    return [mock_result_dicts], mock_meta_dict

PropertyIntelligenceOrchestrator.run_search = _patched_run_search
```

Key fields in result dicts: `listing_photos`, `photos`, `primary_photo`, `image_url`

For unit testing individual functions:
- `normalize_mashvisor_validation(result)` — test with mock validate responses
- `_extract_mashvisor_photos(normalized, raw_result)` — test photo extraction from nested paths
- `_resolve_mashvisor_property_id(result, normalized)` — test fallback chain
- `_proxy_search_result_images(result)` — needs Flask app context (`with app.test_request_context():`)

### Common Issues
- Searching with dummy RentCast key returns 0 results — must mock `run_search` for UI testing
- Mock photo URLs from external sites (Zillow, Realtor) will 404 through the local proxy — this is expected; the `onerror` fallback shows placeholder
- CSRF protection blocks `fetch()` calls to the search API from browser console — use Flask test client instead
- Land/vacant lot properties typically have no Mashvisor photos — test with residential ZIP codes

## Workspace Testing

- URL: `/investor/deals/workspace?prop_id=X`
- Photos come from `resolved_json` in SavedProperty model
- Template: `deal_workspace.html` — photos have `referrerpolicy="no-referrer"` and `onerror` fallback
- Empty state shows "No listing photos are attached yet."

## Role-Based Access

| Role | Dashboard | Deal Finder | Workspace | Admin |
|------|-----------|-------------|-----------|-------|
| investor | `/investor/dashboard` | Yes | Yes | No |
| admin | `/admin/company/X/dashboard` | No | No | Yes |
| executive | `/executive/dashboard` | No | No | No |

- Executive routing is email-based (allowlist in `auth.py`)
- To test investor features with an admin account, create a separate investor account
