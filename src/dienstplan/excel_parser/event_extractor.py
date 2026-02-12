"""Extrahiert strukturierte Events aus den Rohtext-Zellen des Jahresplans.

Parst Zelltexte wie:
  "Probe NY 09:30-14:00"
  "Bad Lausick 20:00 - Sommerer - Kahle"
  "SK SBP Hohburg/Lossatal 10:00 & 11:30 Kofferprogramm"
  "Abflug nach NYC"
  "Urlaub 31"
  "Frei"
  "Karfreitag - freier Tag"
"""

from __future__ import annotations

import re
from datetime import date, time
from typing import List, Optional, Tuple, Set

from ..models.events import Event, DienstType, Formation
from .reader import JahresplanCell


# Regex-Patterns
TIME_RANGE_RE = re.compile(
    r'(\d{1,2})[.:](\d{2})\s*[-–]\s*(\d{1,2})[.:](\d{2})'
)
SINGLE_TIME_RE = re.compile(
    r'(?<!\d)(\d{1,2})[.:](\d{2})(?!\s*[-–]\s*\d)'
)
DOUBLE_TIME_RE = re.compile(
    r'(\d{1,2})[.:](\d{2})\s*[&]\s*(\d{1,2})[.:](\d{2})'
)

# Typ-Keywords (Reihenfolge = Priorität – erste Treffer gewinnt!)
TYPE_KEYWORDS: List[Tuple[str, DienstType]] = [
    # Frei/Urlaub zuerst (höchste Prio)
    (r'\bUrlaub\b', DienstType.URLAUB),
    (r'\bfrei\b', DienstType.FREI),
    (r'\bfreier Tag\b', DienstType.FREI),
    (r'\bMuss frei bleiben\b', DienstType.FREI),
    # Reisezeitausgleich vor Reise
    (r'[Rr]eisezeitausgleich', DienstType.REISEZEITAUSGLEICH),
    (r'[Aa]usgleich(?:s)?zeitraum', DienstType.REISEZEITAUSGLEICH),
    (r'[Aa]usgleichzeitraum', DienstType.REISEZEITAUSGLEICH),
    # Reise
    (r'\bAbflug\b', DienstType.REISE),
    (r'\bRückflug\b', DienstType.REISE),
    (r'\bHinfahrt\b', DienstType.REISE),
    (r'\bRückreise\b', DienstType.REISE),
    (r'\bRückfahrt\b', DienstType.REISE),
    (r'\bBusabfahrt\b', DienstType.REISE),
    (r'\bAnkunft\b', DienstType.REISE),
    # Proben (spezifisch vor generisch)
    (r'\bGeneralprobe\b', DienstType.GENERALPROBE),
    (r'\bGP\b', DienstType.GENERALPROBE),
    (r'\bHauptprobe\b', DienstType.HAUPTPROBE),
    (r'\bHP\b', DienstType.HAUPTPROBE),
    (r'\bAnspielprobe\b', DienstType.ANSPIELPROBE),
    (r'\bAnsp\.\s*\d', DienstType.ANSPIELPROBE),
    # Schulkonzerte, Babykonzerte
    (r'\bSK\b', DienstType.SCHUELERKONZERT),
    (r'\bSchülerkonzert', DienstType.SCHUELERKONZERT),
    (r'\bBabykonzert\b', DienstType.BABYKONZERT),
    (r'\bKuscheltierkonzert\b', DienstType.BABYKONZERT),
    (r'\bFamilienkonzert\b', DienstType.KONZERT),
    (r'\bStadtfest\b', DienstType.KONZERT),
    (r'\bMarktfest\b', DienstType.KONZERT),
    # Konzerte
    (r'\bAbo-Konzert\b', DienstType.ABO_KONZERT),
    (r'\bAbo\b.*\bKonzert', DienstType.ABO_KONZERT),
    (r'\bKonzert\b', DienstType.KONZERT),
    # Spezialtypen
    (r'\bDirigierkurs\b', DienstType.DIRIGIERKURS),
    (r'\bHfM\b', DienstType.DIRIGIERKURS),
    (r'\bHfMT\b', DienstType.DIRIGIERKURS),
    (r'\bHochschule\b', DienstType.DIRIGIERKURS),
    (r'\bAkademie\b', DienstType.AKADEMIEDIENST),
    (r'\bPodcast\b', DienstType.PODCAST),
    (r'\bAufnahme\b', DienstType.TONAUFNAHME),
    (r'\bTonaufnahme\b', DienstType.TONAUFNAHME),
    (r'\bProbespiel\b', DienstType.PROBESPIEL),
    (r'\bBetriebsratswahl\b', DienstType.DIENSTBERATUNG),
    (r'\bDienstberatung\b', DienstType.DIENSTBERATUNG),
    (r'\bBetriebsärztliche\b', DienstType.DIENSTBERATUNG),
    (r'\bGastspiel\b', DienstType.GASTSPIEL),
    (r'\bStadtmusik\b', DienstType.SONSTIGES),
    (r'\bÜberregionaler\b', DienstType.SONSTIGES),
    (r'\bOSTINATO\b', DienstType.SONSTIGES),
    (r'\bTreffen\b', DienstType.SONSTIGES),
    (r'\bMitgliederversammlung\b', DienstType.SONSTIGES),
    # Probe generisch (ganz unten)
    (r'\bProbe\b', DienstType.PROBE),
    (r'\bLeseprobe\b', DienstType.PROBE),
    (r'\bSichtung\b', DienstType.PROBE),
    (r'\bEinspieldienst\b', DienstType.PROBE),
]

