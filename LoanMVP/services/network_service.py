# LoanMVP/services/network_service.py
"""Ravlo Network helpers.

resolve_professional_label() mirrors the owner-resolution pattern in
payments_service.py: VIPProfile (realtor/insurance/contractor/loan
officer/property manager) and StylistProfile (salon) are separate model
trees, so this is the one place that knows how to turn "some User" into
"what kind of professional they are" for a post/comment byline.
"""
from LoanMVP.extensions import db
from LoanMVP.models.network_models import NetworkGroup

_VIP_ROLE_LABELS = {
    "realtor": "Realtor",
    "contractor": "Contractor",
    "contractor_realtor": "Contractor & Realtor",
    "insurance": "Insurance Agent",
    "insurance_realtor": "Insurance Agent & Realtor",
    "loan_officer": "Loan Officer",
    "property_manager": "Property Manager",
}


def resolve_professional_label(user) -> str:
    """Read-only lookup -- unlike payments_service.resolve_current_owner(),
    this never creates a VIPProfile row just to render a byline."""
    from LoanMVP.models.salon_models import StylistProfile
    from LoanMVP.models.vip_models import VIPProfile

    stylist = StylistProfile.query.filter_by(user_id=user.id).first()
    if stylist:
        return "Stylist"

    profile = VIPProfile.query.filter_by(user_id=user.id).first()
    if profile:
        return _VIP_ROLE_LABELS.get(profile.role_type, "Member")

    return "Member"


def _find_stylist_and_vip_profile(user):
    from LoanMVP.models.salon_models import StylistProfile
    from LoanMVP.models.vip_models import VIPProfile

    stylist = StylistProfile.query.filter_by(user_id=user.id).first()
    profile = VIPProfile.query.filter_by(user_id=user.id).first()
    return stylist, profile


def resolve_profile_url(user):
    """Link to a member's existing public profile page, if they have one.

    Reuses the real public-facing pages (public_pages.realtor_landing,
    salon_public.landing) instead of building a second profile system --
    only members without a public_slug fall back to the plain in-network
    profile page (network.professional_profile)."""
    from flask import url_for

    stylist, profile = _find_stylist_and_vip_profile(user)

    if stylist and stylist.public_slug:
        return url_for("salon_public.landing", slug=stylist.public_slug)
    if profile and profile.public_slug:
        return url_for("public_pages.realtor_landing", slug=profile.public_slug)
    return None


def resolve_profile_bio(user):
    """Bio text for the in-network profile page, from whichever profile
    tree the member actually has (if any)."""
    stylist, profile = _find_stylist_and_vip_profile(user)

    if stylist and stylist.bio:
        return stylist.bio
    if profile and profile.bio:
        return profile.bio
    return None


def get_or_create_group(slug: str, name: str = "", description: str = "") -> NetworkGroup:
    group = NetworkGroup.query.filter_by(slug=slug).first()
    if group:
        return group

    group = NetworkGroup(slug=slug, name=name or slug.replace("-", " ").title(), description=description or None)
    db.session.add(group)
    db.session.commit()
    return group
