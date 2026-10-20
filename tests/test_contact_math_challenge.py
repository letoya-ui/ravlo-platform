"""The /contact form already had a keyword-denylist spam filter (added
earlier) plus rate limiting, but nothing that catches a plain bot posting
the form directly -- no CAPTCHA-style check at all. Added a lightweight,
zero-dependency "what is X + Y?" challenge: the answer lives in the
server-side session (never in form markup a bot could read), a fresh
question is generated on every GET, and a wrong or missing answer is
rejected before the message is ever saved."""
import re

from LoanMVP.models.admin import BusinessInquiry


def _extract_challenge(body):
    match = re.search(r"what is (\d+) \+ (\d+)\?", body, re.IGNORECASE)
    assert match, "contact page did not render a math challenge"
    return int(match.group(1)), int(match.group(2))


def test_contact_page_shows_a_math_challenge(client):
    resp = client.get("/contact")

    assert resp.status_code == 200
    _extract_challenge(resp.get_data(as_text=True))


def test_contact_rejects_a_wrong_math_answer(db_session, client):
    body = client.get("/contact").get_data(as_text=True)
    a, b = _extract_challenge(body)

    resp = client.post(
        "/contact",
        data={
            "name": "Jamie Prospect",
            "email": "jamie.prospect@example.com",
            "subject": "Question",
            "message": "Tell me more about Lending OS.",
            "math_answer": str(a + b + 1),
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert BusinessInquiry.query.filter_by(email="jamie.prospect@example.com").first() is None


def test_contact_rejects_a_missing_math_answer(db_session, client):
    client.get("/contact")

    resp = client.post(
        "/contact",
        data={
            "name": "Jamie Prospect",
            "email": "jamie.prospect2@example.com",
            "subject": "Question",
            "message": "Tell me more about Lending OS.",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert BusinessInquiry.query.filter_by(email="jamie.prospect2@example.com").first() is None


def test_contact_accepts_a_correct_math_answer(db_session, client):
    body = client.get("/contact").get_data(as_text=True)
    a, b = _extract_challenge(body)

    resp = client.post(
        "/contact",
        data={
            "name": "Jamie Prospect",
            "email": "jamie.prospect3@example.com",
            "subject": "Question",
            "message": "Tell me more about Lending OS.",
            "math_answer": str(a + b),
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    inquiry = BusinessInquiry.query.filter_by(email="jamie.prospect3@example.com").first()
    assert inquiry is not None
    assert inquiry.inquiry_type == "contact"


def test_contact_challenge_answer_cannot_be_reused(db_session, client):
    """The stored answer is popped from the session on first use, so a
    bot that captures one correct (question, answer) pair can't replay
    the same answer against a later request."""
    body = client.get("/contact").get_data(as_text=True)
    a, b = _extract_challenge(body)

    first = client.post(
        "/contact",
        data={
            "name": "Jamie Prospect",
            "email": "jamie.prospect4@example.com",
            "subject": "Question",
            "message": "Tell me more about Lending OS.",
            "math_answer": str(a + b),
        },
        # Not following the redirect here is deliberate: contact()'s GET
        # branch calls _new_math_challenge() and overwrites the session's
        # stored answer with a fresh random one. Following it would
        # occasionally (when the new sum happens to equal a + b) make the
        # replay below pass by coincidence instead of by the bug it's
        # meant to catch.
        follow_redirects=False,
    )
    assert first.status_code == 302
    assert BusinessInquiry.query.filter_by(email="jamie.prospect4@example.com").first() is not None

    replay = client.post(
        "/contact",
        data={
            "name": "Jamie Prospect",
            "email": "jamie.prospect5@example.com",
            "subject": "Question",
            "message": "Tell me more about Lending OS.",
            "math_answer": str(a + b),
        },
        follow_redirects=True,
    )
    assert replay.status_code == 200
    assert BusinessInquiry.query.filter_by(email="jamie.prospect5@example.com").first() is None
