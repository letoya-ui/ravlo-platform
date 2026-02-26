def build_borrower_timeline(borrower, loan, conditions):
    timeline = []

    # Loan created
    if loan and loan.created_at:
        timeline.append({
            "timestamp": loan.created_at,
            "type": "loan_created",
            "text": f"Loan application created for {loan.property_address or 'your property'}."
        })

    # Conditions added
    for cond in conditions:
        timeline.append({
            "timestamp": cond.created_at,
            "type": "condition_added",
            "text": f"Condition added: {cond.description}"
        })

        # If borrower uploaded a file
        if cond.file_path:
            timeline.append({
                "timestamp": cond.updated_at or cond.created_at,
                "type": "condition_uploaded",
                "text": f"You uploaded a file for: {cond.description}"
            })

        # If condition cleared
        if cond.status.lower() == "cleared":
            timeline.append({
                "timestamp": cond.updated_at or cond.created_at,
                "type": "condition_cleared",
                "text": f"Condition cleared: {cond.description}"
            })

    # Sort by time
    timeline.sort(key=lambda x: x["timestamp"], reverse=True)

    return timeline