# Formations-Keywords
FORMATION_KEYWORDS: List[Tuple[str, Formation]] = [
    (r'\bBrass inkl\.?\s*Schlagz\.?\b', Formation.BRASS),
    (r'\bBrass ohne\s*Schlagz\.?\b', Formation.BRASS_OHNE),
    (r'\bBlechbläser\b.*\bSchlag', Formation.BRASS),
    (r'\bBrass\b', Formation.BRASS),
    (r'\bBLQ\b', Formation.BLQ),
    (r'\bKLQ\b', Formation.KLQ),
    (r'\bSBQ\b', Formation.SBQ),
    (r'\bSerenaden', Formation.SERENADEN),
    (r'\bHolz\b', Formation.HOLZ),
    (r'\bBlech\b', Formation.BLECH),
    (r'\bSchlagwerk\b', Formation.SCHLAGWERK),
    (r'\bKontrabass\b', Formation.KONTRABASS),
    (r'\bGremien\b', Formation.GREMIEN),
    (r'\bStrategierat\b', Formation.STRATEGIERAT),
    (r'\bGruppen\b', Formation.GRUPPEN),
    (r'\bSBP\b', Formation.SBP),
]

# Bekannte Feiertage als Keywords
HOLIDAY_KEYWORDS = [
    "Karfreitag", "Ostersonntag", "Ostermontag",
    "Tag der Arbeit", "Christi Himmelfahrt",
    "Pfingstsonntag", "Pfingstmontag",
    "Tag der Deutschen Einheit", "Reformationstag",
    "Buß- und Bettag", "1. Weihnachtsfeiertag", "2. Weihnachtsfeiertag",
]


