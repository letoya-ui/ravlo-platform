# Testing Renovation Studio (Rehab Studio)

## Routes
- `/investor/deal-studio/rehab-studio?deal_id=<id>` — Main studio page with deal context
- `/investor/deal-studio/rehab-studio` — Studio without deal (generic mode)
- `/investor/deal-studio/rehab-studio/generate` (POST) — Generate renovation concept
- `/investor/deal-studio/rehab-studio/generate-variant` (POST) — Generate variant concept
- `/investor/deals/<id>/rehab/budget` — Rehab Budget Tracker

## Test Account
- Email: `investor@test.com` / Password: `Password123!`
- Test Deal ID: 1 ("123 Main Street")

## Running Locally
```bash
FLASK_ENV=development \
OPENAI_API_KEY="sk-dummy-key-for-local-testing" \
RENOVATION_ENGINE_URL="<ngrok-or-engine-url>" \
python -m flask --app LoanMVP.app run --host 0.0.0.0 --port 5050 --debug
```

## Key Test Flows

### 1. Page Load
- Navigate to `/investor/deal-studio/rehab-studio?deal_id=1`
- Verify: Hero shows deal info, 4-step workflow strip (Setup/Before/After/Concepts), form with 4 dropdowns, sidebar tracker

### 2. Form Interaction
- All 4 dropdowns: Preset (5 options), Mode (5 options), Room (5 options), Strength (3 options)
- File upload shows thumbnail preview and filename
- Image URL input accepts pasted URLs

### 3. Generate Concept
- Requires: RENOVATION_ENGINE_URL configured, before image uploaded
- Loading overlay shows 3-step progress
- Engine sends POST to `/v1/renovate` with image_base64 payload
- Upload step requires DigitalOcean Spaces credentials (SPACES_KEY, SPACES_SECRET, SPACES_BUCKET, SPACES_ENDPOINT)
- Without DO Spaces creds: engine generates images but upload fails (expected in local dev)

### 4. Reset Button
- Should reset ALL dropdowns to defaults: Luxury / HGTV / Living Room / Balanced
- Should clear file input, image preview, and status pill

### 5. Variant Modal
- Click "Generate Another Concept" to open
- Has Preset and Mode dropdowns
- Close via Cancel button or backdrop click

### 6. Budget Tracker
- Navigate to `/investor/deals/1/rehab/budget`
- 6 stat cards: Estimated Total, Actual Total, Paid Total, Contingency, Total Budget, Remaining Balance
- Add Expense form: Category, Status, Description, Vendor, Paid Amount, Estimated Cost, Actual Cost, Notes
- Submit adds expense to ledger and updates stats

## Known Limitations
- DigitalOcean Spaces credentials required for full generate flow (image upload)
- RENOVATION_ENGINE_URL must point to a running GPU engine (user runs locally via ngrok)
- SCOPE_ENGINE_URL needed for rehab scope analysis
- OpenAI API key needed for AI assistant features (dashboard only, not rehab studio)
