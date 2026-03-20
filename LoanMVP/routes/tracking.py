from flask import Blueprint, Response, request
from LoanMVP.extensions import db
from LoanMVP.models.loan_models import DocumentEvent

tracking_bp = Blueprint("tracking", __name__, url_prefix="/track")

@tracking_bp.route("/pixel")
def pixel():
    loan_id = request.args.get("loan_id")
    borrower_id = request.args.get("borrower_id")
    doc_name = request.args.get("doc", "Pre-Approval Letter")

    # Save event
    event = DocumentEvent(
        loan_id=loan_id,
        borrower_id=borrower_id,
        document_name=doc_name,
        event_type="opened",
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.remote_addr
    )

    db.session.add(event)
    db.session.commit()

    # Return 1x1 transparent gif pixel
    gif = (
        b"GIF89a\x01\x00\x01\x00\xf0\x00\x00\x00\x00\x00"
        b"\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00"
        b"\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    )

    return Response(gif, mimetype="image/gif")