def extract_events(cells: List[JahresplanCell], config: dict) -> List[Event]:
    """Extrahiert Event-Objekte aus Jahresplan-Zellen.

    Wendet Filterung, Datumskorrekturen, Kleidung- und Ort-Anreicherung an.
    """
    events: List[Event] = []
    bekannte_leiter = config.get("bekannte_leiter", [])
    bekannte_orte = config.get("bekannte_orte", [])
    exclude_keywords = config.get("exclude_keywords", [])
    venue_addresses = config.get("venue_addresses", {})
    kleidung_rules = config.get("kleidung_rules", {})

    # Für Premiere-Erkennung: welche Programm-Texte schon gesehen wurden
    seen_programs: Set[str] = set()

    for cell in cells:
        text = cell.text
        if not text:
            continue

        # Zelle in einzelne Event-Texte aufteilen (Multi-Event-Erkennung)
        # WICHTIG: Split VOR exclude-Prüfung, da eine Zelle sowohl relevante
        # als auch nicht-relevante Events enthalten kann (z.B. "Brass / Mitgliederversammlung")
        event_texts = _split_cell_text(text)

        # Nur wenn KEIN Split stattfand: Gesamttext prüfen (Performance)
        if len(event_texts) == 1 and _should_exclude(text, exclude_keywords):
            continue

        for part_text in event_texts:
            part_text = part_text.strip()
            if not part_text:
                continue

            # Einzelne Event-Teile auch gegen exclude-Keywords prüfen
            if _should_exclude(part_text, exclude_keywords):
                continue

            event = Event(
                event_date=cell.event_date,
                raw_text=part_text,
            )

            # Typ erkennen
            event.dienst_type = _detect_type(part_text)

            # Zeiten extrahieren
            start, end = _extract_times(part_text)
            event.start_time = start
            event.end_time = end

            # Formation erkennen
            event.formation = _detect_formation(part_text)

            # Ort erkennen (mit Adress-Anreicherung)
            event.ort = _detect_ort(part_text, bekannte_orte, venue_addresses)

            # Leitung erkennen
            event.leitung = _detect_leiter(part_text, bekannte_leiter)

            # Programm = bereinigter Text
            event.programm = _clean_programm(part_text)

            # Kleidung ableiten
            event.kleidung = _infer_kleidung(event, kleidung_rules, seen_programs)

            # Sonstiges extrahieren (Logistik-Infos)
            event.sonstiges = _extract_sonstiges(part_text)

            events.append(event)

    # Datumskorrekturen anwenden
    date_corrections = config.get("date_corrections", {})
    if date_corrections:
        events = _apply_date_corrections(events, date_corrections, config)

    return sorted(events, key=lambda e: (e.event_date, e.start_time or time(0)))


