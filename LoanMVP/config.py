print(">>> Loaded config from:", __file__)

from datetime import timedelta
from dotenv import load_dotenv
import os

# ===================================================
# 🏗 BASE CONFIG PATH SETUP
# ===================================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_PATH = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_PATH, exist_ok=True)

load_dotenv()

# ===================================================
# ⚙️ MAIN CONFIG CLASS
# ===================================================
 
class Config:
    # --------------------------------------------------
    # 🔐 CORE APP SETTINGS
    # --------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_only_change_me")
    SECURITY_PASSWORD_SALT = os.getenv("SECURITY_PASSWORD_SALT", "dev_salt_change_me")

    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")

    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    SESSION_PROTECTION = "strong"

    # --------------------------------------------------
    # 🗄 DATABASE
    # --------------------------------------------------
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres@localhost:5432/loanmvp_db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --------------------------------------------------
    # 💳 STRIPE
    # --------------------------------------------------
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    # --------------------------------------------------
    # 📧 MAIL SETTINGS
    # --------------------------------------------------
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", MAIL_USERNAME)

    # --------------------------------------------------
    # 📡 SOCKETIO
    # --------------------------------------------------
    SOCKETIO_MESSAGE_QUEUE = os.environ.get("SOCKETIO_MESSAGE_QUEUE", None)
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*"

    # --------------------------------------------------
    # 🌍 CORS
    # --------------------------------------------------
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
    CORS_SUPPORTS_CREDENTIALS = True

    # --------------------------------------------------
    # 📁 FILE UPLOADS
    # --------------------------------------------------
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB

    # --------------------------------------------------
    # 📲 TWILIO
    # --------------------------------------------------
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")

    # --------------------------------------------------
    # 📩 SENDGRID
    # --------------------------------------------------
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
    SENDGRID_FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@caughmanmason.com")

    # --------------------------------------------------
    # 🤖 AI SETTINGS
    # --------------------------------------------------
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    AI_MODEL = os.environ.get("AI_MODEL", "gpt-4-turbo-preview")
    AI_TIMEOUT = int(os.environ.get("AI_TIMEOUT", 30))

    GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")

    # =========================================================
    # 🏠 RENTCAST (Property Data + AVM)
    # =========================================================
    RENTCAST_API_KEY = os.environ.get("RENTCAST_API_KEY", "").strip()
    RENTCAST_BASE_URL = os.environ.get("RENTCAST_BASE_URL", "https://api.rentcast.io/v1").strip()
    RENTCAST_TIMEOUT = int(os.environ.get("RENTCAST_TIMEOUT", 12))

    # AVM tuning (used by BOTH value + rent estimates)
    RENTCAST_COMP_COUNT = int(os.environ.get("RENTCAST_COMP_COUNT", 15))
    RENTCAST_MAX_RADIUS = float(os.environ.get("RENTCAST_MAX_RADIUS", 2))   # miles
    RENTCAST_DAYS_OLD = int(os.environ.get("RENTCAST_DAYS_OLD", 180))

    RENTCAST_LOOKUP_SUBJECT_ATTRS = os.environ.get(
        "RENTCAST_LOOKUP_SUBJECT_ATTRS",
        "true"
    ).lower() in ("1", "true", "yes")

    # Feature toggles
    PROPERTY_PROVIDER = os.environ.get("PROPERTY_PROVIDER", "rentcast")
    ENABLE_PROPERTY_CACHE = os.environ.get("ENABLE_PROPERTY_CACHE", "true").lower() in ("1", "true", "yes")

    # --------------------------------------------------
    # 🏢 BRAND INFO
    # --------------------------------------------------
    COMPANY_NAME = "Caughman Mason Realty Group"
    COMPANY_EMAIL = "info@caughmanmason.com"
    COMPANY_PHONE = "(845) 395-6627"
    COMPANY_ADDRESS = "33 Maple Fields Dr Middletown NY 10940"

    # --------------------------------------------------
    # 📝 LOGGING
    # --------------------------------------------------
    LOG_FOLDER = os.path.join(BASE_DIR, "logs")
    os.makedirs(LOG_FOLDER, exist_ok=True)

    # --------------------------------------------------
    # 🚀 FEATURE TOGGLES
    # --------------------------------------------------
    ENABLE_AI_CHAT = True
    ENABLE_LOAN_ENGINE = True
    ENABLE_CONSTRUCTION_MODE = False
    ENABLE_DEVELOPER_TOOLS = True
