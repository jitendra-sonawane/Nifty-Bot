"""
Base classes for pluggable intelligence modules.

Every intelligence module:
 - receives market data via update()
 - exposes a snapshot via get_context()
 - can be enabled/disabled at runtime
 - can be registered / unregistered from IntelligenceEngine without touching other code
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class IntelligenceModule(ABC):
    """Abstract base for all intelligence modules."""

    # Subclasses MUST set a unique name
    name: str = "base"
    enabled: bool = True

    @abstractmethod
    def update(self, data: Dict[str, Any]) -> None:
        """
        Receive a snapshot of the latest market data and update internal state.

        `data` keys vary by module; each module documents what it consumes.
        Unknown keys are silently ignored.
        """

    @abstractmethod
    def get_context(self) -> Dict[str, Any]:
        """
        Return the current intelligence snapshot as a plain dict.
        Must never raise — return safe defaults on missing data.
        """

    def reset(self) -> None:
        """
        Optional: reset daily/session state.
        Called at start of each trading day.
        """
