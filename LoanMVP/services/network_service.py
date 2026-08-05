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


def get_or_create_group(slug: str, name: str = "", description: str = "") -> NetworkGroup:
    group = NetworkGroup.query.filter_by(slug=slug).first()
    if group:
        return group

    group = NetworkGroup(slug=slug, name=name or slug.replace("-", " ").title(), description=description or None)
    db.session.add(group)
    db.session.commit()
    return group
