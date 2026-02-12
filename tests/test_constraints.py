"""Tests für die TVK/HTV-Constraints."""

import pytest
from datetime import date, time

from dienstplan.models.events import Event, Dienst, DienstType
from dienstplan.models.calendar import PlanWeek
from dienstplan.models.plan import Dienstplan
from dienstplan.constraints.base import Severity
from dienstplan.constraints.tvk_rules import (
    MaxDienstePerWeek,
    MinFreeDayPerWeek,
    WeeklyDiensteWarning,
    HTVEscalation,
    HTVAusgleichszeitraum,
)
from dienstplan.dienst_calculator import calculate_dienste


def _make_plan_with_weekly_dienste(dienst_count: float, week_num: int = 10):
    """Hilfsfunktion: Erstellt Plan mit einer Woche und gegebener Dienst-Summe."""
    start = date(2026, 3, 2)  # Montag KW 10
    end = date(2026, 3, 8)    # Sonntag KW 10

    events = []
    dienste = []
    remaining = dienst_count
    for i in range(7):
        d = date(2026, 3, 2 + i)
        if remaining > 0:
            count = min(remaining, 2.0)
            dienste.append(Dienst(
                dienst_date=d,
                events=[Event(
                    event_date=d, start_time=time(10, 0),
                    dienst_type=DienstType.KONZERT, raw_text="Test"
                )],
                dienst_count=count,
            ))
            remaining -= count
        else:
            dienste.append(Dienst(dienst_date=d, dienst_count=0.0, is_free=True))

    return Dienstplan.from_events(events, dienste, start, end)


def _make_multi_week_plan(weekly_counts: list):
    """Erstellt Plan mit mehreren Wochen, jede mit gegebener Dienst-Summe."""
    all_dienste = []
    base = date(2026, 3, 2)  # KW 10 Montag

    for week_idx, count in enumerate(weekly_counts):
        remaining = count
        for day in range(7):
            d = base + __import__('datetime').timedelta(days=week_idx * 7 + day)
            if remaining > 0:
                dc = min(remaining, 2.0)
                all_dienste.append(Dienst(
                    dienst_date=d,
                    events=[Event(event_date=d, start_time=time(10, 0),
                                  dienst_type=DienstType.KONZERT, raw_text="Test")],
                    dienst_count=dc,
                ))
                remaining -= dc
            else:
                all_dienste.append(Dienst(dienst_date=d, dienst_count=0.0, is_free=True))

    total_days = len(weekly_counts) * 7
    plan_start = base
    plan_end = base + __import__('datetime').timedelta(days=total_days - 1)
    return Dienstplan.from_events([], all_dienste, plan_start, plan_end)


# ============================================================
# Standard-Tests (HTV-Modus, da config Default HTV aktiv ist)
# ============================================================

