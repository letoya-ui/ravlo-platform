# Testing the Elena CRM Dashboard

The Elena dashboard is the CRM + content engine for partners (realtors,
investors, contractors, etc.). It is separate from the generic partner
dashboards under `/partners/*`. Code lives in:

- Routes: `LoanMVP/routes/elena.py`
- Models: `LoanMVP/models/elena_models.py`
- Templates: `LoanMVP/templates/elena/`

## Test login

| Role             | Email                        | Password              |
| ---------------- | ---------------------------- | --------------------- |
| Elena (realtor)  | nyrealtorelena@gmail.com     | $ELENA_TEST_PASSWORD  |

Ask the user for the password if it is not already in your secrets;
do not commit the literal value. Elena's user row must have
`partner_category='realtor'` and be tied to a `Partner` record,
otherwise `/partners/*` and `/elena/*` routes will 302.

## Key routes

- `GET /elena/` — main CRM dashboard: summary cards, quick actions,
  pipeline kanban, activity timeline, Template Studio sidebar, listing
  manager with `?listing_status=` filter.
- `GET/POST /elena/clients/new`
- `GET/POST /elena/listings/new`
- `GET/POST /elena/interactions/new`
- `GET /elena/template-studio`

All routes use `@role_required("partner", "admin")`.

## Seeding Elena data with flask shell

Chrome's native `datetime-local` input is unreliable inside the computer-use
harness (the segmented picker over-fills the year segment and ignores
backspace to a blank state). To test anything that depends on `due_at`,
skip the UI and insert rows directly:

```python
from LoanMVP.app import app, db
from LoanMVP.models.elena_models import (
    ElenaClient, ElenaListing, ElenaInteraction, InteractionType
)
from datetime import datetime, timedelta

with app.app_context():
    client = ElenaClient(
        name="Maya Rivera (TEST)",
        email="maya.rivera.test@example.com",
        role="investor",
        pipeline_stage="warm",
        tags="vip, brooklyn",
    )
    db.session.add(client)
    db.session.flush()

    db.session.add(ElenaListing(
        address="221 Devin Test Ave",
        city="Brooklyn", state="NY", zip="11201",
        status="active", price=750000, beds=3, baths=2,
        client_id=client.id,
    ))

    db.session.add(ElenaInteraction(
        client_id=client.id,
        interaction_type=InteractionType.FOLLOW_UP,
        content="Seed: null-due_at interaction (excluded from Follow-Ups Due).",
    ))
    db.session.add(ElenaInteraction(
        client_id=client.id,
        interaction_type=InteractionType.FOLLOW_UP,
        content="Seed: +3d follow-up (counted inside 7-day window).",
        due_at=datetime.utcnow() + timedelta(days=3),
    ))
    db.session.commit()
```

## Semantics you should sanity-check

- **Follow-Ups Due** counter is a *strict* 7-day window: rows with
  `due_at IS NULL` or `due_at < now` or `due_at > now + 7 days` are
  excluded. If the counter grows every week without ever dropping, the
  lower-bound filter is missing again.
- **Pipeline column badges** render a real `.count()` aggregate per stage.
  The `clients` list is capped at 12 for rendering, but the badge must
  reflect the true stage total.
- **`_parse_due_at`** accepts four datetime formats:
  `%Y-%m-%dT%H:%M`, `%Y-%m-%dT%H:%M:%S`, `%Y-%m-%d %H:%M:%S`, `%Y-%m-%d`.
  If you add a fifth format, add a line in this skill so future sessions
  know to test it.

## Database migrations

The dashboard requires columns added in migration
`20260417elena01` (role/tags on ElenaClient, status on ElenaListing,
title/cta on ElenaFlyer, due_at on ElenaInteraction, MEETING/FOLLOW_UP in
InteractionType). Run `alembic upgrade head` if the local DB is older.
