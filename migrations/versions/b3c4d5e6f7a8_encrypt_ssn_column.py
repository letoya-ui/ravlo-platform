"""encrypt ssn column to text for Fernet storage

Revision ID: b3c4d5e6f7a8
Revises: f80fae86417f
Create Date: 2026-05-29

"""
from alembic import op
import sqlalchemy as sa


revision = 'b3c4d5e6f7a8'
down_revision = 'f80fae86417f'
branch_labels = None
depends_on = None


def upgrade():
    # Widen the column so it can hold Fernet-encrypted ciphertext (~100+ chars).
    with op.batch_alter_table('borrower_profile', schema=None) as batch_op:
        batch_op.alter_column(
            'ssn',
            existing_type=sa.String(length=20),
            type_=sa.Text(),
            existing_nullable=True,
        )
    # Encrypt any existing plaintext SSNs.
    _encrypt_existing_ssns()


def downgrade():
    with op.batch_alter_table('borrower_profile', schema=None) as batch_op:
        batch_op.alter_column(
            'ssn',
            existing_type=sa.Text(),
            type_=sa.String(length=20),
            existing_nullable=True,
        )


def _encrypt_existing_ssns():
    """Encrypt rows where ssn does not look like a Fernet token."""
    import os, base64
    from hashlib import sha256
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return

    raw = os.environ.get("SSN_ENCRYPTION_KEY") or os.environ.get("SECRET_KEY", "")
    if not raw:
        return
    raw_bytes = raw.encode()
    try:
        decoded = base64.urlsafe_b64decode(raw_bytes + b"==")
        key = raw_bytes if len(decoded) == 32 else base64.urlsafe_b64encode(sha256(raw_bytes).digest())
    except Exception:
        key = base64.urlsafe_b64encode(sha256(raw_bytes).digest())

    f = Fernet(key)
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, ssn FROM borrower_profile WHERE ssn IS NOT NULL")).fetchall()
    for row in rows:
        ssn_val = row[1]
        if ssn_val and not ssn_val.startswith('gAA'):  # Fernet tokens start with gAA
            encrypted = f.encrypt(ssn_val.encode()).decode()
            conn.execute(
                sa.text("UPDATE borrower_profile SET ssn = :enc WHERE id = :id"),
                {"enc": encrypted, "id": row[0]}
            )
