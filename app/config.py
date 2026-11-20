"""Application configuration.

Reads all settings from environment variables so the same code runs locally
(with a local PostgreSQL instance) and on Vercel (with Supabase).
"""
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
# Only load .env when it exists; on Vercel values come from the platform.
load_dotenv(BASE_DIR / ".env", override=False)


class Config:
    """Base configuration shared by every environment."""

    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-only-secret-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Storage mode: "local" writes to ./static/uploads, "supabase" uses the
    # Supabase Storage REST API. Kept behind one switch for easy deployment.
    STORAGE_MODE = os.getenv("STORAGE_MODE", "local").lower()
    UPLOAD_FOLDER = str(BASE_DIR / "static" / "courseware")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB per upload

    SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "courseware")

    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv(
        "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
    )
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    @staticmethod
    def database_url():
        """Build the SQLAlchemy URL from either DATABASE_URL or PG* vars."""
        url = os.getenv("DATABASE_URL", "").strip()
        if url:
            # Supabase / Vercel provide a postgres:// URL; SQLAlchemy needs the
            # psycopg2 driver name in the scheme.
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg2://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return url

        from sqlalchemy.engine import URL

        return URL.create(
            drivername="postgresql+psycopg2",
            username=os.getenv("PGUSER", "postgres"),
            password=os.getenv("PGPASSWORD", ""),
            host=os.getenv("PGHOST", "localhost"),
            port=int(os.getenv("PGPORT", "5432")),
            database=os.getenv("PGDATABASE", "SOE206_CW1"),
        )


class DevelopmentConfig(Config):
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"


class ProductionConfig(Config):
    DEBUG = False


def get_config(name=None):
    """Return a config class by name, defaulting to development."""
    name = (name or os.getenv("FLASK_ENV", "development")).lower()
    return {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
    }.get(name, DevelopmentConfig)
