"""TVK/HTV-Constraint-Implementierungen für die Sächsische Bläserphilharmonie.

Enthält sowohl Standard-TVK-Regeln als auch HTV-spezifische Constraints
(5. HTV vom 04.12.2025).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import List, TYPE_CHECKING

from .base import Constraint, Violation, Severity

if TYPE_CHECKING:
    from ..models.plan import Dienstplan


def _get_max_weekly(config: dict) -> int:
    """Gibt das effektive Wochen-Limit zurück (HTV oder TVK)."""
    if config.get("htv", {}).get("active", False):
        return config.get("htv", {}).get("dienste", {}).get("max_per_week", 10)
    return config.get("tvk", {}).get("dienste", {}).get("max_per_week", 8)


class MaxDienstePerWeek(Constraint):
    """Max Dienste pro Kalenderwoche (HTV: 10, TVK: 8)."""

    rule_id = "TVK_15_2"
    rule_name = "Max. Dienste pro Woche"
    tvk_paragraph = "§15 Abs. 2 / HTV"

    def validate(self, plan, config) -> List[Violation]:
        max_weekly = _get_max_weekly(config)
        violations = []
        for week in plan.weeks:
            total = week.total_dienste
            if total > max_weekly:
                violations.append(Violation(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=Severity.ERROR,
                    message=f"KW {week.week_number}: {total} Dienste (max. {max_weekly})",
                    tvk_paragraph=self.tvk_paragraph,
                    affected_week=week.week_number,
                    affected_dates=[d.dienst_date for d in week.dienste if d.dienst_count > 0],
                    current_value=total,
                    limit_value=max_weekly,
                    suggestion=f"{total - max_weekly} Dienste in KW {week.week_number} reduzieren",
                ))
        return violations


class WeeklyDiensteWarning(Constraint):
    """Warnung bei Annäherung an Wochen-Limit."""

    rule_id = "TVK_15_2_WARN"
    rule_name = "Dienste-Auslastung pro Woche"
    tvk_paragraph = "§15 Abs. 2 / HTV"

    def validate(self, plan, config) -> List[Violation]:
        max_weekly = _get_max_weekly(config)
        violations = []
        for week in plan.weeks:
            total = week.total_dienste
            if max_weekly - 1 <= total <= max_weekly:
                violations.append(Violation(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=Severity.WARNING,
                    message=f"KW {week.week_number}: {total} von {max_weekly} Diensten (am Limit)",
                    tvk_paragraph=self.tvk_paragraph,
                    affected_week=week.week_number,
                    current_value=total,
                    limit_value=max_weekly,
                    suggestion="Puffer einplanen – keine weiteren Dienste möglich",
                ))
        return violations


class MinFreeDayPerWeek(Constraint):
    """§16 Abs. 1: Mindestens ein dienstfreier Tag pro Woche."""

    rule_id = "TVK_16_1"
    rule_name = "Min. 1 freier Tag/Woche"
    tvk_paragraph = "§16 Abs. 1"

    def validate(self, plan, config) -> List[Violation]:
        violations = []
        for week in plan.weeks:
            if not week.has_free_day:
                violations.append(Violation(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=Severity.ERROR,
                    message=f"KW {week.week_number}: Kein dienstfreier Tag",
                    tvk_paragraph=self.tvk_paragraph,
                    affected_week=week.week_number,
                    affected_dates=[d.dienst_date for d in week.dienste],
                    current_value=0,
                    limit_value=1,
                    suggestion="Mindestens einen Dienst aus dieser Woche entfernen",
                ))
        return violations


class FreeSundaysCount(Constraint):
    """§16 Abs. 5: 8 freie Sonntage pro Spielzeit-Halbjahr."""

    rule_id = "TVK_16_5"
    rule_name = "Freie Sonntage pro Spielzeit"
    tvk_paragraph = "§16 Abs. 5"

    def validate(self, plan, config) -> List[Violation]:
        required = config.get("tvk", {}).get("freie_tage", {}).get("free_sundays_per_spielzeit_half", 8)
        free_sundays = plan.free_sundays
        violations = []
        total_weeks = len(plan.weeks)
        if total_weeks > 0:
            expected_proportional = (required / 26.0) * total_weeks
            if free_sundays < expected_proportional * 0.7:
                violations.append(Violation(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=Severity.WARNING,
                    message=f"{free_sundays} freie Sonntage in {total_weeks} Wochen "
                            f"(Soll anteilig: ~{expected_proportional:.0f})",
                    tvk_paragraph=self.tvk_paragraph,
                    current_value=free_sundays,
                    limit_value=expected_proportional,
                    suggestion="Mehr dienstfreie Sonntage einplanen",
                ))
        return violations


class MaxDienstePerDay(Constraint):
    """Max. 2 Dienste pro Tag."""

    rule_id = "TVK_MAX_DAILY"
    rule_name = "Max. Dienste pro Tag"
    tvk_paragraph = "§15"

    def validate(self, plan, config) -> List[Violation]:
        max_daily = config.get("tvk", {}).get("dienste", {}).get("max_per_day", 2)
        violations = []
        for dienst in plan.all_dienste():
            if dienst.dienst_count > max_daily:
                violations.append(Violation(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=Severity.ERROR,
                    message=f"{dienst.dienst_date.strftime('%d.%m.')}: "
                            f"{dienst.dienst_count} Dienste (max. {max_daily})",
                    tvk_paragraph=self.tvk_paragraph,
                    affected_dates=[dienst.dienst_date],
                    current_value=dienst.dienst_count,
                    limit_value=max_daily,
                    suggestion="Events auf verschiedene Tage verteilen",
                ))
        return violations


class DailyRestPeriod(Constraint):
    """§5 ArbZG: Mindestens 11h Ruhezeit zwischen Diensten."""

    rule_id = "TVK_ARBZG_5"
    rule_name = "Tägliche Ruhezeit (11h)"
    tvk_paragraph = "§5 ArbZG"

    def validate(self, plan, config) -> List[Violation]:
        min_rest = config.get("tvk", {}).get("ruhezeiten", {}).get("taegliche_ruhezeit_hours", 11)
        violations = []
        all_dienste = plan.all_dienste()

        for i in range(len(all_dienste) - 1):
            current = all_dienste[i]
            next_d = all_dienste[i + 1]

            if current.dienst_count == 0 or next_d.dienst_count == 0:
                continue

            last_end = _latest_end_time(current)
            first_start = _earliest_start_time(next_d)

            if last_end and first_start:
                end_dt = datetime.combine(current.dienst_date, last_end)
                start_dt = datetime.combine(next_d.dienst_date, first_start)
                rest_hours = (start_dt - end_dt).total_seconds() / 3600

                if 0 < rest_hours < min_rest:
                    violations.append(Violation(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        severity=Severity.ERROR,
                        message=f"{current.dienst_date.strftime('%d.%m.')} → "
                                f"{next_d.dienst_date.strftime('%d.%m.')}: "
                                f"Nur {rest_hours:.1f}h Ruhezeit (min. {min_rest}h)",
                        tvk_paragraph=self.tvk_paragraph,
                        affected_dates=[current.dienst_date, next_d.dienst_date],
                        current_value=round(rest_hours, 1),
                        limit_value=min_rest,
                        suggestion="Abendveranstaltung früher beenden oder Morgendienst später beginnen",
                    ))
        return violations


class RehearsalTimeWindow(Constraint):
    """Proben frühestens 09:30, spätestens 22:00 Uhr Ende."""

    rule_id = "TVK_TIMING"
    rule_name = "Proben-Zeitfenster"
    tvk_paragraph = "§12"

    def validate(self, plan, config) -> List[Violation]:
        timing = config.get("tvk", {}).get("timing", {})
        earliest_str = timing.get("fruehester_probenbeginn", "09:30")
        latest_str = timing.get("spaetestes_probenende", "22:00")
        earliest = time(*[int(x) for x in earliest_str.split(":")])
        latest = time(*[int(x) for x in latest_str.split(":")])

        violations = []
        from ..models.events import DienstType
        probe_types = {
            DienstType.PROBE, DienstType.GENERALPROBE,
            DienstType.HAUPTPROBE, DienstType.ANSPIELPROBE,
        }

        for dienst in plan.all_dienste():
            for event in dienst.events:
                if event.dienst_type not in probe_types:
                    continue
                if event.start_time and event.start_time < earliest:
                    violations.append(Violation(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        severity=Severity.WARNING,
                        message=f"{event.event_date.strftime('%d.%m.')}: "
                                f"Probe beginnt {event.start_time.strftime('%H:%M')} "
                                f"(frühestens {earliest_str})",
                        tvk_paragraph=self.tvk_paragraph,
                        affected_dates=[event.event_date],
                        suggestion="Probenbeginn auf frühestens 09:30 Uhr legen",
                    ))
                if event.end_time and event.end_time > latest:
                    violations.append(Violation(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        severity=Severity.WARNING,
                        message=f"{event.event_date.strftime('%d.%m.')}: "
                                f"Probe endet {event.end_time.strftime('%H:%M')} "
                                f"(spätestens {latest_str})",
                        tvk_paragraph=self.tvk_paragraph,
                        affected_dates=[event.event_date],
                        suggestion="Probenende auf spätestens 22:00 Uhr legen",
                    ))
        return violations


class HolidayCompensation(Constraint):
    """Sonntags-/Feiertags-Dienste markieren (Info).

    SBP: Keine Zuschläge für Sonn-/Feiertagsarbeit.
    Stattdessen 45 Tage Urlaub als Ausgleich (generelle TVK-Regelung).
    Jeder Wochentag wird identisch gehandhabt.
    """

    rule_id = "TVK_FEIERTAG"
    rule_name = "Feiertags-/Sonntagsdienst"
    tvk_paragraph = "§7"

    def validate(self, plan, config) -> List[Violation]:
        violations = []
        for dienst in plan.all_dienste():
            if dienst.dienst_count == 0:
                continue
            is_sunday = dienst.dienst_date.weekday() == 6
            if dienst.is_holiday or is_sunday:
                label = dienst.holiday_name if dienst.is_holiday else "Sonntag"
                violations.append(Violation(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=Severity.INFO,
                    message=f"{dienst.dienst_date.strftime('%d.%m.')} ({label}): "
                            f"{dienst.dienst_count} Dienste",
                    tvk_paragraph=self.tvk_paragraph,
                    affected_dates=[dienst.dienst_date],
                    current_value=dienst.dienst_count,
                    suggestion="",
                ))
        return violations


class SameDayBreak(Constraint):
    """Min. 1,5h Pause zwischen zwei Diensten am gleichen Tag."""

    rule_id = "TVK_PAUSE"
    rule_name = "Pause zwischen Diensten"
    tvk_paragraph = "§13"

    def validate(self, plan, config) -> List[Violation]:
        min_break = config.get("tvk", {}).get("ruhezeiten", {}).get(
            "zwischen_diensten_gleicher_tag_minutes", 90
        )
        violations = []

        for dienst in plan.all_dienste():
            if len(dienst.events) < 2:
                continue
            timed_events = [e for e in dienst.events if e.start_time and e.end_time]
            timed_events.sort(key=lambda e: e.start_time)

            for i in range(len(timed_events) - 1):
                curr_end = timed_events[i].end_time
                next_start = timed_events[i + 1].start_time
                if curr_end and next_start:
                    end_dt = datetime.combine(dienst.dienst_date, curr_end)
                    start_dt = datetime.combine(dienst.dienst_date, next_start)
                    break_min = (start_dt - end_dt).total_seconds() / 60

                    if 0 < break_min < min_break:
                        violations.append(Violation(
                            rule_id=self.rule_id,
                            rule_name=self.rule_name,
                            severity=Severity.WARNING,
                            message=f"{dienst.dienst_date.strftime('%d.%m.')}: "
                                    f"Nur {break_min:.0f} Min. Pause "
                                    f"(min. {min_break} Min.)",
                            tvk_paragraph=self.tvk_paragraph,
                            affected_dates=[dienst.dienst_date],
                            current_value=break_min,
                            limit_value=min_break,
                            suggestion="Mindestens 1,5h Pause zwischen Diensten einplanen",
                        ))
        return violations


# === HTV-spezifische Constraints ===

class HTVEscalation(Constraint):
    """HTV: >10 Dienste in einer Woche → nächste Woche max 9."""

    rule_id = "HTV_ESKALATION"
    rule_name = "HTV-Eskalation"
    tvk_paragraph = "5. HTV"

    def validate(self, plan, config) -> List[Violation]:
        if not config.get("htv", {}).get("active", False):
            return []

        eskalation = config.get("htv", {}).get("eskalation", {})
        trigger = eskalation.get("trigger_threshold", 10)
        reduced_max = eskalation.get("reduced_max_next_week", 9)

        violations = []
        for i, week in enumerate(plan.weeks[:-1]):
            if week.total_dienste > trigger:
                next_week = plan.weeks[i + 1]
                if next_week.total_dienste > reduced_max:
                    violations.append(Violation(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        severity=Severity.ERROR,
                        message=f"KW {week.week_number}: {week.total_dienste} Dienste "
                                f"→ KW {next_week.week_number} muss max {reduced_max} haben, "
                                f"hat aber {next_week.total_dienste}",
                        tvk_paragraph=self.tvk_paragraph,
                        affected_week=next_week.week_number,
                        current_value=next_week.total_dienste,
                        limit_value=reduced_max,
                        suggestion=f"Dienste in KW {next_week.week_number} auf max {reduced_max} reduzieren",
                    ))
        return violations


class HTVAusgleichszeitraum(Constraint):
    """HTV §12,2: Max 183 Dienste pro 24-Wochen-Ausgleichszeitraum.

    Zwei feste 24-Wochen-Perioden pro Spielzeit:
    - Periode 1: Erster Montag nach Konzertferien (z.B. 17.08.2026)
    - Periode 2: Direkt danach (24 Wochen)
    - Bis zu 9 Dienste können zwischen Perioden übertragen werden.

    Wird IMMER als Auswertung ausgegeben (auch wenn kein Verstoß).
    """

    rule_id = "HTV_AUSGLEICH"
    rule_name = "Ausgleichszeitraum (§12,2)"
    tvk_paragraph = "HTV §12,2"

    def validate(self, plan, config) -> List[Violation]:
        if not config.get("htv", {}).get("active", False):
            return []

        azr = config.get("htv", {}).get("ausgleichszeitraum", {})
        window_size = azr.get("weeks", 24)
        max_dienste = azr.get("max_dienste", 183)
        transfer = azr.get("transfer_dienste", 9)
        period_1_start_str = azr.get("period_1_start", "2026-08-17")

        # Feste Perioden-Startdaten berechnen
        period_1_start = date.fromisoformat(period_1_start_str)
        period_1_end = period_1_start + timedelta(weeks=window_size) - timedelta(days=1)
        period_2_start = period_1_end + timedelta(days=1)
        period_2_end = period_2_start + timedelta(weeks=window_size) - timedelta(days=1)

        periods = [
            ("Periode 1", period_1_start, period_1_end),
            ("Periode 2", period_2_start, period_2_end),
        ]

        violations = []

        for label, p_start, p_end in periods:
            # Summiere Dienste der Plan-Wochen, die in diese Periode fallen
            total = 0.0
            matching_weeks = []
            for week in plan.weeks:
                # Woche zählt, wenn sie sich mit der Periode überschneidet
                if week.end_date >= p_start and week.start_date <= p_end:
                    total += week.total_dienste
                    matching_weeks.append(week)

            if not matching_weeks:
                continue  # Keine Daten für diese Periode

            first_kw = matching_weeks[0].week_number
            last_kw = matching_weeks[-1].week_number
            weeks_count = len(matching_weeks)

            # Immer als INFO ausgeben (Audit-Auswertung)
            if total > max_dienste:
                violations.append(Violation(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=Severity.ERROR,
                    message=f"{label} (KW {first_kw}–{last_kw}, {weeks_count} Wo.): "
                            f"{total:g} Dienste (max {max_dienste}). "
                            f"Übertrag bis {transfer} Dienste möglich.",
                    tvk_paragraph=self.tvk_paragraph,
                    affected_week=first_kw,
                    current_value=total,
                    limit_value=max_dienste,
                    suggestion=f"{total - max_dienste:g} Dienste zu viel im Zeitraum",
                ))
            else:
                violations.append(Violation(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=Severity.INFO,
                    message=f"{label} (KW {first_kw}–{last_kw}, {weeks_count} Wo.): "
                            f"{total:g} von {max_dienste} Diensten "
                            f"({max_dienste - total:g} Puffer)",
                    tvk_paragraph=self.tvk_paragraph,
                    affected_week=first_kw,
                    current_value=total,
                    limit_value=max_dienste,
                    suggestion="",
                ))

        return violations


# Hilfsfunktionen

def _latest_end_time(dienst) -> time | None:
    """Findet die späteste Endzeit eines Tages."""
    times = []
    for e in dienst.events:
        if e.end_time:
            times.append(e.end_time)
        elif e.start_time:
            h = e.start_time.hour + 2
            m = e.start_time.minute
            if h >= 24:
                h = 23
                m = 59
            times.append(time(h, m))
    return max(times) if times else None


def _earliest_start_time(dienst) -> time | None:
    """Findet die früheste Startzeit eines Tages."""
    times = [e.start_time for e in dienst.events if e.start_time]
    return min(times) if times else None
