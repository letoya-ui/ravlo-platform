"""Regression tests for normalize_mashvisor_validation() reading the real
Mashvisor Lookup response field names.

The code previously only looked for "rental_income"/"daily_rate"-style keys
at the top level of the lookup response's "content". Mashvisor's own docs
and a third-party connector both show the real field names are
"median_rental_income" and "median_night_rate", and that "content" groups
results by bed/bath configuration rather than being a flat object -- so a
field can be one level deeper than the code was looking.
"""
from LoanMVP.services.mashvisor_service import normalize_mashvisor_validation


def test_reads_median_rental_income_and_median_night_rate_at_top_level():
    result = {
        "lookup": {
            "content": {
                "median_rental_income": 3200,
                "median_night_rate": 165,
                "median_occupancy": 71,
            }
        }
    }

    normalized = normalize_mashvisor_validation(result)

    assert normalized["airbnb_revenue"] == 3200
    assert normalized["adr"] == 165
    assert normalized["occupancy_rate"] == 71


def test_reads_fields_nested_one_level_under_bed_bath_subgroups():
    # Mashvisor's real response groups results by bed/bath configuration,
    # e.g. content -> {"2bed2bath": {...}, "studio": {...}}, so the fields
    # aren't always top-level on "content" itself.
    result = {
        "lookup": {
            "content": {
                "2bed2bath": {
                    "median_rental_income": 4100,
                    "median_night_rate": 210,
                },
            }
        }
    }

    normalized = normalize_mashvisor_validation(result)

    assert normalized["airbnb_revenue"] == 4100
    assert normalized["adr"] == 210


def test_still_falls_back_to_legacy_field_names():
    result = {
        "lookup": {
            "content": {
                "rental_income": 2900,
                "daily_rate": 140,
            }
        }
    }

    normalized = normalize_mashvisor_validation(result)

    assert normalized["airbnb_revenue"] == 2900
    assert normalized["adr"] == 140


def test_returns_none_for_empty_or_unparseable_lookup():
    assert normalize_mashvisor_validation({})["airbnb_revenue"] is None
    assert normalize_mashvisor_validation({"lookup": {"content": {}}})["airbnb_revenue"] is None
