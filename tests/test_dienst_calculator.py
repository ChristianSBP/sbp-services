"""Tests für die automatische Dienste-Berechnung."""

import pytest
from datetime import date, time

from dienstplan.models.events import Event, DienstType
from dienstplan.dienst_calculator import calculate_dienste


class TestProbeBerechnung:
    """Probe-Dienste: kurz (≤3h) = 1, lang (>3h) = 2."""

    def test_probe_kurz_eine_dienst(self, config):
        events = [Event(
            event_date=date(2026, 3, 8), start_time=time(15, 0), end_time=time(18, 0),
            dienst_type=DienstType.GENERALPROBE, raw_text="GP 15:00-18:00"
        )]
        dienste = calculate_dienste(events, config, date(2026, 3, 8), date(2026, 3, 8))
        assert dienste[0].dienst_count == 1.0

    def test_probe_lang_zwei_dienste(self, config):
        events = [Event(
            event_date=date(2026, 3, 6), start_time=time(9, 30), end_time=time(14, 0),
            dienst_type=DienstType.PROBE, raw_text="Probe 09:30-14:00"
        )]
        dienste = calculate_dienste(events, config, date(2026, 3, 6), date(2026, 3, 6))
        assert dienste[0].dienst_count == 2.0


class TestKonzertBerechnung:
    """Konzert-Dienste."""

    def test_einzelkonzert_eine_dienst(self, config):
        events = [Event(
            event_date=date(2026, 3, 9), start_time=time(20, 0),
            dienst_type=DienstType.KONZERT, raw_text="Bad Lausick 20:00"
        )]
        dienste = calculate_dienste(events, config, date(2026, 3, 9), date(2026, 3, 9))
        assert dienste[0].dienst_count == 1.0

    def test_anspielprobe_plus_konzert(self, config):
        events = [
            Event(event_date=date(2026, 5, 3), start_time=time(14, 30), end_time=time(15, 15),
                  dienst_type=DienstType.ANSPIELPROBE, raw_text="Ansp. 14:30-15:15"),
            Event(event_date=date(2026, 5, 3), start_time=time(16, 0),
                  dienst_type=DienstType.KONZERT, raw_text="Trebsen 16:00"),
        ]
        dienste = calculate_dienste(events, config, date(2026, 5, 3), date(2026, 5, 3))
        assert dienste[0].dienst_count == 1.5


class TestSchuelerkonzertBerechnung:
    """Schülerkonzert-Dienste."""

    def test_sk_doppel_htv(self, config):
        """HTV: Identische Doppelvorstellung = 1 Dienst."""
        events = [Event(
            event_date=date(2026, 3, 16), start_time=time(10, 0),
            dienst_type=DienstType.SCHUELERKONZERT,
            raw_text="SK Markkleeberg 10:00 Supervulkan & 11:30 Supervulkan"
        )]
        dienste = calculate_dienste(events, config, date(2026, 3, 16), date(2026, 3, 16))
        # HTV: identische Back-to-back = 1.0 Dienst
        assert dienste[0].dienst_count == 1.0

    def test_sk_doppel_tvk(self, tvk_only_config):
        """TVK: Doppel-SK = 1.5 Dienste."""
        events = [Event(
            event_date=date(2026, 3, 16), start_time=time(10, 0),
            dienst_type=DienstType.SCHUELERKONZERT,
            raw_text="SK Markkleeberg 10:00 Supervulkan & 11:30 Supervulkan"
        )]
        dienste = calculate_dienste(events, tvk_only_config, date(2026, 3, 16), date(2026, 3, 16))
        assert dienste[0].dienst_count == 1.5

    def test_sk_einzel(self, config):
        """Einzel-SK ohne & oder 11:30 = 1 Dienst."""
        events = [Event(
            event_date=date(2026, 3, 17), start_time=time(10, 0),
            dienst_type=DienstType.SCHUELERKONZERT,
            raw_text="SK Leipzig 10:00 Supervulkan"
        )]
        dienste = calculate_dienste(events, config, date(2026, 3, 17), date(2026, 3, 17))
        assert dienste[0].dienst_count == 1.0


class TestHTVAkademiedienst:
    """HTV: Akademiedienst-Berechnung in 3 Stufen."""

    def test_akademie_kurz_1_dienst(self, config):
        """≤3h Akademie = 1 Dienst."""
        events = [Event(
            event_date=date(2026, 5, 10), start_time=time(10, 0), end_time=time(12, 30),
            dienst_type=DienstType.AKADEMIEDIENST,
            raw_text="Akademie DBA 10:00-12:30"
        )]
        dienste = calculate_dienste(events, config, date(2026, 5, 10), date(2026, 5, 10))
        assert dienste[0].dienst_count == 1.0

    def test_akademie_mittel_2_dienste(self, config):
        """3-6h Akademie = 2 Dienste."""
        events = [Event(
            event_date=date(2026, 5, 11), start_time=time(9, 0), end_time=time(14, 0),
            dienst_type=DienstType.AKADEMIEDIENST,
            raw_text="Akademie DBA 09:00-14:00"
        )]
        dienste = calculate_dienste(events, config, date(2026, 5, 11), date(2026, 5, 11))
        assert dienste[0].dienst_count == 2.0

    def test_akademie_lang_3_dienste(self, config):
        """6h+ Akademie = 3 Dienste."""
        events = [Event(
            event_date=date(2026, 5, 12), start_time=time(8, 0), end_time=time(16, 0),
            dienst_type=DienstType.AKADEMIEDIENST,
            raw_text="Akademie Ganztag 08:00-16:00"
        )]
        dienste = calculate_dienste(events, config, date(2026, 5, 12), date(2026, 5, 12))
        assert dienste[0].dienst_count == 3.0


