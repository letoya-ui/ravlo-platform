from LoanMVP.models.user_model import User

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

    # Normalize tier
    tier = user.subscription or "free"

    # Safety fallback
    if tier not in feature_map:
        tier = "free"

    # Apply features
    for feature, value in feature_map[tier].items():
        setattr(user, feature, value)

    db.session.commit()
