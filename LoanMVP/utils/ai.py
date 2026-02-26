import random
import textwrap

class LoanMVPAI:
    def __init__(self):
        self.greetings = [
            'Hello! How can I assist with your loan today?',
            'Hi there! Need help with rates or loan progress?',
            'Welcome back to LoanMVP AI Assistant!'
        ]

    # === Quote Generator ===
    def generate_quote(self, loan_type, amount):
        base_rate = 6.5 if loan_type.lower() == 'residential' else 7.2
        variance = random.uniform(-0.3, 0.4)
        rate = round(base_rate + variance, 2)
        term = random.choice([15, 20, 30])
        monthly = round((amount * (rate / 100) / 12), 2)
        return {
            'loan_type': loan_type,
            'amount': amount,
            'rate': rate,
            'term': term,
            'monthly_payment': monthly
        }

    # === Conversational Chat ===
    def chat(self, message):
        keywords = {
            'quote': 'Would you like me to generate a sample quote?',
            'loan': 'We currently offer both commercial and residential products.',
            'status': 'You can view your current loan status on your dashboard.',
            'hello': random.choice(self.greetings)
        }
        for key, reply in keywords.items():
            if key in message.lower():
                return reply
        return 'I can help you with loan quotes, progress updates, or lender information.'

    # === Borrower Summary (for AI Intake) ===
    def summarize_borrower(self, borrower_data):
        """
        Generate a simple natural language summary from borrower profile data.
        Used in /ai-intake and /ai-intake-queue routes.
        """
        try:
            # Split out fields
            lines = [l.strip() for l in borrower_data.split('\n') if l.strip()]
            data = {}
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    data[key.strip()] = value.strip()

            name = data.get("Name", "Borrower")
            credit_score = data.get("Credit Score", "N/A")
            income = data.get("Income", "N/A")
            delinq = data.get("Delinquencies", "N/A")
            interactions = data.get("Recent Interactions", "[]")

            # Craft an AI-style summary
            summary = textwrap.dedent(f"""
                📋 **AI Borrower Summary**
                Borrower **{name}** currently has a credit score of **{credit_score}** and reported income of **{income}**.
                Past delinquencies: **{delinq}**.
                Recent interactions suggest interest in continuing or expanding loan discussions.
                The borrower appears to be a potential candidate for pre-qualification or a follow-up consultation.
                ---
                🧠 Insights:
                - Monitor credit stability and verify income sources.
                - Recommend checking the loan-to-value (LTV) before pre-approval.
                - If residential: consider a {random.choice([15, 20, 30])}-year term range.
            """).strip()

            return summary
        except Exception as e:
            return f"⚠️ Unable to summarize borrower data. Error: {str(e)}"
