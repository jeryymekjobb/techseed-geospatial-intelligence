"""The Docker images the demo and its tools run are pinned to a digest, the tools work without
os.getuid (Windows), and the steps declare the packages they import."""

from __future__ import annotations

import re
from pathlib import Path

from tools import build_offline_tiles, build_terrain, fetch_landsat_scene, fetch_scenario

ROOT = Path(__file__).resolve().parents[1]
PINNED = re.compile(r"[a-z0-9./-]+:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}")


def test_every_image_is_pinned_to_a_digest() -> None:
    compose = re.findall(r"^\s*image:\s*(\S+)", (ROOT / "docker-compose.yml").read_text(encoding="utf-8"), re.M)
    images = [*compose, build_offline_tiles.TILEMAKER_IMAGE, build_offline_tiles.OSMIUM_IMAGE,
              build_terrain.CTB_IMAGE, fetch_landsat_scene.GDAL_IMAGE]
    assert len(compose) == 3
    for image in images:
        assert PINNED.fullmatch(image), image


def test_the_tools_name_a_user_without_os_getuid(monkeypatch) -> None:
    for module in (build_offline_tiles, build_terrain, fetch_landsat_scene):
        monkeypatch.delattr(module.os, "getuid", raising=False)
        assert module.user() == "0:0"


def test_the_sentinel1_wind_step_declares_numpy() -> None:
    step = next(step for step in fetch_scenario.steps("ljungan-aug2023") if step.key == "sentinel1-wind")
    assert "numpy" in step.packages
