"""Roster-Verwaltung: Musiker, Register, Ensembles der SBP.

Liest die Personalbesetzung aus config/roster.yaml und stellt
Funktionen zur Verfügung, um zu bestimmen welcher Musiker an
welcher Formation teilnimmt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional

import yaml

from .models.events import Formation


# Default-Pfad relativ zum Projekt
_CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
ROSTER_CONFIG_PATH = _CONFIG_DIR / "roster.yaml"


@dataclass
class Musician:
    """Ein Musiker der SBP."""
    name: str
    position: str
    register: str           # z.B. "Klarinetten"
    gruppe: str             # "HOLZ" oder "BLECH"
    anteil: int = 100       # Stellenanteil in %
    zusatz: str = ""        # z.B. "Konzertmeister"
    ensembles: Set[str] = field(default_factory=set)  # z.B. {"BLQ", "KLQ"}

    @property
    def nachname(self) -> str:
        parts = self.name.split()
        return parts[-1] if parts else self.name

    @property
    def vorname(self) -> str:
        parts = self.name.split()
        return parts[0] if len(parts) > 1 else ""

    @property
    def filename(self) -> str:
        """Dateiname: 'Nachname Vorname.docx' oder 'Position.docx' bei vakanten Stellen."""
        if self.is_vakant:
            # Sonderzeichen im Positionsnamen ersetzen
            safe = re.sub(r'[/\\]', '_', self.position)
            return f"{safe}.docx"
        return f"{self.nachname} {self.vorname}.docx".strip()

    @property
    def display_name(self) -> str:
        """Anzeigename: 'Vorname Nachname' oder Position bei Vakanz."""
        if self.is_vakant:
            return f"vakant ({self.position})"
        return self.name

    @property
    def is_vakant(self) -> bool:
        return self.name.lower() == "vakant"

    def participates_in(self, formation: Formation) -> bool:
        """Prüft ob dieser Musiker an einer Formation teilnimmt."""

        # SBP = tutti → alle spielen
        if formation == Formation.SBP:
            return True

        # BRASS / BRASS_OHNE = alle Blechbläser + Schlagzeug
        if formation in (Formation.BRASS, Formation.BRASS_OHNE):
            return self.gruppe == "BLECH"

        # HOLZ = alle Holzbläser
        if formation == Formation.HOLZ:
            return self.gruppe == "HOLZ"

        # BLECH = alle Blechbläser
        if formation == Formation.BLECH:
            return self.gruppe == "BLECH"

        # SCHLAGWERK
        if formation == Formation.SCHLAGWERK:
            return self.register == "Schlagzeug"

        # KONTRABASS
        if formation == Formation.KONTRABASS:
            return self.register == "Kontrabass"

        # Kammerensembles: Mitgliedschaft prüfen
        if formation == Formation.BLQ:
            return "BLQ" in self.ensembles
        if formation == Formation.KLQ:
            return "KLQ" in self.ensembles
        if formation == Formation.SBQ:
            return "SBQ" in self.ensembles
        if formation == Formation.SERENADEN:
            return "SERENADEN" in self.ensembles

        # GREMIEN, STRATEGIERAT, GRUPPEN → kein Dienst für Einzelpläne
        if formation in (Formation.GREMIEN, Formation.STRATEGIERAT, Formation.GRUPPEN):
            return False

        # UNBEKANNT → wie SBP (sicherheitshalber alle)
        if formation == Formation.UNBEKANNT:
            return True

        return False


@dataclass
class Roster:
    """Vollständige Orchesterbesetzung."""
    musicians: List[Musician] = field(default_factory=list)

    @property
    def all_musicians(self) -> List[Musician]:
        """Alle Musiker (inkl. vakante Stellen)."""
        return self.musicians

    @property
    def active_musicians(self) -> List[Musician]:
        """Nur besetzte Stellen."""
        return [m for m in self.musicians if not m.is_vakant]

    def by_register(self) -> Dict[str, List[Musician]]:
        """Gruppiert nach Register."""
        result: Dict[str, List[Musician]] = {}
        for m in self.musicians:
            result.setdefault(m.register, []).append(m)
        return result


def load_roster(config_path: Optional[Path] = None) -> Roster:
    """Lädt die Orchesterbesetzung aus der YAML-Konfiguration."""
    path = config_path or ROSTER_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    musicians: List[Musician] = []
    register_data = data.get("register", {})
    ensemble_data = data.get("ensembles", {})

    # Schritt 1: Alle Musiker aus den Registern laden
    for register_name, register_info in register_data.items():
        gruppe = register_info.get("gruppe", "")
        for m_data in register_info.get("musiker", []):
            musician = Musician(
                name=m_data["name"],
                position=m_data["position"],
                register=register_name,
                gruppe=gruppe,
                anteil=m_data.get("anteil", 100),
                zusatz=m_data.get("zusatz", ""),
            )
            musicians.append(musician)

    # Schritt 2: Ensemble-Mitgliedschaften auflösen
    for ens_key, ens_info in ensemble_data.items():
        positionen = ens_info.get("positionen", [])
        spezifisch = ens_info.get("spezifisch", {})

        for position in positionen:
            # Alle Musiker mit dieser Position bekommen die Ensemble-Zugehörigkeit
            for m in musicians:
                if m.position == position:
                    m.ensembles.add(ens_key)

        # Spezifische Zuordnungen (wenn Position mehrfach besetzt)
        for position, target_name in spezifisch.items():
            for m in musicians:
                if m.name == target_name:
                    m.ensembles.add(ens_key)

    return Roster(musicians=musicians)
