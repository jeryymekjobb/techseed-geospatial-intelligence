"""Read-only installation checks; no services, downloads or browser windows are started.

Run with ``python -m tools.startup_check [scenario]`` after cloning the repository.
These presence checks do not validate data contents, coverage or graphics performance.
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from app.backend.scenarios import AVAILABLE, DEFAULT, REPO_ROOT
from tools.fetch_web_vendor import PACKAGES


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


def find_chrome() -> str | None:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chrome", "chrome.exe"):
        executable = shutil.which(name)
        if executable:
            return executable
    candidates = [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                  Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        if os.environ.get(variable):
            candidates.append(Path(os.environ[variable]) / "Google/Chrome/Application/chrome.exe")
    return next((str(path) for path in candidates if path.is_file()), None)


def probe(name: str, command: list[str]) -> Check:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return Check(name, False, "not available or did not answer within 15 s")
    # Do not echo command output: Docker diagnostics can contain local configuration.
    return Check(name, result.returncode == 0, "available" if result.returncode == 0 else "check failed")


def data_checks(settings, root: Path = REPO_ROOT) -> list[Check]:
    """Check configured inputs, not raw build inputs or a database's contents."""
    files = [Path(settings.TERRAIN_FILE), Path(settings.TARGETS_FILE), Path(settings.WIND_FILE),
              Path(settings.TLE_DIR) / settings.TLE_FILE_NAME,
              root / "data/tiles" / settings.TILES_FILE, *map(Path, settings.FIRMS_FILES)]
    files.extend(map(Path, getattr(settings, "FORECAST_WEATHER_FILES", [])))
    for name, value in vars(settings).items():
        if name.endswith("_FILE") and isinstance(value, Path) and value not in files:
            files.append(value)
        markers = {"WEATHER_DIR": "stations.json", "HYDRO_DIR": "stations.json",
                   "DAILY_RAIN_DIR": "stations.json", "TERRAIN_DIR": "layer.json",
                   "LANDSAT_DIR": "SOURCE.json", "SENTINEL1_DIR": "SOURCE.json",
                   "SENTINEL2_DIR": "SOURCE.json", "MET_FORECAST_DIR": "SOURCE.json",
                   "LIGHTNING_DIR": "SOURCE.json", "RADAR_DIR": "SOURCE.json",
                   "EMS_DIR": "perimeters.geojson", "MUNICIPAL_BASEMAP_DIR": "SOURCE.json"}
        if name in markers and isinstance(value, Path):
            if name == "LANDSAT_DIR" and not getattr(settings, "LANDSAT_SCENES", {}):
                continue
            files.append(value / markers[name])
    checks = [Check(str(path), path.is_file() and path.stat().st_size > 0, "required input file")
              for path in dict.fromkeys(files)]
    for name, spec in PACKAGES.items():
        path = root / "app/frontend/vendor" / f"{name}-{spec['version']}"
        entry = path / ("Cesium.js" if name == "cesium" else "index.js")
        checks.append(Check(str(entry), entry.is_file(), "browser library; tools.fetch_web_vendor"))
    voice = root / "data/voices/sv_SE-alma-medium.onnx"
    for path in (voice, Path(str(voice) + ".json")):
        checks.append(Check(str(path), path.is_file(), "Alma voice; tools.fetch_piper_voices"))
    return checks


def installation_checks(name: str) -> list[Check]:
    settings = importlib.import_module(f"app.backend.scenarios.{name}")
    chrome = find_chrome()
    return [Check("Python", sys.version_info >= (3, 10), f"{sys.version.split()[0]}: {sys.executable}"),
            Check("Chrome/Chromium", chrome is not None, chrome or "not found"),
            probe("Docker Compose", ["docker", "compose", "version"]),
            probe("Docker engine", ["docker", "info", "--format", "{{.ServerVersion}}"]),
            *data_checks(settings)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("scenario", nargs="?", choices=AVAILABLE, default=DEFAULT)
    args = parser.parse_args(argv)
    checks = installation_checks(args.scenario)
    for check in checks:
        print(f"{'OK' if check.passed else 'MISSING/FAILED'} {check.name}: {check.detail}")
    print("Presence checks only; database contents, Python packages, audio and window placement are not verified.")
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
