"""WSGI-Entrypoint fuer Gunicorn."""

import sys
import os

# Projekt-Root in den Python-Pfad einfuegen
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from api.app import create_app

app = create_app()
