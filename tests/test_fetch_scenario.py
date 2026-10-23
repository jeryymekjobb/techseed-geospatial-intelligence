"""Tests for tools/fetch_scenario.py with stand-ins for the tools: nothing is fetched."""

from __future__ import annotations

import io
import subprocess
from datetime import date
from pathlib import Path

import pytest

from app.backend.scenarios import AVAILABLE, REPO_ROOT
from tools import fetch_scenario as fetch


def keys(name: str) -> list[str]:
    return [step.key for step in fetch.steps(name)]


@pytest.mark.parametrize("name", AVAILABLE)
def test_every_scenario_s_steps_run_existing_tools_in_an_order_their_inputs_allow(name: str) -> None:
    plan = fetch.steps(name)
    for step in plan:
        if step.command:
            assert (REPO_ROOT / "tools" / f"{step.command[2].removeprefix('tools.')}.py").is_file(), step.key
            assert step.env == {"TECHSEED_SCENARIO": name, "TECHSEED_TOOLS": "docker"}
    order = [step.key for step in plan]
    before = lambda first, then: first not in order or then not in order or order.index(first) < order.index(then)  # noqa: E731
    assert before("dem", "terrain") and before("dem", "sentinel1") and before("osm-terrain", "sentinel1")
    assert before("era5-land", "era5-sea") and before("postgis", "level-sensors") and before("mcf", "postgis")
    for image in ("landsat", "sentinel2", "sentinel1"):
        assert before(image, "meteosat-clm")  # the cloud mask is asked for at each image's time
    assert order[-1] in ("postgis", "route-exposure", "radar-sensors", "level-sensors")


def test_the_steps_follow_each_scenario_s_data() -> None:
    assert "landsat" in keys("vastmanland2014") and "landsat" not in keys("flen2019") and "ems" in keys("ljusdal2018")
    assert "municipal-basemap" in keys("sundsvall2026") and "municipal-basemap" not in keys("kramfors2026")
    assert "smhi-spinup" in keys("ljusdal2018") and "era5-sea" in keys("vasternorrland2025")
    # Two tools write the level sensors: by the rivers where the scenario names them, else at the damage.
    tool_of = lambda name: next(step.command[2] for step in fetch.steps(name) if step.key == "level-sensors")  # noqa: E731
    assert tool_of("skane2024") == tool_of("flenkommun2024") == "tools.derive_level_sensor_points"
    assert tool_of("flen2019") == tool_of("vasternorrland2025") == "tools.derive_impact_sensor_points"
    # Västmanland's weather, wind and OSM layers are tracked in git, not fetched.
    tracked = {step.key: step for step in fetch.steps("vastmanland2014") if step.command is None}
    assert {"smhi-weather", "era5-land", "osm-terrain", "osm-targets"} <= set(tracked)
    radar = next(step.command for step in fetch.steps("flen2019") if step.key == "smhi-radar")
    assert radar[radar.index("--start") + 1:radar.index("--start") + 2] == ["2019-12-07"] and "30" in radar
    terrain = next(step for step in fetch.steps("flen2019", "native") if step.key == "terrain")
    assert terrain.command[-2:] == ["--tools", "native"] and "pydelatin" in terrain.packages


def test_smhi_s_recent_data_and_the_radar_s_step() -> None:
    assert fetch.smhi_period(date(2026, 8, 22), today=date(2026, 10, 22)) == "latest-months"
    assert fetch.smhi_period(date(2024, 3, 12), today=date(2026, 10, 22)) == "corrected-archive"
    sundsvall = fetch.module("sundsvall2026")
    assert fetch.radar_dates(sundsvall) == ("2026-08-14", "2026-08-23", "10")
    # A clean clone's flen2019 lacked the frame at the playback's stop, 29 December 00:00 UTC (2026-10-23).
    assert fetch.radar_dates(fetch.module("flen2019")) == ("2019-12-07", "2019-12-29", "30")


def step(tmp_path: Path, key: str, done: bool = False, **extra) -> fetch.Step:
    marker = tmp_path / f"{key}.json"
    if done:
        marker.write_text("{}")
    return fetch.Step(key, key, ["python", "-m", f"tools.{key}"], marker, **extra)


def test_a_run_skips_what_is_done_stops_at_a_failure_and_goes_on_from_there(tmp_path: Path) -> None:
    ran = []

    def runner(command, **kwargs):
        ran.append(command[-1])
        if command[-1] == "tools.b":
            return subprocess.CompletedProcess(command, 2)
        (tmp_path / f"{command[-1].removeprefix('tools.')}.json").write_text("{}")
        return subprocess.CompletedProcess(command, 0)

    plan = [step(tmp_path, "a", done=True), step(tmp_path, "b"), step(tmp_path, "c")]
    assert fetch.run(plan, runner=runner) == 2 and ran == ["tools.b"]  # a was done; c waits for b
    ran.clear()
    (tmp_path / "b.json").write_text("{}")
    assert fetch.run(plan, runner=runner) == 0 and ran == ["tools.c"]  # the same command goes on from there
    ran.clear()
    assert fetch.run(plan, force=True, runner=runner) == 2 and ran == ["tools.a", "tools.b"]
    # A step that says it succeeded but wrote nothing is a failure too.
    assert fetch.run([step(tmp_path, "silent")], runner=lambda command, **kwargs: subprocess.CompletedProcess(command, 0)) == 1


