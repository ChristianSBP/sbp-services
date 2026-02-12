"""Tests für den Excel-Parser (gegen echten Jahresplan)."""

import pytest
from datetime import date
from pathlib import Path

from dienstplan.excel_parser.reader import read_jahresplan
from dienstplan.excel_parser.event_extractor import extract_events
from dienstplan.models.events import DienstType


JAHRESPLAN_PATH = (
    "/Users/christiansaalfrank/Library/CloudStorage/"
    "OneDrive-FreigegebeneBibliotheken–DeutscheBläserakademieGmbH/"
    "Business - Documents/Jahrespläne/Jahresplan 2026.xlsx"
)


@pytest.fixture
def jahresplan_cells():
    if not Path(JAHRESPLAN_PATH).exists():
        pytest.skip("Jahresplan-Datei nicht verfügbar")
    return read_jahresplan(JAHRESPLAN_PATH, year=2026)


@pytest.fixture
def all_events(jahresplan_cells, config):
    return extract_events(jahresplan_cells, config)


@pytest.fixture
def march_may_events(all_events):
    return [e for e in all_events if date(2026, 3, 1) <= e.event_date <= date(2026, 5, 31)]


class TestJahresplanParser:
    """Tests gegen den echten Jahresplan."""

    def test_reads_cells(self, jahresplan_cells):
        assert len(jahresplan_cells) > 200  # 295 erwartet

    def test_all_12_months_present(self, jahresplan_cells):
        """Alle 12 Monate müssen Daten haben."""
        months = {c.month for c in jahresplan_cells}
        for m in range(1, 13):
            assert m in months, f"Monat {m} fehlt!"

    def test_march_may_events_count(self, march_may_events):
        assert len(march_may_events) >= 50  # Mindestens 50 Events in 3 Monaten


class TestParserDateAlignment:
    """Prüft, dass Daten korrekt den richtigen Monaten zugeordnet werden.

    Jeder Monat hat seine eigene Tagesnummern-Spalte.
    Die Zeilen variieren pro Monat (z.B. Tag 28 in Jan=Zeile 30, Feb=Zeile 33).
    """

    def test_jan_28_content(self, jahresplan_cells):
        """Jan 28 (C30) = SK Markranstädt Gymnasium."""
        jan28 = [c for c in jahresplan_cells if c.month == 1 and c.day == 28]
        assert len(jan28) >= 1, "Jan 28 fehlt!"
        assert "Markranstädt" in jan28[0].text or "SK" in jan28[0].text

    def test_feb_28_content(self, jahresplan_cells):
        """Feb 28 (E33) = Podcast 1."""
        feb28 = [c for c in jahresplan_cells if c.month == 2 and c.day == 28]
        assert len(feb28) >= 1, "Feb 28 fehlt!"
        assert "Podcast" in feb28[0].text

    def test_apr_28_content(self, jahresplan_cells):
        """Apr 28 (I29) = GP Sparkasse Muldental."""
        apr28 = [c for c in jahresplan_cells if c.month == 4 and c.day == 28]
        assert len(apr28) >= 1, "Apr 28 fehlt!"
        assert "Sparkasse" in apr28[0].text or "GP" in apr28[0].text

    def test_apr_6_nyc(self, jahresplan_cells):
        """Apr 6 = NYC / Carnegie Hall / Ostermontag."""
        apr6 = [c for c in jahresplan_cells if c.month == 4 and c.day == 6]
        assert len(apr6) >= 1, "Apr 6 fehlt!"
        assert "NYC" in apr6[0].text or "Ostermontag" in apr6[0].text

    def test_no_month_has_zero_entries(self, jahresplan_cells):
        """Jeder Monat muss mindestens einige Einträge haben."""
        for m in range(1, 13):
            count = sum(1 for c in jahresplan_cells if c.month == m)
            assert count >= 10, f"Monat {m} hat nur {count} Einträge (min. 10 erwartet)"


class TestEventExtraction:
    """Tests für die Event-Extraktion."""

    def test_karfreitag_is_frei(self, march_may_events):
        """Karfreitag 2026 = 3. April."""
        karfreitag = [e for e in march_may_events if e.event_date == date(2026, 4, 3)]
        assert len(karfreitag) >= 1
        assert karfreitag[0].dienst_type == DienstType.FREI

    def test_probe_detected(self, march_may_events):
        proben = [e for e in march_may_events if e.dienst_type == DienstType.PROBE]
        assert len(proben) >= 5

    def test_nyc_abflug_is_reise(self, march_may_events):
        """NYC-Abflug = 4. April."""
        abflug = [e for e in march_may_events if e.event_date == date(2026, 4, 4)]
        assert len(abflug) >= 1
        assert abflug[0].dienst_type == DienstType.REISE

    def test_sk_detected(self, march_may_events):
        sk = [e for e in march_may_events if e.dienst_type == DienstType.SCHUELERKONZERT]
        assert len(sk) >= 5  # Viele Schulkonzerte in diesem Zeitraum

    def test_times_extracted(self, march_may_events):
        with_times = [e for e in march_may_events if e.start_time is not None]
        assert len(with_times) >= 30  # Die meisten Events haben Zeitangaben
