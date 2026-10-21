"""Explicit Chromium browser selection; Chrome remains the default."""

from __future__ import annotations

import os
from pathlib import Path
import shutil


def choice(value: str | None = None) -> str:
    value = value or os.environ.get("TECHSEED_BROWSER", "chrome")
    if value not in ("chrome", "edge"):
        raise ValueError("Browser must be chrome or edge (TECHSEED_BROWSER)")
    return value


def find_edge() -> str | None:
    for name in ("msedge", "msedge.exe", "microsoft-edge", "microsoft-edge-stable"):
        executable = shutil.which(name)
        if executable:
            return executable
    candidates = [Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                  Path.home() / "Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        if os.environ.get(variable):
            candidates.append(Path(os.environ[variable]) / "Microsoft/Edge/Application/msedge.exe")
    return next((str(path) for path in candidates if path.is_file()), None)


def channel(browser: str) -> str:
    return "msedge" if choice(browser) == "edge" else "chrome"
