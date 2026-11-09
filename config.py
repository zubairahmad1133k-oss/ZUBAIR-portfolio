"""Application configuration for Zubair OS.

All secrets and deployment-specific values come from environment variables
(or a local .env file). Nothing sensitive is hardcoded here.
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


ON_VERCEL = bool(os.environ.get("VERCEL"))


def _database_url() -> str:
    """SQLite locally; PostgreSQL when DATABASE_URL is set (Render/Vercel + Supabase)."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        if ON_VERCEL:
            raise RuntimeError(
                "DATABASE_URL is not set. Vercel cannot keep a SQLite file, so add your Supabase "
                "PostgreSQL connection string as DATABASE_URL in the Vercel project settings."
            )
        return "sqlite:///" + str(BASE_DIR / "instance" / "zubair_os.db")
    # Some hosts still hand out the legacy "postgres://" scheme.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


_DB_URL = _database_url()


def _engine_options(url: str) -> dict:
    options = {"pool_pre_ping": True}
    if url.startswith("postgresql"):
        # Small pool: serverless hosts and Supabase poolers dislike many open connections.
        options.update(pool_size=2, max_overflow=0, pool_recycle=300)
    return options


class Config:
    ENV_NAME = "development"
    SECRET_KEY = os.environ.get("SECRET_KEY", "").strip() or None

    SQLALCHEMY_DATABASE_URI = _DB_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(_DB_URL)

    # Sessions / cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # One-time web setup of the first admin (needed on hosts without a terminal).
    ADMIN_SETUP_TOKEN = os.environ.get("ADMIN_SETUP_TOKEN", "").strip() or None

    # Optional AI explanations in the Analyst page. Leave blank to use rule-based analysis only.
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip() or None
    ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "").strip() or "claude-sonnet-5-5"

    # Uploads
    # Vercel's disk is read-only/temporary, so uploads are switched off there.
    UPLOADS_ENABLED = not ON_VERCEL
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "").strip() or (
        "/tmp/zubair_os_uploads" if ON_VERCEL else str(BASE_DIR / "uploads")
    )
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    PUBLIC_MEDIA_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    # Rate limiting (in-memory by default; fine for a single worker)
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    # Public site details (taken from your brief; nothing invented)
    SITE_URL = os.environ.get("SITE_URL", "").strip().rstrip("/")
    SITE = {
        "name": "Zubair OS",
        "owner": "Zubair Ahmad",
        "title": "Zubair Ahmad | Software Developer & AI Product Builder",
        "description": (
            "Zubair Ahmad — Software Developer and AI Product Builder. "
            "Explore digital products, software projects and development services."
        ),
        "email": "zubairahmad1133k@gmail.com",
        "whatsapp_display": "+92 302 5852709",
        "whatsapp_url": "https://wa.me/923025852709",
    }


class DevelopmentConfig(Config):
    DEBUG = False  # use `flask run --debug` when you want the debugger


class ProductionConfig(Config):
    ENV_NAME = "production"
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"


class TestingConfig(Config):
    ENV_NAME = "testing"
    TESTING = True
    SECRET_KEY = "testing-only-not-a-real-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    ADMIN_SETUP_TOKEN = "test-setup-token"


_CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(name: str | None = None):
    name = (name or os.environ.get("APP_ENV", "development")).lower()
    try:
        return _CONFIGS[name]
    except KeyError:
        raise RuntimeError(
            f"Unknown APP_ENV '{name}'. Use one of: {', '.join(_CONFIGS)}."
        )
