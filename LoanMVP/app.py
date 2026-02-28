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
    send_from_directory,
)
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_migrate import Migrate
from flask_login import LoginManager, current_user

from LoanMVP.config import Config
from LoanMVP.extensions import db, login_manager, migrate, mail, stripe
from LoanMVP.models import User
from LoanMVP.models.loan_models import BorrowerProfile, LoanNotification

import engineio
import engineio.async_drivers.threading
import socketio as sio_pkg


# ---------------------------------------------------------
# Patch engineio BEFORE Flask-SocketIO usage
# ---------------------------------------------------------
if not hasattr(engineio, "async_modes") or "threading" not in getattr(engineio, "async_modes", []):
    engineio.async_modes = ["threading"]
    engineio.Server = engineio.server.Server


# ---------------------------------------------------------
# Flask Extensions (local instances)
# ---------------------------------------------------------
cors = CORS()
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode="threading",
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

    # Core configuration
    app.config.from_object(Config)

    # ✅ Make sure secret key comes from config/env
    app.secret_key = app.config.get("SECRET_KEY")

    # ✅ Remove filesystem sessions on Render (ephemeral)
    app.config.pop("SESSION_TYPE", None)

    # Stripe configuration
    stripe.api_key = app.config.get("STRIPE_SECRET_KEY")

    # Initialize extensions
    cors.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    socketio.init_app(app)
    app.socketio = socketio

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
    def home_redirect():
        return redirect("/cm-dashboard")

    @app.route("/index")
    def index():
        dashboards = [
            ("Admin", "/admin"),
            ("AI", "/ai"),
            ("Auth", "/auth"),
            ("Borrower", "/borrower"),
            ("Borrower AI", "/borrower_ai"),
            ("Compliance", "/compliance"),
            ("Contractors", "/contractors"),
            ("CRM", "/crm"),
            ("Executive", "/executive"),
            ("Intelligence", "/intelligence"),
            ("Loan Officer", "/loan_officer"),
            ("Master", "/master"),
            ("Notifications", "/notifications"),
            ("Processor", "/processor"),
            ("Processor Queue", "/processor"),
            ("Property", "/property"),
            ("System", "/system"),
            ("Tracking", "/track"),
            ("Underwriter", "/underwriter"),
        ]
        return render_template("index.html", dashboards=dashboards)

    # Global error handler
    @app.errorhandler(Exception)
    def handle_any_exception(e):
        print("\n========== REAL TRACEBACK START ==========")
        traceback.print_exc()
        print("========== REAL TRACEBACK END ==========\n")
        tb = traceback.format_exc()
        return Response(f"<pre>{tb}</pre>", mimetype="text/plain"), 500

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, "static"),
            "favicon.ico",
            mimetype="image/vnd.microsoft.icon",
        )

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
    def inject_datetime():
        return dict(datetime=datetime)

    @app.template_filter("currency")
    def currency_format(value):
        try:
            return "${:,.0f}".format(int(value))
        except (ValueError, TypeError):
            return "$0"

    return app


# ---------------------------------------------------------
# Dynamic Blueprint Registration
# ---------------------------------------------------------
def register_blueprints(app):
    routes_dir = os.path.join(os.path.dirname(__file__), "routes")
    if not os.path.exists(routes_dir):
        print("No routes folder found.")
        return

    for file in os.listdir(routes_dir):
        if file.endswith(".py") and not file.startswith("__"):
            mod_name = f"LoanMVP.routes.{file[:-3]}"
            try:
                mod = importlib.import_module(mod_name)
                for attr in dir(mod):
                    obj = getattr(mod, attr)
                    if isinstance(obj, Blueprint):
                        app.register_blueprint(obj)
                        print(f"Registered blueprint: {obj.name} -> {obj.url_prefix}")
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
