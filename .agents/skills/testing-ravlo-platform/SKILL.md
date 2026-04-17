# Testing ravlo-platform

## Overview
ravlo-platform is a Flask web application for real estate investors. The main features include Deal Finder (property search and analysis), Deal Workspace, Project Studio, Budget Studio, and Capital Studio.

## Devin Secrets Needed
- `RAPIDAPI_KEY` — RapidAPI key with Realtor API subscription (primary property search)
- `RENTCAST_API_KEY` — RentCast API key (rent estimates, property values, fallback search)
- `ATTOM_API_KEY` — ATTOM API key (property details and enrichment)
- `MASHVISOR_API_KEY` — Mashvisor API key (STR/Airbnb data)
- `OPENAI_API_KEY` — OpenAI API key (AI recommendations, Portfolio Insight). A dummy value (`sk-dummy`) works for most features except AI-powered ones.

All API keys should be repo-scoped secrets for `letoya-ui/ravlo-platform`.

## Local Setup

```bash
cd /home/ubuntu/repos/ravlo-platform
pip install -r requirements.txt

# Start the Flask app (use python run.py, NOT flask run — SocketIO requires it)
export FLASK_ENV=development
export OPENAI_API_KEY="sk-dummy-key-for-local-testing"
# Set API keys if testing Deal Finder:
export RAPIDAPI_KEY="..."
export RENTCAST_API_KEY="..."
export ATTOM_API_KEY="..."
export MASHVISOR_API_KEY="..."
python run.py
# Server starts on http://127.0.0.1:5050
```

## Test Credentials
- **Investor user**: `investor@test.com` / `Password123!` (role=investor)
- If the test user doesn't exist, create one via the seed script or manually via Python shell.

## Testing Deal Finder

### Prerequisites
1. Flask app running with API keys configured
2. Test user logged in as investor
3. **InvestorProfile must exist** for the test user — Save & Analyze will fail with "Investor profile not found" without it. Create one via:
   ```python
   from LoanMVP.app import create_app
   from LoanMVP.extensions import db
   from LoanMVP.models.user_model import User
   from LoanMVP.models.investor_models import InvestorProfile
   
   app = create_app()
   with app.app_context():
       user = User.query.filter_by(email='investor@test.com').first()
       profile = InvestorProfile(user_id=user.id, full_name='Test Investor', email='investor@test.com', strategy='flip')
       db.session.add(profile)
       db.session.commit()
   ```

### Deal Finder Flow
1. Navigate to `/investor/property_tool`
2. Enter search criteria (address, city, state, ZIP code)
3. Select strategy (Fix & Flip, Rental, Airbnb, All) and asset type
4. Click "Find Deals"
5. Review property cards with scores, strategy analysis, exit strategy cards
6. Click "Save & Analyze" to save deal to workspace
7. Verify deal appears in Deal Workspace (`/investor/deals/workspace`)
8. Verify deal appears in Saved Properties (`/investor/saved_properties`)

### Search Architecture & Known Issues
- **Primary search**: Realtor API via RapidAPI (`RAPIDAPI_KEY`). If the key doesn't have an active Realtor subscription, searches will fail silently and fall back.
- **Fallback search**: RentCast sale listings API. **Requires city + state fields** — ZIP-only searches will return 0 results when Realtor API is unavailable.
- **Enrichment**: After finding candidates, the orchestrator enriches with ATTOM (property details), RentCast (rent estimates/values), and Mashvisor (STR data).
- The search engine status shows "Connected" when all APIs work, "Partial" when some fail.

### What to Verify
- Search returns property cards with score (X/99), classification (strong/moderate/etc.), strategy tag
- Property card shows: list price, estimated value, beds/baths/sqft, DOM
- Exit strategy cards: Flip (projected profit), Rental (monthly cash flow), Airbnb (net monthly), Land/Build (optionality score)
- AI recommendation and risk notes sections
- Save & Analyze redirects to Deal Workspace with full analysis
- Saved Properties page shows the saved deal with correct data

### Tips
- If searches return 0 results, check Flask server logs for API error messages (e.g., "You are not subscribed to this API")
- Use real addresses from RentCast listings for testing — fake addresses won't match in the RentCast fallback
- You can test RentCast API directly: `curl -s "https://api.rentcast.io/v1/listings/sale?city=Atlanta&state=GA&status=Active&limit=3" -H "X-Api-Key: $RENTCAST_API_KEY"`
- The "Portfolio Insight" AI feature on Saved Properties requires a real OpenAI key
