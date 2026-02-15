"""
Intelligence Engine — plug-in registry for all market intelligence modules.

Usage:
    engine = IntelligenceEngine()
    engine.register(MarketRegimeModule())
    engine.register(IVRankModule())

    # On every market tick:
    engine.update({"df": df, "greeks": greeks, "nifty50_quotes": quotes})

    # Before strategy signal check:
    ctx = engine.get_context()
    result = strategy_engine.check_signal(df, pcr, greeks, intelligence_context=ctx)

Adding a new module: create a new file in this package, subclass IntelligenceModule,
and register it in main.py — zero changes required anywhere else.
"""

import logging
from typing import Dict, Any

from app.intelligence.base import IntelligenceModule

logger = logging.getLogger(__name__)


class IntelligenceEngine:
    """Orchestrates all registered intelligence modules."""

    def __init__(self):
        self._modules: Dict[str, IntelligenceModule] = {}

    # ── Registration ────────────────────────────────────────────────────────

    def register(self, module: IntelligenceModule) -> None:
        self._modules[module.name] = module
        logger.info(f"🧠 Intelligence module registered: {module.name}")

    def unregister(self, name: str) -> None:
        if name in self._modules:
            del self._modules[name]
            logger.info(f"🧠 Intelligence module unregistered: {name}")

    def enable(self, name: str) -> None:
        if name in self._modules:
            self._modules[name].enabled = True

    def disable(self, name: str) -> None:
        if name in self._modules:
            self._modules[name].enabled = False

    # ── Data Flow ───────────────────────────────────────────────────────────

    def update(self, data: Dict[str, Any]) -> None:
        """Push fresh market data to every enabled module."""
        for module in self._modules.values():
            if module.enabled:
                try:
                    module.update(data)
                except Exception as e:
                    logger.error(f"Intelligence module '{module.name}' update error: {e}")

    def get_context(self) -> Dict[str, Any]:
        """
        Collect snapshots from all enabled modules.
        Returns: { "<module_name>": { ...context... }, ... }
        """
        context: Dict[str, Any] = {}
        for name, module in self._modules.items():
            if module.enabled:
                try:
                    context[name] = module.get_context()
                except Exception as e:
                    logger.error(f"Intelligence module '{name}' get_context error: {e}")
                    context[name] = {}
        return context

    def reset_daily(self) -> None:
        """Reset all module daily state (call at start of trading day)."""
        for module in self._modules.values():
            try:
                module.reset()
            except Exception as e:
                logger.error(f"Intelligence module '{module.name}' reset error: {e}")

    @property
    def modules(self) -> Dict[str, IntelligenceModule]:
        return dict(self._modules)
