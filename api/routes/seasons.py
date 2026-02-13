"""Spielzeit-Endpoints fuer Planung SBP."""

from datetime import date

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt

from ..models import db, Season

seasons_bp = Blueprint("seasons", __name__, url_prefix="/api/seasons")


def _admin_required():
    """Prueft ob der aktuelle User Admin ist."""
    jwt_data = get_jwt()
    if jwt_data.get("role") != "admin":
        return jsonify({"error": "Nur Admin erlaubt."}), 403
    return None


@seasons_bp.route("", methods=["GET"])
@jwt_required()
def list_seasons():
    """Alle Spielzeiten."""
    seasons = Season.query.order_by(Season.start_date.desc()).all()
    return jsonify([{
        "id": s.id,
        "name": s.name,
        "start_date": s.start_date.isoformat(),
        "end_date": s.end_date.isoformat(),
        "is_active": s.is_active,
        "event_count": len(s.events) if s.events else 0,
        "project_count": len(s.projects) if s.projects else 0,
    } for s in seasons])


@seasons_bp.route("", methods=["POST"])
@jwt_required()
def create_season():
    """Neue Spielzeit anlegen."""
    err = _admin_required()
    if err:
        return err

    data = request.get_json()
    name = data.get("name", "").strip()
    start_str = data.get("start_date")
    end_str = data.get("end_date")

    if not name or not start_str or not end_str:
        return jsonify({"error": "Name, start_date und end_date erforderlich."}), 400

    try:
        start = date.fromisoformat(start_str)
        end = date.fromisoformat(end_str)
    except ValueError:
        return jsonify({"error": "Ungueliges Datumsformat (YYYY-MM-DD)."}), 400

    if start >= end:
        return jsonify({"error": "start_date muss vor end_date liegen."}), 400

    season = Season(name=name, start_date=start, end_date=end, is_active=data.get("is_active", False))

    # Wenn aktiv, alle anderen deaktivieren
    if season.is_active:
        Season.query.update({"is_active": False})

    db.session.add(season)
    db.session.commit()

    return jsonify({
        "id": season.id,
        "name": season.name,
        "start_date": season.start_date.isoformat(),
        "end_date": season.end_date.isoformat(),
        "is_active": season.is_active,
    }), 201


@seasons_bp.route("/<int:season_id>", methods=["PUT"])
@jwt_required()
def update_season(season_id):
    """Spielzeit bearbeiten."""
    err = _admin_required()
    if err:
        return err

    season = Season.query.get_or_404(season_id)
    data = request.get_json()

    if "name" in data:
        season.name = data["name"].strip()
    if "start_date" in data:
        season.start_date = date.fromisoformat(data["start_date"])
    if "end_date" in data:
        season.end_date = date.fromisoformat(data["end_date"])
    if "is_active" in data:
        if data["is_active"]:
            Season.query.update({"is_active": False})
        season.is_active = data["is_active"]

    db.session.commit()

    return jsonify({
        "id": season.id,
        "name": season.name,
        "start_date": season.start_date.isoformat(),
        "end_date": season.end_date.isoformat(),
        "is_active": season.is_active,
    })


@seasons_bp.route("/<int:season_id>", methods=["GET"])
@jwt_required()
def get_season(season_id):
    """Einzelne Spielzeit mit Statistiken."""
    season = Season.query.get_or_404(season_id)
    return jsonify({
        "id": season.id,
        "name": season.name,
        "start_date": season.start_date.isoformat(),
        "end_date": season.end_date.isoformat(),
        "is_active": season.is_active,
        "event_count": len(season.events) if season.events else 0,
        "project_count": len(season.projects) if season.projects else 0,
    })
