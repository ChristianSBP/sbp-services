"""API-Konfiguration fuer Planung SBP."""

import os
from pathlib import Path


class Config:
    """Flask-Konfiguration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-in-production")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = 86400  # 24 Stunden

    # PostgreSQL (Render) oder SQLite (lokal)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///sbp_planung.db"
    )
    # Render setzt postgres:// statt postgresql://
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # Pfade
    BASE_DIR = Path(__file__).parent
    PROJECT_ROOT = BASE_DIR.parent
    UPLOAD_FOLDER = str(BASE_DIR / "instance" / "uploads")
    OUTPUT_FOLDER = str(BASE_DIR / "instance" / "output")

    # Admin-Email (wird beim Setup vorausgefuellt)
    ADMIN_EMAIL = "saalfrank@sbphil.music"
