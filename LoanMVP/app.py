# LoanMVP/app.py

import os
import sys
import importlib
import traceback
from datetime import datetime

from flask import (
    Flask,
    Blueprint,
    Response,
    redirect,
    render_template,
    request,
    send_from_directory,
    current_app,
    url_for,
    session,
    jsonify,
)
from sqlalchemy.exc import SQLAlchemyError
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_migrate import Migrate
from flask_login import LoginManager, current_user, login_required
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

from LoanMVP.config import get_config
from LoanMVP.extensions import db, login_manager, migrate, mail, stripe, csrf, limiter
from LoanMVP.models import User
from LoanMVP.models.loan_models import BorrowerProfile, LoanNotification
from LoanMVP.utils.role_helpers import get_role_display, get_request_type_display, get_status_display, get_status_badge
from LoanMVP.services.unified_resolver import resolve_property

ENV_NAME = os.environ.get("FLASK_ENV", "production").strip().lower()
DEFAULT_SOCKETIO_ASYNC_MODE = "threading" if ENV_NAME in {"dev", "development", "local"} else "eventlet"
SOCKETIO_ASYNC_MODE = os.environ.get("SOCKETIO_ASYNC_MODE", DEFAULT_SOCKETIO_ASYNC_MODE).strip().lower()

if SOCKETIO_ASYNC_MODE == "threading":
    import engineio
    import engineio.async_drivers.threading

    if not hasattr(engineio, "async_modes") or "threading" not in getattr(engineio, "async_modes", []):
        engineio.async_modes = ["threading"]
        engineio.Server = engineio.server.Server


# ---------------------------------------------------------
# Flask Extensions (local instances)
# ---------------------------------------------------------
cors = CORS()
socketio = SocketIO(
    async_mode=SOCKETIO_ASYNC_MODE,
    logger=False,
    engineio_logger=False,
    transports=["websocket", "polling"],
)


# ---------------------------------------------------------
# Helper
# ---------------------------------------------------------
def resource_path(relative_path: str) -> str:
    """Resolve absolute path for bundled & dev modes."""
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ---------------------------------------------------------
# Schema self-heal
# ---------------------------------------------------------
# Columns added in recent migrations that must exist for the app to boot,
# paired with the SQL-level type to add if the migration hasn't run yet.
# Only additive, nullable columns are safe to self-heal here — destructive
# or type-changing operations must go through Alembic.
_SCHEMA_COMPAT_COLUMNS = [
    ("user",                       "stripe_customer_id",  "VARCHAR(255)"),
    ("user",                       "university_tier",     "VARCHAR(20)"),
    ("user",                       "trial_ends_at",       "TIMESTAMP"),
    ("vip_profiles",              "markets_json",       "TEXT"),
    ("deals",                     "local_cost_factor",  "FLOAT"),
    ("deals",                     "local_cost_label",   "VARCHAR(120)"),
    ("elena_listings",            "market",             "VARCHAR(100)"),
    ("elena_listings",            "updated_at",         "TIMESTAMP"),
    ("elena_listings",            "county",             "VARCHAR(120)"),
    ("elena_clients",             "market",             "VARCHAR(100)"),
    ("elena_clients",             "assigned_member_id", "INTEGER"),
    ("vip_expenses",              "market",             "VARCHAR(100)"),
    ("vip_income",                "market",             "VARCHAR(100) DEFAULT 'received'"),
    ("vip_assistant_suggestions", "proposed_amount",    "INTEGER"),
    ("vip_assistant_suggestions", "source",             "VARCHAR(50)"),
    ("vip_design_projects",       "blueprint_url",      "TEXT"),
    # vip_client_sessions columns (migration 20260514cs01)
    ("vip_client_sessions",       "client_name",        "VARCHAR(255)"),
    ("vip_client_sessions",       "client_email",       "VARCHAR(255)"),
    ("vip_client_sessions",       "client_phone",       "VARCHAR(50)"),
    ("vip_client_sessions",       "property_zip",       "VARCHAR(20)"),
    ("vip_client_sessions",       "property_state",     "VARCHAR(10)"),
    ("vip_client_sessions",       "bedrooms",           "INTEGER"),
    ("vip_client_sessions",       "bathrooms",          "VARCHAR(10)"),
    ("vip_client_sessions",       "sqft",               "INTEGER"),
    ("vip_client_sessions",       "scope_json",         "TEXT"),
    ("vip_client_sessions",       "commission_tier",    "VARCHAR(20)"),
    ("vip_client_sessions",       "commission_label",   "VARCHAR(80)"),
    ("vip_client_sessions",       "commission_pct",     "VARCHAR(20)"),
    ("vip_client_sessions",       "sale_price",         "INTEGER"),
    ("vip_client_sessions",       "notes",              "TEXT"),
    ("vip_client_sessions",       "updated_at",         "TIMESTAMP"),
    ("project_budgets",           "status",             "VARCHAR(32) NOT NULL DEFAULT 'active'"),
    ("investor_profile",          "ssn",                "TEXT"),
]

# Tables that must exist at boot. If missing, we ask SQLAlchemy's metadata
# to create just that table (equivalent to a single `db.create_all()` scoped
# to one model). Order only matters for foreign-key dependencies; the list
# here is kept small on purpose.
_SCHEMA_COMPAT_TABLES = [
    "subscription_requests",
    "cost_observations",
    "vip_profiles",
    "vip_contacts",
    "vip_interactions",
    "vip_expenses",
    "vip_income",
    "vip_budgets",
    "vip_assistant_suggestions",
    "vip_assistant_actions",
    "vip_notifications",
    "vip_design_projects",
    "vip_design_annotations",
    "vip_team_members",
    "insurance_quote_requests",
    "realtor_listing_presentations",
    "vip_client_sessions",
    "canva_connections",
    "external_partner_leads",
    "partner_connection_requests",
    "partner_requests",
    "contractor_bid_opportunities",
    "discovery_events",
]

_SCHEMA_COMPAT_INDEXES = [
    (
        "ix_realtor_presentations_vip_profile_id",
        "realtor_listing_presentations",
        ("vip_profile_id",),
        False,
    ),
    (
        "ix_realtor_presentations_listing_id",
        "realtor_listing_presentations",
        ("listing_id",),
        False,
    ),
]


# NOTE: The rest of this file is unchanged from the existing application.
