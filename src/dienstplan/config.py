"""TVK-Konfiguration laden und mergen."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "tvk_defaults.yaml"


def load_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Lade TVK-Konfiguration aus YAML-Datei.

    Falls ein custom config_path angegeben wird, wird dieser mit den
    Default-Werten gemergt (custom überschreibt defaults).
    """
    defaults = _load_yaml(DEFAULT_CONFIG_PATH)

    if config_path:
        custom = _load_yaml(Path(config_path))
        return _deep_merge(defaults, custom)

    return defaults


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def is_htv_active(config: dict) -> bool:
    """Prüft ob der HTV-Modus aktiviert ist."""
    return config.get("htv", {}).get("active", False)


def get_max_weekly_dienste(config: dict) -> int:
    """Gibt das effektive Max-Dienste-pro-Woche-Limit zurück (HTV oder TVK)."""
    if is_htv_active(config):
        return config.get("htv", {}).get("dienste", {}).get("max_per_week", 10)
    return config.get("tvk", {}).get("dienste", {}).get("max_per_week", 8)


def _deep_merge(base: dict, override: dict) -> dict:
    """Rekursives Mergen: override-Werte überschreiben base-Werte."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
