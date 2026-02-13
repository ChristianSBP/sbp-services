# === Stage 1: Frontend Build ===
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# === Stage 2: Python API + LibreOffice ===
FROM python:3.11-slim

WORKDIR /app

# System-Dependencies: LibreOffice + Ghostscript
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice-writer \
        ghostscript && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Python-Dependencies zuerst (Cache-freundlich)
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

COPY api/requirements.txt ./api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

# App-Code kopieren
COPY config/ ./config/
COPY api/ ./api/

# Frontend-Build aus Stage 1 kopieren
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Instance-Verzeichnis
RUN mkdir -p /app/instance /app/api/instance/uploads /app/api/instance/output

# Umgebungsvariablen
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 10000

# Gunicorn: 1 Worker, grosszuegiger Timeout fuer PDF-Generierung
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "300", "--workers", "1", "--log-level", "info", "--access-logfile", "-", "--error-logfile", "-", "api.wsgi:app"]
