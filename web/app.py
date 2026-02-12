"""Flask App Factory fuer SBP Interne Services."""

import os
from pathlib import Path

from flask import Flask
from flask_login import LoginManager

from .config import Config
from .models import db, User


login_manager = LoginManager()


def create_app(config_class=Config):
    """Erstellt und konfiguriert die Flask-App."""
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.config.from_object(config_class)

    # Verzeichnisse sicherstellen
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)

    # Erweiterungen initialisieren
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Bitte einloggen."

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints registrieren
    from .routes_auth import auth_bp
    from .routes_admin import admin_bp
    from .routes_musiker import musiker_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(musiker_bp)

    # Root-Route
    @app.route("/")
    def index():
        from flask import redirect, url_for
        from flask_login import current_user

        if current_user.is_authenticated:
            if current_user.role == "admin":
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("musiker.dashboard"))
        return redirect(url_for("auth.login"))

    # Datenbank erstellen
    with app.app_context():
        db.create_all()

    return app
