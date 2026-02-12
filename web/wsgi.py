"""WSGI Entrypoint fuer Gunicorn."""

import sys
import os

# Sicherstellen dass das Projektverzeichnis im Python-Pfad ist
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from web.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
