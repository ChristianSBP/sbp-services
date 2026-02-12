FROM python:3.11-slim

WORKDIR /app

# System-Dependencies fuer pdfplumber (ghostscript) und LibreOffice
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

COPY web/requirements.txt ./web/requirements.txt
RUN pip install --no-cache-dir -r web/requirements.txt

# App-Code kopieren
COPY config/ ./config/
COPY web/ ./web/

# Instance-Verzeichnis
RUN mkdir -p /app/instance /app/web/instance/uploads /app/web/instance/output

# Umgebungsvariablen
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 10000

# Gunicorn: 1 Worker, grosszuegiger Timeout fuer PDF-Generierung
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "300", "--workers", "1", "--log-level", "info", "--access-logfile", "-", "--error-logfile", "-", "web.wsgi:app"]
