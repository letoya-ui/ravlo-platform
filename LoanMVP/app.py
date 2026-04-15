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
)
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
        current_app.logger.exception("Unhandled application error")
        if app.debug or app.testing:
            tb = traceback.format_exc()
            return Response(f"<pre>{tb}</pre>", mimetype="text/plain"), 500
        return render_template("errors/500.html"), 500

    @app.get("/robots.txt")
    def robots_txt():
        # Keep it simple: disallow indexing (you can change later)
        return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")


    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, "static"),
            "favicon.ico",
            mimetype="image/vnd.microsoft.icon",
        )

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
        if current_user.is_authenticated:
            borrower = BorrowerProfile.query.filter_by(user_id=current_user.id).first()
            if borrower:
                unread = LoanNotification.query.filter_by(
                    borrower_id=borrower.id,
                    is_read=False,
                ).count()
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

    socketio.run(app, host="0.0.0.0", port=5050, debug=True, use_reloader=False)
