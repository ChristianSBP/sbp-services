"""Musiker-Endpoints fuer Planung SBP."""

from io import BytesIO

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt

from ..models import db, Musician, MusicianEnsemble, GeneratedPlan, IndividualPlan

musicians_bp = Blueprint("musicians", __name__, url_prefix="/api/musicians")


@musicians_bp.route("", methods=["GET"])
@jwt_required()
def list_musicians():
    """Alle Musiker sortiert nach Register und Position."""
    musicians = Musician.query.order_by(Musician.sort_order, Musician.register).all()
    return jsonify([m.to_dict() for m in musicians])


@musicians_bp.route("/<int:musician_id>", methods=["GET"])
@jwt_required()
def get_musician(musician_id):
    """Einzelner Musiker mit Details."""
    musician = Musician.query.get_or_404(musician_id)
    return jsonify(musician.to_dict())


@musicians_bp.route("/<int:musician_id>/plans", methods=["GET"])
@jwt_required()
def musician_plans(musician_id):
    """Alle individuellen Plaene eines Musikers."""
    musician = Musician.query.get_or_404(musician_id)
    plans = IndividualPlan.query.filter_by(musician_id=musician_id)\
        .order_by(IndividualPlan.id.desc()).all()

    return jsonify([{
        "id": p.id,
        "generated_plan_id": p.generated_plan_id,
        "display_name": p.display_name,
        "has_docx": p.docx_data is not None,
        "has_pdf": p.pdf_data is not None,
        "plan_start": p.generated_plan.plan_start.isoformat() if p.generated_plan else None,
        "plan_end": p.generated_plan.plan_end.isoformat() if p.generated_plan else None,
    } for p in plans])


@musicians_bp.route("/plans/<int:plan_id>/individual.docx", methods=["GET"])
@jwt_required()
def download_individual_docx(plan_id):
    """Individuellen Dienstplan als DOCX herunterladen."""
    ind_plan = IndividualPlan.query.get_or_404(plan_id)
    if not ind_plan.docx_data:
        return jsonify({"error": "Kein DOCX vorhanden."}), 404

    filename = f"Dienstplan {ind_plan.display_name}.docx"
    return send_file(
        BytesIO(ind_plan.docx_data),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=filename,
    )


@musicians_bp.route("/plans/<int:plan_id>/individual.pdf", methods=["GET"])
@jwt_required()
def download_individual_pdf(plan_id):
    """Individuellen Dienstplan als PDF herunterladen (on-demand Konvertierung)."""
    ind_plan = IndividualPlan.query.get_or_404(plan_id)

    if not ind_plan.docx_data:
        return jsonify({"error": "Kein Dienstplan vorhanden."}), 404

    # On-demand PDF konvertieren und cachen
    if not ind_plan.pdf_data:
        from ..services.converter import docx_to_pdf
        pdf_data = docx_to_pdf(ind_plan.docx_data)
        if not pdf_data:
            return jsonify({"error": "PDF-Konvertierung fehlgeschlagen."}), 500
        ind_plan.pdf_data = pdf_data
        db.session.commit()

    filename = f"Dienstplan {ind_plan.display_name}.pdf"
    return send_file(
        BytesIO(ind_plan.pdf_data),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@musicians_bp.route("/plans/<int:plan_id>/collective.pdf", methods=["GET"])
@jwt_required()
def download_collective_pdf(plan_id):
    """Kollektiven Dienstplan als PDF herunterladen (on-demand Konvertierung)."""
    ind_plan = IndividualPlan.query.get_or_404(plan_id)
    gen_plan = ind_plan.generated_plan

    if not gen_plan or not gen_plan.collective_docx:
        return jsonify({"error": "Kein Dienstplan vorhanden."}), 404

    if not gen_plan.collective_pdf:
        from ..services.converter import docx_to_pdf
        pdf_data = docx_to_pdf(gen_plan.collective_docx)
        if not pdf_data:
            return jsonify({"error": "PDF-Konvertierung fehlgeschlagen."}), 500
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


# --- Alphabetische Musiker-Liste (fuer Musiker-Bereich) ---

@musicians_bp.route("/directory", methods=["GET"])
@jwt_required()
def musician_directory():
    """Alphabetische Musiker-Liste mit aktuellstem Plan-Status.

    Fuer den Musiker-Download-Bereich: zeigt alle Musiker mit
    Links zu ihren individuellen Plaenen.
    """
    # Neuester generierter Plan
    latest_plan = GeneratedPlan.query\
        .filter_by(status="ready")\
        .order_by(GeneratedPlan.created_at.desc())\
        .first()

    if not latest_plan:
        return jsonify({"musicians": [], "plan": None})

    ind_plans = IndividualPlan.query\
        .filter_by(generated_plan_id=latest_plan.id)\
        .all()

    # Sortiert nach Nachname (vakante am Ende)
    sorted_plans = sorted(ind_plans, key=lambda p: p.sort_key)

    musicians_list = []
    for p in sorted_plans:
        musicians_list.append({
            "id": p.id,
            "display_name": p.display_name,
            "is_vakant": p.is_vakant,
            "has_individual_pdf": p.pdf_data is not None or p.docx_data is not None,
        })

    return jsonify({
        "musicians": musicians_list,
        "plan": latest_plan.to_dict(),
    })
