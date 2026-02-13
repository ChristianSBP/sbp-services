"""Generator-Endpoints fuer Planung SBP — Dienstplan erzeugen."""

from io import BytesIO
from datetime import date

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt

from ..models import db, GeneratedPlan, IndividualPlan, Season

generator_bp = Blueprint("generator", __name__, url_prefix="/api/generator")


@generator_bp.route("/generate", methods=["POST"])
@jwt_required()
def generate():
    """Dienstplan generieren aus DB-Events.

    Erwartet: { season_id, start_date, end_date }
    """
    jwt_data = get_jwt()
    if jwt_data.get("role") != "admin":
        return jsonify({"error": "Nur Admin darf Dienstplaene generieren."}), 403

    data = request.get_json()
    season_id = data.get("season_id")
    start_str = data.get("start_date")
    end_str = data.get("end_date")

    if not season_id or not start_str or not end_str:
        return jsonify({"error": "season_id, start_date und end_date erforderlich."}), 400

    season = Season.query.get(season_id)
    if not season:
        return jsonify({"error": "Spielzeit nicht gefunden."}), 404

    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except ValueError:
        return jsonify({"error": "Ungueltiges Datumsformat (YYYY-MM-DD)."}), 400

    # Plan-Eintrag erstellen
    plan_entry = GeneratedPlan(
        season_id=season_id,
        plan_start=start_date,
        plan_end=end_date,
        status="generating",
    )
    db.session.add(plan_entry)
    db.session.commit()

    try:
        from ..services.generator_service import run_generator_from_db
        result = run_generator_from_db(season_id, start_date, end_date)

        # Kollektiver Plan (nur DOCX — PDF on-demand)
        plan_entry.collective_docx = result["collective_docx"]
        plan_entry.violations_json = result.get("violations_json", "")

        # Individuelle Plaene (nur DOCX — PDF on-demand)
        for ip in result["individual_plans"]:
            ind = IndividualPlan(
                generated_plan_id=plan_entry.id,
                musician_id=ip.get("musician_id"),
                display_name=ip["display_name"],
                is_vakant=ip["is_vakant"],
                docx_data=ip["docx"],
            )
            db.session.add(ind)

        plan_entry.status = "ready"
        db.session.commit()

        return jsonify({
            "message": "Dienstplan erfolgreich generiert.",
            "plan": plan_entry.to_dict(),
        }), 201

    except Exception as e:
        plan_entry.status = "error"
        db.session.commit()
        return jsonify({"error": f"Generierung fehlgeschlagen: {str(e)}"}), 500


@generator_bp.route("/plans", methods=["GET"])
@jwt_required()
def list_plans():
    """Alle generierten Plaene."""
    plans = GeneratedPlan.query.order_by(GeneratedPlan.created_at.desc()).all()
    return jsonify([p.to_dict() for p in plans])


@generator_bp.route("/plans/<int:plan_id>", methods=["GET"])
@jwt_required()
def get_plan(plan_id):
    """Einzelner Plan mit individuellen Plaenen."""
    plan = GeneratedPlan.query.get_or_404(plan_id)
    result = plan.to_dict()

    ind_plans = sorted(plan.individual_plans, key=lambda p: p.sort_key)
    result["individual_plans"] = [{
        "id": p.id,
        "display_name": p.display_name,
        "is_vakant": p.is_vakant,
        "has_docx": p.docx_data is not None,
        "has_pdf": p.pdf_data is not None,
    } for p in ind_plans]

    return jsonify(result)


@generator_bp.route("/plans/<int:plan_id>/collective.docx", methods=["GET"])
@jwt_required()
def download_collective_docx(plan_id):
    """Kollektiven Dienstplan als DOCX herunterladen."""
    jwt_data = get_jwt()
    if jwt_data.get("role") != "admin":
        return jsonify({"error": "Nur Admin darf DOCX herunterladen."}), 403

    plan = GeneratedPlan.query.get_or_404(plan_id)
    if not plan.collective_docx:
        return jsonify({"error": "Kein Dienstplan vorhanden."}), 404

    month_range = f"{plan.plan_start.strftime('%m')}-{plan.plan_end.strftime('%m')}"
    filename = f"Dienstplan {plan.plan_start.year} {month_range}.docx"
    return send_file(
        BytesIO(plan.collective_docx),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=filename,
    )


@generator_bp.route("/plans/<int:plan_id>/collective.pdf", methods=["GET"])
@jwt_required()
def download_collective_pdf(plan_id):
    """Kollektiven Dienstplan als PDF herunterladen (on-demand)."""
    plan = GeneratedPlan.query.get_or_404(plan_id)

    if not plan.collective_docx:
        return jsonify({"error": "Kein Dienstplan vorhanden."}), 404

    if not plan.collective_pdf:
        from ..services.converter import docx_to_pdf
        pdf_data = docx_to_pdf(plan.collective_docx)
        if not pdf_data:
            return jsonify({"error": "PDF-Konvertierung fehlgeschlagen."}), 500
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