def test_missing_accounts_and_packages_stop_the_run_before_anything_is_fetched(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setitem(fetch.ACCOUNTS, "copernicus-cds", (tmp_path / ".cdsapirc", "Copernicus CDS"))
    plan = [step(tmp_path, "era5", account="copernicus-cds"), step(tmp_path, "terrain", packages=("no_such_package_here",)),
            step(tmp_path, "done", done=True, account="copernicus-cds")]
    found = fetch.problems(plan)
    assert len(found) == 2 and "Copernicus CDS" in found[0] and "no_such_package_here" in found[1]  # a step that is done needs nothing
    (tmp_path / ".cdsapirc").write_text("not read by the tool")
    assert len(fetch.problems(plan)) == 1
    monkeypatch.setattr(fetch, "steps", lambda name, tools="docker": plan)
    monkeypatch.setattr(fetch, "run", lambda *args, **kwargs: pytest.fail("nothing may be fetched"))
    assert fetch.main(["flen2019"]) == 1
    printed = capsys.readouterr().out
    assert "Saknas: terrain" in printed and "inget hämtades" in printed and "not read by the tool" not in printed
    assert fetch.main(["flen2019", "--list"]) == 0  # the plan is shown without fetching anything


def test_the_optional_forecasts_run_only_when_asked() -> None:
    plan = fetch.steps("flen2019")
    assert "met-forecasts" not in [s.key for s in fetch.selected(plan, False)]
    assert "met-forecasts" in [s.key for s in fetch.selected(plan, True)]


def test_the_osm_extract_continues_an_interrupted_download(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "sweden.osm.pbf"
    (tmp_path / "sweden.osm.pbf.part").write_bytes(b"first half ")
    asked = []

    class Response(io.BytesIO):
        status = 206

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def opener(request, timeout):
        asked.append(request.get_header("Range"))
        return Response(b"second half")
    monkeypatch.setattr(fetch, "urlopen", opener)
    fetch.download("https://example.test/sweden.osm.pbf", target)
    assert asked == ["bytes=11-"] and target.read_bytes() == b"first half second half"
    assert not (tmp_path / "sweden.osm.pbf.part").exists()


def test_a_run_asks_first_and_never_fetches_without_an_answer(monkeypatch, capsys, tmp_path: Path) -> None:
    plan = [step(tmp_path, "a")]
    monkeypatch.setattr(fetch, "steps", lambda name, tools="docker": plan)
    monkeypatch.setattr(fetch, "run", lambda *args, **kwargs: pytest.fail("nothing may be fetched"))
    monkeypatch.setattr(fetch.sys.stdin, "isatty", lambda: False)
    assert fetch.main(["flen2019"]) == 1 and "--yes" in capsys.readouterr().out  # no terminal: only with --yes
    monkeypatch.setattr(fetch.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    assert fetch.main(["flen2019"]) == 1  # no is the default
    ran = []
    monkeypatch.setattr(fetch, "run", lambda plan, force=False: ran.append(plan) or 1)
    monkeypatch.setattr("builtins.input", lambda prompt: "j")
    assert fetch.main(["flen2019"]) == 1 and len(ran) == 1
    assert fetch.main(["flen2019", "--yes"]) == 1 and len(ran) == 2


def test_native_steps_need_their_programs_and_point_to_the_package_without_tilemaker(monkeypatch) -> None:
    plan = fetch.steps("flen2024", "native")
    assert next(s for s in plan if s.key == "tiles").programs == ("osmium", "tilemaker")
    assert next(s for s in plan if s.key == "sentinel2").programs == fetch.GDAL
    assert all(not s.programs for s in fetch.steps("flen2024", "docker"))  # Docker brings its own
    monkeypatch.setattr(fetch.shutil, "which", lambda name: None if name == "tilemaker" else f"/usr/bin/{name}")
    tiles = [s for s in plan if s.key == "tiles"]
    tiles[0].marker = Path("/nonexistent/tiles.mbtiles")
    found = fetch.problems(tiles)
    assert len(found) == 1 and "tilemaker" in found[0] and "datapaket" in found[0]


def test_the_image_steps_need_pillow_from_its_requirements_file() -> None:
    # A clean clone lacked Pillow (2026-10-23): the steps that write images check it before fetching.
    plan = {step.key: step for step in fetch.steps("sundsvall2026")}
    for key in ("smhi-radar", "landsat", "sentinel2", "sentinel1", "municipal-basemap"):
        assert "PIL" in plan[key].packages, key
    assert fetch.requirements_for(("PIL",)) == "pip install -r tools/requirements-data.txt"
    assert "Pillow==" in (REPO_ROOT / "tools" / "requirements-data.txt").read_text(encoding="utf-8")


# The pip project of each third-party module the code imports, and the requirements files that name them.
PIP_NAMES = {"PIL": "pillow", "paho": "paho-mqtt", "piper": "piper-tts", "quantized_mesh_encoder": "quantized-mesh-encoder"}


def test_every_third_party_module_the_code_imports_is_in_a_requirements_file() -> None:
    # A clean clone lacked Pillow, and numpy came only through onnxruntime (2026-10-23).
    import ast
    import re
    import sys

    required = set()
    for path in [*REPO_ROOT.glob("app/requirements-*.txt"), *REPO_ROOT.glob("tools/requirements-*.txt")]:
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\s*([A-Za-z0-9_.-]+)", line.split("#", 1)[0])
            if match:
                required.add(match.group(1).lower().replace("_", "-"))
    imported = {}
    for path in [*REPO_ROOT.glob("tools/*.py"), *REPO_ROOT.glob("app/backend/**/*.py")]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 else []
            for name in names:
                top = name.split(".")[0]
                if top not in sys.stdlib_module_names and top not in ("app", "tools", "tests"):
                    imported.setdefault(top, path.name)
    missing = {top: where for top, where in imported.items() if PIP_NAMES.get(top, top).lower().replace("_", "-") not in required}
    assert not missing, missing
