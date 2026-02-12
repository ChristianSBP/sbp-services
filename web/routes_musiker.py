"""Musiker-Bereich: Dienstplaene ansehen und herunterladen."""

from __future__ import annotations

from io import BytesIO

from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    send_file, abort,
)
from flask_login import login_required, current_user

from .models import db, GeneratedPlan, IndividualPlan
from .converter import docx_to_pdf

musiker_bp = Blueprint("musiker", __name__, url_prefix="/musiker")


def musiker_or_admin_required(f):
    """Decorator: Fuer Musiker und Admins zugaenglich."""
    from functools import wraps

    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role not in ("musiker", "admin"):
            flash("Zugriff verweigert.", "error")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated


@musiker_bp.route("/")
@musiker_or_admin_required
def dashboard():
    """Musiker-Dashboard: Alphabetische Liste aller Musiker."""
    latest_plan = (
        GeneratedPlan.query
        .filter_by(status="ready")
        .order_by(GeneratedPlan.created_at.desc())
        .first()
    )

    musicians = []
    if latest_plan:
        # Individuelle Plaene laden und sortieren
        plans = IndividualPlan.query.filter_by(
            generated_plan_id=latest_plan.id
        ).all()

        musicians = sorted(plans, key=lambda p: p.sort_key)

    return render_template(
        "musiker/dashboard.html",
        latest_plan=latest_plan,
        musicians=musicians,
    )


@musiker_bp.route("/<int:plan_id>")
@musiker_or_admin_required
def musician_detail(plan_id):
    """Download-Seite fuer einen einzelnen Musiker."""
    ind_plan = IndividualPlan.query.get_or_404(plan_id)
    gen_plan = ind_plan.generated_plan

    return render_template(
        "musiker/download.html",
        musician=ind_plan,
        generated_plan=gen_plan,
    )


@musiker_bp.route("/<int:plan_id>/individual.pdf")
@musiker_or_admin_required
def download_individual_pdf(plan_id):
    """Individuellen Dienstplan als PDF herunterladen (on-demand Konvertierung)."""
    ind_plan = IndividualPlan.query.get_or_404(plan_id)

    if not ind_plan.docx_data:
        flash("Kein Dienstplan vorhanden.", "error")
        return redirect(url_for("musiker.musician_detail", plan_id=plan_id))

    # On-demand PDF konvertieren und cachen
    if not ind_plan.pdf_data:
        pdf_data = docx_to_pdf(ind_plan.docx_data)
        if not pdf_data:
            flash("PDF-Konvertierung fehlgeschlagen.", "error")
            return redirect(url_for("musiker.musician_detail", plan_id=plan_id))
        ind_plan.pdf_data = pdf_data
        db.session.commit()

    filename = f"Dienstplan {ind_plan.display_name}.pdf"

    return send_file(
        BytesIO(ind_plan.pdf_data),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@musiker_bp.route("/<int:plan_id>/collective.pdf")
@musiker_or_admin_required
def download_collective_pdf(plan_id):
    """Kollektiven Dienstplan als PDF herunterladen (on-demand Konvertierung)."""
    ind_plan = IndividualPlan.query.get_or_404(plan_id)
    gen_plan = ind_plan.generated_plan

    if not gen_plan.collective_docx:
        flash("Kein Dienstplan vorhanden.", "error")
        return redirect(url_for("musiker.musician_detail", plan_id=plan_id))

    # On-demand PDF konvertieren und cachen
    if not gen_plan.collective_pdf:
        pdf_data = docx_to_pdf(gen_plan.collective_docx)
        if not pdf_data:
            flash("PDF-Konvertierung fehlgeschlagen.", "error")
            return redirect(url_for("musiker.musician_detail", plan_id=plan_id))
        gen_plan.collective_pdf = pdf_data
        db.session.commit()

    month_range = f"{gen_plan.plan_start.strftime('%m')}-{gen_plan.plan_end.strftime('%m')}"
    filename = f"Dienstplan {gen_plan.plan_start.year} {month_range}.pdf"

    return send_file(
        BytesIO(gen_plan.collective_pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )
