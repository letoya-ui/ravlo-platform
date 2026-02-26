from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
import stripe

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()


stripe.api_key = None  # Set in app.py

__all__ = ["db", "login_manager", "migrate", "mail", "stripe"]
