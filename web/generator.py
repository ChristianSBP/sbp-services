"""Generator-Wrapper: Ruft die bestehende Dienstplan-Pipeline auf.

Wiederverwendet 100% des bestehenden Codes aus dem CLI.
Kein Code wird dupliziert.
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from typing import Dict, List, Any

from dienstplan.config import load_config
from dienstplan.excel_parser.reader import read_jahresplan
from dienstplan.excel_parser.event_extractor import extract_events
from dienstplan.dienst_calculator import calculate_dienste
from dienstplan.models.plan import Dienstplan
from dienstplan.constraints.validator import TVKValidator
from dienstplan.output.word_writer import write_dienstplan_docx
from dienstplan.output.individual_writer import write_individual_docx
from dienstplan.roster import load_roster
from dienstplan.individual_plan import create_individual_plan


def run_generator(
    xlsx_path: str | Path,
    start_date: date,
    end_date: date,
    year: int = 2026,
) -> Dict[str, Any]:
    """Generiert kollektiven + individuelle Dienstplaene.

    Returns:
        {
            'collective_docx': bytes,       # Word-Datei des Gesamtplans
            'plan_start': date,
            'plan_end': date,
            'violations_summary': dict,     # Fehler/Warnungen/Hinweise
            'individual_plans': [
                {
                    'name': str,            # Musiker-Name
                    'position': str,        # Instrument/Position
                    'is_vakant': bool,
                    'display_name': str,    # Anzeigename
                    'docx': bytes,          # Word-Datei
                },
                ...
            ]
        }
    """
    config = load_config()

    # === Schritt 1: Kollektiven Plan generieren ===
    cells = read_jahresplan(str(xlsx_path), year=year)
    events = extract_events(cells, config)
    events_in_range = [
        e for e in events if start_date <= e.event_date <= end_date
    ]

    dienste = calculate_dienste(events_in_range, config, start_date, end_date)
    plan = Dienstplan.from_events(events_in_range, dienste, start_date, end_date)

    # Validierung
    validator = TVKValidator(config)
    violations = validator.validate(plan)
    summary = validator.summary(violations)

    # Kollektiven Plan als DOCX in temporaere Datei schreiben
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    write_dienstplan_docx(plan, tmp_path, config)
    collective_docx = tmp_path.read_bytes()
    tmp_path.unlink()

    # === Schritt 2: Individuelle Plaene generieren ===
    roster = load_roster()
    individual_plans = []

    for musician in roster.all_musicians:
        individual = create_individual_plan(plan, musician, config)

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            ind_path = Path(tmp.name)

        write_individual_docx(individual, musician, ind_path, config)
        ind_docx = ind_path.read_bytes()
        ind_path.unlink()

        individual_plans.append({
            "name": musician.name,
            "position": musician.position,
            "is_vakant": musician.is_vakant,
            "display_name": musician.display_name,
            "docx": ind_docx,
        })

    return {
        "collective_docx": collective_docx,
        "plan_start": start_date,
        "plan_end": end_date,
        "violations_summary": summary,
        "individual_plans": individual_plans,
    }
