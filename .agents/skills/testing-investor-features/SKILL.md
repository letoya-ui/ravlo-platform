# Testing Ravlo Investor Features

## Local Dev Setup

```bash
# Start the Flask dev server
PYENV_VERSION=3.10.16 OPENAI_API_KEY=sk-dummy FLASK_ENV=development python run.py
# Runs on http://localhost:5050
```

- The server uses Socket.IO with threading async mode
- `OPENAI_API_KEY=sk-dummy` is fine for testing non-AI features (AI calls will fail with 401)
- Server must be restarted after code changes (no auto-reload observed)

## Test Account

- **Email:** test_investor@test.com
- **Password:** TestPass123!
- **Role:** investor
- **Login URL:** `/auth/login` (NOT `/login`)
- **Test Deal ID:** 1 (local), 20 (production at ravlohq.com)

## Key Routes

| Feature | URL |
|---------|-----|
| Login | `/auth/login` |
| Dashboard | `/investor/dashboard` |
| Deal Finder (property search) | `/investor/property-tool` |
| Deal Workspace | `/investor/deals/workspace?prop_id={id}` |
| Rehab Studio | `/investor/deals/{deal_id}/rehab` |
| Save property | `POST /investor/api/property_tool_save` |
| Save & Analyze | `POST /investor/api/property_tool_save_and_analyze` |
| Generate renovation | `POST /investor/deal-studio/rehab-studio/generate` |

## Devin Secrets Needed

For full end-to-end testing of image features:
- `SPACES_BUCKET` — DigitalOcean Spaces bucket name
- `SPACES_REGION` — DO Spaces region (e.g., nyc3)
- `SPACES_ENDPOINT` — DO Spaces endpoint URL
- `SPACES_ACCESS_KEY_ID` — DO Spaces access key
- `SPACES_SECRET_ACCESS_KEY` — DO Spaces secret key
- `SPACES_PUBLIC_BASE_URL` — CDN base URL for uploaded images
- `OPENAI_API_KEY` — For AI-powered features (deal analysis, recommendations)
- `RENOVATION_ENGINE_URL` — URL to the renovation/build engine (ngrok URL)

Without DO Spaces credentials, image upload tests will verify graceful failure (returns empty list with warning log) but cannot verify actual uploads.

## Common Pitfalls

1. **CSRF tokens for curl-based API testing:** The Flask app uses CSRF protection. Extract the token from a page via `csrfToken = "..."` pattern in the HTML, then pass as `X-CSRFToken` header. CSRF extraction via curl can be unreliable — consider testing backend functions directly via Python import instead.

2. **Auth route is `/auth/login`, not `/login`:** The auth blueprint is mounted at `/auth`.

3. **`/investor/command-center` might not exist:** Use `/investor/dashboard` as the landing page after login.

4. **Photo URLs from property search:** The frontend proxies image URLs through `/investor/api/property_tool_image?src=<original_url>` for display, but sends the **original** URLs in the save payload. The backend's `_unwrap_proxy_url` handles cases where proxied URLs slip through.

5. **Non-image URLs as listing photos:** Property search results sometimes include listing page URLs (e.g., realtor.com pages) instead of direct image URLs. The `_is_image_url` function filters these using hostname+path matching. If new real estate sites are added, `_LISTING_PAGE_RULES` in `investor_media_helpers.py` may need updating.

6. **Server restart needed:** After editing Python files, restart the Flask dev server to pick up changes. The dev server does not always auto-reload.

## Testing Photo Upload Pipeline

The photo upload pipeline can be tested directly via Python without the full Flask server:

```python
from LoanMVP.services.investor.investor_media_helpers import (
    _is_image_url, _unwrap_proxy_url, download_image_bytes,
    upload_listing_photos_to_spaces, _try_upload_and_attach_listing_photos
)

# Test URL filtering
assert _is_image_url('https://ap.rdcpix.com/photo.jpg') == True
assert _is_image_url('https://www.realtor.com/realestateandhomes-detail/123') == False

# Test proxy unwrapping  
assert _unwrap_proxy_url('/api/property_tool_image?src=https%3A%2F%2Fcdn.example.com%2Fphoto.jpg') == 'https://cdn.example.com/photo.jpg'

# Test image download (needs network)
result = download_image_bytes('https://picsum.photos/id/10/300/200')
assert result is not None and len(result) > 1000
```
