"""The backend's passes over the incident (app/backend/passes.py) against the screens' (orbits.js)."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.backend import passes

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
# A Space-Track element set of Sentinel-2B (NORAD 42063) from August 2026.
ELEMENT = {"epoch_utc": "2026-08-16T06:39:28.272384Z",
           "line1": "1 42063U 17013A   26228.27741056 -.00000121  00000-0 -29555-4 0  9995",
           "line2": "2 42063  98.5662 302.1938 0001241  90.7915 269.3410 14.30821649493232"}
SUNDSVALL = (62.391, 17.307)
DAY = (datetime(2026, 8, 16, tzinfo=timezone.utc), datetime(2026, 8, 17, tzinfo=timezone.utc))

needs_sgp4 = pytest.mark.skipif(not passes.available(), reason="needs sgp4 (app/requirements-orbits.txt)")


@needs_sgp4
def test_the_backend_finds_the_same_passes_as_the_satellite_monitor(tmp_path: Path) -> None:
    if shutil.which("node") is None:
        pytest.skip("needs Node.js")
    backend = passes.passes_between(passes.Orbit([ELEMENT]), *DAY, *SUNDSVALL, 145.0)
    # satellite.js is an ES module in the vendored copy; give it a package.json of its own to load it in Node.
    library = tmp_path / "satjs"
    shutil.copytree(FRONTEND / "vendor" / "satellite.js-7.1.0", library)
    (library / "package.json").write_text('{"type": "module"}', encoding="utf-8")
    script = tmp_path / "passes.mjs"
    script.write_text(f"""
import * as lib from {json.dumps(str(library / 'index.js'))};
import {{ createRequire }} from "module";
const orbits = createRequire(import.meta.url)({json.dumps(str(FRONTEND / 'orbits.js'))});
const found = orbits.passesBetween(lib, [{json.dumps(ELEMENT)}], Date.parse("2026-08-16T00:00:00Z"), Date.parse("2026-08-17T00:00:00Z"),
  {SUNDSVALL[0]}, {SUNDSVALL[1]}, 145);
console.log(JSON.stringify(found));
""", encoding="utf-8")
    screens = json.loads(subprocess.run(["node", str(script)], check=True, capture_output=True, text=True).stdout)
    assert len(backend) == len(screens) >= 1
    for (start, end), screen in zip(backend, screens):
        assert abs(start.timestamp() * 1000 - screen["start"]) <= 2000 and abs(end.timestamp() * 1000 - screen["end"]) <= 2000


def test_known_acquisitions_are_passes_without_orbits() -> None:
    satellites = [{"name": "Sentinel-1C", "half_swath_km": None, "acquisitions": ["2026-08-16T05:21:32Z", "2026-08-18T16:21:13Z"]}]
    found = passes.incident_passes(satellites, *DAY, SUNDSVALL)
    assert [(start.strftime("%H:%M:%S"), end.strftime("%H:%M:%S"), name) for start, end, name in found] == [
        ("05:21:32", "05:21:57", "Sentinel-1C")]  # the one on the day, 25 seconds long
