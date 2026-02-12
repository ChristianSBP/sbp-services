"""Kern-Datenmodelle für Events und Dienste der Sächsischen Bläserphilharmonie."""

from __future__ import annotations

from datetime import date, time, datetime, timedelta
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field


class DienstType(str, Enum):
    """Klassifikation der Dienstarten."""
    PROBE = "Probe"
    GENERALPROBE = "GP"
    HAUPTPROBE = "HP"
    ANSPIELPROBE = "Anspielprobe"
    KONZERT = "Konzert"
    ABO_KONZERT = "Abo-Konzert"
    SCHUELERKONZERT = "SK"
    BABYKONZERT = "Babykonzert"
    DIRIGIERKURS = "Dirigierkurs"
    PODCAST = "Podcast"
    GASTSPIEL = "Gastspiel"
    REISE = "Reise"
    REISEZEITAUSGLEICH = "RZA"
    DIENSTBERATUNG = "Dienstberatung"
    PROBESPIEL = "Probespiel"
    TONAUFNAHME = "Tonaufnahme"
    AKADEMIEDIENST = "Akademiedienst"
    FREI = "Frei"
    URLAUB = "Urlaub"
    SONSTIGES = "Sonstiges"


class Formation(str, Enum):
    """Besetzungsgruppen der SBP."""
    SBP = "SBP"
    BRASS = "Brass inkl. Schlagz."
    BRASS_OHNE = "Brass ohne Schlagz."
    BLQ = "BLQ"
    KLQ = "KLQ"
    SBQ = "SBQ"
    SERENADEN = "Serenaden"
    HOLZ = "Holz"
    BLECH = "Blech"
    SCHLAGWERK = "Schlagwerk"
    KONTRABASS = "Kontrabass"
    GREMIEN = "Gremien"
    STRATEGIERAT = "Strategierat"
    GRUPPEN = "Gruppen"
    UNBEKANNT = "Unbekannt"


class Event(BaseModel):
    """Ein einzelnes Ereignis aus dem Jahresplan."""
    event_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    dienst_type: DienstType = DienstType.SONSTIGES
    formation: Formation = Formation.UNBEKANNT
    programm: str = ""
    ort: str = ""
    leitung: str = ""
    kleidung: str = ""
    sonstiges: str = ""
    raw_text: str = ""

    @property
    def duration_minutes(self) -> Optional[int]:
        """Dauer des Events in Minuten."""
        if self.start_time and self.end_time:
            start_dt = datetime.combine(self.event_date, self.start_time)
            end_dt = datetime.combine(self.event_date, self.end_time)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            return int((end_dt - start_dt).total_seconds() / 60)
        return None

    @property
    def is_free(self) -> bool:
        return self.dienst_type in (DienstType.FREI, DienstType.URLAUB, DienstType.REISEZEITAUSGLEICH)

    @property
    def is_travel(self) -> bool:
        return self.dienst_type in (DienstType.REISE, DienstType.REISEZEITAUSGLEICH)


class Dienst(BaseModel):
    """Ein berechneter Dienst mit Dienste-Wert."""
    dienst_date: date
    events: List[Event] = Field(default_factory=list)
    dienst_count: float = 0.0
    is_free: bool = False
    is_holiday: bool = False
    holiday_name: str = ""
    notes: str = ""

    @property
    def day_of_week(self) -> str:
        days = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        return days[self.dienst_date.weekday()]

    @property
    def primary_type(self) -> DienstType:
        """Haupttyp des Tages (basierend auf dem wichtigsten Event)."""
        if not self.events:
            return DienstType.FREI
        priority = [
            DienstType.ABO_KONZERT, DienstType.KONZERT, DienstType.GASTSPIEL,
            DienstType.GENERALPROBE, DienstType.HAUPTPROBE,
            DienstType.PROBE, DienstType.ANSPIELPROBE,
            DienstType.SCHUELERKONZERT, DienstType.BABYKONZERT,
            DienstType.DIRIGIERKURS, DienstType.AKADEMIEDIENST,
            DienstType.PODCAST, DienstType.TONAUFNAHME,
            DienstType.DIENSTBERATUNG, DienstType.PROBESPIEL,
            DienstType.REISE, DienstType.REISEZEITAUSGLEICH,
            DienstType.FREI, DienstType.URLAUB,
        ]
        for p in priority:
            if any(e.dienst_type == p for e in self.events):
                return p
        return self.events[0].dienst_type

    @property
    def summary(self) -> str:
        """Kurzbeschreibung des Tages für die Kalenderansicht."""
        if self.is_free:
            free_event = next((e for e in self.events if e.is_free), None)
            if free_event and free_event.dienst_type == DienstType.URLAUB:
                return "Urlaub"
            if free_event and free_event.dienst_type == DienstType.REISEZEITAUSGLEICH:
                return "Reisezeitausgleich"
            return "Frei"
        parts = []
        for e in self.events:
            desc = e.programm or e.raw_text or e.dienst_type.value
            if e.start_time:
                time_str = e.start_time.strftime("%H:%M")
                if e.end_time:
                    time_str += f"-{e.end_time.strftime('%H:%M')}"
                desc = f"{desc} {time_str}"
            parts.append(desc)
        return " / ".join(parts)
