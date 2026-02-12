"""Admin-Bereich: Dashboard, Generator, Downloads."""

from __future__ import annotations

import os
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import bcrypt
from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, send_file, current_app,
)
from flask_login import login_required, current_user

from .models import db, User, GeneratedPlan, IndividualPlan
from .generator import run_generator
from .converter import docx_to_pdf, is_libreoffice_available

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    """Decorator: Nur fuer Admin-Benutzer."""
    from functools import wraps

    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != "admin":
            flash("Zugriff verweigert.", "error")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated


@admin_bp.route("/")
@admin_required
def dashboard():
    """Admin-Dashboard mit letztem generierten Plan."""
    latest_plan = (
        GeneratedPlan.query
        .filter_by(status="ready")
        .order_by(GeneratedPlan.created_at.desc())
        .first()
    )
    musiker_user = User.query.filter_by(role="musiker").first()
    has_musiker_pw = musiker_user is not None

    return render_template(
        "admin/dashboard.html",
        latest_plan=latest_plan,
        has_musiker_pw=has_musiker_pw,
    )


@admin_bp.route("/generate", methods=["GET", "POST"])
@admin_required
def generate():
    """Dienstplan generieren: Upload + Zeitraum."""
    if request.method == "POST":
        # Datei pruefen
        if "jahresplan" not in request.files:
            flash("Keine Datei ausgewaehlt.", "error")
            return redirect(request.url)

        file = request.files["jahresplan"]
        if file.filename == "":
            flash("Keine Datei ausgewaehlt.", "error")
            return redirect(request.url)

        if not file.filename.endswith(".xlsx"):
            flash("Bitte eine .xlsx-Datei hochladen.", "error")
            return redirect(request.url)

        # Datum parsen
        try:
            start_str = request.form.get("start_date", "2026-03-01")
            end_str = request.form.get("end_date", "2026-05-31")
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Ungueltiges Datumsformat.", "error")
            return redirect(request.url)

        # Jahr aus Dateiname oder Start-Datum
        year = start_date.year

        # Datei speichern
        upload_path = Path(current_app.config["UPLOAD_FOLDER"])
        upload_path.mkdir(parents=True, exist_ok=True)
        filepath = upload_path / file.filename
        file.save(str(filepath))

        # Plan-Eintrag erstellen
        plan_entry = GeneratedPlan(
            plan_start=start_date,
            plan_end=end_date,
            jahresplan_filename=file.filename,
            status="generating",
        )
        db.session.add(plan_entry)
        db.session.commit()

        try:
            # Generator ausfuehren
            result = run_generator(filepath, start_date, end_date, year=year)

            # Kollektiver Plan speichern (nur DOCX — PDF on-demand)
            plan_entry.collective_docx = result["collective_docx"]

            # Individuelle Plaene speichern (nur DOCX — PDF on-demand)
            for ip in result["individual_plans"]:
                ind = IndividualPlan(
                    generated_plan_id=plan_entry.id,
                    musician_name=ip["name"],
                    position=ip["position"],
                    is_vakant=ip["is_vakant"],
                    docx_data=ip["docx"],
                )
                db.session.add(ind)

            plan_entry.status = "ready"
            db.session.commit()

            summary = result["violations_summary"]
            flash(
                f"Dienstplan erstellt! {summary['errors']} Fehler, "
                f"{summary['warnings']} Warnungen, {summary['infos']} Hinweise. "
                f"{len(result['individual_plans'])} Einzelplaene generiert.",
                "success",
            )

        except Exception as e:
            plan_entry.status = "error"
            db.session.commit()
            flash(f"Fehler bei der Generierung: {str(e)}", "error")

        finally:
            # Upload-Datei aufraeumen
            if filepath.exists():
                filepath.unlink()

        return redirect(url_for("admin.dashboard"))

    return render_template(
        "admin/generate.html",
        lo_available=is_libreoffice_available(),
    )


@admin_bp.route("/download/<int:plan_id>/collective")
@admin_required
def download_collective_docx(plan_id):
    """Kollektiven Dienstplan als DOCX herunterladen."""
    plan = GeneratedPlan.query.get_or_404(plan_id)
    if not plan.collective_docx:
        flash("Keine DOCX-Datei vorhanden.", "error")
        return redirect(url_for("admin.dashboard"))

    month_range = f"{plan.plan_start.strftime('%m')}-{plan.plan_end.strftime('%m')}"
    filename = f"Dienstplan {plan.plan_start.year} {month_range}.docx"

    return send_file(
        BytesIO(plan.collective_docx),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=filename,
    )


@admin_bp.route("/download/<int:plan_id>/collective-pdf")
@admin_required
def download_collective_pdf(plan_id):
    """Kollektiven Dienstplan als PDF herunterladen (on-demand Konvertierung)."""
    plan = GeneratedPlan.query.get_or_404(plan_id)

    if not plan.collective_docx:
        flash("Kein Dienstplan vorhanden.", "error")
        return redirect(url_for("admin.dashboard"))

    # On-demand PDF konvertieren und cachen
    if not plan.collective_pdf:
        pdf_data = docx_to_pdf(plan.collective_docx)
        if not pdf_data:
            flash("PDF-Konvertierung fehlgeschlagen.", "error")
            return redirect(url_for("admin.dashboard"))
        plan.collective_pdf = pdf_data
        db.session.commit()

    month_range = f"{plan.plan_start.strftime('%m')}-{plan.plan_end.strftime('%m')}"
    filename = f"Dienstplan {plan.plan_start.year} {month_range}.pdf"

    return send_file(
        BytesIO(plan.collective_pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@admin_bp.route("/musiker-password", methods=["POST"])
@admin_required
def set_musiker_password():
    """Musiker-Zugangspasswort setzen oder aendern."""
    password = request.form.get("musiker_password", "")
    if not password or len(password) < 4:
        flash("Musiker-Passwort muss mindestens 4 Zeichen lang sein.", "error")
        return redirect(url_for("admin.dashboard"))

    hashed = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    musiker_user = User.query.filter_by(role="musiker").first()
    if musiker_user:
        musiker_user.password_hash = hashed
    else:
        musiker_user = User(
            email=None,
            password_hash=hashed,
            role="musiker",
        )
        db.session.add(musiker_user)

    db.session.commit()
    flash("Musiker-Passwort gesetzt.", "success")
    return redirect(url_for("admin.dashboard"))
