"""Dienstplan-Aggregat."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, computed_field

from .events import Dienst, DienstType, Event
from .calendar import PlanWeek, build_weeks


class Dienstplan(BaseModel):
    """Vollständiger Dienstplan für einen Zeitraum."""
    orchestra_name: str = "Sächsische Bläserphilharmonie"
    plan_start: date
    plan_end: date
    weeks: List[PlanWeek] = Field(default_factory=list)
    violations: List = Field(default_factory=list)

    @computed_field
    @property
    def total_dienste(self) -> float:
        return sum(w.total_dienste for w in self.weeks)

    @computed_field
    @property
    def total_weeks(self) -> int:
        return len(self.weeks)

    @computed_field
    @property
    def avg_dienste_per_week(self) -> float:
        if not self.weeks:
            return 0.0
        return round(self.total_dienste / len(self.weeks), 1)

    @computed_field
    @property
    def free_sundays(self) -> int:
        return sum(1 for w in self.weeks if w.is_sunday_free)

    @computed_field
    @property
    def weeks_with_violations(self) -> int:
        return sum(1 for w in self.weeks if w.tvk_status == "error")

    @computed_field
    @property
    def total_free_days(self) -> int:
        return sum(w.free_days_count for w in self.weeks)

    def all_dienste(self) -> List[Dienst]:
        """Flache Liste aller Dienste."""
        result = []
        for week in self.weeks:
            result.extend(week.dienste)
        return sorted(result, key=lambda d: d.dienst_date)

    def dienste_by_type(self) -> dict[DienstType, int]:
        """Dienste-Verteilung nach Typ."""
        counts: dict[DienstType, int] = {}
        for d in self.all_dienste():
            if d.dienst_count > 0:
                t = d.primary_type
                counts[t] = counts.get(t, 0) + 1
        return counts

    @classmethod
    def from_events(
        cls,
        events: List[Event],
        dienste: List[Dienst],
        plan_start: date,
        plan_end: date,
    ) -> Dienstplan:
        """Erstelle Dienstplan aus Events und berechneten Diensten."""
        weeks = build_weeks(plan_start, plan_end)

        # Dienste den Wochen zuordnen
        for dienst in dienste:
            for week in weeks:
                if week.start_date <= dienst.dienst_date <= week.end_date:
                    week.dienste.append(dienst)
                    break

        return cls(
            plan_start=plan_start,
            plan_end=plan_end,
            weeks=weeks,
        )
