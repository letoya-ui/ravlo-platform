"""add lo_is_external columns

Revision ID: f80fae86417f
Revises: f18b98c11cad
Create Date: 2026-04-19 14:32:28.389436
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f80fae86417f'
down_revision = 'f18b98c11cad'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    vaa_cols = {c["name"] for c in inspector.get_columns("vip_assistant_actions")} if inspector.has_table("vip_assistant_actions") else set()
    with op.batch_alter_table('vip_assistant_actions', schema=None) as batch_op:
        if "miles" in vaa_cols:
            batch_op.drop_column('miles')
        if "amount" in vaa_cols:
            batch_op.drop_column('amount')
        if "notes" in vaa_cols:
            batch_op.drop_column('notes')

    vas_cols = {c["name"] for c in inspector.get_columns("vip_assistant_suggestions")} if inspector.has_table("vip_assistant_suggestions") else set()
    with op.batch_alter_table('vip_assistant_suggestions', schema=None) as batch_op:
        if "proposed_miles" in vas_cols:
            batch_op.drop_column('proposed_miles')
        if "due_at" in vas_cols:
            batch_op.drop_column('due_at')

    vda_cols = {c["name"] for c in inspector.get_columns("vip_design_annotations")} if inspector.has_table("vip_design_annotations") else set()
    with op.batch_alter_table('vip_design_annotations', schema=None) as batch_op:
        if "updated_at" not in vda_cols:
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    vdp_cols = {c["name"] for c in inspector.get_columns("vip_design_projects")} if inspector.has_table("vip_design_projects") else set()
    with op.batch_alter_table('vip_design_projects', schema=None) as batch_op:
        if "contact_id" not in vdp_cols:
            batch_op.add_column(sa.Column('contact_id', sa.Integer(), nullable=True))
        if "status" not in vdp_cols:
            batch_op.add_column(sa.Column('status', sa.String(length=50), nullable=True))
        if "contact_id" not in vdp_cols:
            try:
                batch_op.create_foreign_key(None, 'vip_contacts', ['contact_id'], ['id'])
            except Exception:
                pass

    op.execute("UPDATE vip_design_projects SET status = 'active' WHERE status IS NULL")

    with op.batch_alter_table('vip_design_projects', schema=None) as batch_op:
        batch_op.alter_column('status', existing_type=sa.String(length=50), nullable=False)

    ve_cols = {c["name"] for c in inspector.get_columns("vip_expenses")} if inspector.has_table("vip_expenses") else set()
    with op.batch_alter_table('vip_expenses', schema=None) as batch_op:
        if "market" not in ve_cols:
            batch_op.add_column(sa.Column('market', sa.String(length=100), nullable=True))

    vi_cols = {c["name"] for c in inspector.get_columns("vip_income")} if inspector.has_table("vip_income") else set()
    with op.batch_alter_table('vip_income', schema=None) as batch_op:
        if "market" not in vi_cols:
            batch_op.add_column(sa.Column('market', sa.String(length=100), nullable=True))

    vp_cols = {c["name"] for c in inspector.get_columns("vip_profiles")} if inspector.has_table("vip_profiles") else set()
    with op.batch_alter_table('vip_profiles', schema=None) as batch_op:
        if "lo_is_external" not in vp_cols:
            batch_op.add_column(sa.Column('lo_is_external', sa.Boolean(), nullable=True))
        if "lo_licensed_residential" not in vp_cols:
            batch_op.add_column(sa.Column('lo_licensed_residential', sa.Boolean(), nullable=True))
        if "lo_company_id" not in vp_cols:
            batch_op.add_column(sa.Column('lo_company_id', sa.Integer(), nullable=True))
        if "lo_license_number" not in vp_cols:
            batch_op.add_column(sa.Column('lo_license_number', sa.String(length=100), nullable=True))
        if "lo_license_state" not in vp_cols:
            batch_op.add_column(sa.Column('lo_license_state', sa.String(length=50), nullable=True))
        if "lo_nmls" not in vp_cols:
            batch_op.add_column(sa.Column('lo_nmls', sa.String(length=50), nullable=True))
        if "lo_company_id" not in vp_cols:
            try:
                batch_op.create_foreign_key(None, 'companies', ['lo_company_id'], ['id'])
            except Exception:
                pass

    op.execute("""
        UPDATE vip_profiles
        SET lo_is_external = false
        WHERE lo_is_external IS NULL
    """)

    op.execute("""
        UPDATE vip_profiles
        SET lo_licensed_residential = false
        WHERE lo_licensed_residential IS NULL
    """)

    with op.batch_alter_table('vip_profiles', schema=None) as batch_op:
        batch_op.alter_column('lo_is_external', existing_type=sa.Boolean(), nullable=False)
        batch_op.alter_column('lo_licensed_residential', existing_type=sa.Boolean(), nullable=False)


def downgrade():
    with op.batch_alter_table('vip_profiles', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('lo_nmls')
        batch_op.drop_column('lo_license_state')
        batch_op.drop_column('lo_license_number')
        batch_op.drop_column('lo_company_id')
        batch_op.drop_column('lo_licensed_residential')
        batch_op.drop_column('lo_is_external')

    with op.batch_alter_table('vip_income', schema=None) as batch_op:
        batch_op.drop_column('market')

    with op.batch_alter_table('vip_expenses', schema=None) as batch_op:
        batch_op.drop_column('market')

    with op.batch_alter_table('vip_design_projects', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('status')
        batch_op.drop_column('contact_id')

    with op.batch_alter_table('vip_design_annotations', schema=None) as batch_op:
        batch_op.drop_column('updated_at')

    with op.batch_alter_table('vip_assistant_suggestions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('due_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('proposed_miles', sa.INTEGER(), autoincrement=False, nullable=True))

    with op.batch_alter_table('vip_assistant_actions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notes', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('amount', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('miles', sa.INTEGER(), autoincrement=False, nullable=True))