def _should_exclude(text: str, keywords: List[str]) -> bool:
    """Prüft ob der Text zu einem nicht-relevanten Event gehört."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _apply_date_corrections(
    events: List[Event], corrections: dict, config: dict
) -> List[Event]:
    """Wendet Datumskorrekturen aus der Config an."""
    bekannte_leiter = config.get("bekannte_leiter", [])
    bekannte_orte = config.get("bekannte_orte", [])
    venue_addresses = config.get("venue_addresses", {})
    kleidung_rules = config.get("kleidung_rules", {})

    for date_str, correction in corrections.items():
        try:
            parts = date_str.split("-")
            corr_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            continue

        override_text = correction.get("override_text", "")
        if override_text:
            # Bestehende Events für dieses Datum entfernen und ersetzen
            events = [e for e in events if e.event_date != corr_date]

            for part in override_text.split(" + "):
                part = part.strip()
                if not part:
                    continue

                event = Event(event_date=corr_date, raw_text=part)
                event.dienst_type = _detect_type(part)
                start, end = _extract_times(part)
                event.start_time = start
                event.end_time = end
                event.formation = _detect_formation(part)
                event.ort = _detect_ort(part, bekannte_orte, venue_addresses)
                event.leitung = _detect_leiter(part, bekannte_leiter)
                event.programm = _clean_programm(part)
                event.kleidung = _infer_kleidung(event, kleidung_rules, set())
                event.sonstiges = correction.get("note", "")

                events.append(event)

        # Events hinzufügen (ohne bestehende zu löschen)
        add_texts = correction.get("add_events", [])
        for add_text in add_texts:
            add_text = add_text.strip()
            if not add_text:
                continue

            event = Event(event_date=corr_date, raw_text=add_text)
            event.dienst_type = _detect_type(add_text)
            start, end = _extract_times(add_text)
            event.start_time = start
            event.end_time = end
            event.formation = _detect_formation(add_text)
            event.ort = _detect_ort(add_text, bekannte_orte, venue_addresses)
            event.leitung = _detect_leiter(add_text, bekannte_leiter)
            event.programm = _clean_programm(add_text)
            event.kleidung = _infer_kleidung(event, kleidung_rules, set())
            event.sonstiges = correction.get("note", "")

            events.append(event)

    return events


def _infer_kleidung(event: Event, rules: dict, seen_programs: Set[str]) -> str:
    """Leitet die Kleidung aus dem Diensttyp und Kontext ab."""
    dt = event.dienst_type

    if dt in (DienstType.PROBE, DienstType.GENERALPROBE,
              DienstType.HAUPTPROBE, DienstType.ANSPIELPROBE):
        return rules.get("rehearsal", "")

    if dt == DienstType.SCHUELERKONZERT:
        return rules.get("school_concert", "Polo-Shirts/Jeans/Sneakers")

    if dt == DienstType.BABYKONZERT:
        return rules.get("baby_concert", "Polo-Shirts/Jeans/Sneakers")

    if dt == DienstType.GASTSPIEL:
        return rules.get("gastspiel", "Schw. Anzug/weißes Hemd/Krawatte")

    if dt == DienstType.ABO_KONZERT:
        programm_key = event.programm.strip().lower()
        if programm_key and programm_key in seen_programs:
            return rules.get("repeat_abo", "Schw. Anzug/weißes Hemd/Krawatte")
        else:
            if programm_key:
                seen_programs.add(programm_key)
            return rules.get("premiere_abo", "Frack")

    if dt == DienstType.KONZERT:
        return rules.get("repeat_abo", "Schw. Anzug/weißes Hemd/Krawatte")

    return rules.get("default", "")


def _extract_sonstiges(text: str) -> str:
    """Extrahiert Logistik-Informationen für die Sonstiges-Spalte."""
    notes = []

    bus_match = re.search(r'(Bus\s*(?:ab\s*)?\d{1,2}[.:]\d{2})', text, re.IGNORECASE)
    if bus_match:
        notes.append(bus_match.group(1))

    if re.search(r'\bBusabfahrt\b', text):
        notes.append("Busfahrt")

    if re.search(r'\b(Abflug|Rückflug|Flug)\b', text, re.IGNORECASE):
        notes.append("Reise/Flug")

    return "; ".join(notes)


def _split_cell_text(text: str) -> List[str]:
    """Teilt eine Zelle mit mehreren Events in einzelne Event-Texte.

    Der Jahresplan der SBP enthält häufig mehrere Termine in einer Zelle.
    Erkannte Muster:

    1. Anspielprobe + Konzert:
       "Bad Düben 15:00 - Ansp. 13:45-14:15" → 2 Events
    2. Slash-Separator mit eigenen Zeiten:
       "GP Brass 11:00-14:00/ 15-17.30 SBP Supervulkan" → 2 Events
    3. Newline-Separator mit eigenen Zeiten:
       "Konzert Brass 19:00\\nProbe KLQ 09:30-14:00" → 2 Events
    """
    text_clean = text.strip()
    if not text_clean:
        return [text]

    # === Muster 1: "Ort HH:MM ... Ansp. HH:MM-HH:MM" ===
    # Erkennt: "Bad Düben 15:00 - Ansp. 13:45-14:15"
    #          "Trebsen 16:00 - Ansp. 14:30-15:15"
    #          "Oschatz 17:00 St. Ägidien Kirche - Ansp. 15:30-16:15 - ..."
    ansp_match = re.search(
        r'(Ansp\.?\s*\d{1,2}[.:]\d{2}\s*[-–]\s*\d{1,2}[.:]\d{2})',
        text_clean
    )
    if ansp_match:
        ansp_text = ansp_match.group(1).strip()
        # Rest des Texts ohne die Anspielprobe = Konzert-Teil
        rest = text_clean[:ansp_match.start()] + text_clean[ansp_match.end():]
        rest = rest.strip().strip('-–').strip().rstrip(',').strip()
        if rest:
            return [ansp_text, rest]
        return [ansp_text]

    # === Muster 2: '/' als Separator ===
    # "GP Brass 11:00-14:00/ 15-17.30 SBP Supervulkan"
    # "10:00 Betriebsratswahl / 11:00 Probespiel Bariton"
    # ABER NICHT: "Hohburg/Lossatal" (Ortsname)
    if '/' in text_clean:
        slash_parts = re.split(r'\s*/\s*|\s*/|/\s*', text_clean)
        valid_parts = [p.strip() for p in slash_parts if p.strip()]
        if len(valid_parts) >= 2:
            # Mindestens ein Teil nach dem ersten muss eine Zeitangabe haben
            has_time_after = any(
                re.search(r'\d{1,2}[.:]\d{2}', p) for p in valid_parts[1:]
            )
            if has_time_after:
                return valid_parts

    # === Muster 3: Newline-Separator ===
    # Zellen mit Zeilenumbrüchen, wo jeder Teil eigene Zeiten hat
    if '\n' in text_clean:
        nl_parts = [p.strip() for p in text_clean.split('\n') if p.strip()]
        if len(nl_parts) >= 2:
            # Prüfe ob mindestens 2 Teile eigene Zeitangaben haben
            parts_with_time = sum(
                1 for p in nl_parts if re.search(r'\d{1,2}[.:]\d{2}', p)
            )
            if parts_with_time >= 2:
                return nl_parts

    return [text]


def _detect_type(text: str) -> DienstType:
    """Erkennt den Diensttyp aus dem Zelltext."""
    for pattern, dtype in TYPE_KEYWORDS:
        if re.search(pattern, text, re.IGNORECASE):
            return dtype
    for holiday in HOLIDAY_KEYWORDS:
        if holiday.lower() in text.lower():
            if "frei" in text.lower():
                return DienstType.FREI
            return DienstType.SONSTIGES
    if SINGLE_TIME_RE.search(text) or TIME_RANGE_RE.search(text):
        return DienstType.KONZERT
    return DienstType.SONSTIGES


def _extract_times(text: str) -> Tuple[Optional[time], Optional[time]]:
    """Extrahiert Start- und Endzeit aus dem Text."""
    m = TIME_RANGE_RE.search(text)
    if m:
        start = time(int(m.group(1)), int(m.group(2)))
        end = time(int(m.group(3)), int(m.group(4)))
        return start, end

    matches = SINGLE_TIME_RE.findall(text)
    if matches:
        h, m_val = int(matches[0][0]), int(matches[0][1])
        if 0 <= h <= 23 and 0 <= m_val <= 59:
            return time(h, m_val), None

    return None, None


def _detect_formation(text: str) -> Formation:
    """Erkennt die Besetzung aus dem Text."""
    for pattern, formation in FORMATION_KEYWORDS:
        if re.search(pattern, text, re.IGNORECASE):
            return formation
    return Formation.SBP


def _detect_ort(text: str, bekannte_orte: List[str],
                venue_addresses: dict = None) -> str:
    """Erkennt den Aufführungsort und reichert mit Adresse an."""
    if venue_addresses is None:
        venue_addresses = {}

    for ort in sorted(bekannte_orte, key=len, reverse=True):
        if ort.lower() in text.lower():
            return venue_addresses.get(ort, ort)
    return ""


def _detect_leiter(text: str, bekannte_leiter: List[str]) -> str:
    """Erkennt den Dirigenten/Leiter."""
    for leiter in bekannte_leiter:
        if leiter.lower() in text.lower():
            return leiter
    return ""


def _clean_programm(text: str) -> str:
    """Bereinigt den Text für die Programm-Spalte."""
    cleaned = TIME_RANGE_RE.sub("", text)
    cleaned = re.sub(r'\d{1,2}[.:]\d{2}', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = cleaned.strip(' -–')
    return cleaned if cleaned else text
