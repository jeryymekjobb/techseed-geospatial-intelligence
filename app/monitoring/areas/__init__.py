"""The areas the monitoring can watch, one module each, chosen with --area."""

from __future__ import annotations

import importlib
from types import ModuleType

AVAILABLE = ("flenkommun", "sundsvallkommun", "kramforskommun", "ljusdalkommun", "salakommun", "vasterasstad",
             "hoorkommun", "vellingekommun")


def load(name: str) -> ModuleType:
    if name not in AVAILABLE:
        raise ValueError(f"unknown area: {name} (available: {', '.join(AVAILABLE)})")
    return importlib.import_module(f"app.monitoring.areas.{name}")
