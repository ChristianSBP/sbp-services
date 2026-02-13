"""Generator-Service: Erzeugt Dienstplaene aus DB-Events.

Nutzt die bestehende Pipeline (100% Wiederverwendung), liest aber
Events aus PostgreSQL statt aus Excel.
"""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path
from typing import Dict, Any

from ..models import db, Event as DBEvent, Musician as DBMusician

# Bestehende Pipeline-Module — 100% Wiederverwendung
from dienstplan.config import load_config
from dienstplan.dienst_calculator import calculate_dienste
from dienstplan.models.plan import Dienstplan
from dienstplan.models.events import Event as PydanticEvent, Formation
from dienstplan.constraints.validator import TVKValidator
from dienstplan.output.word_writer import write_dienstplan_docx
from dienstplan.output.individual_writer import write_individual_docx
from dienstplan.individual_plan import create_individual_plan
from dienstplan.roster import Musician as RosterMusician

from .validator_service import db_event_to_pydantic


def _db_musician_to_roster(db_mus: DBMusician) -> RosterMusician:
    """Konvertiert DB-Musiker in Roster-Musiker fuer die Pipeline."""
    return RosterMusician(
        name=db_mus.name,
        position=db_mus.position,
        register=db_mus.register,
        gruppe=db_mus.gruppe,
        anteil=db_mus.anteil,
        zusatz=db_mus.zusatz or "",
        ensembles=db_mus.ensemble_set,
    )


def run_generator_from_db(
    season_id: int,
    start_date: date,
    end_date: date,
) -> Dict[str, Any]:
    """Generiert kollektiven + individuelle Dienstplaene aus DB-Events.

    Ersetzt den Excel-basierten run_generator().
    Nutzt identische Pipeline: Events → Dienste → Plan → Validierung → DOCX.

    Returns:
        {
            'collective_docx': bytes,
            'violations_json': str,
            'individual_plans': [
                {'musician_id': int, 'display_name': str, 'is_vakant': bool, 'docx': bytes},
                ...
            ]
        }
    """
    config = load_config()

    # === Schritt 1: Events aus DB laden und konvertieren ===
    db_events = DBEvent.query.filter(
        DBEvent.season_id == season_id,
        DBEvent.event_date >= start_date,
        DBEvent.event_date <= end_date,
    ).order_by(DBEvent.event_date).all()

    pydantic_events = [db_event_to_pydantic(e) for e in db_events]

    # === Schritt 2: Kollektiven Plan generieren ===
    dienste = calculate_dienste(pydantic_events, config, start_date, end_date)
    plan = Dienstplan.from_events(pydantic_events, dienste, start_date, end_date)

    # Validierung
    validator = TVKValidator(config)
    violations_summary = validator.validate(plan)

    # Violations als JSON speichern
    violations_data = [{
        "rule_id": v.rule_id,
        "severity": v.severity.value,
        "message": v.message,
        "affected_dates": [d.isoformat() for d in v.affected_dates],
    } for v in plan.violations]

    # Kollektiven Plan als DOCX
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    write_dienstplan_docx(plan, tmp_path, config)
    collective_docx = tmp_path.read_bytes()
    tmp_path.unlink()

    # === Schritt 3: Musiker aus DB laden ===
    db_musicians = DBMusician.query.order_by(DBMusician.sort_order).all()
    if not db_musicians:
        # Fallback: roster.yaml laden (fuer Migration)
        from dienstplan.roster import load_roster
        roster = load_roster()
        roster_musicians = roster.all_musicians
        # musician_id bleibt None bei Fallback
        musicians_with_ids = [(None, m) for m in roster_musicians]
    else:
        musicians_with_ids = [
            (db_m.id, _db_musician_to_roster(db_m)) for db_m in db_musicians
        ]

    # === Schritt 4: Individuelle Plaene generieren ===
    individual_plans = []

    for musician_id, musician in musicians_with_ids:
        individual = create_individual_plan(plan, musician, config)

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            ind_path = Path(tmp.name)

        write_individual_docx(individual, musician, ind_path, config)
        ind_docx = ind_path.read_bytes()
        ind_path.unlink()

        individual_plans.append({
            "musician_id": musician_id,
            "display_name": musician.display_name,
            "is_vakant": musician.is_vakant,
            "docx": ind_docx,
        })

    return {
        "collective_docx": collective_docx,
        "violations_json": json.dumps(violations_data, ensure_ascii=False),
        "individual_plans": individual_plans,
    }
