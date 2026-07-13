# Property Management

Investor-facing rental portfolio tool at `/property` (`property_bp` in
`LoanMVP/routes/property_routes.py`). Ravlo staff (platform_admin,
master_admin, lending_admin, executive) see every investor's portfolio;
an `investor` account only sees properties they own
(`Property.owner_investor_id`).

Distinct from `Deal`/`PropertyAnalysis` (one-time underwriting records
for a prospective purchase) -- this tracks ongoing rental operations for
a property an investor already owns and manages.

| Template | Route | Description |
|---|---|---|
| `dashboard.html` | `/property/dashboard` | Portfolio overview: unit/occupancy counts, rent collected, maintenance cost, net cash flow. |
| `list.html` | `/property/list` | List of properties in the portfolio. |
| `new.html` | `/property/new` | Add a property. |
| `view.html` | `/property/view/<id>` | Property detail: units, add-unit form, edit property details. |
| `unit_detail.html` | `/property/unit/<id>` | Unit detail: tenant/lease, rent roll, maintenance requests. |
| `search.html` | `/property/search` | Address search/lookup page (uses `/property/autocomplete` + `/property/resolve`). |

`/property/autocomplete`, `/property/resolve`, and
`/property/resolver/metrics` are address-lookup utilities (Google Places
autocomplete, `unified_property_resolver`) unrelated to the tables above
-- they don't touch the database and are reused wherever an address needs
resolving.

`/property/manage` is a legacy URL kept as a redirect to `/property/dashboard`
for old bookmarks/sidebar links.
