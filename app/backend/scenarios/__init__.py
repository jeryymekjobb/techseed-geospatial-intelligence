"""The demo scenarios: one module per scenario, holding everything that belongs to it.

app/backend/scenario.py loads the chosen one, so the rest of the code reads the
scenario's values from there. A scenario module holds the area, period, titles and
texts, data files, database, map tiles, camera route and the satellites and Landsat
scenes of its period.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT = "vastmanland2014"
AVAILABLE = ("vastmanland2014", "sundsvall2026", "skane2024", "ljusdal2018")
