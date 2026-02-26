from utils.doc_detector import detect_documents

# ===============================================================
#   CALL TRANSCRIPT STREAMING
# ===============================================================
@socketio.on("call_transcript")
def handle_call_transcript(data):
    borrower_id = data.get("borrower_id")
    speaker = data.get("speaker")
    text = data.get("text")

    # Broadcast transcript to UI
    emit("call_transcript", data, broadcast=False)

    # AI coaching
    advice = master_ai.call_coach(
        text=text,
        speaker=speaker,
        borrower_id=borrower_id
    )

    emit("ai_call_coach", {"advice": advice}, broadcast=False)


# ===============================================================
#   CALL END — FULL SUMMARY
# ===============================================================
@socketio.on("call_end")
def handle_call_end(data):
    borrower_id = data.get("borrower_id")
    transcript = session.get("latest_transcript", "")

    summary = master_ai.summarize_call(borrower_id, transcript)

    emit("ai_call_coach", {"advice": summary})


# ===============================================================
#   CALL STREAM — LIVE SENTIMENT + DOCS + OBJECTIONS
# ===============================================================
@socketio.on("call_stream")
def handle_call_stream(data):
    text = data.get("text", "")
    borrower_id = data.get("borrower_id")

    # 1 — Sentiment
    sentiment = analyze_sentiment(text)

    # 2 — Document detection
    detected_docs = detect_documents(text)
    if detected_docs:
        emit("doc_popup", {
            "docs": detected_docs,
            "borrower_id": borrower_id,
            "original_text": text
        }, broadcast=True)

    # 3 — Call Coaching
    coaching = master_ai.ask(
        f"The borrower said: {text}\n"
        f"Sentiment: {sentiment}\n"
        f"Give the LO one-sentence coaching.",
        role="loan_officer"
    )

    # 4 — Objection detection
    objection = detect_objection(text)
    if objection:
        objection_response = master_ai.ask(f"""
Borrower objection detected: {objection}
Borrower said: "{text}"

Write:
1. SAY_THIS: (2–4 sentence answer)
2. STRATEGY:
3. FOLLOW_UP_QUESTION:
4. OPTIONAL_SMS:
5. OPTIONAL_EMAIL:
Tone: luxury, calm, professional.
""", role="loan_officer")

        emit("objection_handler", {
            "response": objection_response,
            "objection_type": objection
        })

    # 5 — Emit updates
    emit("sentiment_update", {"sentiment": sentiment})
    emit("ai_call_coach", {"advice": coaching})


# ===============================================================
#   LIVE PRICING
# ===============================================================
@socketio.on("price_request")
def handle_price_request(data):
    borrower_id = data.get("borrower_id")
    borrower = BorrowerProfile.query.get(borrower_id)
    loan = LoanApplication.query.filter_by(
        borrower_profile_id=borrower.id
    ).first()
    credit = borrower.credit_reports[-1] if borrower.credit_reports else None

    rate = estimate_rate(
        credit.credit_score,
        loan.amount / loan.property_value,
        loan.loan_type
    )
    payment = calc_payment(loan.amount, rate)

    emit("live_pricing", {"rate": rate, "payment": payment})
