def detect_documents(text):
    text = text.lower()
    docs = []

    rules = {
        "paystub": ["paystub", "pay stub", "paycheck", "stub"],
        "w2": ["w2", "w-2"],
        "bank_statement": ["bank statement", "bank statements", "checking", "savings"],
        "id": ["id", "identification", "driver", "license", "state id"],
        "tax_return": ["tax return", "taxes", "1040", "schedule"],
        "insurance": ["insurance", "home insurance", "mortgage insurance"],
        "employment_letter": ["employment letter", "verification", "voe"],
        "lease": ["lease", "rental agreement"],
    }

    for doc_type, triggers in rules.items():
        if any(t in text for t in triggers):
            docs.append(doc_type)

    return docs
