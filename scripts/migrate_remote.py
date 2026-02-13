#!/usr/bin/env python3
"""Remote-Migration: Parsed Excel lokal, sendet Bulk-Import an Render-API.

Laeuft lokal, nutzt den Excel-Parser, und schickt alle Daten in einem
einzigen Bulk-Request an die Live-Datenbank.

Ausfuehrung:
    cd orchestra-dienstplan
    source .venv/bin/activate
    python scripts/migrate_remote.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, time
from pathlib import Path
from collections import defaultdict
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# Projekt-Root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dienstplan.config import load_config
from dienstplan.excel_parser.reader import read_jahresplan
from dienstplan.excel_parser.event_extractor import extract_events

# ──────────────── Konfiguration ────────────────

API_BASE = "https://sbp-services.onrender.com/api"
ADMIN_EMAIL = "saalfrank@sbphil.music"
ADMIN_PASSWORD = "SBP2026!"

EXCEL_BASE = (
    "/Users/christiansaalfrank/Library/CloudStorage/"
    "OneDrive-FreigegebeneBibliotheken\u2013DeutscheBl\u00e4serakademieGmbH/"
    "Business - Documents/Jahrespl\u00e4ne"
)

SEASONS = [
    {"name": "Spielzeit 2025",      "start": "2025-01-01", "end": "2025-12-31", "year": 2025, "is_active": False},
    {"name": "Spielzeit 2026",      "start": "2026-01-01", "end": "2026-07-31", "year": 2026, "is_active": False},
    {"name": "Rumpfspielzeit 2026", "start": "2026-08-01", "end": "2026-12-31", "year": 2026, "is_active": True},
    {"name": "Spielzeit 2027",      "start": "2027-01-01", "end": "2027-12-31", "year": 2027, "is_active": False},
    {"name": "Spielzeit 2028",      "start": "2028-01-01", "end": "2028-12-31", "year": 2028, "is_active": False},
    {"name": "Spielzeit 2029",      "start": "2029-01-01", "end": "2029-12-31", "year": 2029, "is_active": False},
    {"name": "Spielzeit 2030",      "start": "2030-01-01", "end": "2030-12-31", "year": 2030, "is_active": False},
]

EXCEL_FILES = {
    2025: "Jahresplan 2025.xlsx",
    2026: "Jahresplan 2026.xlsx",
    2027: "Jahresplan 2027.xlsx",
    2028: "Jahresplan 2028.xlsx",
    2029: "Jahresplan 2029.xlsx",
    2030: "Jahresplan 2030.xlsx",
}


def api_request(method: str, path: str, data: dict = None, token: str = None,
                timeout: int = 120) -> dict:
    """Sendet einen API-Request."""
    url = f"{API_BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = json.dumps(data).encode("utf-8") if data else None
    req = Request(url, data=body, headers=headers, method=method)

    try:
        resp = urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode())
    except HTTPError as e:
        error_body = e.read().decode()
        print(f"  API ERROR {e.code}: {error_body[:300]}")
        raise


def login_or_setup() -> str:
    """Loggt sich als Admin ein (oder erstellt Account)."""
    status = api_request("GET", "/auth/status")

    if not status.get("admin_exists"):
        print("  Admin existiert noch nicht — erstelle Account...")
        result = api_request("POST", "/auth/setup", {
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        })
        return result["token"]
    else:
        result = api_request("POST", "/auth/login", {
            "type": "admin",
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        })
        return result["token"]


def time_to_str(t: time | None) -> str | None:
    """time → HH:MM"""
    return t.strftime("%H:%M") if t else None


def find_season_name(event_date: date) -> str | None:
    """Findet den Season-Namen fuer ein Datum."""
    for s in SEASONS:
        if date.fromisoformat(s["start"]) <= event_date <= date.fromisoformat(s["end"]):
            return s["name"]
    return None


def event_key(event_date, start_time, end_time, raw_text):
    """Duplikat-Schluessel."""
    return (
        event_date,
        str(start_time) if start_time else "",
        str(end_time) if end_time else "",
        (raw_text or "").strip()[:80],
    )


def main():
    print("=" * 60)
    print("PLANUNG SBP — REMOTE BULK-MIGRATION")
    print(f"Ziel: {API_BASE}")
    print("=" * 60)

    # 1. Login
    print("\n[1/3] Login...")
    token = login_or_setup()
    print("  OK")

    # 2. Events parsen und nach Season sortieren
    print("\n[2/3] Excel-Dateien parsen...")
    config = load_config()
    seen_keys = set()

    # Events pro Season sammeln
    season_events = {s["name"]: [] for s in SEASONS}

    for year, filename in sorted(EXCEL_FILES.items()):
        xlsx_path = os.path.join(EXCEL_BASE, filename)
        if not os.path.exists(xlsx_path):
            print(f"  [{year}] NICHT GEFUNDEN: {xlsx_path}")
            continue

        cells = read_jahresplan(xlsx_path, year=year)
        events = extract_events(cells, config)

        imported = 0
        skipped = 0

        for event in events:
            ey = event.event_date.year

            # Nur Events des Hauptjahres (Ausnahme: 2025→2026)
            if ey != year:
                if year == 2025 and ey == 2026:
                    pass
                else:
                    skipped += 1
                    continue

            # Duplikat-Check
            key = event_key(event.event_date, event.start_time,
                            event.end_time, event.raw_text)
            if key in seen_keys:
                skipped += 1
                continue
            seen_keys.add(key)

            # Season finden
            season_name = find_season_name(event.event_date)
            if not season_name:
                skipped += 1
                continue

            season_events[season_name].append({
                "event_date": event.event_date.isoformat(),
                "start_time": time_to_str(event.start_time),
                "end_time": time_to_str(event.end_time),
                "dienst_type": event.dienst_type.value,
                "formation": event.formation.value,
                "status": "fest",
                "programm": event.programm or "",
                "ort": event.ort or "",
                "leitung": event.leitung or "",
                "kleidung": event.kleidung or "",
                "sonstiges": event.sonstiges or "",
                "raw_text": event.raw_text or "",
            })
            imported += 1

        print(f"  [{year}] {filename}: {imported} importiert, {skipped} uebersprungen")

    # Bulk-Import Payload bauen
    bulk_payload = {
        "clear_existing": True,
        "seasons": [],
    }

    total = 0
    for s_def in SEASONS:
        name = s_def["name"]
        events_list = season_events[name]
        total += len(events_list)

        bulk_payload["seasons"].append({
            "name": name,
            "start_date": s_def["start"],
            "end_date": s_def["end"],
            "is_active": s_def["is_active"],
            "events": events_list,
        })
        print(f"  -> {name}: {len(events_list)} Events")

    print(f"\n  Gesamt: {total} Events in {len(SEASONS)} Spielzeiten")

    # Payload-Groesse
    payload_json = json.dumps(bulk_payload)
    payload_size = len(payload_json)
    print(f"  Payload-Groesse: {payload_size / 1024:.0f} KB")

    # 3. Bulk-Import senden
    print(f"\n[3/3] Bulk-Import an {API_BASE}/seasons/bulk-import ...")
    try:
        result = api_request("POST", "/seasons/bulk-import", bulk_payload,
                             token=token, timeout=300)
        print(f"\n  ERFOLG: {result.get('message')}")
        print(f"\n  --- Ergebnis ---")
        for s in result.get("seasons", []):
            print(f"  {s['name']}: {s['events_imported']} Events (ID {s['season_id']})")
        print(f"\n  Total: {result.get('total_events')} Events")
    except Exception as e:
        print(f"\n  FEHLER beim Import: {e}")
        return

    print("\n" + "=" * 60)
    print("REMOTE-MIGRATION ABGESCHLOSSEN!")
    print("=" * 60)


if __name__ == "__main__":
    main()
