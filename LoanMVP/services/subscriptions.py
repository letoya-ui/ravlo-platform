def sync_features_with_subscription(user_id):
    user = User.query.get(user_id)
    tier = user.subscription_tier  # "free", "featured", "premium"

    feature_map = {
        "free": {
            "crm": True,
            "deal_visibility": False,
            "proposal_builder": False,
            "instant_quote": False,
            "ai_assist": False,
            "priority_placement": False,
            "smart_notifications": False,
            "portfolio_showcase": False
        },
        "featured": {
            "crm": True,
            "deal_visibility": True,
            "proposal_builder": True,
            "instant_quote": False,
            "ai_assist": False,
            "priority_placement": False,
            "smart_notifications": False,
            "portfolio_showcase": False
        },
        "premium": {
            "crm": True,
            "deal_visibility": True,
            "proposal_builder": True,
            "instant_quote": True,
            "ai_assist": True,
            "priority_placement": True,
            "smart_notifications": True,
            "portfolio_showcase": True
        }
    }

    for feature, value in feature_map[tier].items():
        setattr(user, feature, value)

    db.session.commit()
