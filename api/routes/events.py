"""Event-Endpoints fuer Planung SBP — CRUD + TVK-Validierung."""

from datetime import date, time

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt

from ..models import db, Event, Season

events_bp = Blueprint("events", __name__, url_prefix="/api/events")


def _parse_time(time_str):
    """Parst HH:MM String zu time-Objekt."""
    if not time_str:
        return None
    try:
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None


def _event_from_data(data, event=None):
    """Erstellt oder aktualisiert ein Event aus Request-Daten."""
    if event is None:
        event = Event()

    event.season_id = data.get("season_id", event.season_id)
    event.project_id = data.get("project_id", event.project_id)

    if "event_date" in data:
        event.event_date = date.fromisoformat(data["event_date"])
    if "start_time" in data:
        event.start_time = _parse_time(data["start_time"])
    if "end_time" in data:
        event.end_time = _parse_time(data["end_time"])

    for field in ["dienst_type", "formation", "status", "programm",
                   "ort", "ort_adresse", "leitung", "kleidung", "sonstiges"]:
        if field in data:
            setattr(event, field, data[field])

    return event


@events_bp.route("", methods=["GET"])
@jwt_required()
def list_events():
    """Events filtern nach Spielzeit, Datumsbereich, Formation, Status."""
    query = Event.query

    season_id = request.args.get("season_id", type=int)
    if season_id:
        query = query.filter(Event.season_id == season_id)

    start = request.args.get("start")
    if start:
        query = query.filter(Event.event_date >= date.fromisoformat(start))

    end = request.args.get("end")
    if end:
        query = query.filter(Event.event_date <= date.fromisoformat(end))

    formation = request.args.get("formation")
    if formation:
        query = query.filter(Event.formation == formation)

    status = request.args.get("status")
    if status:
        query = query.filter(Event.status == status)

    dienst_type = request.args.get("dienst_type")
    if dienst_type:
        query = query.filter(Event.dienst_type == dienst_type)

    events = query.order_by(Event.event_date, Event.start_time).all()
    return jsonify([e.to_dict() for e in events])


@events_bp.route("/<int:event_id>", methods=["GET"])
@jwt_required()
def get_event(event_id):
    """Einzelnes Event."""
    event = Event.query.get_or_404(event_id)
    return jsonify(event.to_dict())


@events_bp.route("", methods=["POST"])
@jwt_required()
def create_event():
    """Neues Event anlegen + TVK-Validierung."""
    jwt_data = get_jwt()
    if jwt_data.get("role") != "admin":
        return jsonify({"error": "Nur Admin darf Events anlegen."}), 403

    data = request.get_json()
    if not data.get("event_date") or not data.get("season_id"):
        return jsonify({"error": "event_date und season_id erforderlich."}), 400

    # Spielzeit pruefen
    season = Season.query.get(data["season_id"])
    if not season:
        return jsonify({"error": "Spielzeit nicht gefunden."}), 404

    event = _event_from_data(data)
    db.session.add(event)
    db.session.commit()

    # TVK-Validierung fuer die betroffene Woche
    validation = _validate_week(event.event_date, event.season_id)

    return jsonify({
        "event": event.to_dict(),
        "validation": validation,
    }), 201


@events_bp.route("/<int:event_id>", methods=["PUT"])
@jwt_required()
def update_event(event_id):
    """Event bearbeiten."""
    jwt_data = get_jwt()
    if jwt_data.get("role") != "admin":
        return jsonify({"error": "Nur Admin darf Events bearbeiten."}), 403

    event = Event.query.get_or_404(event_id)
    data = request.get_json()
    _event_from_data(data, event)
    db.session.commit()

    validation = _validate_week(event.event_date, event.season_id)

    return jsonify({
        "event": event.to_dict(),
        "validation": validation,
    })


@events_bp.route("/<int:event_id>", methods=["DELETE"])
@jwt_required()
def delete_event(event_id):
    """Event loeschen."""
    jwt_data = get_jwt()
    if jwt_data.get("role") != "admin":
        return jsonify({"error": "Nur Admin darf Events loeschen."}), 403

    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    return jsonify({"message": "Event geloescht."}), 200


@events_bp.route("/validate", methods=["POST"])
@jwt_required()
def validate_events():
    """Dry-Run TVK-Validierung (ohne Speichern).

    Akzeptiert ein neues Event und prueft wie es sich auf die
    Woche auswirken wuerde.
    """
    data = request.get_json()
    event_date_str = data.get("event_date")
    season_id = data.get("season_id")

    if not event_date_str or not season_id:
        return jsonify({"error": "event_date und season_id erforderlich."}), 400

    event_date = date.fromisoformat(event_date_str)
    validation = _validate_week(event_date, season_id, extra_event_data=data)

    return jsonify({"validation": validation})


def _validate_week(event_date, season_id, extra_event_data=None):
    """Validiert die TVK-Konformitaet fuer die Woche des Events.

    Nutzt den bestehenden TVK-Validator ueber den validator_service.
    """
    try:
        from ..services.validator_service import validate_week
        return validate_week(event_date, season_id, extra_event_data)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Validierung fehlgeschlagen: {str(e)}",
            "violations": [],
        }
