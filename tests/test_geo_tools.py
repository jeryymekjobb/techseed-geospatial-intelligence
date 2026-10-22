"""Tests for tools/geo_tools.py and the fetch and build tools' native route (no GDAL, osmium or Docker needed)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tools import build_offline_tiles, fetch_ems_perimeters, fetch_landsat_scene, fetch_sentinel1_scene, fetch_sentinel2_scene, geo_tools


def test_the_tools_are_docker_unless_native_is_chosen(monkeypatch) -> None:
    monkeypatch.delenv("TECHSEED_TOOLS", raising=False)
    assert geo_tools.choice() == "docker" and geo_tools.choice("native") == "native"
    monkeypatch.setenv("TECHSEED_TOOLS", "native")
    assert geo_tools.choice() == "native"
    with pytest.raises(ValueError):
        geo_tools.choice("wsl")


def test_the_container_gets_the_same_script_as_before() -> None:
    # The steps are quoted for the shell, so a URL with ? and & stays one argument, as the
    # hand-written scripts quoted it.
    script = geo_tools.shell_script([["gdalwarp", "-q", "/vsicurl/https://x.test/a.tif?st=1&sig=2", "a.tif"],
                                     ["gdal_translate", "-q", "a.tif", "a.bil"]], ["a.tif", "*.aux.xml"])
    assert script == ("set -e\ncd /data\ngdalwarp -q '/vsicurl/https://x.test/a.tif?st=1&sig=2' a.tif\n"
                      "gdal_translate -q a.tif a.bil\nrm -f a.tif *.aux.xml")


def test_native_steps_run_in_order_in_the_directory_and_clean_up(tmp_path: Path) -> None:
    write = "import pathlib, sys; pathlib.Path(sys.argv[1]).write_text('x')"
    steps = [[sys.executable, "-c", write, "a.tif"], [sys.executable, "-c", write, "a.bil"], [sys.executable, "-c", write, "b.aux.xml"]]
    run = geo_tools.run_native(steps, tmp_path, ["a.tif", "*.aux.xml"], {"GDAL_HTTP_TIMEOUT": "60"})
    assert run.returncode == 0 and sorted(path.name for path in tmp_path.iterdir()) == ["a.bil"]
    env = [sys.executable, "-c", "import os, pathlib; pathlib.Path('env').write_text(os.environ['GDAL_HTTP_TIMEOUT'])"]
    assert geo_tools.run_native([env], tmp_path, environment={"GDAL_HTTP_TIMEOUT": "60"}).returncode == 0
    assert (tmp_path / "env").read_text() == "60"  # the same GDAL options as the container gets


def test_a_failing_or_missing_step_stops_the_rest_and_says_why(tmp_path: Path) -> None:
    fail = [sys.executable, "-c", "import sys; sys.stderr.write('ERROR 1: no such band'); sys.exit(1)"]
    never = [sys.executable, "-c", "open('never', 'w')"]
    run = geo_tools.run_native([fail, never], tmp_path, ["*"])
    assert run.returncode == 1 and "no such band" in run.stderr and not (tmp_path / "never").exists()
    missing = geo_tools.run_native([["gdalwarp-that-is-not-installed", "x"]], tmp_path)
    assert missing.returncode == 127 and "not found on PATH" in missing.stderr and "--tools docker" in missing.stderr


def test_the_satellite_tools_run_their_steps_natively_with_the_gdal_options(monkeypatch, tmp_path: Path) -> None:
    calls = []
    monkeypatch.setattr(geo_tools, "run_native", lambda steps, directory, cleanup=(), environment=None:
                        calls.append((steps, directory, cleanup, environment)) or geo_tools.subprocess.CompletedProcess([], 0, "", ""))
    steps = fetch_landsat_scene.warp_steps({band: f"https://x.test/{band}.TIF?t" for band in
                                            ["red", "green", "blue", "nir08", "swir16", "swir22", "qa_pixel"]}, "SCENE")
    assert fetch_landsat_scene.run_gdal(steps, tmp_path, "native").returncode == 0
    native_steps, directory, cleanup, environment = calls[0]
    assert native_steps[0][0] == "gdalwarp" and "/vsicurl/https://x.test/blue.TIF?t" in native_steps[0]
    assert directory == tmp_path and "*.vrt" in cleanup and environment == fetch_landsat_scene.GDAL_HTTP
    # The Sentinel-1 DEM's tiles are read where they lie, not from the container's /dem.
    bbox, size = (16.9, 62.15, 17.8, 62.62), (90, 47)  # the tests run Västmanland, which has no Sentinel scenes
    dem, _ = fetch_sentinel1_scene.dem_steps(["N62.tif"], bbox, size, dem=(tmp_path / "dem").as_posix())
    assert f"{(tmp_path / 'dem').as_posix()}/N62.tif" in dem[0]
    assert "/dem/N62.tif" in fetch_sentinel1_scene.dem_script(["N62.tif"], bbox, size)
    s2, _ = fetch_sentinel2_scene.warp_steps({"SCL": ["https://x.test/a.tif?t", "https://x.test/b.tif?t"]}, "S", "05.11", bbox, size)
    assert s2[0][-3:] == ["/vsicurl/https://x.test/a.tif?t", "/vsicurl/https://x.test/b.tif?t", "SCL.tif"]


def test_ems_converts_natively_with_the_sql_as_one_argument(monkeypatch, tmp_path: Path) -> None:
    steps = fetch_ems_perimeters.convert_steps("EMSR1_observed_event_a", "EMSR1_source")
    sql = steps[0][steps[0].index("-sql") + 1]
    assert sql.startswith("SELECT geometry, ST_Area(ST_Transform(geometry, 3006))") and sql.endswith("FROM 'EMSR1_observed_event_a'")
    assert steps[1] == ["ogr2ogr", "-f", "CSV", "source.csv", "EMSR1_source.dbf"]


def test_the_offline_map_runs_osmium_and_tilemaker_natively_only_when_both_are_there(monkeypatch, tmp_path: Path) -> None:
    source, area = tmp_path / "sweden.osm.pbf", tmp_path / "area.osm.pbf"
    assert build_offline_tiles.extract_step(source, area, "16.3,58.8,17.1,59.28") == [
        "osmium", "extract", "-b", "16.3,58.8,17.1,59.28", "--strategy", "smart", "--overwrite", str(source), "-o", str(area)]
    resources = tmp_path / "tilemaker" / "resources"
    step = build_offline_tiles.tilemaker_step(area, tmp_path / "out.mbtiles", "16.3,58.8,17.1,59.28", resources)
    assert step[step.index("--config") + 1] == str(resources / "config-openmaptiles.json")
    assert step[step.index("--process") + 1] == str(build_offline_tiles.PROCESS_DIR / build_offline_tiles.PROCESS_FILE)
    # Without tilemaker, as on Windows, it stops before anything runs and points to the data package.
    monkeypatch.setattr(build_offline_tiles.shutil, "which", lambda name: None if name == "tilemaker" else f"/usr/bin/{name}")
    monkeypatch.setattr(build_offline_tiles.subprocess, "run", lambda *a, **kw: pytest.fail("nothing may run"))
    with pytest.raises(SystemExit) as error:
        build_offline_tiles.main(["--tools", "native", "--tilemaker-resources", str(resources)])
    assert error.value.code == 2
