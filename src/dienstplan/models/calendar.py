"""Kalender-Modelle: Wochen, Ausgleichszeiträume."""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional

from pydantic import BaseModel, Field, computed_field

from .events import Dienst, DienstType


class PlanWeek(BaseModel):
    """Eine Kalenderwoche (Mo–So) im Dienstplan."""
    week_number: int
    year: int
    start_date: date  # Montag
    end_date: date    # Sonntag
    dienste: List[Dienst] = Field(default_factory=list)

    @computed_field
    @property
    def total_dienste(self) -> float:
        return sum(d.dienst_count for d in self.dienste)

    @computed_field
    @property
    def free_days_count(self) -> int:
        return sum(1 for d in self.dienste if d.is_free or d.dienst_count == 0)

    @computed_field
    @property
    def has_free_day(self) -> bool:
        """Mindestens ein komplett dienstfreier Tag in dieser Woche."""
        dienst_dates = {d.dienst_date for d in self.dienste if d.dienst_count > 0}
        all_dates = {self.start_date + timedelta(days=i) for i in range(7)}
        free_dates = all_dates - dienst_dates
        return len(free_dates) >= 1

    @computed_field
    @property
    def is_sunday_free(self) -> bool:
        return not any(
            d.dienst_date == self.end_date and d.dienst_count > 0
            for d in self.dienste
        )

    def tvk_status_for(self, max_weekly: int = 10) -> str:
        """TVK/HTV-Ampel mit konfigurierbarem Limit."""
        if self.total_dienste > max_weekly:
            return "error"
        elif self.total_dienste >= max_weekly - 1:
            return "warning"
        return "ok"

    @property
    def tvk_status(self) -> str:
        """TVK-Ampel: ok / warning / error (Standard: HTV max 10)."""
        return self.tvk_status_for(10)

    def dienst_for_date(self, d: date) -> Optional[Dienst]:
        return next((dienst for dienst in self.dienste if dienst.dienst_date == d), None)


def build_weeks(start: date, end: date) -> List[PlanWeek]:
    """Erstelle leere PlanWeek-Objekte für den Zeitraum."""
    weeks = []
    # Zum Montag der Startwoche gehen
    monday = start - timedelta(days=start.weekday())
    while monday <= end:
        sunday = monday + timedelta(days=6)
        iso_year, iso_week, _ = monday.isocalendar()
        weeks.append(PlanWeek(
            week_number=iso_week,
            year=iso_year,
            start_date=monday,
            end_date=sunday,
        ))
        monday += timedelta(days=7)
    return weeks
