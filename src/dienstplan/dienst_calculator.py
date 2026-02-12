"""Automatische Dienste-Berechnung basierend auf TVK/HTV-Regeln und SBP-Praxis.

Berechnet den Dienste-Wert (1, 1.5, 2, 2.5, 3) für jeden Tag
basierend auf den Events des Tages.

HTV-Abweichungen (5. HTV SBP vom 04.12.2025):
- Kinderkonzerte: identische Doppelvorstellungen <3h = 1 Dienst
- Akademiedienst: 1-3h=1, 3-6h=2, 6+=3 Dienste
- Doppeldienst: 2 Proben kombiniert max 4,5h
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, time
from typing import List, Optional

import holidays

from .models.events import Event, Dienst, DienstType, Formation
from .config import is_htv_active


def calculate_dienste(
    events: List[Event],
    config: dict,
    plan_start: date,
    plan_end: date,
) -> List[Dienst]:
    """Berechnet Dienste für jeden Tag im Zeitraum."""
    bundesland = config.get("tvk", {}).get("orchester", {}).get("bundesland", "SN")
    de_holidays = holidays.Germany(years=[plan_start.year, plan_end.year], state=bundesland)

    # Events nach Datum gruppieren
    events_by_date: dict[date, List[Event]] = defaultdict(list)
    for event in events:
        if plan_start <= event.event_date <= plan_end:
            events_by_date[event.event_date].append(event)

    # Für jeden Tag im Zeitraum einen Dienst erstellen
    dienste: List[Dienst] = []
    current = plan_start
    while current <= plan_end:
        day_events = events_by_date.get(current, [])
        is_holiday = current in de_holidays
        holiday_name = de_holidays.get(current, "")

        dienst = _calculate_day(current, day_events, config, is_holiday, holiday_name)
        dienste.append(dienst)

        current = date.fromordinal(current.toordinal() + 1)

    return dienste


def _calculate_day(
    day: date,
    events: List[Event],
    config: dict,
    is_holiday: bool,
    holiday_name: str,
) -> Dienst:
    """Berechnet den Dienste-Wert für einen einzelnen Tag."""
    dienst = Dienst(
        dienst_date=day,
        events=events,
        is_holiday=is_holiday,
        holiday_name=holiday_name,
    )

    if not events:
        dienst.is_free = True
        dienst.dienst_count = 0.0
        return dienst

    # Prüfe ob es ein freier Tag ist
    if any(e.dienst_type in (DienstType.FREI, DienstType.URLAUB, DienstType.REISEZEITAUSGLEICH) for e in events):
        dienst.is_free = True
        dienst.dienst_count = 0.0
        return dienst

    # Prüfe ob es ein reiner Reisetag ist (ohne Performance)
    if all(e.dienst_type == DienstType.REISE for e in events):
        dienst.is_free = False
        if is_htv_active(config):
            # HTV §12 Protokollnotiz 3: Reisezeit gilt als Dienst
            dienst.dienst_count = 1.0
            dienst.notes = "Reisetag (HTV: 1 Dienst)"
        else:
            dienst.dienst_count = 0.0
            dienst.notes = "Reisetag"
        return dienst

    # Berechne Dienste-Wert
    dienst.dienst_count = _calc_dienst_value(events, config)
    return dienst


def _calc_dienst_value(events: List[Event], config: dict) -> float:
    """Berechnet den Dienste-Wert basierend auf Events des Tages."""
    calc_config = config.get("dienst_berechnung", {})
    htv_active = is_htv_active(config)
    htv_config = config.get("htv", {}) if htv_active else {}

    # Filtere nicht-relevante Events
    # Hinweis: REISE wird nicht mehr gefiltert — gilt als Dienst bei HTV (§12 Protokollnotiz 3)
    active_events = [e for e in events if e.dienst_type not in (
        DienstType.FREI, DienstType.URLAUB, DienstType.REISEZEITAUSGLEICH
    )]

    if not active_events:
        return 0.0

    # Sonstiges ohne Zeitangabe = kein Dienst
    if all(
        e.dienst_type == DienstType.SONSTIGES and e.start_time is None
        for e in active_events
    ):
        return 0.0

    probe_kurz_max = calc_config.get("probe_kurz_max_minutes", 180)

    # === Nicht-überlappende Kammermusik-Ensembles ===
    # Wenn alle Events aus verschiedenen, nicht-überlappenden Formationen stammen
    # (z.B. BRASS + BLQ), zählt der Tag als 1 Dienst im Gesamtplan,
    # da kein Musiker in beiden Ensembles spielt.
    _NON_OVERLAPPING = {
        Formation.BRASS, Formation.BRASS_OHNE, Formation.BLQ,
        Formation.KLQ, Formation.SBQ, Formation.SERENADEN,
    }
    formations = {e.formation for e in active_events}
    if (len(formations) > 1
            and Formation.SBP not in formations
            and formations.issubset(_NON_OVERLAPPING)):
        return 1.0

    # === HTV: Akademiedienst ===
    akademie_events = [e for e in active_events if e.dienst_type == DienstType.AKADEMIEDIENST]
    if akademie_events:
        return _calc_akademiedienst(akademie_events, htv_config.get("akademiedienst", {}))

    # === Anspielprobe + Konzert ===
    has_anspielprobe = any(e.dienst_type == DienstType.ANSPIELPROBE for e in active_events)
    has_konzert = any(e.dienst_type in (
        DienstType.KONZERT, DienstType.ABO_KONZERT, DienstType.GASTSPIEL
    ) for e in active_events)

    if has_anspielprobe and has_konzert and len(active_events) <= 2:
        return calc_config.get("anspielprobe_plus_konzert", 1.5)

    # === Schüler-/Kinder-/Babykonzert ===
    # HTV Protokollnotiz 2: Identische Doppelvorstellungen bei Baby-/Kita-/Kinder-/
    # Schüler-/Jugendkonzerten = 1 Dienst wenn ≤3h Gesamtdauer
    kinder_types = {DienstType.SCHUELERKONZERT, DienstType.BABYKONZERT}
    sk_events = [e for e in active_events if e.dienst_type in kinder_types]
    if sk_events:
        raw = " ".join(e.raw_text for e in sk_events)
        if "&" in raw or "11:30" in raw:
            # Doppelvorstellung erkannt
            if htv_active:
                kk_config = htv_config.get("kinderkonzerte", {})
                max_min = kk_config.get("identical_back_to_back_max_minutes", 180)
                htv_dienst = kk_config.get("identical_back_to_back_dienst_count", 1.0)
                total_dur = sum(e.duration_minutes or 0 for e in sk_events)
                if total_dur > max_min:
                    # Dauer definitiv >3h → TVK-Standard (1.5)
                    base = calc_config.get("schuelerkonzert_doppel", 1.5)
                else:
                    # Identische Doppelvorstellung ≤3h (oder Dauer unbekannt) → 1 Dienst
                    base = htv_dienst
            else:
                base = calc_config.get("schuelerkonzert_doppel", 1.5)

            has_bus = any("Bus" in e.raw_text or "07:" in e.raw_text or "08:" in e.raw_text
                         for e in events)
            if has_bus:
                base += 0.5
            other_events = [e for e in active_events if e.dienst_type not in kinder_types]
            if other_events:
                base += _calc_single_events(other_events, probe_kurz_max)
            return base
        return 1.0

    # === Dirigierkurs ===
    if any(e.dienst_type == DienstType.DIRIGIERKURS for e in active_events):
        return calc_config.get("dirigierkurs_ganztag", 2.0)

    # === Podcast / Tonaufnahme ===
    if any(e.dienst_type in (DienstType.PODCAST, DienstType.TONAUFNAHME) for e in active_events):
        return calc_config.get("podcast_aufnahme", 2.0)

    # === HTV: Doppeldienst (2 Proben kombiniert max 4,5h) ===
    if htv_active:
        probe_types = {DienstType.PROBE, DienstType.GENERALPROBE, DienstType.HAUPTPROBE}
        probe_events = [e for e in active_events if e.dienst_type in probe_types]
        if len(probe_events) == 2:
            dd_max = htv_config.get("doppeldienst", {}).get("max_combined_minutes", 270)
            combined = sum(e.duration_minutes or 0 for e in probe_events)
            if 0 < combined <= dd_max:
                return 2.0

    # === Standard: Einzelevents summieren ===
    total = _calc_single_events(active_events, probe_kurz_max)

    has_bus = any("Bus" in e.raw_text for e in events)
    if has_bus and total > 0:
        total += 0.5

    return total


def _calc_akademiedienst(events: List[Event], akademie_config: dict) -> float:
    """HTV Akademiedienst-Berechnung: Stufenweise nach Dauer."""
    total_minutes = sum(e.duration_minutes or 0 for e in events)
    total_hours = total_minutes / 60.0

    tier_1_max = akademie_config.get("tier_1_max_hours", 3)
    tier_2_max = akademie_config.get("tier_2_max_hours", 6)

    if total_hours <= tier_1_max:
        return akademie_config.get("tier_1_dienste", 1.0)
    elif total_hours <= tier_2_max:
        return akademie_config.get("tier_2_dienste", 2.0)
    else:
        return akademie_config.get("tier_3_dienste", 3.0)


def _calc_single_events(events: List[Event], probe_kurz_max: int) -> float:
    """Berechnet Dienste-Wert für eine Liste von Einzel-Events."""
    total = 0.0

    for event in events:
        if event.dienst_type in (DienstType.DIENSTBERATUNG, DienstType.PROBESPIEL):
            total += 1.0
            continue

        duration = event.duration_minutes
        if duration is not None:
            if duration <= probe_kurz_max:
                total += 1.0
            else:
                total += 2.0
        else:
            if event.dienst_type in (DienstType.KONZERT, DienstType.ABO_KONZERT, DienstType.GASTSPIEL):
                total += 1.0
            elif event.dienst_type in (DienstType.PROBE, DienstType.GENERALPROBE, DienstType.HAUPTPROBE):
                total += 1.0
            elif event.dienst_type == DienstType.ANSPIELPROBE:
                total += 0.5
            elif event.dienst_type == DienstType.BABYKONZERT:
                total += 1.0
            elif event.dienst_type == DienstType.SONSTIGES:
                raw = event.raw_text.lower()
                if any(kw in raw for kw in ["stadtmusik", "orchestertag", "ostinato", "treffen", "betriebsärzt"]):
                    total += 0.0
                else:
                    total += 1.0
            else:
                total += 1.0

    return total
