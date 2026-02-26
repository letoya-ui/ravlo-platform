def calculate_progress(loan):
    """
    Returns (percent, stage_text)
    """
    score = 0

    borrower = loan.borrower_profile

    # 0 → 20% | Borrower 1003 started
    if borrower.full_name and borrower.address and borrower.income:
        score += 20
        stage = "1003 Completed"
    else:
        return 10, "Application Started"

    # 20 → 40% | Documents Uploaded
    if loan.loan_documents and len(loan.loan_documents) >= 4:
        score += 20
        stage = "Documents Submitted"
    else:
        return score, "Awaiting Documents"

    # 40 → 60% | eSign Completed
    if borrower.esign_documents and all(d.status == "Signed" for d in borrower.esign_documents):
        score += 20
        stage = "Disclosures Signed"
    else:
        return score, "eSign Required"

    # 60 → 70% | Conditions Cleared
    if loan.underwriting_conditions:
        open_conditions = [c for c in loan.underwriting_conditions if c.status != "Cleared"]
        if len(open_conditions) == 0:
            score += 10
            stage = "Conditions Cleared"
        else:
            return score, "Conditions Pending"

    # 70 → 90% | Appraisal Received
    if loan.property and loan.property.value:
        score += 20
        stage = "Appraisal Completed"
    else:
        return score, "Appraisal In Progress"

    # 90 → 100% | Final UW Approval
    if loan.status.lower() in ["approved", "clear_to_close"]:
        score = 100
        stage = "Clear to Close"

    return score, stage
