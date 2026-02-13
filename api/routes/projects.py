"""Projekt-Endpoints fuer Planung SBP."""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt

from ..models import db, Project, Season

projects_bp = Blueprint("projects", __name__, url_prefix="/api/projects")


@projects_bp.route("", methods=["GET"])
@jwt_required()
def list_projects():
    """Projekte filtern nach Spielzeit und Status."""
    query = Project.query

    season_id = request.args.get("season_id", type=int)
    if season_id:
        query = query.filter(Project.season_id == season_id)

    status = request.args.get("status")
    if status:
        query = query.filter(Project.status == status)

    projects = query.order_by(Project.created_at.desc()).all()
    return jsonify([p.to_dict() for p in projects])


@projects_bp.route("/<int:project_id>", methods=["GET"])
@jwt_required()
def get_project(project_id):
    """Einzelnes Projekt mit Events."""
    project = Project.query.get_or_404(project_id)
    result = project.to_dict()
    result["events"] = [e.to_dict() for e in project.events]
    return jsonify(result)


@projects_bp.route("", methods=["POST"])
@jwt_required()
def create_project():
    """Neues Projekt anlegen."""
    jwt_data = get_jwt()
    if jwt_data.get("role") != "admin":
        return jsonify({"error": "Nur Admin darf Projekte anlegen."}), 403

    data = request.get_json()
    name = data.get("name", "").strip()
    season_id = data.get("season_id")

    if not name or not season_id:
        return jsonify({"error": "name und season_id erforderlich."}), 400

    season = Season.query.get(season_id)
    if not season:
        return jsonify({"error": "Spielzeit nicht gefunden."}), 404

    project = Project(
        season_id=season_id,
        name=name,
        description=data.get("description", ""),
        status=data.get("status", "geplant"),
        formation=data.get("formation"),
        conductor=data.get("conductor"),
        soloist=data.get("soloist"),
        moderator=data.get("moderator"),
        notes=data.get("notes"),
    )
    db.session.add(project)
    db.session.commit()

    return jsonify(project.to_dict()), 201


@projects_bp.route("/<int:project_id>", methods=["PUT"])
@jwt_required()
def update_project(project_id):
    """Projekt bearbeiten."""
    jwt_data = get_jwt()
    if jwt_data.get("role") != "admin":
        return jsonify({"error": "Nur Admin darf Projekte bearbeiten."}), 403

    project = Project.query.get_or_404(project_id)
    data = request.get_json()

    for field in ["name", "description", "status", "formation",
                   "conductor", "soloist", "moderator", "notes"]:
        if field in data:
            setattr(project, field, data[field])

    db.session.commit()
    return jsonify(project.to_dict())


@projects_bp.route("/<int:project_id>", methods=["DELETE"])
@jwt_required()
def delete_project(project_id):
    """Projekt loeschen (Events bleiben, verlieren nur Projekt-Zuordnung)."""
    jwt_data = get_jwt()
    if jwt_data.get("role") != "admin":
        return jsonify({"error": "Nur Admin darf Projekte loeschen."}), 403

    project = Project.query.get_or_404(project_id)

    # Events behalten, aber Projekt-Zuordnung entfernen
    from ..models import Event
    Event.query.filter_by(project_id=project_id).update({"project_id": None})

    db.session.delete(project)
    db.session.commit()
    return jsonify({"message": "Projekt geloescht."}), 200


@projects_bp.route("/<int:project_id>/events", methods=["GET"])
@jwt_required()
def list_project_events(project_id):
    """Events eines Projekts."""
    project = Project.query.get_or_404(project_id)
    events = sorted(project.events, key=lambda e: (e.event_date, e.start_time or ""))
    return jsonify([e.to_dict() for e in events])
