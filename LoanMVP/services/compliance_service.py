"""ECOA / Regulation B adverse-action notice generation.

NOTE: the boilerplate notice text below follows the shape of Regulation B's
model notice (Appendix C, Form C-1) for a business-credit denial, adapted
for Ravlo's business-purpose real estate lending. This is not legal advice
-- have counsel review and, if needed, customize the notice language (in
particular the "federal agency" paragraph, which must name the actual
regulator applicable to each lending company) before relying on it for
real compliance.
"""
from datetime import datetime
from markupsafe import escape

from LoanMVP.extensions import db

# Statuses that constitute a final "adverse action" under ECOA/Reg B.
# "Suspended" is a request for more information, not a final credit
# decision, so it does not trigger a notice.
ADVERSE_ACTION_STATUSES = {"declined", "denied", "rejected"}

_DEFAULT_REGULATOR_NOTICE = (
    "The federal agency that administers compliance with this law concerning "
    "this creditor is the Federal Trade Commission, Consumer Response Center, "
    "600 Pennsylvania Avenue NW, Washington, DC 20580."
)

_ECOA_NOTICE_HTML = (
    "<p><strong>NOTICE:</strong> The Federal Equal Credit Opportunity Act "
    "prohibits creditors from discriminating against credit applicants on "
    "the basis of race, color, religion, national origin, sex, marital "
    "status, age (provided the applicant has the capacity to enter into a "
    "binding contract); because all or part of the applicant's income "
    "derives from any public assistance program; or because the applicant "
    "has in good faith exercised any right under the Consumer Credit "
    "Protection Act.</p>"
    f"<p>{_DEFAULT_REGULATOR_NOTICE}</p>"
)


def _build_notice_html(loan, reasons: str) -> str:
    borrower_name = escape(loan.borrower_profile.full_name) if loan.borrower_profile and loan.borrower_profile.full_name else "Applicant"
    reasons_html = (
        f"<p><strong>Reason(s) for this decision:</strong> {escape(reasons)}</p>"
        if reasons
        else (
            "<p>You have the right to request the specific reasons for this "
            "decision. To do so, contact your loan officer within 60 days of "
            "this notice.</p>"
        )
    )
    return (
        f"<div class=\"adverse-action-notice\">"
        f"<p>Dear {borrower_name},</p>"
        f"<p>Thank you for your loan application. After careful review, we are "
        f"unable to approve your request for credit at this time.</p>"
        f"{reasons_html}"
        f"{_ECOA_NOTICE_HTML}"
        f"</div>"
    )


def generate_adverse_action_notice(loan):
    """Create and (best-effort) email an adverse-action notice for a declined loan.

    Idempotent per loan -- calling this again for a loan that already has a
    notice just returns the existing one rather than sending a duplicate.
    """
    from LoanMVP.models.loan_models import AdverseActionNotice

    existing = AdverseActionNotice.query.filter_by(loan_id=loan.id).first()
    if existing:
        return existing

    reasons = (loan.decision_notes or "").strip()
    notice_html = _build_notice_html(loan, reasons)

    notice = AdverseActionNotice(
        loan_id=loan.id,
        borrower_profile_id=loan.borrower_profile_id,
        company_id=loan.company_id,
        reasons=reasons or None,
        notice_html=notice_html,
        created_at=datetime.utcnow(),
    )
    db.session.add(notice)
    db.session.commit()

    borrower = loan.borrower_profile
    if borrower and borrower.email:
        try:
            from LoanMVP.utils.emailer import send_email
            send_email(
                borrower.email,
                "Important Notice About Your Loan Application",
                notice_html,
            )
            notice.email_sent = True
            db.session.commit()
        except Exception:
            # Never let a notification failure block the credit decision
            # itself -- the notice record above is the compliance artifact
            # of record regardless of whether the email actually sent.
            db.session.rollback()
            notice = AdverseActionNotice.query.filter_by(loan_id=loan.id).first()

    return notice
