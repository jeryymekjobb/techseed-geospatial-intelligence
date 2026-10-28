"""A scenario's dam as a marked "if" (tools/derive_dam_exposure.py): the buildings by the stream below it.

There is no dam-break model: /api/threats gives the dam, the number of buildings within a distance
of the stream below it and the places the scenario names, and the satellite monitor's log says
"if the dam failed" with a warning triangle at each when the scenario's trigger sensor alarms
(satlog.js), marked illustrative.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.backend import scenario


@lru_cache(maxsize=1)
def layer() -> dict[str, Any] | None:
    """The dam for the screens, without the stream's geometry, or None."""
    path = scenario.DAM_FILE
    if path is None or not path.is_file():
        return None
    found = json.loads(path.read_text(encoding="utf-8"))
    return {key: value for key, value in found.items() if key != "stream_geometry"}
