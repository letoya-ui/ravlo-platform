# LoanMVP/ai/cm_ai.py
import os
from openai import OpenAI

# FIX: Proper client initialization
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class CaughmanMasonAI:
    """
    Global AI with the official CAUGHMAN MASON Signature Tone.
    Used across ALL dashboards: Borrower, LO, Processor, UW, CRM, Exec.
    """

    BRAND_TONE = """
You are the CAUGHMAN MASON Intelligence Engine.

Speak with:

• Luxury private-advisor energy  
• Calm authority  
• High-competence financial expertise  
• Precision, clarity, and confidence  
• Emotionally intelligent guidance  
• Professional elegance — never casual, never rushed  

Avoid filler. Avoid slang.  
Your job is to elevate clarity, reduce anxiety, and deliver strategic insight.

Always respond with:
- Clear structure
- Strategic framing
- Subtle reassurance
- High-end service tone
- Premium vocabulary
"""

    def ask(self, prompt: str, role: str = "general"):
        """
        Generate an AI response using the CM Signature Tone.
        """

        final_prompt = f"""
{self.BRAND_TONE}

Context role: {role}

User request:
{prompt}

Provide an elevated, precise, structured response.
"""

        reply = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": self.BRAND_TONE},
                {"role": "user", "content": final_prompt},
            ],
            max_tokens=500,
            temperature=0.6,
        )

        return reply.choices[0].message["content"].strip()


# 🔥 GLOBAL SINGLETON INSTANCE
cm_ai = CaughmanMasonAI()
