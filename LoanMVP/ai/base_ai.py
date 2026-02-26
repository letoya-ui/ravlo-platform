# =========================================================
# 🧠 Unified AI Assistant – LoanMVP 2025 Architecture
# =========================================================

import os
from openai import OpenAI
from datetime import datetime

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------------------------------------
# Context Map
# ---------------------------------------------------------
ROLE_CONTEXT = {
    "borrower": (
        "You are a helpful AI assistant for borrowers using a loan portal. "
        "Guide them through completing loan applications, uploading documents, "
        "and understanding loan terms clearly and supportively."
    ),
    "loan_officer": (
        "You are an analytical and efficient AI assistant for a loan officer. "
        "Summarize leads, CRM activity, borrower status, and pipeline performance. "
        "Respond concisely, using a business-friendly tone."
    ),
    "processor": (
        "You are a workflow assistant for a loan processor. "
        "Summarize pending loans, document verifications, and underwriting conditions. "
        "Provide next-step recommendations or highlight missing information."
    ),
    "underwriter": (
        "You are a risk-evaluation AI for underwriters. "
        "Review loan files, analyze DSCR, LTV, credit trends, and summarize risk factors. "
        "Offer approval reasoning or flag inconsistencies."
    ),
    "admin": (
        "You are an executive assistant AI for an admin overseeing multiple loan teams. "
        "Provide summarized reports on loans, performance, and compliance health."
    ),
    "property": (
        "You are a property intelligence assistant. "
        "Provide property search insights, valuations, comparable data, and zoning details."
    ),
    "crm": (
        "You are a CRM insight assistant. "
        "Summarize lead activity, response times, and engagement health for sales pipelines."
    ),
    "general": (
        "You are a friendly, general-purpose AI assistant for the LoanMVP system. "
        "Be concise, professional, and actionable."
    ),
}


