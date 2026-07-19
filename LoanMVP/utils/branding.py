"""White Label branding -- the visible product behind the Enterprise/
"white_label" pricing tier (see LoanMVP/services/ae_pricing.py's add-ons
and the Quote Worksheet's Branding field). A licensed company's own name,
logo, color palette, and tagline replace Ravlo's in the sidebar; everyone
else always sees Ravlo, regardless of what a Company row happens to have
stored, so this never leaks the paid feature to a standard-tier company.
"""
from collections import namedtuple

RAVLO_BRAND_NAME = "Ravlo"
RAVLO_BRAND_MARK = "RV"
RAVLO_BRAND_PRIMARY = "#7ab8ff"
RAVLO_BRAND_ACCENT = "#3e5a75"

Brand = namedtuple("Brand", ["name", "mark", "primary", "accent", "tagline", "logo_url"])

_RAVLO_BRAND = Brand(
    name=RAVLO_BRAND_NAME,
    mark=RAVLO_BRAND_MARK,
    primary=RAVLO_BRAND_PRIMARY,
    accent=RAVLO_BRAND_ACCENT,
    tagline=None,
    logo_url=None,
)


def effective_brand(company):
    """Returns a Brand(name, mark, primary, accent, tagline, logo_url) for
    the sidebar.

    Only a company on the white_label subscription tier with a brand_name
    actually set gets its own branding; every other case (no company,
    wrong tier, tier set but never configured) falls back to Ravlo's own
    branding, including its default color palette.

    logo_url, when set, is a static-relative path (e.g.
    "images/demo/meridian_capital_logo.png") to a full logo lockup image
    that the sidebar renders in place of the text name/mark entirely.
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
            logo_url=company.brand_logo_url,
        )
    return _RAVLO_BRAND
