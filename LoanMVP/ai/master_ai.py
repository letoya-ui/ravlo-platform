# =====================================================
# CM LOANS — ADAPTIVE AI ENGINE (Hybrid Luxury + Fintech)
# =====================================================

import re
from LoanMVP.ai.base_ai import AIAssistant
from LoanMVP.models.loan_models import LoanApplication, BorrowerProfile


class CMAIEngine:
    """
    Master AI routing engine for CM Loans.
    Adaptive tone, sentiment, and role-awareness.
    """

    def __init__(self):
        self.ai = AIAssistant()

    # -------------------------------------------------
    # 🔍 SENTIMENT DETECTOR
    # -------------------------------------------------
    def detect_sentiment(self, text):
        text = text.lower()

        if any(w in text for w in ["confused", "stuck", "don't understand", "worried", "help"]):
            return "nervous"

        if any(w in text for w in ["angry", "upset", "frustrated"]):
            return "frustrated"

        if any(w in text for w in ["great", "thanks", "perfect", "awesome"]):
            return "positive"

        return "neutral"

    # -------------------------------------------------
    # 🎯 INTENT DETECTOR
    # -------------------------------------------------
    def detect_intent(self, text):
        text = text.lower()

        if any(k in text for k in ["quote", "rate", "ltv", "monthly payment", "approval"]):
            return "loan_quote"

        if any(k in text for k in ["conditions", "approve", "risk", "guideline", "uw"]):
            return "underwriting"

        if any(k in text for k in ["doc", "upload", "missing", "processor"]):
            return "processor"

        if any(k in text for k in ["pipeline", "kpi", "trend", "overview"]):
            return "executive"

        if any(k in text for k in ["search", "borrower", "lookup", "profile"]):
            return "crm"

        return "general"

    # -------------------------------------------------
    # 🎭 ROLE-BASED TONES
    # -------------------------------------------------
    def tone_borrower(self, sentiment, intent):
        if sentiment in ["nervous", "frustrated"]:
            return (
                "Use a calm, reassuring concierge tone. "
                "Focus on comfort, clarity, and step-by-step guidance."
            )

        if intent == "loan_quote":
            return (
                "Respond in a premium quote layout with payment options, "
                "LTV, DTI notes, and next steps. Fintech + luxury style."
            )

        return "Warm, modern fintech tone."

    def tone_loan_officer(self):
        return "Strategic, confident, deal-maker tone."

    def tone_processor(self):
        return "Checklist-driven, organized, concise."

    def tone_underwriter(self):
        return "Technical, analytical, unemotional. Use bullet points."

    def tone_executive(self):
        return "High-level, KPI-driven, concise leadership tone."

    # -------------------------------------------------
    # 🧠 FINAL RESPONSE BUILDER
    # -------------------------------------------------
    def generate(self, message, role="general"):
        sentiment = self.detect_sentiment(message)
        intent = self.detect_intent(message)

        if role == "borrower":
            tone = self.tone_borrower(sentiment, intent)
        elif role == "loan_officer":
            tone = self.tone_loan_officer()
        elif role == "processor":
            tone = self.tone_processor()
        elif role == "underwriter":
            tone = self.tone_underwriter()
        elif role == "executive":
            tone = self.tone_executive()
        else:
            tone = "Modern, professional fintech voice."

        prompt = f"""
You are **CM LOANS AI** — a luxury × fintech hybrid intelligence assistant.

Role: {role}
Sentiment: {sentiment}
Intent: {intent}

Tone Guidelines:
{tone}

Brand Aesthetic:
- Caughman Mason Loan Services
- Black | Silver | Neon Blue
- High-end fintech clarity + luxury elegance

User Message:
\"{message}\"

Respond in CM Loans premium style.
"""

        return self.ai.generate_reply(prompt, role)

    # -------------------------------------------------
    # ☎️ CALL COACH (Loan Officer)
    # -------------------------------------------------
    def call_coach(self, text, speaker, borrower_id):
        borrower = BorrowerProfile.query.get(borrower_id)
        loan = LoanApplication.query.filter_by(
            borrower_profile_id=borrower_id
        ).first()

        prompt = f"""
You are a live AI call coach helping a Loan Officer.

Borrower: {borrower.full_name}
Loan Amount: {loan.amount if loan else 'N/A'}
Property Value: {loan.property_value if loan else 'N/A'}
Income: {borrower.income}
Credit Score: {borrower.credit_reports[-1].credit_score if borrower.credit_reports else 'N/A'}

Latest Caller Line:
{speaker}: {text}

Provide:
- What the Loan Officer should say NEXT (2–3 sentences)
- Any objection handling
- Opportunities for document requests
- Loan structuring or terms if useful
- Rapport-building tip
- 3–5 next-step action items
"""

        return self.ai.generate_reply(prompt, role="loan_officer")

    # -------------------------------------------------
    # 📞 CALL SUMMARY
    # -------------------------------------------------
    def summarize_call(self, borrower_id, transcript):
        borrower = BorrowerProfile.query.get(borrower_id)
        loan = LoanApplication.query.filter_by(
            borrower_profile_id=borrower_id
        ).first()

        prompt = f"""
You are an AI loan assistant. Summarize this borrower call.

Borrower: {borrower.full_name}
Loan Amount: {loan.amount if loan else 'N/A'}
Income: {borrower.income}
Credit Score: {borrower.credit_reports[-1].credit_score if borrower.credit_reports else 'N/A'}

CALL TRANSCRIPT:
{transcript}

Include:
- Borrower goals
- Income insights
- Credit concerns
- Loan program fit
- Required follow-up tasks
- Missing docs
- Red flags
- Next steps
"""

        return self.ai.generate_reply(prompt, role="call_summary")


# =====================================================
# CLEAN MASTER AI INITIALIZER (NO CONTEXTS)
# =====================================================

master_ai = CMAIEngine()

