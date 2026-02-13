#!/usr/bin/env python3
"""Einmalige Migration aller Excel-Jahresplaene (2025-2030) in die PostgreSQL-Datenbank.

Erstellt Spielzeiten und importiert Events mit Duplikat-Erkennung.
Migriert auch den Musiker-Roster aus roster.yaml.

Ausfuehrung:
    cd orchestra-dienstplan
    source .venv/bin/activate
    python scripts/migrate_all.py
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from collections import defaultdict

# Projekt-Root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Flask-App initialisieren
os.environ.setdefault("FLASK_ENV", "production")

from api.app import create_app
from api.models import db, Season, Event as DBEvent, Musician as DBMusician, MusicianEnsemble
from dienstplan.config import load_config
from dienstplan.excel_parser.reader import read_jahresplan
from dienstplan.excel_parser.event_extractor import extract_events
from dienstplan.roster import load_roster

# ──────────────── Konfiguration ────────────────

EXCEL_BASE = (
    "/Users/christiansaalfrank/Library/CloudStorage/"
    "OneDrive-FreigegebeneBibliotheken\u2013DeutscheBl\u00e4serakademieGmbH/"
    "Business - Documents/Jahrespl\u00e4ne"
)

# Spielzeiten-Definition
SEASONS = [
    {"name": "Spielzeit 2025",         "start": date(2025, 1, 1),  "end": date(2025, 12, 31), "year": 2025},
    {"name": "Spielzeit 2026",         "start": date(2026, 1, 1),  "end": date(2026, 7, 31),  "year": 2026},
    {"name": "Rumpfspielzeit 2026",    "start": date(2026, 8, 1),  "end": date(2026, 12, 31), "year": 2026},
    {"name": "Spielzeit 2027",         "start": date(2027, 1, 1),  "end": date(2027, 12, 31), "year": 2027},
    {"name": "Spielzeit 2028",         "start": date(2028, 1, 1),  "end": date(2028, 12, 31), "year": 2028},
    {"name": "Spielzeit 2029",         "start": date(2029, 1, 1),  "end": date(2029, 12, 31), "year": 2029},
    {"name": "Spielzeit 2030",         "start": date(2030, 1, 1),  "end": date(2030, 12, 31), "year": 2030},
]

# Welches Excel-File welche Jahre enthält
EXCEL_FILES = {
    2025: "Jahresplan 2025.xlsx",
    2026: "Jahresplan 2026.xlsx",
    2027: "Jahresplan 2027.xlsx",
    2028: "Jahresplan 2028.xlsx",
    2029: "Jahresplan 2029.xlsx",
    2030: "Jahresplan 2030.xlsx",
}


def find_season_for_date(event_date: date, seasons: list[Season]) -> Season | None:
    """Findet die passende Spielzeit fuer ein Datum."""
    for s in seasons:
        if s.start_date <= event_date <= s.end_date:
            return s
    return None


def event_key(event_date, start_time, end_time, raw_text):
    """Erzeugt einen Schluessel zur Duplikat-Erkennung."""
    return (
        event_date,
        str(start_time) if start_time else "",
        str(end_time) if end_time else "",
        (raw_text or "").strip()[:80],
    )


def migrate_seasons(app) -> list[Season]:
    """Erstellt die Spielzeiten in der DB."""
    print("\n" + "=" * 60)
    print("SPIELZEITEN ERSTELLEN")
    print("=" * 60)

    created = []

    with app.app_context():
        # Bestehende Spielzeiten + Test-Daten aufraeumen
        existing = Season.query.all()
        if existing:
            print(f"  Bestehende Spielzeiten gefunden: {[s.name for s in existing]}")
            # Bestehende Events und Seasons loeschen (frischer Import)
            DBEvent.query.delete()
            Season.query.delete()
            db.session.commit()
            print("  -> Bestehende Daten geloescht (frischer Import)")

        for s_def in SEASONS:
            season = Season(
                name=s_def["name"],
                start_date=s_def["start"],
                end_date=s_def["end"],
                is_active=(s_def["name"] == "Rumpfspielzeit 2026"),
            )
            db.session.add(season)
            created.append(season)

        db.session.commit()

        for s in created:
            print(f"  [+] {s.name}: {s.start_date} - {s.end_date} (ID {s.id})"
                  + (" [AKTIV]" if s.is_active else ""))

    return created


def migrate_events(app, seasons: list[Season]) -> dict:
    """Importiert Events aus allen Excel-Dateien mit Duplikat-Erkennung."""
    print("\n" + "=" * 60)
    print("EVENTS IMPORTIEREN")
    print("=" * 60)

    config = load_config()
    stats = defaultdict(lambda: {"total_parsed": 0, "imported": 0, "skipped_foreign": 0,
                                  "skipped_duplicate": 0, "skipped_no_season": 0})
    # Globaler Duplikat-Tracker
    seen_keys = set()

    with app.app_context():
        # Seasons neu laden (nach commit haben sie IDs)
        db_seasons = Season.query.order_by(Season.start_date).all()

        for year, filename in sorted(EXCEL_FILES.items()):
            xlsx_path = os.path.join(EXCEL_BASE, filename)
            if not os.path.exists(xlsx_path):
                print(f"\n  [{year}] DATEI NICHT GEFUNDEN: {xlsx_path}")
                continue

            print(f"\n  [{year}] Lese {filename}...")
            cells = read_jahresplan(xlsx_path, year=year)
            events = extract_events(cells, config)
            stats[year]["total_parsed"] = len(events)

            # Nur Events filtern die tatsaechlich in dieses Jahr gehoeren
            # Ausnahme: Events aus 2025 die ins 2026 fallen werden akzeptiert
            for event in events:
                ey = event.event_date.year

                # Hauptregel: Nur Events des Hauptjahres
                if ey != year:
                    # Spezialfall: 2025-Excel hat Events fuer Jan-Jul 2026
                    # (NY-Tournee, BLQ Bad Lausick). Diese gehoeren zu 2026.
                    if year == 2025 and ey == 2026:
                        pass  # Akzeptieren, wird zur passenden 2026-Season zugeordnet
                    else:
                        stats[year]["skipped_foreign"] += 1
                        continue

                # Duplikat-Check
                key = event_key(event.event_date, event.start_time,
                                event.end_time, event.raw_text)
                if key in seen_keys:
                    stats[year]["skipped_duplicate"] += 1
                    continue
                seen_keys.add(key)

                # Passende Spielzeit finden
                season = find_season_for_date(event.event_date, db_seasons)
                if not season:
                    stats[year]["skipped_no_season"] += 1
                    continue

                # Event erstellen
                db_event = DBEvent(
                    season_id=season.id,
                    event_date=event.event_date,
                    start_time=event.start_time,
                    end_time=event.end_time,
                    dienst_type=event.dienst_type.value,
                    formation=event.formation.value,
                    status="fest",
                    programm=event.programm or "",
                    ort=event.ort or "",
                    ort_adresse="",
                    leitung=event.leitung or "",
                    kleidung=event.kleidung or "",
                    sonstiges=event.sonstiges or "",
                    raw_text=event.raw_text or "",
                )
                db.session.add(db_event)
                stats[year]["imported"] += 1

            db.session.commit()

            s = stats[year]
            print(f"        Geparsed: {s['total_parsed']}, "
                  f"Importiert: {s['imported']}, "
                  f"Fremd: {s['skipped_foreign']}, "
                  f"Duplikate: {s['skipped_duplicate']}, "
                  f"Keine Season: {s['skipped_no_season']}")

        # Zusammenfassung pro Season
        print("\n  --- Events pro Spielzeit ---")
        for season in db_seasons:
            count = DBEvent.query.filter_by(season_id=season.id).count()
            print(f"  {season.name}: {count} Events")

    return dict(stats)


def migrate_roster(app) -> dict:
    """Migriert roster.yaml in die musicians-Tabelle."""
    print("\n" + "=" * 60)
    print("MUSIKER-ROSTER MIGRIEREN")
    print("=" * 60)

    with app.app_context():
        roster = load_roster()
        count = 0

        # Bestehende loeschen
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
            db.session.flush()

            for ens in musician.ensembles:
                db.session.add(MusicianEnsemble(
                    musician_id=db_mus.id,
                    ensemble=ens,
                ))
            count += 1

        db.session.commit()
        print(f"  [+] {count} Musiker importiert")

        # Zusammenfassung
        gruppen = defaultdict(int)
        for m in DBMusician.query.all():
            gruppen[m.register] += 1
        for reg, cnt in sorted(gruppen.items()):
            print(f"      {reg}: {cnt}")

    return {"migrated_musicians": count}


def verify_import(app):
    """Verifiziert den Import."""
    print("\n" + "=" * 60)
    print("VERIFIKATION")
    print("=" * 60)

    with app.app_context():
        seasons = Season.query.order_by(Season.start_date).all()
        total_events = 0

        for season in seasons:
            events = DBEvent.query.filter_by(season_id=season.id).all()
            total_events += len(events)

            if events:
                dates = sorted([e.event_date for e in events])
                types = defaultdict(int)
                formations = defaultdict(int)
                for e in events:
                    types[e.dienst_type] += 1
                    formations[e.formation] += 1

                print(f"\n  {season.name} ({season.start_date} - {season.end_date}):")
                print(f"    Events: {len(events)} | {dates[0]} - {dates[-1]}")
                print(f"    Typen: {dict(sorted(types.items(), key=lambda x: -x[1]))}")
                print(f"    Formationen: {dict(sorted(formations.items(), key=lambda x: -x[1]))}")
            else:
                print(f"\n  {season.name}: 0 Events")

        musicians = DBMusician.query.count()
        vakant = DBMusician.query.filter_by(is_vakant=True).count()
        print(f"\n  Gesamt: {total_events} Events in {len(seasons)} Spielzeiten")
        print(f"  Musiker: {musicians} ({musicians - vakant} besetzt, {vakant} vakant)")


def main():
    print("=" * 60)
    print("PLANUNG SBP — DATEN-MIGRATION")
    print("Excel-Jahresplaene 2025-2030 → PostgreSQL")
    print("=" * 60)

    app = create_app()

    # 1. Spielzeiten erstellen
    seasons = migrate_seasons(app)

    # 2. Events importieren
    migrate_events(app, seasons)

    # 3. Roster migrieren
    migrate_roster(app)

    # 4. Verifizieren
    verify_import(app)

    print("\n" + "=" * 60)
    print("MIGRATION ABGESCHLOSSEN!")
    print("=" * 60)


if __name__ == "__main__":
    main()
