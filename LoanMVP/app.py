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
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

from LoanMVP.config import get_config
from LoanMVP.extensions import db, login_manager, migrate, mail, stripe, csrf
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
    ("vip_income",                "market",             "VARCHAR(100)"),
    ("vip_income",                "status",             "VARCHAR(50) DEFAULT 'received'"),
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


def _ensure_schema_compat(app):
    """Best-effort guard against deploys that race ahead of Alembic.

    For each (table, column, type) tuple, if the column is missing we issue
    `ALTER TABLE ... ADD COLUMN`. For each table in `_SCHEMA_COMPAT_TABLES`,
    if the table is missing we ask SQLAlchemy to create it from the model
    metadata. Errors are logged but never raised — at worst we fall back to
    whatever downstream try/except the callers already have. Running
    `flask db upgrade` afterward is still the correct long-term path; this
    is a safety net so a cold deploy doesn't 500 the app while migrations
    catch up.
    """
    try:
        import sqlalchemy as sa
        from sqlalchemy import inspect, text
    except Exception as e:
        print(f"[schema-compat] sqlalchemy import failed: {e}")
        return

    with app.app_context():
        try:
            inspector = inspect(db.engine)
        except Exception as e:
            print(f"[schema-compat] could not inspect engine: {e}")
            return

        for table, column, col_type in _SCHEMA_COMPAT_COLUMNS:
            try:
                if not inspector.has_table(table):
                    continue
                existing = {c["name"] for c in inspector.get_columns(table)}
                if column in existing:
                    continue

                print(f"[schema-compat] adding {table}.{column} ({col_type})")
                with db.engine.begin() as conn:
                    conn.execute(text(
                        f'ALTER TABLE "{table}" ADD COLUMN "{column}" {col_type}'
                    ))
            except Exception as e:
                print(f"[schema-compat] failed on {table}.{column}: {e}")

        # Table-level self-heal for tables introduced without a migration.
        for table_name in _SCHEMA_COMPAT_TABLES:
            try:
                if inspector.has_table(table_name):
                    continue
                table_obj = db.metadata.tables.get(table_name)
                if table_obj is None:
                    print(f"[schema-compat] no model found for missing table {table_name}")
                    continue
                print(f"[schema-compat] creating table {table_name}")
                table_obj.create(bind=db.engine, checkfirst=True)
            except Exception as e:
                print(f"[schema-compat] failed creating table {table_name}: {e}")

        for index_name, table_name, columns, unique in _SCHEMA_COMPAT_INDEXES:
            try:
                inspector = inspect(db.engine)
                if not inspector.has_table(table_name):
                    continue
                table_obj = db.metadata.tables.get(table_name)
                if table_obj is None:
                    print(f"[schema-compat] no model found for index {index_name}")
                    continue
                if any(column not in table_obj.c for column in columns):
                    print(f"[schema-compat] skipped index {index_name}; missing columns")
                    continue

                existing_indexes = {idx.name: idx for idx in table_obj.indexes}
                index_obj = existing_indexes.get(index_name)
                if index_obj is None:
                    index_obj = sa.Index(
                        index_name,
                        *(table_obj.c[column] for column in columns),
                        unique=unique,
                    )
                print(f"[schema-compat] ensuring index {index_name}")
                index_obj.create(bind=db.engine, checkfirst=True)
            except Exception as e:
                print(f"[schema-compat] failed creating index {index_name}: {e}")


