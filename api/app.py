"""Flask App Factory fuer Planung SBP — REST-API."""

import os
import sys
from pathlib import Path

from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate

from .config import Config
from .models import db

# Sicherstellen, dass das Projekt-Root im Python-Pfad ist
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

jwt = JWTManager()
migrate = Migrate()


def create_app(config_class=Config):
    """Erstellt und konfiguriert die Flask-App."""

    app = Flask(
        __name__,
        static_folder=str(Path(__file__).parent / "static"),
        static_url_path="/static",
    )
    app.config.from_object(config_class)

    # Verzeichnisse sicherstellen
    os.makedirs(app.config.get("UPLOAD_FOLDER", "instance/uploads"), exist_ok=True)
    os.makedirs(app.config.get("OUTPUT_FOLDER", "instance/output"), exist_ok=True)

    # Erweiterungen initialisieren
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ---------- API Blueprints ----------
    from .routes.auth import auth_bp
    from .routes.events import events_bp
    from .routes.projects import projects_bp
    from .routes.seasons import seasons_bp
    from .routes.musicians import musicians_bp
    from .routes.generator import generator_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(seasons_bp)
    app.register_blueprint(musicians_bp)
    app.register_blueprint(generator_bp)

    # ---------- Health Check ----------
    @app.route("/api/healthz")
    def healthz():
        return {"status": "ok"}, 200

    # ---------- React SPA Serving ----------
    # Im Production-Mode wird das React-Build aus frontend/dist served
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        """Serve React SPA — alle nicht-API-Routen gehen an index.html."""
        if path and (frontend_dist / path).exists():
            return send_from_directory(str(frontend_dist), path)
        if frontend_dist.exists() and (frontend_dist / "index.html").exists():
            return send_from_directory(str(frontend_dist), "index.html")
        return {"message": "Planung SBP API", "status": "running"}, 200

    # ---------- Datenbank erstellen ----------
    with app.app_context():
        db.create_all()

    return app
