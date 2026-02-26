# LoanMVP/services/ai_insights.py
from LoanMVP.ai.base_ai import AIAssistant

assistant = AIAssistant()

def generate_ai_insights(mode, results, comps):
    return assistant.generate_reply(
        f"Provide insights for a {mode} strategy with results: {results} and comps: {list(comps.keys())}.",
        "deal_workspace_insights",
    )