# ---------------------------------------------------------
# App Factory
# ---------------------------------------------------------
def create_app():
    base_dir = os.path.abspath(os.path.dirname(__file__))

    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
        instance_relative_config=True,
    )

    config_class = get_config()
    config_class.validate()
    app.config.from_object(config_class)
    app.config["SOCKETIO_ASYNC_MODE"] = app.config.get("SOCKETIO_ASYNC_MODE") or SOCKETIO_ASYNC_MODE

    # ✅ Make sure secret key comes from config/env
    app.secret_key = app.config.get("SECRET_KEY")

    # ✅ Remove filesystem sessions on Render (ephemeral)
    app.config.pop("SESSION_TYPE", None)

    # Stripe configuration
    stripe.api_key = app.config.get("STRIPE_SECRET_KEY")

    # Initialize extensions
    cors_origins = app.config.get("CORS_ORIGINS") or []
    cors.init_app(
        app,
        origins=cors_origins or None,
        supports_credentials=app.config.get("CORS_SUPPORTS_CREDENTIALS", True),
    )
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    socketio.init_app(
        app,
        cors_allowed_origins=app.config.get("SOCKETIO_CORS_ALLOWED_ORIGINS") or [],
        message_queue=app.config.get("SOCKETIO_MESSAGE_QUEUE"),
    )
    app.socketio = socketio
    csrf.init_app(app)
     

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Login manager settings
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
     
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except Exception as e:
            print(f"Error loading user: {e}")
            return None

    # Register all route blueprints dynamically
    register_blueprints(app)

    # Best-effort schema self-heal for columns added by recent migrations.
    # Keeps prod from hard-crashing when a deploy beats the Alembic run.
    _ensure_schema_compat(app)

    # -----------------------------------------------------
    # Routes
    # -----------------------------------------------------
    @app.route("/")
    def marketing_home():
        return redirect(url_for("marketing.homepage"))


    @app.route("/dashboard")
    def dashboard_redirect():
        if current_user.is_authenticated:
            role = (getattr(current_user, "role", "") or "").strip().lower()

            if role == "executive":
                return redirect(url_for("executive.dashboard"))

            if role in {"admin", "platform_admin", "master_admin", "lending_admin"}:
                return redirect(url_for("admin.dashboard"))

            if role == "loan_officer":
                return redirect(url_for("loan_officer.dashboard"))

            if role == "processor":
                return redirect(url_for("processor.dashboard"))

            if role == "underwriter":
                return redirect(url_for("underwriter.dashboard"))

            if role == "crm":
                return redirect(url_for("crm.dashboard"))

            if role == "investor":
                return redirect(url_for("investor.command_center"))

        dashboards = [
            # User-facing
            ("Investor", "/investor"),
            ("Investor AI", "/investor_ai"),
       
            # Partner-facing        
            ("Partner", "/partner"),

            # Internal lending workflow
            ("Loan Officer", "/loan_officer"),
            ("Processor", "/processor"),
            ("Underwriter", "/underwriter"),
            ("Compliance", "/compliance"),

            # System-level dashboards
            ("Admin", "/admin"),
            ("Executive", "/executive"),
            ("Intelligence", "/intelligence"),
            ("CRM", "/crm"),
            ("Contractors", "/contractors"),
            ("Property", "/property"),
            ("Notifications", "/notifications"),
            ("System", "/system"),
            ("Tracking", "/track"),
            ("Master", "/master"),
            ("AI", "/ai"),
            ("Auth", "/auth"),
        ]
        return render_template("dashboard.html", dashboards=dashboards)

    @app.route("/dashboard-index")
    def index():
        dashboards = [
            # User-facing
            ("Investor", "/investor"),
            ("Investor AI", "/investor_ai"),
       
            # Partner-facing        
            ("Partner", "/partner"),

            # Internal lending workflow
            ("Loan Officer", "/loan_officer"),
            ("Processor", "/processor"),
            ("Underwriter", "/underwriter"),
            ("Compliance", "/compliance"),

            # System-level dashboards
            ("Admin", "/admin"),
            ("Executive", "/executive"),
            ("Intelligence", "/intelligence"),
            ("CRM", "/crm"),
            ("Contractors", "/contractors"),
            ("Property", "/property"),
            ("Notifications", "/notifications"),
            ("System", "/system"),
            ("Tracking", "/track"),
            ("Master", "/master"),
            ("AI", "/ai"),
            ("Auth", "/auth"),
        ]
        return render_template("dashboard.html", dashboards=dashboards)

    

    @app.route("/api/property/resolve", methods=["POST"])
    def api_resolve_property():
        payload = request.get_json() or {}
        address = payload.get("address")
        city = payload.get("city")
        state = payload.get("state")

        if not all([address, city, state]):
            return jsonify({"error": "address, city, state required"}), 400

        result = resolve_property(address, city, state)
        return jsonify(result), 200


        
    # Global error handler
    @app.errorhandler(Exception)
    def handle_any_exception(e):
        from werkzeug.exceptions import HTTPException

        if isinstance(e, HTTPException):
            return e

        try:
            db.session.rollback()
        except Exception:
            pass

        current_app.logger.exception("Unhandled application error")

        if current_app.debug or current_app.testing:
            tb = traceback.format_exc()
            return Response(f"<pre>{tb}</pre>", mimetype="text/plain"), 500

        return render_template("errors/500.html"), 500

    @app.get("/robots.txt")
    def robots_txt():
        site_url = os.environ.get("SITE_URL", "https://ravlohq.com").rstrip("/")
        body = (
            "User-agent: *\n"
            "\n"
            # ── Public marketing pages are crawlable by default ──────────
            # ── Block all private / authenticated app areas ──────────────
            "Disallow: /admin/\n"
            "Disallow: /executive/\n"
            "Disallow: /system/\n"
            "\n"
            "Disallow: /borrower/\n"
            "Disallow: /investor/\n"
            "Disallow: /loan_officer/\n"
            "Disallow: /processor/\n"
            "Disallow: /underwriter/\n"
            "Disallow: /crm/\n"
            "\n"
            "Disallow: /partners/\n"
            "Disallow: /vip/\n"
            "\n"
            "Disallow: /auth/\n"
            "Disallow: /account/\n"
            "Disallow: /notifications/\n"
            "\n"
            "Disallow: /api/\n"
            "Disallow: /checkout/\n"
            "Disallow: /stripe/\n"
            "Disallow: /track/\n"
            "Disallow: /canva/\n"
            "Disallow: /elena/\n"
            "\n"
            "Disallow: /academy/\n"         # API/portal endpoints (not marketing page)
            "Disallow: /university/chat\n"
            "Disallow: /university/portal\n"
            "\n"
            "Disallow: /flask_session/\n"
            "Disallow: /property/\n"
            "\n"
            f"Sitemap: {site_url}/sitemap.xml\n"
        )
        return Response(body, mimetype="text/plain")

    @app.get("/sitemap.xml")
    def sitemap_xml():
        site_url = os.environ.get("SITE_URL", "https://ravlohq.com").rstrip("/")
        pages = [
            ("/",                    "1.0", "weekly"),
            ("/university",          "0.9", "weekly"),
            ("/about",               "0.8", "monthly"),
            ("/tour",                "0.8", "monthly"),
            ("/lending-os",          "0.8", "monthly"),
            ("/plans",               "0.7", "monthly"),
            ("/partners",            "0.7", "monthly"),
            ("/faq",                 "0.6", "monthly"),
            ("/support",             "0.6", "monthly"),
            ("/story",               "0.6", "monthly"),
            ("/vision",              "0.6", "monthly"),
            ("/mission",             "0.6", "monthly"),
            ("/contact",             "0.5", "monthly"),
            ("/privacy",             "0.4", "yearly"),
            ("/terms",               "0.4", "yearly"),
            ("/disclaimer",          "0.4", "yearly"),
        ]
        rows = "\n".join(
            f"  <url>\n"
            f"    <loc>{site_url}{path}</loc>\n"
            f"    <priority>{priority}</priority>\n"
            f"    <changefreq>{freq}</changefreq>\n"
            f"  </url>"
            for path, priority, freq in pages
        )
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{rows}\n"
            "</urlset>"
        )
        return Response(xml, mimetype="application/xml")


    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, "static"),
            "favicon.ico",
            mimetype="image/vnd.microsoft.icon",
        )

    @app.context_processor
    def inject_canva_status():
        """Expose canva_connected to every template."""
        try:
            from flask_login import current_user
            if current_user and current_user.is_authenticated:
                from LoanMVP.models.canva_models import CanvaConnection
                conn = CanvaConnection.query.filter_by(user_id=current_user.id).first()
                return {"canva_connected": conn is not None and bool(conn.access_token)}
        except Exception:
            pass
        return {"canva_connected": False}

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        if request.blueprint == "auth":
            flash_message = "Your session expired. Please try signing in again."
            from flask import flash
            flash(flash_message, "warning")
            next_page = request.args.get("next") or request.form.get("next")
            return redirect(url_for("auth.login", next=next_page) if next_page else url_for("auth.login"))
        return render_template("errors/500.html"), 400

    @app.after_request
    def add_auth_cache_headers(response):
        if request.blueprint == "auth" and request.method == "GET":
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            existing_vary = response.headers.get("Vary", "")
            vary_values = {value.strip() for value in existing_vary.split(",") if value.strip()}
            vary_values.add("Cookie")
            response.headers["Vary"] = ", ".join(sorted(vary_values))
        return response

    # Context processors
    @app.context_processor
    def inject_notifications():
        unread = 0

        if not current_user.is_authenticated:
            return dict(unread_count=0)

        try:
            borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
            if borrower:
                unread = LoanNotification.query.filter_by(
                    borrower_id=borrower.id,
                    is_read=False,
                ).count()
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("inject_notifications failed: %s", e)
            unread = 0

        return dict(unread_count=unread)
    
    
    @app.context_processor
    def inject_role_helpers():
        return dict(get_role_display=get_role_display)  

    @app.context_processor
    def inject_ui_helpers():
        return dict(
            get_role_display=get_role_display,
            get_request_type_display=get_request_type_display,
            get_status_display=get_status_display,
            get_status_badge=get_status_badge,
        ) 
   
    @app.context_processor
    def inject_datetime():
        return dict(datetime=datetime)

    @app.template_filter("currency")
    def currency_format(value):
        try:
            return "${:,.0f}".format(int(value))
        except (ValueError, TypeError):
            return "$0"
   
    def safe_url_for(endpoint, **values):
        try:
            return url_for(endpoint, **values)
        except Exception:
            return None

    app.jinja_env.globals["safe_url_for"] = safe_url_for

    @app.before_request
    def make_session_permanent():
        session.permanent = True

    _TRIAL_EXEMPT_PREFIXES = ("auth.", "marketing.", "public_pages.", "preview.")
    _TRIAL_EXEMPT_EXACT = {"static", "favicon", "marketing_home", "robots_txt", "sitemap_xml", "index"}

    @app.before_request
    def check_trial_expiry():
        if not current_user.is_authenticated:
            return None
        sub = (getattr(current_user, "subscription", "") or "").strip().lower()
        if sub != "preview":
            return None
        trial_ends_at = getattr(current_user, "trial_ends_at", None)
        if not trial_ends_at:
            return None
        if datetime.utcnow() <= trial_ends_at:
            return None
        endpoint = request.endpoint or ""
        if (
            any(endpoint.startswith(p) for p in _TRIAL_EXEMPT_PREFIXES)
            or endpoint in _TRIAL_EXEMPT_EXACT
        ):
            return None
        return redirect(url_for("preview.trial_expired"))

    @app.before_request
    def handle_custom_domain():
        """Serve VIP realtor pages when traffic arrives on a custom domain.

        When `bonniesellsochomes.com` (or any custom domain stored in
        VIPProfile.custom_domain) resolves to this server, Flask would
        normally route to the marketing home page.  This hook intercepts
        the request before routing and renders the correct public page.

        Supported paths on custom domains:
          GET  /             → realtor landing page
          POST /contact      → lead-capture form
          GET  /sitemap.xml  → per-realtor sitemap
          GET  /blog         → blog post list
          GET  /blog/<slug>  → individual blog post
        """
        host = request.host.split(":")[0].lower()
        # Skip for localhost / known internal hosts
        if host in ("localhost", "127.0.0.1", "0.0.0.0"):
            return None

        from LoanMVP.models.vip_models import VIPProfile
        from sqlalchemy import func as sa_func
        profile = VIPProfile.query.filter(
            sa_func.lower(VIPProfile.custom_domain) == host,
            VIPProfile.marketplace_enabled == "yes",
        ).first()
        if not profile:
            return None

        from LoanMVP.routes.public_pages import (
            _load_realtor_context, _template_for, _handle_lead_capture,
        )
        slug = profile.public_slug
        path = request.path.rstrip("/") or "/"
        method = request.method.upper()

        if path == "/" and method == "GET":
            ctx = _load_realtor_context(slug)
            if not ctx:
                return None
            return render_template(_template_for(slug), **ctx)

        if path == "/contact" and method == "POST":
            return _handle_lead_capture(slug)

        if path == "/sitemap.xml" and method == "GET":
            from LoanMVP.routes.public_pages import _build_sitemap_xml
            return _build_sitemap_xml(profile)

        if path == "/blog" and method == "GET":
            from LoanMVP.routes.public_pages import _render_blog_list
            return _render_blog_list(slug)

        if path.startswith("/blog/") and method == "GET":
            post_slug = path[len("/blog/"):]
            from LoanMVP.routes.public_pages import _render_blog_post
            return _render_blog_post(slug, post_slug)

        return None

    return app