class TestMaxDienstePerWeek:
    """Max Dienste pro Woche — HTV: max 10, TVK: max 8."""

    def test_under_limit_no_violation(self, config):
        """6 Dienste: keine Verletzung bei HTV oder TVK."""
        plan = _make_plan_with_weekly_dienste(6.0)
        violations = MaxDienstePerWeek().validate(plan, config)
        assert len(violations) == 0

    def test_at_htv_limit_no_error(self, config):
        """10 Dienste = genau am HTV-Limit → kein Fehler."""
        plan = _make_plan_with_weekly_dienste(10.0)
        violations = MaxDienstePerWeek().validate(plan, config)
        errors = [v for v in violations if v.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_over_htv_limit_error(self, config):
        """10.5 Dienste: über dem HTV-Limit von 10."""
        plan = _make_plan_with_weekly_dienste(10.5)
        violations = MaxDienstePerWeek().validate(plan, config)
        errors = [v for v in violations if v.severity == Severity.ERROR]
        assert len(errors) == 1
        assert errors[0].current_value == 10.5
        assert errors[0].limit_value == 10

    def test_tvk_only_over_limit(self, tvk_only_config):
        """9.5 Dienste: über TVK-Limit von 8 (aber unter HTV 10)."""
        plan = _make_plan_with_weekly_dienste(9.5)
        violations = MaxDienstePerWeek().validate(plan, tvk_only_config)
        errors = [v for v in violations if v.severity == Severity.ERROR]
        assert len(errors) == 1
        assert errors[0].current_value == 9.5
        assert errors[0].limit_value == 8

    def test_tvk_only_at_limit_no_error(self, tvk_only_config):
        """8 Dienste: genau am TVK-Limit → kein Fehler."""
        plan = _make_plan_with_weekly_dienste(8.0)
        violations = MaxDienstePerWeek().validate(plan, tvk_only_config)
        errors = [v for v in violations if v.severity == Severity.ERROR]
        assert len(errors) == 0


class TestMinFreeDayPerWeek:
    """§16 Abs. 1: Min 1 freier Tag pro Woche."""

    def test_free_day_exists_no_violation(self, config):
        plan = _make_plan_with_weekly_dienste(6.0)  # 3 Tage frei, 4 Tage Dienst
        violations = MinFreeDayPerWeek().validate(plan, config)
        assert len(violations) == 0

    def test_no_free_day_violation(self, config):
        # Alle 7 Tage mit Dienst
        start = date(2026, 3, 2)
        end = date(2026, 3, 8)
        dienste = []
        for i in range(7):
            d = date(2026, 3, 2 + i)
            dienste.append(Dienst(
                dienst_date=d,
                events=[Event(event_date=d, dienst_type=DienstType.KONZERT, raw_text="Test")],
                dienst_count=1.0,
            ))
        plan = Dienstplan.from_events([], dienste, start, end)
        violations = MinFreeDayPerWeek().validate(plan, config)
        errors = [v for v in violations if v.severity == Severity.ERROR]
        assert len(errors) == 1


class TestWeeklyWarning:
    """Warnung bei Annäherung an Wochen-Limit."""

    def test_htv_9_dienste_warning(self, config):
        """HTV: 9 Dienste = max-1 → Warnung."""
        plan = _make_plan_with_weekly_dienste(9.0)
        violations = WeeklyDiensteWarning().validate(plan, config)
        warnings = [v for v in violations if v.severity == Severity.WARNING]
        assert len(warnings) == 1

    def test_htv_8_dienste_no_warning(self, config):
        """HTV: 8 Dienste = deutlich unter Limit → keine Warnung."""
        plan = _make_plan_with_weekly_dienste(8.0)
        violations = WeeklyDiensteWarning().validate(plan, config)
        assert len(violations) == 0

    def test_tvk_7_dienste_warning(self, tvk_only_config):
        """TVK: 7 Dienste = max-1 → Warnung."""
        plan = _make_plan_with_weekly_dienste(7.0)
        violations = WeeklyDiensteWarning().validate(plan, tvk_only_config)
        warnings = [v for v in violations if v.severity == Severity.WARNING]
        assert len(warnings) == 1

    def test_6_dienste_no_warning(self, config):
        plan = _make_plan_with_weekly_dienste(6.0)
        violations = WeeklyDiensteWarning().validate(plan, config)
        assert len(violations) == 0


# ============================================================
# HTV-spezifische Constraint-Tests
# ============================================================

class TestHTVEscalation:
    """HTV: >10 Dienste in Woche N → Woche N+1 max 9."""

    def test_escalation_triggered(self, config):
        """11 Dienste in Woche 1, 10 in Woche 2 → Fehler."""
        plan = _make_multi_week_plan([11.0, 10.0])
        violations = HTVEscalation().validate(plan, config)
        errors = [v for v in violations if v.severity == Severity.ERROR]
        assert len(errors) == 1
        assert errors[0].limit_value == 9

    def test_escalation_compliant(self, config):
        """11 Dienste in Woche 1, 9 in Woche 2 → OK."""
        plan = _make_multi_week_plan([11.0, 9.0])
        violations = HTVEscalation().validate(plan, config)
        assert len(violations) == 0

    def test_no_escalation_when_under_threshold(self, config):
        """10 Dienste (= Trigger, nicht darüber) → keine Eskalation."""
        plan = _make_multi_week_plan([10.0, 10.0])
        violations = HTVEscalation().validate(plan, config)
        assert len(violations) == 0

    def test_disabled_in_tvk_mode(self, tvk_only_config):
        """Eskalation greift nicht im TVK-Modus."""
        plan = _make_multi_week_plan([11.0, 11.0])
        violations = HTVEscalation().validate(plan, tvk_only_config)
        assert len(violations) == 0


class TestHTVAusgleichszeitraum:
    """HTV §12,2: Max 183 Dienste pro 24-Wochen-Periode (feste Perioden)."""

    def _make_plan_in_period(self, weekly_counts):
        """Erstellt Plan innerhalb der 2. Ausgleichsperiode (ab 02.02.2026).

        Spielzeit 2025/26: P1=18.08.2025, P2=02.02.2026.
        """
        from datetime import timedelta
        all_dienste = []
        base = date(2026, 2, 2)  # Montag, Start Periode 2

        for week_idx, count in enumerate(weekly_counts):
            remaining = count
            for day in range(7):
                d = base + timedelta(days=week_idx * 7 + day)
                if remaining > 0:
                    dc = min(remaining, 2.0)
                    all_dienste.append(Dienst(
                        dienst_date=d,
                        events=[Event(event_date=d, start_time=time(10, 0),
                                      dienst_type=DienstType.KONZERT, raw_text="Test")],
                        dienst_count=dc,
                    ))
                    remaining -= dc
                else:
                    all_dienste.append(Dienst(dienst_date=d, dienst_count=0.0, is_free=True))

        total_days = len(weekly_counts) * 7
        plan_start = base
        plan_end = base + timedelta(days=total_days - 1)
        return Dienstplan.from_events([], all_dienste, plan_start, plan_end)

    def test_under_limit_info(self, config):
        """24 Wochen mit je 7 Diensten = 168 → INFO mit Puffer."""
        plan = self._make_plan_in_period([7.0] * 24)
        violations = HTVAusgleichszeitraum().validate(plan, config)
        infos = [v for v in violations if v.severity == Severity.INFO]
        assert len(infos) >= 1
        assert infos[0].current_value == 168.0
        assert infos[0].limit_value == 183

    def test_over_limit_error(self, config):
        """24 Wochen mit je 8 Diensten = 192 → ERROR."""
        plan = self._make_plan_in_period([8.0] * 24)
        violations = HTVAusgleichszeitraum().validate(plan, config)
        errors = [v for v in violations if v.severity == Severity.ERROR]
        assert len(errors) >= 1
        assert errors[0].current_value == 192.0
        assert errors[0].limit_value == 183

    def test_partial_period_shows_info(self, config):
        """10 Wochen in der Periode → zeigt anteilige Info."""
        plan = self._make_plan_in_period([7.0] * 10)
        violations = HTVAusgleichszeitraum().validate(plan, config)
        # Auch bei unvollständiger Periode wird Info ausgegeben
        assert len(violations) >= 1
        assert violations[0].current_value == 70.0

    def test_disabled_in_tvk_mode(self, tvk_only_config):
        """Ausgleichszeitraum greift nicht im TVK-Modus."""
        plan = self._make_plan_in_period([8.0] * 24)
        violations = HTVAusgleichszeitraum().validate(plan, tvk_only_config)
        assert len(violations) == 0
