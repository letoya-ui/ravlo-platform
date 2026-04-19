"""
CostObservation — real, attributed rehab/new-build cost data.

Every row is one data point Ravlo can learn from. Rows come from:
  * investors entering / saving a deal with a concrete rehab cost
  * contractors submitting a bid or line-item budget
  * a deal closing / funding (highest confidence, real spend)
  * optional manual admin seeding for high-trust markets

The cost index blends the static RSMeans seed table with a weighted
average of observations for the same ZIP/state/category, shrinking toward
the seed when observations are sparse and toward the observed mean as
data accumulates.

This table is append-only (no in-place edits). Corrections should be
appended as a new row with ``status='corrected'`` pointing at the prior
row via ``supersedes_id``.
"""

from datetime import datetime

from LoanMVP.extensions import db


# High-level categorization so a "rehab" observation in Hudson Valley
# doesn't pollute the "new_build" multiplier for the same ZIP.
CATEGORY_REHAB = "rehab"
CATEGORY_NEW_BUILD = "new_build"

# Rehab-scope buckets (matches rehab_service).
SCOPE_LIGHT = "light"
SCOPE_MEDIUM = "medium"
SCOPE_HEAVY = "heavy"
SCOPE_LUXURY = "luxury"

# Source trust weights — baseline confidence when no other signal is present.
SOURCE_CONFIDENCE = {
    "admin_seed":     0.40,
    "investor_input": 0.50,
    "contractor_bid": 0.70,
    "closed_deal":    1.00,
}


class CostObservation(db.Model):
    __tablename__ = "cost_observations"

    id = db.Column(db.Integer, primary_key=True)

    # Provenance
    source          = db.Column(db.String(32), nullable=False, index=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    deal_id         = db.Column(db.Integer, db.ForeignKey("deals.id"),  nullable=True, index=True)
    partner_id      = db.Column(db.Integer, db.ForeignKey("partners.id"), nullable=True, index=True)

    # Location
    zip_code        = db.Column(db.String(10), nullable=True, index=True)
    zip3            = db.Column(db.String(3),  nullable=True, index=True)
    state           = db.Column(db.String(2),  nullable=True, index=True)
    city            = db.Column(db.String(120), nullable=True)

    # What was measured
    category        = db.Column(db.String(16), nullable=False, index=True)   # rehab | new_build
    asset_type      = db.Column(db.String(32), nullable=True)                # single_family | multi_family | land | ...
    scope           = db.Column(db.String(16), nullable=True, index=True)    # light | medium | heavy | luxury (rehab only)

    sqft            = db.Column(db.Float,   nullable=True)
    total_cost      = db.Column(db.Float,   nullable=True)
    cost_per_sqft   = db.Column(db.Float,   nullable=True, index=True)

    # Trust + lifecycle
    confidence      = db.Column(db.Float,   nullable=False, default=0.5)   # 0..1 weight in the blend
    status          = db.Column(db.String(16), nullable=False, default="verified", index=True)
    supersedes_id   = db.Column(db.Integer, db.ForeignKey("cost_observations.id"), nullable=True)
    notes           = db.Column(db.Text,    nullable=True)

    created_at      = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user    = db.relationship("User",   backref=db.backref("cost_observations", lazy="dynamic"))
    deal    = db.relationship("Deal",   backref=db.backref("cost_observations", lazy="dynamic"))
    partner = db.relationship("Partner",backref=db.backref("cost_observations", lazy="dynamic"))

    __table_args__ = (
        db.Index("ix_cost_obs_zip3_category", "zip3", "category"),
        db.Index("ix_cost_obs_state_category", "state", "category"),
        db.Index("ix_cost_obs_zip3_category_scope", "zip3", "category", "scope"),
    )

    def __repr__(self):
        return (
            f"<CostObservation id={self.id} src={self.source} "
            f"zip3={self.zip3} cat={self.category} scope={self.scope} "
            f"cpsf={self.cost_per_sqft}>"
        )
