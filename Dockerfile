FROM python:3.11-slim

# LibreOffice fuer DOCX→PDF Konvertierung
RUN apt-get update && \
    apt-get install -y --no-install-recommends libreoffice-writer && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies installieren
COPY pyproject.toml ./
COPY src/ ./src/
COPY config/ ./config/
COPY web/ ./web/

RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir -r web/requirements.txt

# Instance-Verzeichnis (wird von Render persistent disk ueberlagert)
RUN mkdir -p /app/web/instance/uploads /app/web/instance/output

EXPOSE 10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "300", "--workers", "1", "web.wsgi:app"]
