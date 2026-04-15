import os
from datetime import timedelta

from dotenv import load_dotenv

# ===================================================
# 🏗 BASE CONFIG PATH SETUP
# ===================================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
INSTANCE_PATH = os.path.join(BASE_DIR, "instance")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
LOG_FOLDER = os.path.join(BASE_DIR, "logs")
DEFAULT_SQLITE_PATH = os.path.join(PROJECT_ROOT, "instance", "local.db")
DEFAULT_SQLITE_URI = "sqlite:///" + DEFAULT_SQLITE_PATH.replace("\\", "/")

for path in (INSTANCE_PATH, UPLOAD_FOLDER, LOG_FOLDER):
    os.makedirs(path, exist_ok=True)

load_dotenv()

TRUE_VALUES = {"1", "true", "yes", "on"}


def _resolve_database_uri() -> str:
    raw_uri = (os.getenv("DATABASE_URL") or "").strip()
    if not raw_uri:
        return DEFAULT_SQLITE_URI

    # Keep local development on the shared workspace DB instead of a cwd-dependent file.
    if raw_uri in {"sqlite:///local.db", "sqlite://local.db"}:
        return DEFAULT_SQLITE_URI

    sqlite_prefix = "sqlite:///"
    if raw_uri.startswith(sqlite_prefix):
        sqlite_path = raw_uri[len(sqlite_prefix):]
        if sqlite_path and not os.path.isabs(sqlite_path):
            return "sqlite:///" + os.path.abspath(os.path.join(PROJECT_ROOT, sqlite_path)).replace("\\", "/")

    return raw_uri


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in TRUE_VALUES


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _env_list(name: str, default: str = ""):
    raw = os.environ.get(name, default).strip()
    if not raw:
        return []
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


def _env_origin_list(name: str, *fallback_env_names: str, default: str = ""):
    values = _env_list(name, default)
    if values:
        return values

    for fallback_name in fallback_env_names:
        values = _env_list(fallback_name)
        if values:
            return values

    return []

# ===================================================
# ⚙️ MAIN CONFIG CLASS
# ===================================================
 
class Config:
    ENV_NAME = os.environ.get("FLASK_ENV", "production").strip().lower()
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_only_change_me")
    SECURITY_PASSWORD_SALT = os.getenv("SECURITY_PASSWORD_SALT", "dev_salt_change_me")

    DEBUG = _env_bool("FLASK_DEBUG", False)

    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    SESSION_COOKIE_NAME = "ravlo_session"
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    SESSION_PROTECTION = "basic"
    SESSION_REFRESH_EACH_REQUEST = True
    WTF_CSRF_TIME_LIMIT = 60 * 60 * 2
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "https")
 
    # DATABASE
    SQLALCHEMY_DATABASE_URI = _resolve_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False


    # STRIPE
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_BILLING_ENABLED = _env_bool("STRIPE_BILLING_ENABLED", False)
    STRIPE_PRICE_CORE = os.environ.get("STRIPE_PRICE_CORE", "")
    STRIPE_PRICE_PRO = os.environ.get("STRIPE_PRICE_PRO", "")
    STRIPE_PRICE_ENTERPRISE = os.environ.get("STRIPE_PRICE_ENTERPRISE", "")
    STRIPE_PRICE_BROKERAGE_SMALL_TEAM = os.environ.get("STRIPE_PRICE_BROKERAGE_SMALL_TEAM", "")
    STRIPE_PRICE_INDIVIDUAL_LOAN_OFFICER = os.environ.get("STRIPE_PRICE_INDIVIDUAL_LOAN_OFFICER", "")
    STRIPE_PRICE_FEATURED_PARTNER = os.environ.get("STRIPE_PRICE_FEATURED_PARTNER", "")
    STRIPE_PRICE_PREFERRED_PARTNER = os.environ.get("STRIPE_PRICE_PREFERRED_PARTNER", "")
    STRIPE_PRICE_BASIC_LISTING = os.environ.get("STRIPE_PRICE_BASIC_LISTING", "")
    STRIPE_PRICE_OPERATOR = os.environ.get("STRIPE_PRICE_OPERATOR", "")
    STRIPE_PRICE_EXPLORER = os.environ.get("STRIPE_PRICE_EXPLORER", "")

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.sendgrid.net")
    MAIL_PORT = _env_int("MAIL_PORT", 587)
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", True)
    MAIL_USE_SSL = _env_bool("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", MAIL_USERNAME)

    SOCKETIO_MESSAGE_QUEUE = os.environ.get("SOCKETIO_MESSAGE_QUEUE") or None
    SOCKETIO_ASYNC_MODE = os.environ.get("SOCKETIO_ASYNC_MODE", "threading").strip().lower()
    CORS_ORIGINS = _env_origin_list("CORS_ORIGINS", "APP_ORIGIN", "RENDER_EXTERNAL_URL")
    SOCKETIO_CORS_ALLOWED_ORIGINS = _env_origin_list(
        "SOCKETIO_CORS_ALLOWED_ORIGINS",
        "CORS_ORIGINS",
        "APP_ORIGIN",
        "RENDER_EXTERNAL_URL",
    )
    CORS_SUPPORTS_CREDENTIALS = _env_bool("CORS_SUPPORTS_CREDENTIALS", True)

    UPLOAD_FOLDER = UPLOAD_FOLDER
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024

    # TWILIO
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")

    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
    SENDGRID_FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@ravlohq.com")

    # AI
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    AI_MODEL = os.environ.get("AI_MODEL", "gpt-4-turbo-preview")
    AI_TIMEOUT = _env_int("AI_TIMEOUT", 30)
    RENOVATION_ENGINE_URL = os.getenv(
        "RENOVATION_ENGINE_URL",
        "https://nondiscoverable-henry-metempirical.ngrok-free.dev"
    ).rstrip("/")

    RENOVATION_API_KEY = os.getenv("RENOVATION_API_KEY", "")

    GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")

    # RENTCAST
    RENTCAST_API_KEY = os.environ.get("RENTCAST_API_KEY", "").strip()
    RENTCAST_BASE_URL = os.environ.get("RENTCAST_BASE_URL", "https://api.rentcast.io/v1").strip()
    RENTCAST_TIMEOUT = _env_int("RENTCAST_TIMEOUT", 12)
    RENTCAST_COMP_COUNT = _env_int("RENTCAST_COMP_COUNT", 15)
    RENTCAST_MAX_RADIUS = _env_float("RENTCAST_MAX_RADIUS", 2)
    RENTCAST_DAYS_OLD = _env_int("RENTCAST_DAYS_OLD", 180)
    RENTCAST_LOOKUP_SUBJECT_ATTRS = _env_bool("RENTCAST_LOOKUP_SUBJECT_ATTRS", True)

    PROPERTY_PROVIDER = os.environ.get("PROPERTY_PROVIDER", "rentcast")
    ENABLE_PROPERTY_CACHE = _env_bool("ENABLE_PROPERTY_CACHE", True)
 
    RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
     
    COMPANY_NAME = os.environ.get("COMPANY_NAME", "Ravlo")
    COMPANY_EMAIL = os.environ.get("COMPANY_EMAIL", "info@ravlohq.com")
    COMPANY_PHONE = os.environ.get("COMPANY_PHONE", "")
    COMPANY_ADDRESS = os.environ.get("COMPANY_ADDRESS", "")
    OWNER_ADMIN_EMAIL = os.environ.get("OWNER_ADMIN_EMAIL", "letoya@ravlohq.com").strip().lower()
    SINGLE_ADMIN_MODE = _env_bool("SINGLE_ADMIN_MODE", False)

    LOG_FOLDER = LOG_FOLDER

    ENABLE_AI_CHAT = _env_bool("ENABLE_AI_CHAT", True)
    ENABLE_LOAN_ENGINE = _env_bool("ENABLE_LOAN_ENGINE", True)
    ENABLE_CONSTRUCTION_MODE = _env_bool("ENABLE_CONSTRUCTION_MODE", False)
    ENABLE_DEVELOPER_TOOLS = _env_bool("ENABLE_DEVELOPER_TOOLS", False)

    BYPASS_PARTNER_SUBSCRIPTION = _env_bool("BYPASS_PARTNER_SUBSCRIPTION", False)
    FREE_PARTNER_MODE = _env_bool("FREE_PARTNER_MODE", False)
    BETA_SUBSCRIPTION_BYPASS = _env_bool("BETA_SUBSCRIPTION_BYPASS", False)
    BETA_ACCESS_AUTO_APPROVE = _env_bool("BETA_ACCESS_AUTO_APPROVE", False)

    @classmethod
    def validate(cls):
        return


