def get_dashboard_snapshots(user_id):
    return {
        "workspace": get_latest_workspace(user_id),
        "concept": get_latest_concept(user_id),
        "rehab": get_latest_rehab(user_id),
        "finder": get_latest_finder(user_id),
        "saved": get_latest_saved_property(user_id),
        "reveal": get_latest_reveal(user_id),
    }
