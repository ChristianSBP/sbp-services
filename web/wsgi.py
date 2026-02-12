"""WSGI Entrypoint fuer Gunicorn."""

from web.app import create_app

app = create_app()