class TestHTVDoppeldienst:
    """HTV: Doppeldienst — 2 Proben kombiniert max 4,5h."""

    def test_doppeldienst_unter_limit(self, config):
        """2 Proben, zusammen 4h = 2 Dienste (Doppeldienst)."""
        events = [
            Event(event_date=date(2026, 3, 20), start_time=time(10, 0), end_time=time(12, 0),
                  dienst_type=DienstType.PROBE, raw_text="Probe 10:00-12:00"),
            Event(event_date=date(2026, 3, 20), start_time=time(14, 0), end_time=time(16, 0),
                  dienst_type=DienstType.PROBE, raw_text="Probe 14:00-16:00"),
        ]
        dienste = calculate_dienste(events, config, date(2026, 3, 20), date(2026, 3, 20))
        assert dienste[0].dienst_count == 2.0

    def test_doppeldienst_ueber_limit(self, config):
        """2 Proben, zusammen 5,5h > 4,5h → normale Einzelberechnung."""
        events = [
            Event(event_date=date(2026, 3, 21), start_time=time(9, 0), end_time=time(12, 0),
                  dienst_type=DienstType.PROBE, raw_text="Probe 09:00-12:00"),
            Event(event_date=date(2026, 3, 21), start_time=time(14, 0), end_time=time(16, 30),
                  dienst_type=DienstType.GENERALPROBE, raw_text="GP 14:00-16:30"),
        ]
        dienste = calculate_dienste(events, config, date(2026, 3, 21), date(2026, 3, 21))
        # Beide Proben jeweils ≤3h → je 1 Dienst = 2 Dienste
        # (Gleich wie Doppeldienst, aber korrekt über Einzelberechnung)
        assert dienste[0].dienst_count == 2.0


class TestFreieTage:
    """Freie Tage, Urlaub, Reise, Reisezeitausgleich = 0 Dienste."""

    def test_frei(self, config):
        events = [Event(
            event_date=date(2026, 4, 2), dienst_type=DienstType.FREI,
            raw_text="Karfreitag - freier Tag"
        )]
        dienste = calculate_dienste(events, config, date(2026, 4, 2), date(2026, 4, 2))
        assert dienste[0].dienst_count == 0.0
        assert dienste[0].is_free is True

    def test_urlaub(self, config):
        events = [Event(
            event_date=date(2026, 4, 15), dienst_type=DienstType.URLAUB,
            raw_text="Urlaub 31"
        )]
        dienste = calculate_dienste(events, config, date(2026, 4, 15), date(2026, 4, 15))
        assert dienste[0].dienst_count == 0.0

    def test_reise_htv(self, config):
        """HTV Protokollnotiz 3: Reisezeit = 1 Dienst."""
        events = [Event(
            event_date=date(2026, 4, 3), dienst_type=DienstType.REISE,
            raw_text="Abflug nach NYC"
        )]
        dienste = calculate_dienste(events, config, date(2026, 4, 3), date(2026, 4, 3))
        assert dienste[0].dienst_count == 1.0

    def test_reise_tvk(self, tvk_only_config):
        """TVK: Reisetag = 0 Dienste."""
        events = [Event(
            event_date=date(2026, 4, 3), dienst_type=DienstType.REISE,
            raw_text="Abflug nach NYC"
        )]
        dienste = calculate_dienste(events, tvk_only_config, date(2026, 4, 3), date(2026, 4, 3))
        assert dienste[0].dienst_count == 0.0

    def test_reisezeitausgleich(self, config):
        events = [Event(
            event_date=date(2026, 4, 7), dienst_type=DienstType.REISEZEITAUSGLEICH,
            raw_text="Reisezeitausgleichraum"
        )]
        dienste = calculate_dienste(events, config, date(2026, 4, 7), date(2026, 4, 7))
        assert dienste[0].dienst_count == 0.0

    def test_kein_event_ist_frei(self, config):
        """Tag ohne Events = freier Tag."""
        dienste = calculate_dienste([], config, date(2026, 3, 1), date(2026, 3, 1))
        assert dienste[0].dienst_count == 0.0
        assert dienste[0].is_free is True


class TestSonderfaelle:
    """Dirigierkurs, Podcast, Stadtmusik."""

    def test_dirigierkurs_ganztags(self, config):
        events = [Event(
            event_date=date(2026, 4, 14), start_time=time(9, 30), end_time=time(14, 0),
            dienst_type=DienstType.DIRIGIERKURS,
            raw_text="HfMT Leipzig - Foremny 09:30-14:00"
        )]
        dienste = calculate_dienste(events, config, date(2026, 4, 14), date(2026, 4, 14))
        assert dienste[0].dienst_count == 2.0

    def test_podcast(self, config):
        events = [Event(
            event_date=date(2026, 5, 19), start_time=time(9, 30), end_time=time(14, 0),
            dienst_type=DienstType.PODCAST,
            raw_text="Probe Podcast 4 9:30 - 14:00"
        )]
        dienste = calculate_dienste(events, config, date(2026, 5, 19), date(2026, 5, 19))
        assert dienste[0].dienst_count == 2.0

    def test_sonstiges_stadtmusik_kein_dienst(self, config):
        """Sonstiges mit 'stadtmusik' = 0 Dienste."""
        events = [Event(
            event_date=date(2026, 5, 20), dienst_type=DienstType.SONSTIGES,
            raw_text="Stadtmusik auf dem Marktplatz"
        )]
        dienste = calculate_dienste(events, config, date(2026, 5, 20), date(2026, 5, 20))
        assert dienste[0].dienst_count == 0.0
