"""initial schema

Revision ID: c71d784e3fb3
Revises: 
Create Date: 2026-03-02 22:56:10.351455

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import Text

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'fix_investor_fk_and_ai_conversation'
down_revision = '<PUT_YOUR_PREVIOUS_REVISION_HERE>'
branch_labels = None
depends_on = None


def upgrade():

    # ---------------------------------------------------------
    # 1. FIX INVESTOR PROFILE FOREIGN KEYS
    # ---------------------------------------------------------

    # LoanApplication → InvestorProfile
    with op.batch_alter_table('loan_application') as batch_op:
        batch_op.drop_constraint('fk_loanapp_investor', type_='foreignkey', if_exists=True)
        batch_op.create_foreign_key(
            'fk_loanapp_investor',
            'investor_profile',
            ['investor_profile_id'],
            ['id']
        )

    # ConditionRequest → InvestorProfile
    with op.batch_alter_table('condition_request') as batch_op:
        batch_op.drop_constraint('fk_conditionreq_investor_id', type_='foreignkey', if_exists=True)
        batch_op.create_foreign_key(
            'fk_conditionreq_investor_id',
            'investor_profile',
            ['investor_profile_id'],
            ['id']
        )

    # LoanDocument → InvestorProfile
    with op.batch_alter_table('loan_document') as batch_op:
        batch_op.drop_constraint('fk_loandoc_investor', type_='foreignkey', if_exists=True)
        batch_op.create_foreign_key(
            'fk_loandoc_investor',
            'investor_profile',
            ['investor_profile_id'],
            ['id']
        )

    # UnderwritingCondition → InvestorProfile
    with op.batch_alter_table('underwriting_condition') as batch_op:
        batch_op.drop_constraint('fk_condition_investor', type_='foreignkey', if_exists=True)
        batch_op.create_foreign_key(
            'fk_condition_investor',
            'investor_profile',
            ['investor_profile_id'],
            ['id']
        )

    # ---------------------------------------------------------
    # 2. FIX AI CONVERSATION RENAME (loan_ai_conversations)
    # ---------------------------------------------------------

    # If table was renamed from ai_conversation → loan_ai_conversation
    # or if column was renamed, handle both safely.

    # Rename table if old name exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    tables = inspector.get_table_names()

    if 'ai_conversation' in tables and 'loan_ai_conversation' not in tables:
        op.rename_table('ai_conversation', 'loan_ai_conversation')

    # Fix FK on LoanAIConversation → LoanApplication
    if 'loan_ai_conversation' in tables:
        with op.batch_alter_table('loan_ai_conversation') as batch_op:
            batch_op.drop_constraint('fk_ai_conversation_loan', type_='foreignkey', if_exists=True)
            batch_op.create_foreign_key(
                'fk_ai_conversation_loan',
                'loan_application',
                ['loan_id'],
                ['id']
            )

    op.create_table('chat_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=True),
    sa.Column('user_message', sa.Text(), nullable=False),
    sa.Column('ai_response', sa.Text(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('contractors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('category', sa.String(length=80), nullable=True),
    sa.Column('phone', sa.String(length=30), nullable=True),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('website', sa.String(length=255), nullable=True),
    sa.Column('location', sa.String(length=120), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('approved', sa.Boolean(), nullable=True),
    sa.Column('featured', sa.Boolean(), nullable=True),
    sa.Column('date_joined', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('deal_shares',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_user_id', sa.Integer(), nullable=False),
    sa.Column('loan_officer_user_id', sa.Integer(), nullable=True),
    sa.Column('property_id', sa.String(length=120), nullable=True),
    sa.Column('strategy', sa.String(length=32), nullable=True),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.Column('results_json', sa.JSON(), nullable=True),
    sa.Column('comps_json', sa.JSON(), nullable=True),
    sa.Column('resolved_json', sa.JSON(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('opened_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('deal_shares', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_deal_shares_borrower_user_id'), ['borrower_user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_deal_shares_loan_officer_user_id'), ['loan_officer_user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_deal_shares_property_id'), ['property_id'], unique=False)

    op.create_table('lead_source',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source_name', sa.String(length=100), nullable=True),
    sa.Column('source_type', sa.String(length=50), nullable=True),
    sa.Column('url', sa.String(length=255), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('property',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('address', sa.String(length=255), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('state', sa.String(length=50), nullable=True),
    sa.Column('zip', sa.String(length=20), nullable=True),
    sa.Column('price', sa.Float(), nullable=True),
    sa.Column('beds', sa.Integer(), nullable=True),
    sa.Column('baths', sa.Float(), nullable=True),
    sa.Column('sqft', sa.Integer(), nullable=True),
    sa.Column('image_url', sa.String(length=255), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('resource_document',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('category', sa.String(length=100), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('system',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=True),
    sa.Column('version', sa.String(length=50), nullable=True),
    sa.Column('environment', sa.String(length=50), nullable=True),
    sa.Column('hostname', sa.String(length=120), nullable=True),
    sa.Column('os', sa.String(length=120), nullable=True),
    sa.Column('uptime_start', sa.DateTime(), nullable=True),
    sa.Column('last_heartbeat', sa.DateTime(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('total_users', sa.Integer(), nullable=True),
    sa.Column('total_loans', sa.Integer(), nullable=True),
    sa.Column('total_errors', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('system_settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('system_name', sa.String(length=120), nullable=True),
    sa.Column('theme_color', sa.String(length=20), nullable=True),
    sa.Column('ai_mode', sa.String(length=50), nullable=True),
    sa.Column('version', sa.String(length=20), nullable=True),
    sa.Column('maintenance_mode', sa.Boolean(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('first_name', sa.String(length=100), nullable=True),
    sa.Column('last_name', sa.String(length=100), nullable=True),
    sa.Column('username', sa.String(length=120), nullable=True),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=True),
    sa.Column('role', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('last_login', sa.DateTime(), nullable=True),
    sa.Column('timeline_status', sa.String(length=50), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )
    op.create_table('audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('system_id', sa.Integer(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('module', sa.String(length=120), nullable=True),
    sa.Column('action', sa.String(length=120), nullable=True),
    sa.Column('object_type', sa.String(length=120), nullable=True),
    sa.Column('object_id', sa.Integer(), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['system_id'], ['system.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('campaign',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('start_date', sa.DateTime(), nullable=True),
    sa.Column('end_date', sa.DateTime(), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=True),
    sa.Column('audience_type', sa.String(length=50), nullable=True),
    sa.Column('audience_segment', sa.String(length=100), nullable=True),
    sa.Column('channel', sa.String(length=50), nullable=True),
    sa.Column('message_subject', sa.String(length=255), nullable=True),
    sa.Column('message_body', sa.Text(), nullable=True),
    sa.Column('ai_generated', sa.Boolean(), nullable=True),
    sa.Column('sent_count', sa.Integer(), nullable=True),
    sa.Column('open_count', sa.Integer(), nullable=True),
    sa.Column('click_count', sa.Integer(), nullable=True),
    sa.Column('response_count', sa.Integer(), nullable=True),
    sa.Column('conversion_count', sa.Integer(), nullable=True),
    sa.Column('last_run', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('contractor_payments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('contractor_id', sa.Integer(), nullable=True),
    sa.Column('amount', sa.Float(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('transaction_id', sa.String(length=120), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['contractor_id'], ['contractors.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('investor_profile',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=True),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('strategy', sa.String(length=50), nullable=True),
    sa.Column('experience_level', sa.String(length=30), nullable=True),
    sa.Column('target_markets', sa.Text(), nullable=True),
    sa.Column('property_types', sa.Text(), nullable=True),
    sa.Column('min_price', sa.Integer(), nullable=True),
    sa.Column('max_price', sa.Integer(), nullable=True),
    sa.Column('min_sqft', sa.Integer(), nullable=True),
    sa.Column('max_sqft', sa.Integer(), nullable=True),
    sa.Column('capital_available', sa.Integer(), nullable=True),
    sa.Column('min_cash_on_cash', sa.Float(), nullable=True),
    sa.Column('min_roi', sa.Float(), nullable=True),
    sa.Column('timeline_days', sa.Integer(), nullable=True),
    sa.Column('risk_tolerance', sa.String(length=30), nullable=True),
    sa.Column('is_verified', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('investor_profile', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_investor_profile_user_id'), ['user_id'], unique=True)

    op.create_table('loan_officer_profile',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('nmls', sa.String(length=20), nullable=True),
    sa.Column('region', sa.String(length=100), nullable=True),
    sa.Column('specialization', sa.String(length=150), nullable=True),
    sa.Column('joined_at', sa.DateTime(), nullable=True),
    sa.Column('signature_image', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('message',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=False),
    sa.Column('receiver_id', sa.Integer(), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('sender_role', sa.String(length=50), nullable=True),
    sa.Column('receiver_role', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('system_generated', sa.Boolean(), nullable=True),
    sa.Column('is_read', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['receiver_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['sender_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('message_threads',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=True),
    sa.Column('recipient_type', sa.String(length=50), nullable=True),
    sa.Column('recipient_id', sa.Integer(), nullable=True),
    sa.Column('message_type', sa.String(length=50), nullable=True),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('sent_at', sa.DateTime(), nullable=True),
    sa.Column('direction', sa.String(length=20), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=True),
    sa.ForeignKeyConstraint(['sender_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('partners',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('company', sa.String(length=120), nullable=True),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('category', sa.String(length=100), nullable=True),
    sa.Column('service_area', sa.String(length=255), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.Column('type', sa.String(length=50), nullable=True),
    sa.Column('website', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('relationship_level', sa.String(length=50), nullable=True),
    sa.Column('joined_date', sa.DateTime(), nullable=True),
    sa.Column('last_contacted', sa.DateTime(), nullable=True),
    sa.Column('last_deal', sa.DateTime(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('deals', sa.Integer(), nullable=True),
    sa.Column('volume', sa.Float(), nullable=True),
    sa.Column('rating', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('listing_description', sa.Text(), nullable=True),
    sa.Column('logo_url', sa.String(length=255), nullable=True),
    sa.Column('approved', sa.Boolean(), nullable=True),
    sa.Column('featured', sa.Boolean(), nullable=True),
    sa.Column('subscription_tier', sa.String(length=50), nullable=True),
    sa.Column('paid_until', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('processor_profile',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('department', sa.String(length=100), nullable=True),
    sa.Column('assigned_loans', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_processor_user_id'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('system_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('system_id', sa.Integer(), nullable=True),
    sa.Column('level', sa.String(length=20), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('origin', sa.String(length=120), nullable=True),
    sa.Column('user', sa.String(length=120), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['system_id'], ['system.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('underwriter_profile',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=True),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('department', sa.String(length=120), nullable=True),
    sa.Column('region', sa.String(length=120), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.Column('total_quotes_reviewed', sa.Integer(), nullable=True),
    sa.Column('total_loans_approved', sa.Integer(), nullable=True),
    sa.Column('last_login', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_underwriter_user_id'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('investment',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('investor_profile_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=True),
    sa.Column('strategy', sa.String(length=50), nullable=True),
    sa.Column('property_address', sa.String(length=200), nullable=True),
    sa.Column('city', sa.String(length=80), nullable=True),
    sa.Column('state', sa.String(length=30), nullable=True),
    sa.Column('zipcode', sa.String(length=15), nullable=True),
    sa.Column('purchase_price', sa.Integer(), nullable=True),
    sa.Column('rehab_budget', sa.Integer(), nullable=True),
    sa.Column('arv', sa.Integer(), nullable=True),
    sa.Column('monthly_rent', sa.Integer(), nullable=True),
    sa.Column('monthly_expenses', sa.Integer(), nullable=True),
    sa.Column('loan_amount', sa.Integer(), nullable=True),
    sa.Column('interest_rate', sa.Float(), nullable=True),
    sa.Column('term_months', sa.Integer(), nullable=True),
    sa.Column('down_payment', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('stage', sa.String(length=50), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('projected_profit', sa.Integer(), nullable=True),
    sa.Column('projected_roi', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('investment', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_investment_investor_profile_id'), ['investor_profile_id'], unique=False)

    op.create_table('lead',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=True),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('source_id', sa.Integer(), nullable=True),
    sa.Column('property_id', sa.Integer(), nullable=True),
    sa.Column('assigned_officer_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('assigned_to', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_officer_id'], ['loan_officer_profile.id'], ),
    sa.ForeignKeyConstraint(['assigned_to'], ['user.id'], ),
    sa.ForeignKeyConstraint(['property_id'], ['property.id'], ),
    sa.ForeignKeyConstraint(['source_id'], ['lead_source.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('loan_officer_analytics',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('officer_id', sa.Integer(), nullable=True),
    sa.Column('total_loans', sa.Integer(), nullable=True),
    sa.Column('approved_loans', sa.Integer(), nullable=True),
    sa.Column('declined_loans', sa.Integer(), nullable=True),
    sa.Column('active_loans', sa.Integer(), nullable=True),
    sa.Column('average_processing_time', sa.Float(), nullable=True),
    sa.Column('performance_score', sa.Float(), nullable=True),
    sa.Column('month', sa.String(length=15), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['officer_id'], ['loan_officer_profile.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('loan_officer_portfolio',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('officer_id', sa.Integer(), nullable=True),
    sa.Column('total_clients', sa.Integer(), nullable=True),
    sa.Column('avg_loan_amount', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('avg_credit_score', sa.Integer(), nullable=True),
    sa.Column('avg_closing_time', sa.Float(), nullable=True),
    sa.Column('rating', sa.Float(), nullable=True),
    sa.Column('last_updated', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['officer_id'], ['loan_officer_profile.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('borrower_profile',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('assigned_to', sa.Integer(), nullable=True),
    sa.Column('lead_id', sa.Integer(), nullable=True),
    sa.Column('assigned_officer_id', sa.Integer(), nullable=True),
    sa.Column('full_name', sa.String(length=120), nullable=True),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('address', sa.String(length=255), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('state', sa.String(length=50), nullable=True),
    sa.Column('zip', sa.String(length=20), nullable=True),
    sa.Column('employment_status', sa.String(length=50), nullable=True),
    sa.Column('employer_name', sa.String(length=150), nullable=True),
    sa.Column('employer_phone', sa.String(length=50), nullable=True),
    sa.Column('job_title', sa.String(length=150), nullable=True),
    sa.Column('years_at_job', sa.Integer(), nullable=True),
    sa.Column('annual_income', sa.Float(), nullable=True),
    sa.Column('income', sa.Float(), nullable=True),
    sa.Column('monthly_income_secondary', sa.Float(), nullable=True),
    sa.Column('bank_balance', sa.Float(), nullable=True),
    sa.Column('assets_description', sa.Text(), nullable=True),
    sa.Column('liabilities_description', sa.Text(), nullable=True),
    sa.Column('housing_status', sa.String(length=50), nullable=True),
    sa.Column('monthly_housing_payment', sa.Float(), nullable=True),
    sa.Column('dob', sa.Date(), nullable=True),
    sa.Column('ssn', sa.String(length=20), nullable=True),
    sa.Column('citizenship', sa.String(length=50), nullable=True),
    sa.Column('marital_status', sa.String(length=50), nullable=True),
    sa.Column('dependents', sa.Integer(), nullable=True),
    sa.Column('reo_properties', postgresql.JSONB(astext_type=Text()), nullable=True),
    sa.Column('declarations_flags', postgresql.JSONB(astext_type=Text()), nullable=True),
    sa.Column('credit_score', sa.Integer(), nullable=True),
    sa.Column('loan_type', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('profile_pic', sa.String(length=255), nullable=True),
    sa.Column('company', sa.String(length=120), nullable=True),
    sa.Column('subscription_plan', sa.String(length=20), nullable=True),
    sa.Column('has_seen_dashboard_tour', sa.Boolean(), nullable=True),
    sa.Column('email_notifications', sa.Boolean(), nullable=True),
    sa.Column('sms_notifications', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_officer_id'], ['loan_officer_profile.id'], name='fk_borrower_officer'),
    sa.ForeignKeyConstraint(['assigned_to'], ['user.id'], name='fk_borrower_assigned_to'),
    sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], name='fk_borrower_lead'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_borrower_user'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('campaign_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lead_id', sa.Integer(), nullable=True),
    sa.Column('subject', sa.String(length=255), nullable=True),
    sa.Column('body', sa.Text(), nullable=True),
    sa.Column('channel', sa.String(length=50), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('scheduled_for', sa.DateTime(), nullable=True),
    sa.Column('sent_at', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
    sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('investment_document',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('investment_id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('stored_path', sa.String(length=500), nullable=False),
    sa.Column('content_type', sa.String(length=120), nullable=True),
    sa.Column('doc_type', sa.String(length=80), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['investment_id'], ['investment.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('investment_document', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_investment_document_investment_id'), ['investment_id'], unique=False)

    op.create_table('partner_lead_link',
    sa.Column('partner_id', sa.Integer(), nullable=False),
    sa.Column('lead_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], ),
    sa.ForeignKeyConstraint(['partner_id'], ['partners.id'], ),
    sa.PrimaryKeyConstraint('partner_id', 'lead_id')
    )
    op.create_table('ai_intake_summary',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=False),
    sa.Column('investor_profile_id', sa.Integer(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('reviewer_notes', sa.Text(), nullable=True),
    sa.Column('reviewer_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['reviewer_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('behavioral_insights',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('officer_id', sa.Integer(), nullable=True),
    sa.Column('total_messages', sa.Integer(), nullable=True),
    sa.Column('avg_response_time', sa.Float(), nullable=True),
    sa.Column('sentiment_score', sa.Float(), nullable=True),
    sa.Column('follow_up_rate', sa.Float(), nullable=True),
    sa.Column('engagement_level', sa.String(length=50), nullable=True),
    sa.Column('ai_summary', sa.Text(), nullable=True),
    sa.Column('ai_suggestions', sa.Text(), nullable=True),
    sa.Column('conversion_rate', sa.Float(), nullable=True),
    sa.Column('loan_success_score', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['officer_id'], ['loan_officer_profile.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('borrower_activity',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=False),
    sa.Column('investor_profile_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(length=255), nullable=False),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('category', sa.String(length=50), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('borrower_interaction',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_id', sa.Integer(), nullable=True),
    sa.Column('interaction_type', sa.String(length=50), nullable=True),
    sa.Column('question', sa.Text(), nullable=True),
    sa.Column('response', sa.Text(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('topic', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['parent_id'], ['borrower_interaction.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('borrower_message',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_id', sa.Integer(), nullable=False),
    sa.Column('sender_type', sa.String(length=20), nullable=True),
    sa.Column('sender_name', sa.String(length=120), nullable=True),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], name='fk_msg_borrower'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('campaign_recipient',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('campaign_id', sa.Integer(), nullable=False),
    sa.Column('lead_id', sa.Integer(), nullable=True),
    sa.Column('borrower_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('sent_at', sa.DateTime(), nullable=True),
    sa.Column('responded_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaign.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('crm_note',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lead_id', sa.Integer(), nullable=True),
    sa.Column('borrower_id', sa.Integer(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('followup_item',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('is_done', sa.Boolean(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('last_contact',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('last_contact_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('loan_application',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('loan_officer_id', sa.Integer(), nullable=True),
    sa.Column('processor_id', sa.Integer(), nullable=True),
    sa.Column('underwriter_id', sa.Integer(), nullable=True),
    sa.Column('property_id', sa.Integer(), nullable=True),
    sa.Column('lender_name', sa.String(length=120), nullable=True),
    sa.Column('amount', sa.Float(), nullable=True),
    sa.Column('loan_type', sa.String(length=50), nullable=True),
    sa.Column('term_months', sa.Integer(), nullable=True),
    sa.Column('rate', sa.Float(), nullable=True),
    sa.Column('ltv', sa.Float(), nullable=True),
    sa.Column('property_value', sa.Float(), nullable=True),
    sa.Column('property_address', sa.String(length=255), nullable=True),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('ai_summary', sa.Text(), nullable=True),
    sa.Column('risk_score', sa.Float(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('processor_notes', sa.Text(), nullable=True),
    sa.Column('risk_level', sa.String(length=50), nullable=True),
    sa.Column('ltv_ratio', sa.Float(), nullable=True),
    sa.Column('decision_notes', sa.Text(), nullable=True),
    sa.Column('decision_date', sa.DateTime(), nullable=True),
    sa.Column('monthly_housing_payment', sa.Float(), nullable=True),
    sa.Column('front_end_dti', sa.Float(), nullable=True),
    sa.Column('back_end_dti', sa.Float(), nullable=True),
    sa.Column('monthly_debt_total', sa.Float(), nullable=True),
    sa.Column('progress_percent', sa.Integer(), nullable=True),
    sa.Column('milestone_stage', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], name='fk_loanapp_borrower'),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_officer_id'], ['loan_officer_profile.id'], name='fk_loanapp_officer'),
    sa.ForeignKeyConstraint(['processor_id'], ['processor_profile.id'], name='fk_loanapp_processor'),
    sa.ForeignKeyConstraint(['property_id'], ['property.id'], name='fk_loanapp_property'),
    sa.ForeignKeyConstraint(['underwriter_id'], ['underwriter_profile.id'], name='fk_loanapp_underwriter'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('loan_intake_session',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('assigned_officer_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('data', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_officer_id'], ['loan_officer_profile.id'], ),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('partner_connection_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_user_id', sa.Integer(), nullable=False),
    sa.Column('investor_user_id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('property_id', sa.Integer(), nullable=True),
    sa.Column('lead_id', sa.Integer(), nullable=True),
    sa.Column('partner_id', sa.Integer(), nullable=False),
    sa.Column('category', sa.String(length=100), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('responded_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['borrower_user_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_user_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], ),
    sa.ForeignKeyConstraint(['partner_id'], ['partners.id'], ),
    sa.ForeignKeyConstraint(['property_id'], ['property.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('partner_jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('partner_id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('property_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('scope', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['partner_id'], ['partners.id'], ),
    sa.ForeignKeyConstraint(['property_id'], ['property.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('saved_properties',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=False),
    sa.Column('investor_profile_id', sa.Integer(), nullable=False),
    sa.Column('property_id', sa.String(length=50), nullable=True),
    sa.Column('address', sa.String(length=255), nullable=True),
    sa.Column('price', sa.String(length=50), nullable=True),
    sa.Column('sqft', sa.Integer(), nullable=True),
    sa.Column('saved_at', sa.DateTime(), nullable=True),
    sa.Column('zipcode', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('resolved_json', sa.Text(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('soft_credit_report',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('credit_score', sa.Integer(), nullable=True),
    sa.Column('bureau', sa.String(length=50), nullable=True),
    sa.Column('credit_data', postgresql.JSONB(astext_type=Text()), nullable=True),
    sa.Column('monthly_debt_total', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('subscription_plan',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=False),
    sa.Column('plan_name', sa.String(length=100), nullable=True),
    sa.Column('price', sa.Float(), nullable=True),
    sa.Column('features', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('start_date', sa.DateTime(), nullable=True),
    sa.Column('end_date', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ai_assistant_interactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('loan_officer_id', sa.Integer(), nullable=True),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('response', sa.Text(), nullable=True),
    sa.Column('context_tag', sa.String(length=100), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.ForeignKeyConstraint(['loan_officer_id'], ['loan_officer_profile.id'], ),
    sa.ForeignKeyConstraint(['parent_id'], ['ai_assistant_interactions.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ai_audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('module', sa.String(length=100), nullable=True),
    sa.Column('action', sa.String(length=100), nullable=True),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('lead_id', sa.Integer(), nullable=True),
    sa.Column('context', sa.String(length=100), nullable=True),
    sa.Column('role_view', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], ),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('call_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('contact_name', sa.String(length=120), nullable=True),
    sa.Column('contact_phone', sa.String(length=20), nullable=True),
    sa.Column('related_lead_id', sa.Integer(), nullable=True),
    sa.Column('related_loan_id', sa.Integer(), nullable=True),
    sa.Column('direction', sa.String(length=10), nullable=False),
    sa.Column('duration_seconds', sa.Integer(), nullable=True),
    sa.Column('outcome', sa.String(length=120), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('sentiment', sa.String(length=20), nullable=True),
    sa.Column('ai_summary', sa.Text(), nullable=True),
    sa.Column('recording_url', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['related_lead_id'], ['lead.id'], ),
    sa.ForeignKeyConstraint(['related_loan_id'], ['loan_application.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('communication_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('channel', sa.String(length=20), nullable=True),
    sa.Column('subject', sa.String(length=255), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('condition_request',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('loan_id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('document_name', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('requested_by', sa.Integer(), nullable=True),
    sa.Column('condition_type', sa.String(length=120), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('assigned_to', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_to'], ['user.id'], ),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], name='fk_conditionreq_borrower_id'),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['borrower_profile.id'], name='fk_conditionreq_investor_id'),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], name='fk_conditionreq_loan_id'),
    sa.ForeignKeyConstraint(['requested_by'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('credit_profile',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('loan_app_id', sa.Integer(), nullable=True),
    sa.Column('credit_score', sa.Integer(), nullable=True),
    sa.Column('report_date', sa.DateTime(), nullable=True),
    sa.Column('score', sa.Integer(), nullable=True),
    sa.Column('report_json', sa.Text(), nullable=True),
    sa.Column('pulled_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('public_records', sa.Integer(), nullable=True),
    sa.Column('delinquencies', sa.Integer(), nullable=True),
    sa.Column('total_accounts', sa.Integer(), nullable=True),
    sa.Column('total_debt', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('pulled_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_app_id'], ['loan_application.id'], ),
    sa.ForeignKeyConstraint(['pulled_by'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('deals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('saved_property_id', sa.Integer(), nullable=True),
    sa.Column('property_id', sa.String(length=120), nullable=True),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.Column('strategy', sa.String(length=32), nullable=True),
    sa.Column('final_before_url', sa.Text(), nullable=True),
    sa.Column('final_after_url', sa.Text(), nullable=True),
    sa.Column('inputs_json', sa.JSON(), nullable=True),
    sa.Column('results_json', sa.JSON(), nullable=True),
    sa.Column('comps_json', sa.JSON(), nullable=True),
    sa.Column('resolved_json', sa.JSON(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['saved_property_id'], ['saved_properties.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('deals', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_deals_property_id'), ['property_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_deals_saved_property_id'), ['saved_property_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_deals_user_id'), ['user_id'], unique=False)

    op.create_table('document_event',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('loan_id', sa.Integer(), nullable=False),
    sa.Column('borrower_id', sa.Integer(), nullable=False),
    sa.Column('investor_profile_id', sa.Integer(), nullable=False),
    sa.Column('document_name', sa.String(length=200), nullable=True),
    sa.Column('event_type', sa.String(length=50), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('user_agent', sa.String(length=300), nullable=True),
    sa.Column('ip_address', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('document_need',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_id', sa.Integer(), nullable=True),
    sa.Column('investor_id', sa.Integer(), nullable=True),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=True),
    sa.Column('reason', sa.String(length=500), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], name='fk_need_borrower'),
    sa.ForeignKeyConstraint(['investor_id'], ['investor_profile.id'], name='fk_need_investor'),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], name='fk_need_loan'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('document_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('requested_by', sa.String(length=120), nullable=True),
    sa.Column('document_name', sa.String(length=255), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('file_path', sa.String(length=255), nullable=True),
    sa.Column('verified_at', sa.DateTime(), nullable=True),
    sa.Column('is_resolved', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('followup_task',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('assigned_to', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('due_date', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_to'], ['user.id'], ),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('lender_quote',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('property_id', sa.Integer(), nullable=True),
    sa.Column('lender_name', sa.String(length=100), nullable=True),
    sa.Column('quote_details', sa.JSON(), nullable=True),
    sa.Column('rate', sa.Float(), nullable=True),
    sa.Column('term_months', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.ForeignKeyConstraint(['property_id'], ['property.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('loan_ai_conversation',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('user_role', sa.String(length=50), nullable=True),
    sa.Column('topic', sa.String(length=120), nullable=True),
    sa.Column('user_message', sa.Text(), nullable=False),
    sa.Column('ai_response', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('loan_document',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('processor_id', sa.Integer(), nullable=True),
    sa.Column('file_name', sa.String(length=255), nullable=True),
    sa.Column('file_path', sa.String(length=255), nullable=True),
    sa.Column('document_type', sa.String(length=100), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('document_name', sa.String(length=255), nullable=True),
    sa.Column('review_status', sa.String(length=50), nullable=True),
    sa.Column('sent_to_underwriter', sa.Boolean(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('uploaded_by', sa.String(length=120), nullable=True),
    sa.Column('submitted_file', sa.String(length=255), nullable=True),
    sa.Column('submitted_at', sa.DateTime(), nullable=True),
    sa.Column('review_notes', sa.Text(), nullable=True),
    sa.Column('reviewed_by', sa.String(length=120), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.ForeignKeyConstraint(['processor_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('loan_notification',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('loan_id', sa.Integer(), nullable=False),
    sa.Column('borrower_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('role', sa.String(length=50), nullable=True),
    sa.Column('message', sa.String(length=800), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('is_read', sa.Boolean(), nullable=True),
    sa.Column('channel', sa.String(length=20), nullable=True),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('loan_officer_ai_summary',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('officer_id', sa.Integer(), nullable=True),
    sa.Column('summary_text', sa.Text(), nullable=True),
    sa.Column('confidence_score', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.ForeignKeyConstraint(['officer_id'], ['loan_officer_profile.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('loan_quote',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=True),
    sa.Column('loan_application_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('lender_name', sa.String(length=120), nullable=True),
    sa.Column('rate', sa.Float(), nullable=True),
    sa.Column('max_ltv', sa.Float(), nullable=True),
    sa.Column('term_months', sa.Integer(), nullable=True),
    sa.Column('loan_amount', sa.Float(), nullable=True),
    sa.Column('loan_type', sa.String(length=120), nullable=True),
    sa.Column('property_address', sa.String(length=255), nullable=True),
    sa.Column('property_type', sa.String(length=120), nullable=True),
    sa.Column('purchase_price', sa.Float(), nullable=True),
    sa.Column('purchase_date', sa.String(length=120), nullable=True),
    sa.Column('as_is_value', sa.Float(), nullable=True),
    sa.Column('after_repair_value', sa.Float(), nullable=True),
    sa.Column('fico_score', sa.Integer(), nullable=True),
    sa.Column('loan_category', sa.String(length=50), nullable=True),
    sa.Column('construction_budget', sa.Float(), nullable=True),
    sa.Column('capex_amount', sa.Float(), nullable=True),
    sa.Column('experience', sa.String(length=255), nullable=True),
    sa.Column('requested_terms', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('photos', sa.String(length=255), nullable=True),
    sa.Column('response_json', sa.Text(), nullable=True),
    sa.Column('selected', sa.Boolean(), nullable=True),
    sa.Column('documents_uploaded', sa.Boolean(), nullable=True),
    sa.Column('deal_type', sa.String(length=50), nullable=True),
    sa.Column('data', sa.JSON(), nullable=True),
    sa.Column('ai_suggestion', sa.Text(), nullable=True),
    sa.Column('assigned_officer_id', sa.Integer(), nullable=True),
    sa.Column('assigned_underwriter_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_officer_id'], ['loan_officer_profile.id'], name='fk_quote_officer'),
    sa.ForeignKeyConstraint(['assigned_underwriter_id'], ['underwriter_profile.id'], name='fk_quote_underwriter'),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], name='fk_quote_borrower'),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], name='fk_quote_investor'),
    sa.ForeignKeyConstraint(['loan_application_id'], ['loan_application.id'], name='fk_quote_loanapp'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('loan_scenario',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=120), nullable=True),
    sa.Column('amount', sa.Float(), nullable=True),
    sa.Column('rate', sa.Float(), nullable=True),
    sa.Column('term_months', sa.Integer(), nullable=True),
    sa.Column('loan_type', sa.String(length=50), nullable=True),
    sa.Column('down_payment', sa.Float(), nullable=True),
    sa.Column('closing_costs', sa.Float(), nullable=True),
    sa.Column('monthly_payment', sa.Float(), nullable=True),
    sa.Column('dti', sa.Float(), nullable=True),
    sa.Column('ltv', sa.Float(), nullable=True),
    sa.Column('apr', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], name='fk_scenario_loan'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('loan_status_event',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('event_name', sa.String(length=120), nullable=True),
    sa.Column('description', sa.String(length=400), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], name='fk_status_loan'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('payment_record',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('payment_type', sa.String(length=100), nullable=True),
    sa.Column('amount', sa.Float(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('stripe_payment_intent', sa.String(length=255), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], name='fk_payment_borrower'),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], name='fk_payment_investor'),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], name='fk_payment_loan'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('payment_record', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payment_record_user_id'), ['user_id'], unique=False)

    op.create_table('project_budgets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=False),
    sa.Column('loan_app_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('project_name', sa.String(length=120), nullable=True),
    sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('total_budget', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('total_cost', sa.Float(), nullable=True),
    sa.Column('materials_cost', sa.Float(), nullable=True),
    sa.Column('labor_cost', sa.Float(), nullable=True),
    sa.Column('contingency', sa.Float(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_app_id'], ['loan_application.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('property_analysis',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=False),
    sa.Column('loan_app_id', sa.Integer(), nullable=True),
    sa.Column('property_id', sa.Integer(), nullable=True),
    sa.Column('property_name', sa.String(length=255), nullable=True),
    sa.Column('property_value', sa.Float(), nullable=True),
    sa.Column('property_type', sa.String(length=120), nullable=True),
    sa.Column('address', sa.String(length=255), nullable=True),
    sa.Column('arv', sa.Float(), nullable=True),
    sa.Column('rehab_cost', sa.Float(), nullable=True),
    sa.Column('purchase_price', sa.Float(), nullable=True),
    sa.Column('ltv', sa.Float(), nullable=True),
    sa.Column('cap_rate', sa.Float(), nullable=True),
    sa.Column('cash_flow', sa.Float(), nullable=True),
    sa.Column('noi', sa.Float(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('profit_margin', sa.Float(), nullable=True),
    sa.Column('expenses', sa.Float(), nullable=True),
    sa.Column('rental_income', sa.Float(), nullable=True),
    sa.Column('roi', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_app_id'], ['loan_application.id'], ),
    sa.ForeignKeyConstraint(['property_id'], ['property.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('task',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_id', sa.Integer(), nullable=True),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('assigned_to', sa.Integer(), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('priority', sa.String(length=50), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=True),
    sa.Column('completed', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('partner_job_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_to'], ['user.id'], ),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.ForeignKeyConstraint(['partner_job_id'], ['partner_jobs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('underwriter_audit_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('user_name', sa.String(length=120), nullable=True),
    sa.Column('action_type', sa.String(length=100), nullable=True),
    sa.Column('actor', sa.String(length=120), nullable=True),
    sa.Column('description', sa.String(length=800), nullable=True),
    sa.Column('outcome', sa.String(length=200), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], name='fk_auditlog_loan_id'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('underwriter_task',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('priority', sa.String(length=50), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('assigned_to', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_to'], ['underwriter_profile.id'], name='fk_task_underwriter_id'),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('underwriting_condition',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=False),
    sa.Column('investor_profile_id', sa.Integer(), nullable=False),
    sa.Column('loan_id', sa.Integer(), nullable=False),
    sa.Column('condition_type', sa.String(length=120), nullable=True),
    sa.Column('description', sa.String(length=800), nullable=True),
    sa.Column('severity', sa.String(length=50), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('requested_by', sa.String(length=100), nullable=True),
    sa.Column('cleared_by', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('cleared_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], name='fk_condition_borrower_id'),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], name='fk_condition_investor_id'),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], name='fk_condition_loan_id'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('upload',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('file_path', sa.String(length=255), nullable=False),
    sa.Column('file_type', sa.String(length=100), nullable=True),
    sa.Column('category', sa.String(length=100), nullable=True),
    sa.Column('size_kb', sa.Float(), nullable=True),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('loan_id', sa.Integer(), nullable=True),
    sa.Column('uploaded_by_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=True),
    sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('review_notes', sa.Text(), nullable=True),
    sa.Column('uploaded_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.ForeignKeyConstraint(['reviewed_by_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('esigned_document',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrower_profile_id', sa.Integer(), nullable=False),
    sa.Column('investor_profile_id', sa.Integer(), nullable=False),
    sa.Column('loan_id', sa.Integer(), nullable=False),
    sa.Column('loan_document_id', sa.Integer(), nullable=True),
    sa.Column('document_name', sa.String(length=255), nullable=False),
    sa.Column('document_type', sa.String(length=100), nullable=True),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('envelope_id', sa.String(length=255), nullable=True),
    sa.Column('signer_email', sa.String(length=255), nullable=True),
    sa.Column('signer_name', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('status_message', sa.String(length=500), nullable=True),
    sa.Column('viewed_at', sa.DateTime(), nullable=True),
    sa.Column('signed_at', sa.DateTime(), nullable=True),
    sa.Column('pdf_original_path', sa.String(length=500), nullable=True),
    sa.Column('pdf_signed_path', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('webhook_log', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_profile_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['loan_document_id'], ['loan_document.id'], ),
    sa.ForeignKeyConstraint(['loan_id'], ['loan_application.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('project_expenses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('budget_id', sa.Integer(), nullable=True),
    sa.Column('category', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['budget_id'], ['project_budgets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('renovation_mockup',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('borrower_id', sa.Integer(), nullable=True),
    sa.Column('investor_profile_id', sa.Integer(), nullable=True),
    sa.Column('property_id', sa.String(length=64), nullable=True),
    sa.Column('saved_property_id', sa.Integer(), nullable=True),
    sa.Column('deal_id', sa.Integer(), nullable=True),
    sa.Column('before_url', sa.Text(), nullable=False),
    sa.Column('after_url', sa.Text(), nullable=False),
    sa.Column('style_prompt', sa.Text(), nullable=True),
    sa.Column('style_preset', sa.String(length=40), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['borrower_id'], ['borrower_profile.id'], ),
    sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], ),
    sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profile.id'], ),
    sa.ForeignKeyConstraint(['saved_property_id'], ['saved_properties.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('renovation_mockup')
    op.drop_table('project_expenses')
    op.drop_table('esigned_document')
    op.drop_table('upload')
    op.drop_table('underwriting_condition')
    op.drop_table('underwriter_task')
    op.drop_table('underwriter_audit_logs')
    op.drop_table('task')
    op.drop_table('property_analysis')
    op.drop_table('project_budgets')
    with op.batch_alter_table('payment_record', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payment_record_user_id'))

    op.drop_table('payment_record')
    op.drop_table('loan_status_event')
    op.drop_table('loan_scenario')
    op.drop_table('loan_quote')
    op.drop_table('loan_officer_ai_summary')
    op.drop_table('loan_notification')
    op.drop_table('loan_document')
    op.drop_table('loan_ai_conversation')
    op.drop_table('lender_quote')
    op.drop_table('followup_task')
    op.drop_table('document_requests')
    op.drop_table('document_need')
    op.drop_table('document_event')
    with op.batch_alter_table('deals', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_deals_user_id'))
        batch_op.drop_index(batch_op.f('ix_deals_saved_property_id'))
        batch_op.drop_index(batch_op.f('ix_deals_property_id'))

    op.drop_table('deals')
    op.drop_table('credit_profile')
    op.drop_table('condition_request')
    op.drop_table('communication_log')
    op.drop_table('call_log')
    op.drop_table('ai_audit_log')
    op.drop_table('ai_assistant_interactions')
    op.drop_table('subscription_plan')
    op.drop_table('soft_credit_report')
    op.drop_table('saved_properties')
    op.drop_table('partner_jobs')
    op.drop_table('partner_connection_requests')
    op.drop_table('loan_intake_session')
    op.drop_table('loan_application')
    op.drop_table('last_contact')
    op.drop_table('followup_item')
    op.drop_table('crm_note')
    op.drop_table('campaign_recipient')
    op.drop_table('borrower_message')
    op.drop_table('borrower_interaction')
    op.drop_table('borrower_activity')
    op.drop_table('behavioral_insights')
    op.drop_table('ai_intake_summary')
    op.drop_table('partner_lead_link')
    with op.batch_alter_table('investment_document', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_investment_document_investment_id'))

    op.drop_table('investment_document')
    op.drop_table('campaign_messages')
    op.drop_table('borrower_profile')
    op.drop_table('loan_officer_portfolio')
    op.drop_table('loan_officer_analytics')
    op.drop_table('lead')
    with op.batch_alter_table('investment', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_investment_investor_profile_id'))

    op.drop_table('investment')
    op.drop_table('underwriter_profile')
    op.drop_table('system_log')
    op.drop_table('processor_profile')
    op.drop_table('partners')
    op.drop_table('message_threads')
    op.drop_table('message')
    op.drop_table('loan_officer_profile')
    with op.batch_alter_table('investor_profile', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_investor_profile_user_id'))

    op.drop_table('investor_profile')
    op.drop_table('contractor_payments')
    op.drop_table('campaign')
    op.drop_table('audit_log')
    op.drop_table('user')
    op.drop_table('system_settings')
    op.drop_table('system')
    op.drop_table('resource_document')
    op.drop_table('property')
    op.drop_table('lead_source')
    with op.batch_alter_table('deal_shares', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_deal_shares_property_id'))
        batch_op.drop_index(batch_op.f('ix_deal_shares_loan_officer_user_id'))
        batch_op.drop_index(batch_op.f('ix_deal_shares_borrower_user_id'))

    op.drop_table('deal_shares')
    op.drop_table('contractors')
    op.drop_table('chat_history')
    def downgrade():

    # Reverse investor FK fixes
    with op.batch_alter_table('loan_application') as batch_op:
        batch_op.drop_constraint('fk_loanapp_investor', type_='foreignkey')

    with op.batch_alter_table('condition_request') as batch_op:
        batch_op.drop_constraint('fk_conditionreq_investor_id', type_='foreignkey')

    with op.batch_alter_table('loan_document') as batch_op:
        batch_op.drop_constraint('fk_loandoc_investor', type_='foreignkey')

    with op.batch_alter_table('underwriting_condition') as batch_op:
        batch_op.drop_constraint('fk_condition_investor', type_='foreignkey')

    # Reverse AI conversation rename
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'loan_ai_conversation' in tables and 'ai_conversation' not in tables:
        op.rename_table('loan_ai_conversation', 'ai_conversation')
:
    # ### commands auto generated by Alembic - please adjust! ###
    # ### end Alembic commands ###