# ---------------------------------------------------------
# Dynamic Blueprint Registration
# ---------------------------------------------------------
def register_blueprints(app):
    routes_dir = os.path.join(os.path.dirname(__file__), "routes")
    if not os.path.exists(routes_dir):
        print("No routes folder found.")
        return

    module_aliases = {
        "executive.py": "LoanMVP.routes.executive_new",
    }

    for file in os.listdir(routes_dir):
        if file.endswith(".py") and not file.startswith("__"):
            if file.endswith("_new.py"):
                continue

            mod_name = module_aliases.get(file, f"LoanMVP.routes.{file[:-3]}")
            try:
                mod = importlib.import_module(mod_name)

                for attr in dir(mod):
                    obj = getattr(mod, attr)

                    if isinstance(obj, Blueprint):
                        # Force prefix to be applied
                        prefix = obj.url_prefix or f"/{obj.name}"

                        # Register blueprint with explicit prefix
                        app.register_blueprint(obj, url_prefix=prefix)

                        print(f"Registered blueprint: {obj.name} -> {prefix}")

            except Exception as e:
                print(f"Failed to load {file}: {e}")

# ---------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------
app = create_app()

if __name__ == "__main__":
    print("\nRegistered routes:")
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint:40s} -> {rule.rule}")

    socketio.run(app, host="0.0.0.0", port=5050, debug=app.config.get("DEBUG", False), use_reloader=False)
