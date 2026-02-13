"""Spielzeit-Endpoints fuer Planung SBP."""

from datetime import date

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt

from ..models import db, Season, Event as DBEvent

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


@seasons_bp.route("/<int:season_id>", methods=["DELETE"])
@jwt_required()
def delete_season(season_id):
    """Spielzeit loeschen (inkl. aller Events)."""
    err = _admin_required()
    if err:
        return err

    season = Season.query.get_or_404(season_id)
    # Zugehoerige Events loeschen
    DBEvent.query.filter_by(season_id=season_id).delete()
    db.session.delete(season)
    db.session.commit()

    return jsonify({"message": f"Spielzeit '{season.name}' geloescht."})


@seasons_bp.route("/bulk-import", methods=["POST"])
@jwt_required()
def bulk_import():
    """Bulk-Import: Erstellt Spielzeiten und Events in einem Request.

    Erwartet JSON:
    {
        "clear_existing": true,
        "seasons": [
            {
                "name": "Spielzeit 2025",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "is_active": false,
                "events": [
                    {
                        "event_date": "2025-01-01",
                        "start_time": "19:00",
                        "end_time": "21:00",
                        "dienst_type": "Konzert",
                        "formation": "SBP",
                        "status": "fest",
                        "programm": "...",
                        "ort": "...",
                        "leitung": "...",
                        "kleidung": "...",
                        "sonstiges": "...",
                        "raw_text": "..."
                    }
                ]
            }
        ]
    }
    """
    from datetime import time

    err = _admin_required()
    if err:
        return err

    data = request.get_json()
    if not data or "seasons" not in data:
        return jsonify({"error": "seasons-Array erforderlich."}), 400

    # Optional bestehende Daten loeschen
    if data.get("clear_existing"):
        DBEvent.query.delete()
        Season.query.delete()
        db.session.commit()

    results = []
    total_events = 0

    for s_data in data["seasons"]:
        try:
            start = date.fromisoformat(s_data["start_date"])
            end = date.fromisoformat(s_data["end_date"])
        except (ValueError, KeyError):
            continue

        season = Season(
            name=s_data.get("name", f"Spielzeit {start.year}"),
            start_date=start,
            end_date=end,
            is_active=s_data.get("is_active", False),
        )

        if season.is_active:
            Season.query.update({"is_active": False})

        db.session.add(season)
        db.session.flush()  # ID generieren

        event_count = 0
        for e_data in s_data.get("events", []):
            try:
                ev_date = date.fromisoformat(e_data["event_date"])
            except (ValueError, KeyError):
                continue

            start_time = None
            end_time = None
            if e_data.get("start_time"):
                try:
                    parts = e_data["start_time"].split(":")
                    start_time = time(int(parts[0]), int(parts[1]))
                except (ValueError, IndexError):
                    pass
            if e_data.get("end_time"):
                try:
                    parts = e_data["end_time"].split(":")
                    end_time = time(int(parts[0]), int(parts[1]))
                except (ValueError, IndexError):
                    pass

            db_event = DBEvent(
                season_id=season.id,
                event_date=ev_date,
                start_time=start_time,
                end_time=end_time,
                dienst_type=e_data.get("dienst_type", "Sonstiges"),
                formation=e_data.get("formation", "Unbekannt"),
                status=e_data.get("status", "fest"),
                programm=e_data.get("programm", ""),
                ort=e_data.get("ort", ""),
                ort_adresse=e_data.get("ort_adresse", ""),
                leitung=e_data.get("leitung", ""),
                kleidung=e_data.get("kleidung", ""),
                sonstiges=e_data.get("sonstiges", ""),
                raw_text=e_data.get("raw_text", ""),
            )
            db.session.add(db_event)
            event_count += 1

        total_events += event_count
        results.append({
            "season_id": season.id,
            "name": season.name,
            "events_imported": event_count,
        })

    db.session.commit()

    return jsonify({
        "message": f"{len(results)} Spielzeiten mit {total_events} Events importiert.",
        "seasons": results,
        "total_events": total_events,
    }), 201
