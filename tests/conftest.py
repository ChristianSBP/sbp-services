"""Test-Fixtures mit echten SBP-Daten."""

import pytest
from datetime import date, time

from dienstplan.models.events import Event, Dienst, DienstType, Formation
from dienstplan.models.calendar import PlanWeek, build_weeks
from dienstplan.models.plan import Dienstplan
from dienstplan.config import load_config


@pytest.fixture
def config():
    """Standard-Config mit HTV aktiv (SBP Default)."""
    return load_config()


@pytest.fixture
def tvk_only_config():
    """Config mit deaktiviertem HTV (reiner TVK-Modus, max 8/Woche)."""
    cfg = load_config()
    cfg["htv"]["active"] = False
    return cfg


@pytest.fixture
def sample_march_events():
    """Realistische Events für März 2026 (eine Woche)."""
    return [
        Event(event_date=date(2026, 3, 6), start_time=time(9, 30), end_time=time(14, 0),
              dienst_type=DienstType.PROBE, raw_text="Probe 09:30-14:00"),
        Event(event_date=date(2026, 3, 7), start_time=time(13, 0), end_time=time(17, 30),
              dienst_type=DienstType.PROBE, raw_text="Probe 13:00-17:30"),
        Event(event_date=date(2026, 3, 8), start_time=time(15, 0), end_time=time(18, 0),
              dienst_type=DienstType.GENERALPROBE, raw_text="GP 15:00-18:00"),
        Event(event_date=date(2026, 3, 9), start_time=time(20, 0),
              dienst_type=DienstType.KONZERT, ort="Bad Lausick",
              raw_text="Bad Lausick 20:00 - Sommerer"),
        Event(event_date=date(2026, 3, 10), start_time=time(17, 0),
              dienst_type=DienstType.KONZERT, ort="Bad Lausick",
              raw_text="Bad Lausick 17:00 - Sommerer"),
        Event(event_date=date(2026, 3, 11), start_time=time(15, 0),
              dienst_type=DienstType.KONZERT, ort="Bad Lausick",
              raw_text="Bad Lausick 15:00 - Sommerer"),
    ]


@pytest.fixture
def free_day_event():
    return Event(event_date=date(2026, 4, 2), dienst_type=DienstType.FREI,
                 raw_text="Karfreitag - freier Tag")


@pytest.fixture
def urlaub_event():
    return Event(event_date=date(2026, 4, 15), dienst_type=DienstType.URLAUB,
                 raw_text="Urlaub 31")


@pytest.fixture
def reise_event():
    return Event(event_date=date(2026, 4, 3), dienst_type=DienstType.REISE,
                 raw_text="Abflug nach NYC")


@pytest.fixture
def rza_event():
    return Event(event_date=date(2026, 4, 7), dienst_type=DienstType.REISEZEITAUSGLEICH,
                 raw_text="Reisezeitausgleichraum")


@pytest.fixture
def sk_doppel_event():
    return Event(event_date=date(2026, 3, 16), start_time=time(10, 0),
                 dienst_type=DienstType.SCHUELERKONZERT,
                 raw_text="SK Markkleeberg 10:00 Supervulkan & 11:30 Supervulkan - Eichhorn")


@pytest.fixture
def anspielprobe_konzert_events():
    return [
        Event(event_date=date(2026, 5, 3), start_time=time(14, 30), end_time=time(15, 15),
              dienst_type=DienstType.ANSPIELPROBE,
              raw_text="Ansp. 14:30-15:15"),
        Event(event_date=date(2026, 5, 3), start_time=time(16, 0),
              dienst_type=DienstType.KONZERT, ort="Trebsen",
              raw_text="Trebsen 16:00"),
    ]
