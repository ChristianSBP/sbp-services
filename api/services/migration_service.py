"""Migration-Service: Einmaliger Import von Excel-Daten und Roster in die DB.

Nutzt den bestehenden Excel-Parser fuer die Daten-Migration.
Danach werden alle Events nur noch ueber die App gepflegt.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Dict, Any, Optional

from ..models import (
    db, Season, Event as DBEvent, Musician as DBMusician,
    MusicianEnsemble,
)

# Bestehende Module fuer Excel-Import
from dienstplan.config import load_config
from dienstplan.excel_parser.reader import read_jahresplan
from dienstplan.excel_parser.event_extractor import extract_events
from dienstplan.roster import load_roster


def migrate_roster_to_db() -> Dict[str, Any]:
    """Migriert roster.yaml in die musicians-Tabelle.

    Kann mehrfach aufgerufen werden — loescht bestehende Eintraege
    und erstellt sie neu.
    """
    roster = load_roster()
    count = 0

    # Bestehende Eintraege loeschen
    MusicianEnsemble.query.delete()
    DBMusician.query.delete()

    for idx, musician in enumerate(roster.all_musicians):
        db_mus = DBMusician(
            name=musician.name,
            position=musician.position,
            register=musician.register,
            gruppe=musician.gruppe,
            anteil=musician.anteil,
            zusatz=musician.zusatz,
            is_vakant=musician.is_vakant,
            sort_order=idx,
        )
        db.session.add(db_mus)
        db.session.flush()  # ID generieren

        # Ensemble-Zugehoerigkeiten
        for ens in musician.ensembles:
            db.session.add(MusicianEnsemble(
                musician_id=db_mus.id,
                ensemble=ens,
            ))

        count += 1

    db.session.commit()
    return {"migrated_musicians": count}


def migrate_excel_to_db(
    xlsx_path: str | Path,
    season_id: int,
    year: int = 2026,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Importiert Events aus einem Jahresplan-Excel in die DB.

    Nutzt den bestehenden Excel-Parser (read_jahresplan + extract_events).
    Events werden einer bestehenden Spielzeit zugeordnet.

    Args:
        xlsx_path: Pfad zur Jahresplan-Excel-Datei
        season_id: ID der Spielzeit in der DB
        year: Jahr fuer die Excel-Auswertung
        start_date: Optional — nur Events ab diesem Datum importieren
        end_date: Optional — nur Events bis zu diesem Datum importieren

    Returns:
        Dict mit Anzahl importierter Events
    """
    season = Season.query.get(season_id)
    if not season:
        raise ValueError(f"Spielzeit {season_id} nicht gefunden.")

    config = load_config()

    # Excel parsen
    cells = read_jahresplan(str(xlsx_path), year=year)
    events = extract_events(cells, config)

    # Optional filtern
    if start_date:
        events = [e for e in events if e.event_date >= start_date]
    if end_date:
        events = [e for e in events if e.event_date <= end_date]

    # In DB schreiben
    imported = 0
    for event in events:
        db_event = DBEvent(
            season_id=season_id,
            event_date=event.event_date,
            start_time=event.start_time,
            end_time=event.end_time,
            dienst_type=event.dienst_type.value,
            formation=event.formation.value,
            status="fest",  # Aus Excel importierte Events gelten als fest
            programm=event.programm,
            ort=event.ort,
            ort_adresse="",
            leitung=event.leitung,
            kleidung=event.kleidung,
            sonstiges=event.sonstiges,
            raw_text=event.raw_text,
        )
        db.session.add(db_event)
        imported += 1

    db.session.commit()
    return {
        "imported_events": imported,
        "season": season.name,
        "date_range": f"{events[0].event_date} - {events[-1].event_date}" if events else "leer",
    }