class DevelopmentConfig(Config):
    ENV_NAME = "development"
    DEBUG = _env_bool("FLASK_DEBUG", True)
    SOCKETIO_ASYNC_MODE = os.environ.get("SOCKETIO_ASYNC_MODE", "threading").strip().lower()
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "http")
    ENABLE_DEVELOPER_TOOLS = _env_bool("ENABLE_DEVELOPER_TOOLS", True)
    CORS_ORIGINS = _env_list("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5050,http://127.0.0.1:5050")
    SOCKETIO_CORS_ALLOWED_ORIGINS = _env_list(
        "SOCKETIO_CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5050,http://127.0.0.1:5050",
    )
    BYPASS_PARTNER_SUBSCRIPTION = _env_bool("BYPASS_PARTNER_SUBSCRIPTION", True)
    FREE_PARTNER_MODE = _env_bool("FREE_PARTNER_MODE", True)
    BETA_SUBSCRIPTION_BYPASS = _env_bool("BETA_SUBSCRIPTION_BYPASS", True)
    BETA_ACCESS_AUTO_APPROVE = _env_bool("BETA_ACCESS_AUTO_APPROVE", True)


class ProductionConfig(Config):
    ENV_NAME = "production"
    DEBUG = False
    SOCKETIO_ASYNC_MODE = os.environ.get("SOCKETIO_ASYNC_MODE", "eventlet").strip().lower()
    ENABLE_DEVELOPER_TOOLS = False

    @classmethod
    def validate(cls):
        missing = []
        if not cls.SECRET_KEY or cls.SECRET_KEY == "dev_only_change_me":
            missing.append("SECRET_KEY")
        if not cls.SECURITY_PASSWORD_SALT or cls.SECURITY_PASSWORD_SALT == "dev_salt_change_me":
            missing.append("SECURITY_PASSWORD_SALT")
        if not cls.SQLALCHEMY_DATABASE_URI:
            missing.append("DATABASE_URL")
        elif cls.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
            missing.append("DATABASE_URL (must not be sqlite in production)")
        if not cls.CORS_ORIGINS:
            missing.append("CORS_ORIGINS")
        if not cls.SOCKETIO_CORS_ALLOWED_ORIGINS:
            missing.append("SOCKETIO_CORS_ALLOWED_ORIGINS")
        if cls.SOCKETIO_ASYNC_MODE not in {"eventlet", "threading"}:
            missing.append("SOCKETIO_ASYNC_MODE (supported: eventlet, threading)")
        if missing:
            raise RuntimeError(
                "Production configuration is incomplete: " + ", ".join(missing)
            )


def get_config():
    env_name = os.environ.get("FLASK_ENV", "production").strip().lower()
    if env_name in {"dev", "development", "local"}:
        return DevelopmentConfig
    return ProductionConfig
