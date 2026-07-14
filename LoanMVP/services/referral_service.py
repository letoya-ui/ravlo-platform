import secrets
import string

from LoanMVP.extensions import db
from LoanMVP.models.referral_models import Referral
from LoanMVP.models.user_model import User

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8


def _generate_referral_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


def get_or_create_referral_code(user: User) -> str:
    """Return a user's personal referral code, generating one on first use."""
    if user.referral_code:
        return user.referral_code

    for _ in range(5):
        candidate = _generate_referral_code()
        if not User.query.filter_by(referral_code=candidate).first():
            user.referral_code = candidate
            db.session.commit()
            return candidate

    # Astronomically unlikely fallback: widen with the user's own id.
    candidate = f"{_generate_referral_code()[:6]}{user.id}"
    user.referral_code = candidate
    db.session.commit()
    return candidate


def find_referrer_by_code(code: str):
    if not code:
        return None
    return User.query.filter_by(referral_code=code.strip().upper()).first()


def record_referral_signup(new_user: User, code: str):
    """Attribute a brand-new signup to the referrer who owns `code`, if any.

    Safe to call with a missing/invalid code or a self-referral attempt --
    both are treated as a no-op rather than an error.
    """
    referrer = find_referrer_by_code(code)
    if not referrer or referrer.id == new_user.id:
        return None

    already_recorded = Referral.query.filter_by(referred_user_id=new_user.id).first()
    if already_recorded:
        return already_recorded

    referral = Referral(
        referrer_user_id=referrer.id,
        referred_user_id=new_user.id,
        referral_code=referrer.referral_code,
        referred_email=new_user.email,
        status="signed_up",
    )
    db.session.add(referral)
    db.session.commit()
    return referral
