"""Basis-Klassen für TVK-Constraints."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ..models.plan import Dienstplan


class Severity(str, Enum):
    ERROR = "error"      # Harte Verletzung
    WARNING = "warning"  # Annäherung an Grenzwert
    INFO = "info"        # Informativ


class Violation(BaseModel):
    """Ein TVK-Verstoß oder eine Warnung."""
    rule_id: str
    rule_name: str
    severity: Severity
    message: str
    tvk_paragraph: str = ""
    affected_dates: List[date] = Field(default_factory=list)
    affected_week: Optional[int] = None
    current_value: Optional[float] = None
    limit_value: Optional[float] = None
    suggestion: str = ""

    @property
    def severity_icon(self) -> str:
        if self.severity == Severity.ERROR:
            return "FEHLER"
        elif self.severity == Severity.WARNING:
            return "WARNUNG"
        return "INFO"


class Constraint(ABC):
    """Abstrakte Basis-Klasse für alle TVK-Constraints."""

    rule_id: str = ""
    rule_name: str = ""
    tvk_paragraph: str = ""

    @abstractmethod
    def validate(self, plan: Dienstplan, config: dict) -> List[Violation]:
        """Prüft den Plan gegen diese Regel.

        Returns:
            Liste von Violations (leer wenn keine Verstöße).
        """
        ...
