"""TVK/HTV-Validator: Führt alle Constraints aus und sammelt Violations."""

from __future__ import annotations

from typing import List, TYPE_CHECKING

from .base import Constraint, Violation, Severity
from .tvk_rules import (
    MaxDienstePerWeek,
    WeeklyDiensteWarning,
    MinFreeDayPerWeek,
    FreeSundaysCount,
    MaxDienstePerDay,
    DailyRestPeriod,
    RehearsalTimeWindow,
    HolidayCompensation,
    SameDayBreak,
    HTVEscalation,
    HTVAusgleichszeitraum,
)

if TYPE_CHECKING:
    from ..models.plan import Dienstplan


class TVKValidator:
    """Führt alle TVK/HTV-Constraints gegen einen Dienstplan aus."""

    def __init__(self, config: dict):
        self.config = config
        self.constraints: List[Constraint] = [
            MaxDienstePerWeek(),
            WeeklyDiensteWarning(),
            MinFreeDayPerWeek(),
            FreeSundaysCount(),
            MaxDienstePerDay(),
            DailyRestPeriod(),
            RehearsalTimeWindow(),
            SameDayBreak(),
            HolidayCompensation(),
            # HTV-spezifische Constraints (deaktivieren sich selbst wenn HTV inaktiv)
            HTVEscalation(),
            HTVAusgleichszeitraum(),
        ]

    def validate(self, plan: Dienstplan) -> List[Violation]:
        """Prüft den Plan gegen alle TVK/HTV-Regeln."""
        all_violations: List[Violation] = []
        for constraint in self.constraints:
            violations = constraint.validate(plan, self.config)
            all_violations.extend(violations)

        severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
        from datetime import date as _date
        all_violations.sort(key=lambda v: (
            severity_order.get(v.severity, 3),
            v.affected_dates[0] if v.affected_dates else _date.max,
        ))

        plan.violations = all_violations
        return all_violations

    def summary(self, violations: List[Violation]) -> dict:
        """Zusammenfassung der Violations."""
        errors = sum(1 for v in violations if v.severity == Severity.ERROR)
        warnings = sum(1 for v in violations if v.severity == Severity.WARNING)
        infos = sum(1 for v in violations if v.severity == Severity.INFO)
        return {
            "total": len(violations),
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
        }
