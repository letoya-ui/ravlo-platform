# Testing the Investor Portal

## Starting the Flask Server

```bash
# Option 1: Using run.py (preferred, supports SocketIO)
export FLASK_ENV=development FLASK_DEBUG=true DATABASE_URL="sqlite:///local.db" SOCKETIO_ASYNC_MODE=threading OPENAI_API_KEY="sk-dummy"
python run.py

# Option 2: Using flask run (fallback)
FLASK_APP=LoanMVP.app:app FLASK_ENV=development FLASK_DEBUG=true DATABASE_URL="sqlite:///local.db" SOCKETIO_ASYNC_MODE=threading OPENAI_API_KEY="sk-dummy" python -m flask run --host=0.0.0.0 --port=5050
```

Server runs on port 5050.

## Test Accounts

| Role | Email | Password |
|------|-------|----------|
| Investor | investor@test.com | Password123! |
| Loan Officer | lo@test.com | Test1234! |
| Processor | proc@test.com | Test1234! |
| Borrower | borrower@test.com | Test1234! |
| Underwriter | uw@test.com | Test1234! |
| Admin | sandra@ravlohq.com | $SANDRA_ADMIN_PASSWORD |

## Key Investor Portal Pages

- **Deal Finder**: `/investor/property_tool` — search for properties by address/ZIP
- **Deal Cards**: `/investor/deals/cards` — grid view of all user's deals
- **Deal Workspace**: `/investor/deals/workspace?prop_id={id}` — detailed analysis view
- **Deal List**: `/investor/deals` — table view of deals
- **Saved Properties**: `/investor/saved_properties` — saved property list

## Injecting Test Data

To test with realistic property data without API keys:

```python
import json, sys
sys.path.insert(0, '.')
from LoanMVP.app import create_app
app = create_app()
with app.app_context():
    from LoanMVP.extensions import db
    from LoanMVP.models import Deal, SavedProperty
    
    sp = db.session.get(SavedProperty, 1)
    sp.resolved_json = json.dumps({
        'property': {
            'address': '123 Oak Street, Atlanta GA 30301',
            'imgSrc': 'https://example.com/photo.jpg',
            'listing_photos': ['https://example.com/photo1.jpg', 'https://example.com/photo2.jpg'],
            'image_url': 'https://example.com/photo.jpg',
        },
        'workspace_analysis': {
            'image_url': 'https://example.com/photo.jpg',
            'listing_photos': ['https://example.com/photo1.jpg', 'https://example.com/photo2.jpg'],
        },
    })
    
    deal = db.session.get(Deal, 1)
    rj = json.loads(deal.results_json) if isinstance(deal.results_json, str) else (deal.results_json or {})
    rj['workspace_analysis'] = rj.get('workspace_analysis', {}) or {}
    rj['workspace_analysis']['image_url'] = 'https://example.com/photo.jpg'
    deal.results_json = rj
    
    db.session.commit()
```

## Photo Pipeline Architecture

1. **API Response** -> `PropertyIntelligenceOrchestrator` enrichment functions extract photos from raw responses
2. **Key extraction**: `_normalize_photo_list` in `investor_media_helpers.py` recognizes API-specific keys: `imgSrc`, `primaryPhoto`, `coverImage`, `listingPhotos`, `propertyPhotos`
3. **Proxy layer**: Workspace listing photos go through `_proxy_photo_list` -> `/investor/api/property_tool_image?src=...` which fetches images server-side
4. **Template rendering**: `deal_workspace.html` reads `primary_photo` and `listing_photos` template variables

## Known Issues

- The image proxy endpoint (`/investor/api/property_tool_image`) may return 404 for certain upstream image URLs
- The placeholder fallback image `/static/images/placeholder_property.jpg` does not exist
- Deal Finder requires real API keys (RENTCAST_API_KEY, ATTOM_API_KEY, MASHVISOR_API_KEY) to return search results with photos
