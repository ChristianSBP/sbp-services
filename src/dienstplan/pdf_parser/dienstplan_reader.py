"""Liest einen bestehenden Dienstplan der SBP aus PDF.

Das PDF-Format der SBP hat 10 Spalten:
Tag | Datum | Zeit | Formation | Ort | Programm | Leitung | Kleidung | Dienste | Sonstiges
"""

from __future__ import annotations

import re
from datetime import date, time, timedelta
from pathlib import Path
from typing import List, Tuple, Optional

import pdfplumber

from ..models.events import Event, Dienst, DienstType, Formation


DAY_MAP = {"Mo": 0, "Di": 1, "Mi": 2, "Do": 3, "Fr": 4, "Sa": 5, "So": 6}

DATE_RE = re.compile(r'(\d{2})\.(\d{2})\.(\d{4})')
TIME_RANGE_RE = re.compile(r'(\d{1,2})[.:](\d{2})\s*[-–]\s*(\d{1,2})[.:](\d{2})')
SINGLE_TIME_RE = re.compile(r'(\d{1,2})[.:](\d{2})')


def read_existing_dienstplan(
    filepath: str | Path,
) -> Tuple[List[Event], List[Dienst], date, date]:
    """Liest den bestehenden Dienstplan aus einer PDF-Datei.

    Returns:
        (events, dienste, plan_start, plan_end)
    """
    events: List[Event] = []
    dienste_map: dict[date, Dienst] = {}

    with pdfplumber.open(str(filepath)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                for row in table:
                    if not row or len(row) < 6:
                        continue

                    parsed = _parse_row(row)
                    if not parsed:
                        continue

                    event, dienst_count = parsed

                    events.append(event)

                    # Dienst für diesen Tag aktualisieren
                    d = event.event_date
                    if d not in dienste_map:
                        dienste_map[d] = Dienst(
                            dienst_date=d,
                            events=[],
                            dienst_count=0.0,
                        )
                    dienste_map[d].events.append(event)
                    dienste_map[d].dienst_count += dienst_count

                    if event.dienst_type in (DienstType.FREI, DienstType.URLAUB, DienstType.REISEZEITAUSGLEICH):
                        dienste_map[d].is_free = True
                        dienste_map[d].dienst_count = 0.0

    # Sortierte Dienste-Liste
    dienste = sorted(dienste_map.values(), key=lambda d: d.dienst_date)

    if dienste:
        plan_start = dienste[0].dienst_date
        plan_end = dienste[-1].dienst_date
    else:
        plan_start = plan_end = date.today()

    return events, dienste, plan_start, plan_end


def _parse_row(row: list) -> Optional[Tuple[Event, float]]:
    """Parst eine Tabellenzeile des bestehenden Dienstplans.

    Returns:
        (Event, dienst_count) oder None wenn nicht parsbar.
    """
    # Bereinige Zellen
    cells = [str(c).strip() if c else "" for c in row]

    # Datum finden
    event_date = None
    for cell in cells[:3]:
        m = DATE_RE.search(cell)
        if m:
            try:
                event_date = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass
            break

    if not event_date:
        return None

    # Zeiten extrahieren
    zeit_text = cells[2] if len(cells) > 2 else ""
    start_time, end_time = _parse_times(zeit_text)

    # Typ erkennen aus Programm-Spalte
    programm = cells[5] if len(cells) > 5 else ""
    dienst_type = _detect_type_from_programm(programm)

    # Formation
    formation_text = cells[3] if len(cells) > 3 else ""
    formation = _parse_formation(formation_text)

    # Dienste-Wert
    dienste_text = cells[8] if len(cells) > 8 else ""
    dienst_count = _parse_dienst_value(dienste_text)

    event = Event(
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        dienst_type=dienst_type,
        formation=formation,
        programm=programm,
        ort=cells[4] if len(cells) > 4 else "",
        leitung=cells[6] if len(cells) > 6 else "",
        kleidung=cells[7] if len(cells) > 7 else "",
        sonstiges=cells[9] if len(cells) > 9 else "",
        raw_text=" | ".join(cells),
    )

    return event, dienst_count


def _parse_times(text: str) -> Tuple[Optional[time], Optional[time]]:
    m = TIME_RANGE_RE.search(text)
    if m:
        return (
            time(int(m.group(1)), int(m.group(2))),
            time(int(m.group(3)), int(m.group(4))),
        )
    m = SINGLE_TIME_RE.search(text)
    if m:
        return time(int(m.group(1)), int(m.group(2))), None
    return None, None


def _detect_type_from_programm(text: str) -> DienstType:
    text_lower = text.lower()
    if "urlaub" in text_lower:
        return DienstType.URLAUB
    if "frei" in text_lower:
        return DienstType.FREI
    if "reisezeitausgleich" in text_lower:
        return DienstType.REISEZEITAUSGLEICH
    if "generalprobe" in text_lower or text.startswith("GP"):
        return DienstType.GENERALPROBE
    if "hauptprobe" in text_lower:
        return DienstType.HAUPTPROBE
    if "anspielprobe" in text_lower or "ansp" in text_lower:
        return DienstType.ANSPIELPROBE
    if "abo-konzert" in text_lower or "abo" in text_lower:
        return DienstType.ABO_KONZERT
    if "schülerkonzert" in text_lower or "sk " in text_lower:
        return DienstType.SCHUELERKONZERT
    if "babykonzert" in text_lower:
        return DienstType.BABYKONZERT
    if "probe" in text_lower:
        return DienstType.PROBE
    if "konzert" in text_lower:
        return DienstType.KONZERT
    if "dirigierkurs" in text_lower:
        return DienstType.DIRIGIERKURS
    if "podcast" in text_lower:
        return DienstType.PODCAST
    return DienstType.SONSTIGES


def _parse_formation(text: str) -> Formation:
    text_lower = text.lower()
    if "sbp" in text_lower:
        return Formation.SBP
    if "brass" in text_lower and "schlag" in text_lower:
        return Formation.BRASS
    if "brass" in text_lower:
        return Formation.BRASS
    if "blq" in text_lower:
        return Formation.BLQ
    if "klq" in text_lower:
        return Formation.KLQ
    if "holz" in text_lower:
        return Formation.HOLZ
    return Formation.UNBEKANNT


def _parse_dienst_value(text: str) -> float:
    text = text.strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0
