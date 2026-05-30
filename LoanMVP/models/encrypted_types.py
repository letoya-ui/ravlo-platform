import os
import base64
from sqlalchemy import types


def _derive_fernet_key() -> bytes:
    """Return a valid 32-byte URL-safe base64 Fernet key from env vars."""
    raw = os.environ.get("SSN_ENCRYPTION_KEY") or os.environ.get("SECRET_KEY", "")
    if not raw:
        raise RuntimeError(
            "SSN_ENCRYPTION_KEY (or SECRET_KEY) must be set to enable SSN encryption"
        )
    # If it's already a valid Fernet key (44 url-safe base64 chars), use it directly.
    raw_bytes = raw.encode()
    try:
        decoded = base64.urlsafe_b64decode(raw_bytes + b"==")
        if len(decoded) == 32:
            return raw_bytes
    except Exception:
        pass
    # Derive 32 bytes via SHA-256 then re-encode for Fernet.
    from hashlib import sha256
    derived = sha256(raw_bytes).digest()
    return base64.urlsafe_b64encode(derived)


class EncryptedString(types.TypeDecorator):
    """SQLAlchemy column type that stores values as Fernet-encrypted text."""
    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        from cryptography.fernet import Fernet
        f = Fernet(_derive_fernet_key())
        return f.encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        from cryptography.fernet import Fernet, InvalidToken
        f = Fernet(_derive_fernet_key())
        try:
            return f.decrypt(value.encode()).decode()
        except (InvalidToken, Exception):
            # Value may be legacy plaintext; return as-is so the app stays up
            # during the migration window. Log but don't crash.
            return value
