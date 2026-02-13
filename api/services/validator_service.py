"""TVK/HTV-Validator Service — Bridge zwischen DB und bestehendem Validator.

Nutzt 100% des bestehenden Codes aus src/dienstplan/constraints/.
"""

from __future__ import annotations

import json
from datetime import date, time, timedelta
from typing import Optional, List, Dict, Any

from ..models import db, Event as DBEvent

# Bestehende Pipeline-Module
from dienstplan.models.events import Event as PydanticEvent, DienstType, Formation
from dienstplan.dienst_calculator import calculate_dienste
from dienstplan.models.plan import Dienstplan
from dienstplan.constraints.validator import TVKValidator
from dienstplan.config import load_config


def db_event_to_pydantic(db_event: DBEvent) -> PydanticEvent:
    """Konvertiert ein DB-Event in ein Pydantic Event fuer die Pipeline."""
    return PydanticEvent(
        event_date=db_event.event_date,
        start_time=db_event.start_time,
        end_time=db_event.end_time,
        dienst_type=_safe_dienst_type(db_event.dienst_type),
        formation=_safe_formation(db_event.formation),
        programm=db_event.programm or "",
        ort=db_event.ort or "",
        leitung=db_event.leitung or "",
        kleidung=db_event.kleidung or "",
        sonstiges=db_event.sonstiges or "",
        raw_text=db_event.raw_text or "",
    )


def _safe_dienst_type(value: str) -> DienstType:
    """Sicheres Mapping von String zu DienstType enum."""
    for dt in DienstType:
        if dt.value == value or dt.name == value:
            return dt
    return DienstType.SONSTIGES


def _safe_formation(value: str) -> Formation:
    """Sicheres Mapping von String zu Formation enum."""
    for f in Formation:
        if f.value == value or f.name == value:
            return f
    return Formation.UNBEKANNT


def validate_week(event_date: date, season_id: int,
                  extra_event_data: Optional[Dict] = None) -> Dict[str, Any]:
    """Validiert die TVK-Konformitaet fuer die Woche eines Events.

    Args:
        event_date: Datum des Events
        season_id: Spielzeit-ID
        extra_event_data: Optionale Daten fuer ein noch nicht gespeichertes Event
                         (Dry-Run Validierung)

    Returns:
        Dict mit status, violations-Liste und Zusammenfassung
    """
    config = load_config()

    # Wochenbereich bestimmen (Montag bis Sonntag)
    weekday = event_date.weekday()
    week_start = event_date - timedelta(days=weekday)
    week_end = week_start + timedelta(days=6)

    # Erweiterten Bereich laden (3 Wochen fuer Ruhezeiten-Checks)
    load_start = week_start - timedelta(days=7)
    load_end = week_end + timedelta(days=7)

    # Events aus DB laden
    db_events = DBEvent.query.filter(
        DBEvent.season_id == season_id,
        DBEvent.event_date >= load_start,
        DBEvent.event_date <= load_end,
    ).all()

    # In Pydantic-Events konvertieren
    pydantic_events = [db_event_to_pydantic(e) for e in db_events]

    # Extra-Event hinzufuegen (Dry-Run)
    if extra_event_data:
        extra_event = PydanticEvent(
            event_date=date.fromisoformat(extra_event_data["event_date"]),
            start_time=_parse_time(extra_event_data.get("start_time")),
            end_time=_parse_time(extra_event_data.get("end_time")),
            dienst_type=_safe_dienst_type(extra_event_data.get("dienst_type", "Sonstiges")),
            formation=_safe_formation(extra_event_data.get("formation", "Unbekannt")),
            programm=extra_event_data.get("programm", ""),
            ort=extra_event_data.get("ort", ""),
            leitung=extra_event_data.get("leitung", ""),
            kleidung=extra_event_data.get("kleidung", ""),
            sonstiges=extra_event_data.get("sonstiges", ""),
        )
        pydantic_events.append(extra_event)

    # Dienste berechnen
    dienste = calculate_dienste(pydantic_events, config, load_start, load_end)

    # Plan erstellen
    plan = Dienstplan.from_events(pydantic_events, dienste, load_start, load_end)

    # Validieren
    validator = TVKValidator(config)
    violations_list = validator.validate(plan)
    summary = validator.summary(violations_list)

    # Violations fuer die betroffene Woche filtern
    week_violations = []
    for v in plan.violations:
        # Violation betrifft die Ziel-Woche?
        if any(load_start <= d <= load_end for d in v.affected_dates):
            week_violations.append({
                "rule_id": v.rule_id,
                "rule_name": v.rule_name,
                "severity": v.severity.value,
                "message": v.message,
                "tvk_paragraph": v.tvk_paragraph,
                "affected_dates": [d.isoformat() for d in v.affected_dates],
                "affected_week": v.affected_week,
                "current_value": v.current_value,
                "limit_value": v.limit_value,
                "suggestion": v.suggestion,
            })

    # Dienste-Zusammenfassung fuer die Woche
    week_dienste = [d for d in dienste if week_start <= d.dienst_date <= week_end]
    total_week = sum(d.dienst_count for d in week_dienste)

    has_errors = any(v["severity"] == "ERROR" for v in week_violations)
    has_warnings = any(v["severity"] == "WARNING" for v in week_violations)

    return {
        "status": "error" if has_errors else ("warning" if has_warnings else "ok"),
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "total_dienste": total_week,
        "max_dienste": config.get("htv", {}).get("dienste", {}).get("max_per_week", 10),
        "violations": week_violations,
        "summary": summary,
    }


def validate_full_season(season_id: int) -> Dict[str, Any]:
    """Vollstaendige TVK-Validierung einer Spielzeit."""
    from ..models import Season
    season = Season.query.get(season_id)
    if not season:
        return {"error": "Spielzeit nicht gefunden."}

    config = load_config()

    db_events = DBEvent.query.filter(
        DBEvent.season_id == season_id,
    ).order_by(DBEvent.event_date).all()

    pydantic_events = [db_event_to_pydantic(e) for e in db_events]
    dienste = calculate_dienste(pydantic_events, config, season.start_date, season.end_date)
    plan = Dienstplan.from_events(pydantic_events, dienste, season.start_date, season.end_date)

    validator = TVKValidator(config)
    violations_list = validator.validate(plan)
    summary = validator.summary(violations_list)

    all_violations = [{
        "rule_id": v.rule_id,
        "rule_name": v.rule_name,
        "severity": v.severity.value,
        "message": v.message,
        "tvk_paragraph": v.tvk_paragraph,
        "affected_dates": [d.isoformat() for d in v.affected_dates],
        "affected_week": v.affected_week,
        "current_value": v.current_value,
        "limit_value": v.limit_value,
        "suggestion": v.suggestion,
    } for v in plan.violations]

    return {
        "season": season.name,
        "total_dienste": plan.total_dienste,
        "total_weeks": plan.total_weeks,
        "avg_per_week": round(plan.avg_dienste_per_week, 1),
        "violations": all_violations,
        "summary": summary,
    }


def _parse_time(time_str: Optional[str]):
    """Parst HH:MM String zu time-Objekt."""
    if not time_str:
        return None
    try:
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None