# ---------------------------------------------------------
# AIAssistant Class
# ---------------------------------------------------------
class AIAssistant:
    """Unified assistant for all roles — contextual replies and summaries."""

    def __init__(self):
        self.client = client
        self.default_model = "gpt-4o-mini"
        self.history = []

    # -----------------------------------------------------
    def generate_reply(self, message: str, role: str = "general") -> str:
        """Generate a contextual AI reply for any role."""
        try:
            print("DEBUG AIAssistant.self.client:", type(self.client), repr(self.client))
            context = ROLE_CONTEXT.get(role, ROLE_CONTEXT["general"])
            response = self.client.chat.completions.create(
                model=self.default_model,
                messages=[
                    {"role": "system", "content": context},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=400,
            )
            reply = response.choices[0].message.content.strip()
            self.history.append({
                "timestamp": datetime.now(),
                "role": role,
                "input": message,
                "output": reply
            })
            return reply
        except Exception as e:
            print(f"⚠️ OpenAI error: {e}")
            return "⚠️ The AI assistant encountered a problem generating a reply."

    # -----------------------------------------------------
    def evaluate_preapproval(self, credit_score, revenue, time_in_business, loan_amount, collateral):
        """Return a preapproval decision, estimated rate, term, and reasoning."""
        prompt = (
            f"Evaluate this borrower for loan preapproval:\n"
            f"- Credit score: {credit_score}\n"
            f"- Annual revenue: ${revenue:,}\n"
            f"- Years in business: {time_in_business}\n"
            f"- Loan amount requested: ${loan_amount:,}\n"
            f"- Collateral: {collateral}\n\n"
            "Return a decision (Preapproved or Not Preapproved), estimated rate, term, and reason."
        )
        return self.generate_reply(prompt, "underwriter")

    # -----------------------------------------------------
    def summarize_workload(self, loans, pending_docs):
        """Quick, human-style summary for dashboards like Processor or Admin."""
        total = len(loans)
        in_review = sum(1 for l in loans if l.status in ["in_review", "under_review"])
        cleared = sum(1 for l in loans if l.status == "cleared")

        prompt = (
            f"You are summarizing workload for a loan processor:\n"
            f"- Total loans: {total}\n"
            f"- In review: {in_review}\n"
            f"- Cleared: {cleared}\n"
            f"- Pending documents: {pending_docs}\n"
            "Give a concise operational summary."
        )
        return self.generate_reply(prompt, "processor")

    # -----------------------------------------------------
    def summarize_leads(self, leads):
        """Summarize CRM leads."""
        active = len([l for l in leads if l.status in ["active", "new"]])
        closed = len([l for l in leads if l.status == "closed"])
        prompt = (
            f"CRM summary request:\nActive leads: {active}\nClosed: {closed}\n"
            "Summarize engagement and follow-up performance."
        )
        return self.generate_reply(prompt, "crm")

    # -----------------------------------------------------
    def summarize_property(self, properties):
        """Summarize property intelligence search results."""
        if not properties:
            return "No property records found."
        avg_value = round(sum(p.value for p in properties if p.value) / len(properties), 2)
        prompt = f"Summarize {len(properties)} properties with an average value of ${avg_value}."
        return self.generate_reply(prompt, "property")

    # -----------------------------------------------------
    def list_memories(self, limit=10):
        """Mock event memory log."""
        events = [
            {"time": "2025-11-06 09:00", "context": "Generated dashboard workload summary."},
            {"time": "2025-11-06 08:45", "context": "Verified document queue update."},
            {"time": "2025-11-06 08:30", "context": "CRM engagement report produced."},
        ]
        return events[:limit]

    # -----------------------------------------------------
    def review_document(self, extracted_text, role="processor"):
        """Summarize key financial insights from a document."""
        prompt = (
            "Review this document and summarize key financial insights for loan processing or underwriting.\n\n"
            f"{extracted_text}"
        )
        return self.generate_reply(prompt, role)

    # -----------------------------------------------------
    def comment_on_budget(self, budget_dict):
        """Review a construction budget and suggest improvements."""
        prompt = (
            "You are a construction budget analyst. Review the following budget and suggest improvements, "
            "missing items, or unrealistic costs.\n\n"
            f"{budget_dict}"
        )
        return self.generate_reply(prompt, "borrower")

    # -----------------------------------------------------
    def recommend_partners(self, borrower_profile):
        """Suggest relevant partners based on borrower profile."""
        prompt = (
            "You are a partner-matching assistant. Based on the borrower's profile, recommend 3 relevant partners "
            "(e.g. contractors, insurers, realtors) who fit their location, loan type, and project scope.\n\n"
            f"{borrower_profile}"
        )
        return self.generate_reply(prompt, "general")

    # -----------------------------------------------------
    def comment_on_timeline(self, loan_status, recent_actions=None):
        """Generate borrower-friendly commentary on loan progress."""
        prompt = (
            f"The borrower’s loan status is: {loan_status}.\n"
            f"Recent actions: {recent_actions or 'None'}\n"
            "Provide a friendly, clear update explaining what this means and what happens next."
        )
        return self.generate_reply(prompt, "borrower")

    # -----------------------------------------------------
    def generate_doc_checklist(self, loan_type, credit_score, time_in_business, collateral=None):
        """Generate a checklist of required documents based on loan type and borrower profile."""
        prompt = (
            f"Generate a checklist of required documents for a loan application.\n"
            f"- Loan type: {loan_type}\n"
            f"- Credit score: {credit_score}\n"
            f"- Years in business: {time_in_business}\n"
            f"- Collateral: {collateral or 'None'}\n\n"
            "Return a list of 5–10 items with short descriptions."
        )
        return self.generate_reply(prompt, "processor")

    # -----------------------------------------------------
    def summarize_partner_activity(self, views, leads, category, location=None):
        """Summarize partner performance and engagement."""
        prompt = (
            f"You are summarizing performance for a {category} partner.\n"
            f"- Profile views this week: {views}\n"
            f"- Leads received: {leads}\n"
            f"- Location: {location or 'N/A'}\n\n"
            "Give a short, encouraging summary with one suggestion to improve visibility or engagement."
        )
        return self.generate_reply(prompt, "general")

    # -----------------------------------------------------
    def chat_with_borrower(self, question, borrower_profile=None):
        """Respond to borrower questions with personalized, helpful guidance."""
        context = (
            "You are a helpful AI assistant for borrowers using a loan portal. "
            "Answer their questions clearly, supportively, and with actionable guidance. "
            "If borrower profile is provided, tailor your response accordingly."
        )

        if borrower_profile:
            question = f"Borrower profile:\n{borrower_profile}\n\nQuestion:\n{question}"

        return self.generate_reply(question, "borrower")

    # -----------------------------------------------------
    def suggest_next_steps(self, question, response, borrower_profile=None):
        """Suggest 1–3 next steps based on the borrower’s question and AI response."""
        prompt = (
            "Based on the borrower's question and the AI assistant's response, suggest 1–3 clear next steps.\n"
            f"Question: {question}\n"
            f"Response: {response}\n"
        )
        if borrower_profile:
            prompt += f"Borrower profile: {borrower_profile}\n"
        prompt += "Return a short list of actionable steps."

        steps = self.generate_reply(prompt, "borrower")

        # Detect if upload actions should be suggested
        upload_trigger = any(
            kw in steps.lower()
            for kw in ["upload", "submit", "income document", "bank statement", "tax return"]
        )

        return steps, upload_trigger
