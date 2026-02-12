"""Web-App Konfiguration."""

import os
from pathlib import Path


class Config:
    """Flask-Konfiguration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///sbp.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # Pfade
    BASE_DIR = Path(__file__).parent
    UPLOAD_FOLDER = str(BASE_DIR / "instance" / "uploads")
    OUTPUT_FOLDER = str(BASE_DIR / "instance" / "output")

    # Admin-Email (wird beim Setup vorausgefuellt)
    ADMIN_EMAIL = "saalfrank@sbphil.music"
