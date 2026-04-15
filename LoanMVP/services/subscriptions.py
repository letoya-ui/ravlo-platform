from LoanMVP.models.user_model import User
from flask import current_app

def sync_features_with_subscription(user_id):
    from LoanMVP.models import User
    from LoanMVP.extensions import db

    user = User.query.get(user_id)
    if not user:
        return

    # Always define feature_map FIRST
    feature_map = {
        "free": {
            "feature_a": False,
            "feature_b": False,
            "feature_c": False,
        },
        "core": {
            "feature_a": True,
            "feature_b": False,
            "feature_c": False,
        },
        "pro": {
            "feature_a": True,
            "feature_b": True,
            "feature_c": False,
        },
        "enterprise": {
            "feature_a": True,
            "feature_b": True,
            "feature_c": True,
        },
    }

    # Beta bypass: unlock feature flags while early-access testing is active.
    if (
        current_app.config.get("BETA_SUBSCRIPTION_BYPASS", False)
        and not current_app.config.get("STRIPE_BILLING_ENABLED", False)
    ):
        for feature in feature_map["enterprise"].keys():
            setattr(user, feature, True)
        user.subscription = user.subscription or "beta"
        db.session.commit()
        return

    # Normalize tier
    tier = user.subscription or "free"

    # Safety fallback
    if tier not in feature_map:
        tier = "free"

    # Apply features
    for feature, value in feature_map[tier].items():
        setattr(user, feature, value)

    db.session.commit()
