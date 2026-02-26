from LoanMVP.models.loan_models import DocumentEvent
from datetime import datetime, timedelta

class EngagementEngine:

    def __init__(self, borrower):
        self.borrower = borrower

    def score(self):
        events = self.borrower.doc_events

        score = 0

        # -------------------------
        # EVENT WEIGHTS
        # -------------------------
        WEIGHTS = {
            "opened": 10,        # email opened
            "viewed": 15,        # viewed doc in portal
            "downloaded": 20,    # downloaded doc
            "uploaded": 35,      # borrower uploaded doc
            "condition_cleared": 25,
            "emailed": 5,
            "status_changed": 5,
        }

        # -------------------------
        # TIME DECAY BOOST
        # -------------------------
        now = datetime.utcnow()

        for e in events:
            if e.event_type in WEIGHTS:
                base = WEIGHTS[e.event_type]

                # Recency boost (last 48 hours = hotter)
                hours_ago = (now - e.timestamp).total_seconds() / 3600
                if hours_ago < 6:
                    base *= 1.4
                elif hours_ago < 24:
                    base *= 1.2
                elif hours_ago < 48:
                    base *= 1.05

                score += base

        # Clamp between 0–100
        score = min(100, round(score))

        return score
