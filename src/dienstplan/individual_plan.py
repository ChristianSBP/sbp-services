"""Generierung individueller Dienstpläne pro Musiker.

Filtert den kollektiven Dienstplan auf die Events, die für
einen bestimmten Musiker relevant sind (basierend auf Formation/Ensemble).
"""

from __future__ import annotations

from copy import deepcopy
from typing import List

from .models.events import Event, Dienst, DienstType, Formation
from .models.plan import Dienstplan
from .roster import Musician
from .dienst_calculator import _calc_dienst_value


def create_individual_plan(
    collective_plan: Dienstplan,
    musician: Musician,
    config: dict,
) -> Dienstplan:
    """Erstellt einen individuellen Dienstplan für einen Musiker.

    Filtert alle Dienste auf Events, an denen der Musiker teilnimmt,
    und berechnet die Dienste-Werte pro Tag neu.
    """
    filtered_dienste: List[Dienst] = []

    for dienst in collective_plan.all_dienste():
        filtered = _filter_dienst_for_musician(dienst, musician, config)
        filtered_dienste.append(filtered)

    # Neuen Dienstplan zusammenbauen
    plan = Dienstplan.from_events(
        events=[],
        dienste=filtered_dienste,
        plan_start=collective_plan.plan_start,
        plan_end=collective_plan.plan_end,
    )

    return plan


def _filter_dienst_for_musician(
    dienst: Dienst, musician: Musician, config: dict
) -> Dienst:
    """Filtert einen einzelnen Tages-Dienst für einen Musiker."""

    # Freie Tage / keine Events → für alle beibehalten
    if dienst.is_free or dienst.dienst_count == 0:
        return deepcopy(dienst)

    # Events filtern: nur behalten wo Musiker teilnimmt
    relevant_events: List[Event] = []
    for event in dienst.events:
        # Frei/Reise → gilt für alle
        if event.is_free or event.is_travel:
            relevant_events.append(event)
        elif musician.participates_in(event.formation):
            relevant_events.append(event)

    if not relevant_events:
        # Keine relevanten Events → freier Tag für diesen Musiker
        return Dienst(
            dienst_date=dienst.dienst_date,
            events=[],
            dienst_count=0.0,
            is_free=True,
            is_holiday=dienst.is_holiday,
            holiday_name=dienst.holiday_name,
        )

    # Alle Events sind Frei/Reise → gleich wie Kollektiv-Plan
    if all(e.is_free or e.is_travel for e in relevant_events):
        return Dienst(
            dienst_date=dienst.dienst_date,
            events=relevant_events,
            dienst_count=dienst.dienst_count,
            is_free=dienst.is_free,
            is_holiday=dienst.is_holiday,
            holiday_name=dienst.holiday_name,
            notes=dienst.notes,
        )

    # Dienst-Count für diese Events neu berechnen
    new_count = _calc_dienst_value(relevant_events, config)

    return Dienst(
        dienst_date=dienst.dienst_date,
        events=relevant_events,
        dienst_count=new_count,
        is_free=False,
        is_holiday=dienst.is_holiday,
        holiday_name=dienst.holiday_name,
        notes=dienst.notes,
    )
