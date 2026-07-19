"""White Label branding -- the visible product behind the Enterprise/
"white_label" pricing tier (see LoanMVP/services/ae_pricing.py's add-ons
and the Quote Worksheet's Branding field). A licensed company's own name,
logo mark, color palette, and tagline replace Ravlo's in the sidebar;
everyone else always sees Ravlo, regardless of what a Company row happens
to have stored, so this never leaks the paid feature to a standard-tier
company.
"""
from collections import namedtuple

RAVLO_BRAND_NAME = "Ravlo"
RAVLO_BRAND_MARK = "RV"
RAVLO_BRAND_PRIMARY = "#7ab8ff"
RAVLO_BRAND_ACCENT = "#3e5a75"

Brand = namedtuple("Brand", ["name", "mark", "primary", "accent", "tagline"])

_RAVLO_BRAND = Brand(
    name=RAVLO_BRAND_NAME,
    mark=RAVLO_BRAND_MARK,
    primary=RAVLO_BRAND_PRIMARY,
    accent=RAVLO_BRAND_ACCENT,
    tagline=None,
)


def effective_brand(company):
    """Returns a Brand(name, mark, primary, accent, tagline) for the sidebar.

    Only a company on the white_label subscription tier with a brand_name
    actually set gets its own branding; every other case (no company,
    wrong tier, tier set but never configured) falls back to Ravlo's own
    branding, including its default color palette.
    """
    if company and company.subscription_tier == "white_label" and company.brand_name:
        name = company.brand_name
        mark = company.brand_logo_initials or "".join(word[0] for word in name.split()[:2])
        return Brand(
            name=name,
            mark=mark.upper()[:3],
            primary=company.brand_primary_color or RAVLO_BRAND_PRIMARY,
            accent=company.brand_accent_color or RAVLO_BRAND_ACCENT,
            tagline=company.brand_tagline,
        )
    return _RAVLO_BRAND
