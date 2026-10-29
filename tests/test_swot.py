"""Tests for SWOT's water heights (tools/fetch_swot.py, app/backend/swot.py, swot.js, satlog.js).
SYNTHETIC measurements round Ljungan and two lakes; the values are made up."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools import fetch_scenario
from tools import fetch_swot as fetch

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"


def measured(wse: float, quality: int, time: str, **extra) -> dict:
    return {"wse": wse, "wse_u": 0.05, "quality_f": quality, "reach_q": quality, "time_str": time, "dark_frac": 0.0,
            "partial_f": 0, "width": 150.0, **extra}


def test_a_good_measurement_against_good_comparisons_is_not_uncertain() -> None:
    result = fetch.compare(measured(20.5, 0, "2023-08-11T11:51:00Z"),
                           [measured(20.0, 0, "2023-08-01T13:29:00Z"), measured(20.1, 0, "2023-08-02T04:41:00Z")], "lake")
    assert (result["change_m"], result["uncertain"], result["uncertainty_notes"]) == (0.45, False, [])
    assert [item["time_utc"] for item in result["baseline"]] == ["2023-08-01T13:29:00Z", "2023-08-02T04:41:00Z"]


def test_every_reason_for_doubt_is_kept_and_named() -> None:
    result = fetch.compare(measured(31.0, 1, "2023-08-11T11:51:00Z", wse_u=0.57, dark_frac=0.5, width=-999999999999.0),
                           [measured(30.0, 2, "2023-08-01T13:29:00Z"), measured(30.6, 3, "2023-08-02T04:41:00Z")], "river")
    assert result["uncertain"] and result["change_m"] == 0.7
    assert result["uncertainty_notes"] == [
        "Mätningen 11 augusti har kvaliteten osäker (suspect).", "Jämförelsen 1 augusti har kvaliteten försämrad (degraded).",
        "Jämförelsen 2 augusti har kvaliteten dålig (bad).", "Jämförelsemätningarna skiljer 0,60 m sinsemellan.",
        "SWOT:s egen osäkerhet är ±0,57 m.", "50 % av ytan var mörk i radarn och fick sin höjd uppskattad.",
        "Ingen bredd kunde mätas; sträckan räknas som osäker."]
    lake = fetch.compare(measured(31.0, 0, "2023-08-11T11:51:00Z", partial_f=1), [measured(30.0, 0, "2023-08-01T13:29:00Z")], "lake")
    assert lake["uncertainty_notes"] == ["Sjön sågs bara delvis."]


def test_without_a_height_at_the_pass_or_before_nothing_is_compared() -> None:
    assert fetch.compare(measured(-999999999999.0, 0, "2023-08-11T11:51:00Z"), [measured(30.0, 0, "2023-08-01T13:29:00Z")], "lake") is None
    assert fetch.compare(measured(30.0, 0, "2023-08-11T11:51:00Z"), [], "lake") is None


def test_the_newest_version_of_each_pass_is_kept() -> None:
    def entry(title: str) -> dict:
        return {"title": title, "time_start": "2023-08-01T13:28:32.625Z",
                "links": [{"href": f"https://archive.swot.podaac.earthdata.nasa.gov/x/{title}.zip"}, {"href": "s3://x"}]}
    found = fetch.newest("lake", [entry("SWOT_L2_HR_LakeSP_Prior_001_318_EU_20230801T132832_20230801T133933_PGD0_01"),
                                  entry("SWOT_L2_HR_LakeSP_Prior_001_318_EU_20230801T132832_20230801T133933_PGD0_02"),
                                  entry("SWOT_L2_HR_LakeSP_Obs_001_318_EU_20230801T132832_20230801T133933_PGD0_02")])
    assert [(item["key"], item["title"][-7:]) for item in found] == [("001_318", "PGD0_02")]


def test_lakes_take_osm_s_name_and_reaches_the_nearest_station() -> None:
    lakes = [("Marmen", (62.25, 17.1), 8.0), ("Vikarn", (62.4, 17.4), 4.0)]
    assert fetch.osm_lake_name((62.251, 17.1), lakes) == "Marmen" and fetch.osm_lake_name((62.0, 16.0), lakes) is None
    stations = [("Skallböle", (62.3636, 16.9619))]
    assert fetch.place_name((62.37, 17.0), stations, []) == "Skallböle"
    assert fetch.place_name((62.37, 17.3), stations, [("Nolby", (62.33, 17.3))]) == "Nolby"


def write_items(directory: Path) -> None:
    good = fetch.compare(measured(20.5, 0, "2023-08-11T11:51:00Z"), [measured(20.0, 0, "2023-08-01T13:29:00Z")], "lake")
    doubtful = fetch.compare(measured(20.0, 1, "2023-08-11T11:51:00Z"), [measured(20.2, 0, "2023-08-01T13:29:00Z")], "lake")
    river = fetch.compare(measured(31.0, 1, "2023-08-11T11:51:00Z"), [measured(30.2, 1, "2023-08-01T13:29:00Z")], "river")
    items = [{"kind": "lake", "name": "Marmen", "area_km2": 8.5, **good}, {"kind": "lake", "name": None, "area_km2": 0.2, **doubtful},
             {"kind": "river", "name": "Ljungan vid Skallböle", "width_m": 160, **river}]
    (directory / "swot.json").write_text(json.dumps({
        "source": fetch.ATTRIBUTION, "baseline_passes": [{"kind": "lake", "time_utc": "2023-08-01T13:29:00Z"}],
        "passes": [{"kind": "lake", "time_utc": "2023-08-11T11:51:00Z"}], "items": items}), encoding="utf-8")


def test_the_backend_sums_up_and_says_every_uncertainty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend import swot
    write_items(tmp_path)
    monkeypatch.setattr(swot.scenario, "SWOT_DIR", tmp_path)
    monkeypatch.setattr(swot.scenario, "SWOT_NOTES", ["Ljungan är reglerad för vattenkraft."])
    swot.data.cache_clear()
    layer = swot.layer()
    swot.data.cache_clear()
    assert layer["event"]["text"] == ("SWOT mätte vattenhöjden: 1 av 1 sjöar med god kvalitet högre än 1 augusti, i mitten 0,50 meter; "
                                      "0 av 1 sjöar med osäker mätning högre; Ljungan 0,80 meter högre, alla sträckor med osäker kvalitet")
    assert layer["event"]["spoken"].endswith("Ljungan 0,8 meter högre, alla sträckor med osäker kvalitet")
    text = " ".join(layer["uncertainties"])
    assert "bara en gång" in text and "1 augusti, före regnet" in text and "EGM2008" in text and "version D" in text
    assert "1 av 1 mätta sträckor med osäker kvalitet" in text and "Ljungan är reglerad för vattenkraft." in text and "1 sjöar saknar namn" in text


def test_the_heights_are_an_optional_step_with_an_earthdata_account() -> None:
    plan = {step.key: step for step in fetch_scenario.steps("ljungan-aug2023")}
    assert plan["swot"].optional and plan["swot"].account == "earthdata"
    assert "swot" not in [step.key for step in fetch_scenario.steps("flen2019")]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_screens_show_the_heights_from_the_pass_and_flag_the_uncertain() -> None:
    item = {"kind": "lake", "name": "Marmen", "area_km2": 8.5, "change_m": 0.23, "wse_u_m": 0.01, "quality": 1, "uncertain": True,
            "baseline": [{}, {}], "uncertainty_notes": ["Mätningen 11 augusti har kvaliteten osäker (suspect)."]}
    code = (f"const w = require({json.dumps(str(FRONTEND / 'swot.js'))}); const s = require({json.dumps(str(FRONTEND / 'satlog.js'))});"
            f"const item = {json.dumps(item)}; const info = {{ pass_utc: '2023-08-11T11:50:40Z' }};"
            "const lines = s.satelliteLog({ swotEvents: [{ time_utc: '2023-08-11T11:50:40Z', text: 'T', spoken: 'S' }] }, Date.parse('2023-08-12T00:00:00Z'));"
            "console.log(JSON.stringify([w.swotShown(info, Date.parse('2023-08-11T11:00:00Z')), w.swotShown(info, Date.parse('2023-08-11T12:00:00Z')),"
            " w.swotLabel(item), w.swotLabel({ ...item, change_m: -0.1, uncertain: false }), w.swotColour(-0.1), w.swotColour(1.2),"
            " w.swotLabelled(item), w.swotTooltip(item), lines.map((l) => [l.text, l.spoken, s.SATLOG_SOURCES[l.source]])]));")
    result = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert result[:7] == [False, True, "+0,23 m?", "−0,10 m", "#9ca3af", "#1e3a8a", True]
    assert result[7] == ("<strong>Marmen</strong>: +0,23 m sedan mätningarna före regnet (±0,01 m)<br>"
                         "Kvalitet: osäker (suspect) – osäker mätning<br>Mätningen 11 augusti har kvaliteten osäker (suspect).")
    assert result[8] == [["T", "S", "SWOT, uppmätt"]]
