"""Tests for the continuous monitoring (app/monitoring/): the events in, the live sources' readers,
the rules, the alarms, the briefing and the operator page's server. SYNTHETIC answers in the
sources' layouts; no network."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.monitoring import alarms, briefing, events, geo, rules, satellites, service, sources
from app.monitoring.areas import flenkommun

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
NO_SCENES = lambda url, body: b'{"features": []}'  # noqa: E731 - Planetary Computer's search, empty
MS = lambda moment: int(moment.timestamp() * 1000)  # noqa: E731
# A square around Flen, in WGS 84.
BORDER = {"type": "Polygon", "coordinates": [[[16.4, 58.85], [17.05, 58.85], [17.05, 59.24], [16.4, 59.24], [16.4, 58.85]]]}


def area(**changes):
    values = {name: getattr(flenkommun, name) for name in dir(flenkommun) if name.isupper()}
    # The scenarios' OSM targets, MCF's flood zone and the level sensors' points are unversioned data: the
    # tests use none, and they do not ask EUMETSAT for Meteosat's cloud mask.
    values.update(OSM_TARGETS_FILE=Path("/nonexistent/targets.geojson"), FLOOD_ZONE_FILES=[],
                  LEVEL_SENSOR_FILE=Path("/nonexistent/level-points.geojson"), METEOSAT_CLM=False)
    values.update(changes)
    return SimpleNamespace(**values)


# --- events in -------------------------------------------------------------------------------

def test_a_tsv_line_in_wgs84_and_one_in_sweref_come_in() -> None:
    text = ("datum\tklockslag\thändelse\tkoordinat 1\tkoordinat 2\tkoordinatsystem\tkälla\n"
            "2026-11-03\t10:15\tbrand\t59.05\t16.59\tEPSG:4326\tSOS Alarm\tnej\n"
            "2026-11-03\t10:20:30\tskred\t6580822\t674032\tEPSG:3006\tKommunen\n")
    batch = events.parse_text(text, "in.tsv")
    assert not batch.refused
    first, second = batch.events
    assert (first.kind, first.latitude, first.longitude, first.simulated, first.simulated_stated) == ("fire", 59.05, 16.59, False, True)
    assert first.time == datetime(2026, 11, 3, 10, 15, tzinfo=timezone.utc) and first.origin == "in.tsv:2"
    # gdaltransform -s_srs EPSG:3006 -t_srs EPSG:4326, as in test_read_vattenwebb.py.
    assert abs(second.latitude - 59.3302312261) < 1e-7 and abs(second.longitude - 18.0591897364) < 1e-7
    # Not stated: counted as simulated.
    assert second.kind == "landslide" and second.simulated and not second.simulated_stated


def test_a_line_without_a_source_is_logged_and_refused(caplog) -> None:
    text = "2026-11-03,10:15,översvämning,59.1,16.7,EPSG:4326,\n"
    with caplog.at_level(logging.WARNING, logger="app.monitoring.events"):
        batch = events.parse_text(text, "in.csv")
    assert batch.events == []
    assert [(item.origin, item.reason, item.line) for item in batch.refused] == [("in.csv:1", "källa saknas", text.strip())]
    (record,) = caplog.records
    assert "källa saknas" in record.getMessage() and "in.csv:1" in record.getMessage() and text.strip() in record.getMessage()


def test_the_log_comes_before_the_refusal_is_kept(monkeypatch) -> None:
    order = []
    monkeypatch.setattr(events.log, "warning", lambda *args: order.append("logged"))
    original = events.Refusal

    def kept(*args):
        order.append("refused")
        return original(*args)

    monkeypatch.setattr(events, "Refusal", kept)
    events.parse_text("2026-11-03\t10:15\tbrand\t59.1\t16.7\tEPSG:4326\t \n", "in.tsv")
    assert order == ["logged", "refused"]


@pytest.mark.parametrize(("line", "reason"), [
    ("2026-11-03\t10:15\tbrand\t59.1\t16.7\tEPSG:4326", "fel antal fält"),
    ("2026-11-03\t10:15\tstorm\t59.1\t16.7\tEPSG:4326\tSMHI", "okänd händelse"),
    ("2026-11-03\t10:15\tbrand\t59.1\t16.7\tEPSG:3857\tSMHI", "okänt koordinatsystem"),
    ("2026-11-31\t10:15\tbrand\t59.1\t16.7\tEPSG:4326\tSMHI", "ogiltig tid"),
    ("2026-11-03\t10:15\tbrand\t99.1\t16.7\tEPSG:4326\tSMHI", "utanför WGS 84"),
    ("2026-11-03\t10:15\tbrand\t59.1\t16.7\tEPSG:3006\tSMHI", "utanför SWEREF 99 TM"),
    ("2026-11-03\t10:15\tbrand\t59.1\t16.7\tEPSG:4326\tSMHI\tkanske", "simulerad"),
])
def test_other_faults_are_logged_and_refused_with_their_reason(line: str, reason: str, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="app.monitoring.events"):
        batch = events.parse_text(line + "\n", "in.tsv")
    assert not batch.events and reason in batch.refused[0].reason and reason in caplog.records[0].getMessage()


def test_json_events_come_in_and_the_inbox_moves_what_it_has_read(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "a.json").write_text(json.dumps([
        {"date": "2026-11-03", "time": "09:00", "event": "flood", "coord1": 59.0, "coord2": 16.6, "crs": "EPSG:4326",
         "source": "Nivågivare", "simulated": True},
        {"date": "2026-11-03", "time": "09:00", "event": "flood", "coord1": 59.0, "coord2": 16.6, "crs": "EPSG:4326"},
    ]), encoding="utf-8")
    (inbox / "b.pdf").write_bytes(b"%PDF")
    batch = events.read_inbox(inbox)
    assert [event.source for event in batch.events] == ["Nivågivare"] and batch.events[0].simulated_stated
    assert sorted(item.reason for item in batch.refused) == ["källa saknas", "okänd filtyp: .pdf"]
    assert sorted(path.name for path in inbox.iterdir() if path.is_file()) == []
    assert len(list((inbox / "processed").iterdir())) == 2
    assert events.read_inbox(inbox).events == []


# --- geometry --------------------------------------------------------------------------------

def test_points_and_polygons() -> None:
    assert geo.contains(BORDER, 59.0, 16.7) and not geo.contains(BORDER, 59.5, 16.7)
    holed = {"type": "Polygon", "coordinates": BORDER["coordinates"] + [[[16.6, 59.0], [16.8, 59.0], [16.8, 59.1], [16.6, 59.1], [16.6, 59.0]]]}
    assert not geo.contains(holed, 59.05, 16.7)
    county = {"type": "MultiPolygon", "coordinates": [[[[16.0, 58.5], [17.5, 58.5], [17.5, 59.5], [16.0, 59.5], [16.0, 58.5]]]]}
    assert geo.overlaps(county, BORDER) and not geo.overlaps(county, {"type": "Polygon", "coordinates": [[[10, 55], [11, 55], [11, 56], [10, 55]]]})
    assert abs(geo.distance_km(59.0, 16.0, 59.0, 17.0) - 57.3) < 0.2


# --- the sources' readers --------------------------------------------------------------------

def flow_answer(values: list[float], quality: str = "O") -> bytes:
    return json.dumps({"position": [{"latitude": 58.95, "longitude": 16.88}],
                       "value": [{"date": MS(NOW - timedelta(minutes=15 * (len(values) - index))), "value": value, "quality": quality}
                                 for index, value in enumerate(values)]}).encode()


ARCHIVE = ("Stationsnamn;Stationsnummer\nSIBRO 2;2587\n\nDatum (svensk sommartid);Vattenföring (Dygn);Kvalitet\n"
           + "".join(f"2020-01-{day:02d};{day}.0;G\n" for day in range(1, 31)) + "2024-02-27;40.0;G\n")


def fake_fetch(answers: dict[str, bytes]):
    def fetch(url: str) -> bytes:
        if "/geotype/multipoint/" in url and "createdtime.json" in answers:
            return grid_answer(url)
        for part, answer in answers.items():
            if part in url:
                return answer
        raise AssertionError(f"unexpected URL {url}")
    return fetch


def test_flows_rain_and_statistics_are_read(tmp_path: Path) -> None:
    fetch = fake_fetch({"parameter/2/station/2587": flow_answer([1.0, 2.0]), "corrected-archive": ARCHIVE.encode(),
                        "parameter/7/station/96040": json.dumps({"position": [{"latitude": 59.06, "longitude": 16.39}], "value": [
                            {"date": MS(NOW - timedelta(hours=30)), "value": "50.0", "quality": "G"},
                            {"date": MS(NOW - timedelta(hours=2)), "value": "4.5", "quality": "G"},
                            {"date": MS(NOW - timedelta(hours=1)), "value": "6.0", "quality": "Y"}]}).encode()})
    (flow,) = sources.read_flows({"2587": "Sibro 2"}, fetch)
    assert [reading["value"] for reading in flow["readings"]] == [1.0, 2.0] and flow["latitude"] == 58.95
    (rain,) = sources.read_rain({"96040": "Floda A"}, fetch)
    assert rain["mm_24h"] == 10.5 and rain["hours"] == 2 and rain["unchecked"]
    path = tmp_path / "stats.json"
    stats = sources.cached_statistics({"2587": "Sibro 2"}, 99.0, path, fetch)
    assert stats["2587"]["record"] == 40.0 and stats["2587"]["record_day"] == "2024-02-27" and 29 < stats["2587"]["high"] < 40
    assert sources.cached_statistics({"2587": "Sibro 2"}, 99.0, path, fake_fetch({})) == stats


def test_warnings_in_the_county_or_over_the_border_count_and_others_not() -> None:
    def warning(code, group, county, polygon, level="YELLOW"):
        return {"id": len(code), "event": {"sv": code.title(), "code": code, "mhoClassification": {"code": group}},
                "warningAreas": [{"id": 1, "areaName": {"sv": "Område"}, "warningLevel": {"sv": "Gul", "code": level},
                                  "eventDescription": {"sv": code}, "affectedAreas": [{"id": county}],
                                  "area": {"geometry": polygon}, "descriptions": [{"text": {"sv": "Text"}}]}]}
    far = {"type": "Polygon", "coordinates": [[[13, 55.5], [14, 55.5], [14, 56], [13, 55.5]]]}
    answer = [warning("HIGH_FLOW", "HYD", 4, far), warning("FIRE", "FIRE", 12, BORDER), warning("WIND", "MET", 12, far),
              warning("WATER_SHORTAGE", "HYD", 4, far, "MESSAGE")]
    found = sources.read_warnings(4, BORDER, fake_fetch({"warning.json": json.dumps(answer).encode()}))
    assert [(item["event"], item["kind"]) for item in found] == [("High_Flow", "flood"), ("Fire", "fire"), ("Water_Shortage", "other")]


def test_krisinformation_fire_bans_and_firms_are_read() -> None:
    vma = [{"identifier": "7", "headline": "Brand i Flen", "preamble": "Stäng fönster", "published": "2026-11-03T12:00:00+01:00",
            "web": "https://example.invalid", "area": [{"description": "Flens kommun"}]},
           {"identifier": "8", "headline": "Annat", "area": [{"description": "Gotlands län"}]}]
    fetch = fake_fetch({"/vmas": json.dumps(vma).encode(), "/news": b"[]"})
    (item,) = sources.read_krisinformation(("Södermanland", "Flen"), fetch)
    assert item["id"] == "vma-7" and item["published_utc"] == "2026-11-03T11:00:00Z"
    ban = {"features": [{"attributes": {"KOMMUNNAMN": "Flen", "STATUS": "Eldningsförbud", "STARTDATUM": MS(NOW), "REVDATUM": None}}]}
    assert sources.read_fire_ban("0482", fake_fetch({"Eldningsforbud": json.dumps(ban).encode()}))[0]["status"] == "Eldningsförbud"
    csv_text = ("latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
                "59.05,16.59,330.1,0.4,0.4,2026-11-03,105,N20,VIIRS,n,2.0NRT,280.0,4.5,D\n")
    (point,) = sources.read_firms("KEY", ("VIIRS_NOAA20_NRT",), flenkommun.BBOX, 1, fake_fetch({"/VIIRS_NOAA20_NRT/": csv_text.encode()}))
    assert point["time_utc"] == "2026-11-03T01:05:00Z" and point["frp"] == 4.5
    with pytest.raises(RuntimeError) as error:
        sources.read_firms("KEY", ("MODIS_NRT",), flenkommun.BBOX, 1, fake_fetch({"MODIS": b"Invalid MAP_KEY KEY."}))
    assert "KEY" not in str(error.value).replace("MAP_KEY", "")


def test_the_firms_key_comes_from_the_environment_or_the_file(tmp_path: Path) -> None:
    assert sources.firms_key({"FIRMS_MAP_KEY": " abc "}, tmp_path / "none") == "abc"
    (tmp_path / "key").write_text("def\n")
    assert sources.firms_key({}, tmp_path / "key") == "def"
    result = sources.guarded("firms", lambda: [{"key": sources.firms_key({}, tmp_path / "none")}])
    assert not result.ok and result.note == "nyckel saknas"


# --- rules -----------------------------------------------------------------------------------

STATS = {"2587": {"high": 10.0, "high_percentile": 99.0, "record": 17.2, "record_day": "2024-02-27",
                  "archive_from": "2012-06-22", "archive_to": "2026-11-02"}}


def flow_station(values, quality="O"):
    return [{"station": "2587", "name": "Sibro 2", "latitude": 58.95, "longitude": 16.88,
             "readings": [{"time_utc": f"2026-11-03T1{index}:00:00Z", "value": value, "quality": quality} for index, value in enumerate(values)]}]


def test_a_high_flow_needs_two_readings_and_a_record_is_marked() -> None:
    assert rules.flow_candidates(flow_station([9.0, 12.0]), STATS, [], [], area()) == []
    (high,) = rules.flow_candidates(flow_station([11.0, 12.0]), STATS, [], [], area())
    assert high.severity == "high" and high.as_json()["single_source"] and high.facts[0]["uncertain"]
    rain = [{"name": "Floda A", "mm_24h": 12.0}]
    (record,) = rules.flow_candidates(flow_station([16.0, 18.0], "G"), STATS, rain, [], area())
    assert record.severity == "record" and record.confirmations == ["Regn 12 mm senaste 24 h vid Floda A (SMHI)"]
    assert not record.facts[0]["uncertain"]


def test_fires_are_clustered_confirmed_by_passes_and_known_heat_sources_left_out() -> None:
    firms = [{"latitude": 59.05, "longitude": 16.59, "time_utc": "2026-04-30T01:05:00Z", "satellite": "N20", "instrument": "VIIRS",
              "confidence": "n", "frp": 3.0},
             {"latitude": 59.052, "longitude": 16.592, "time_utc": "2026-04-30T02:45:00Z", "satellite": "N", "instrument": "VIIRS",
              "confidence": "l", "frp": 2.0},
             {"latitude": 59.15, "longitude": 16.9, "time_utc": "2026-04-30T01:05:00Z", "satellite": "N20", "instrument": "VIIRS",
              "confidence": "h", "frp": 9.0},
             {"latitude": 60.0, "longitude": 16.9, "time_utc": "2026-04-30T01:05:00Z", "satellite": "N20", "instrument": "VIIRS",
              "confidence": "h", "frp": 9.0}]
    filtered = []
    found = rules.fire_candidates(firms, [], BORDER, [{"status": "Eldningsförbud", "description": None, "revised_utc": None}],
                                  area(KNOWN_HEAT_SOURCES=[("Värmeverk", 59.15, 16.9, 0.5)]), filtered)
    (fire,) = found
    assert fire.severity == "confirmed" and "Samma plats vid 2 passager" in fire.confirmations
    assert "Sett av 2 satelliter" in fire.confirmations and fire.facts[1]["uncertain"]
    assert any("valborgsmässoafton" in note for note in fire.notes)
    assert any("Eldningsförbud" in fact["text"] for fact in fire.facts)
    assert filtered == [{"what": "FIRMS N20 2026-04-30T01:05:00Z", "reason": "känd värmekälla: Värmeverk", "latitude": 59.15, "longitude": 16.9}]


def test_events_in_the_area_become_candidates_and_others_are_left_out() -> None:
    def event(origin, lat, simulated=True, stated=False, hours=1, kind="fire"):
        return {"origin": origin, "kind": kind, "latitude": lat, "longitude": 16.59, "coordinates": [lat, 16.59], "crs": "EPSG:4326",
                "source": "Rapport", "simulated": simulated, "simulated_stated": stated,
                "time_utc": (NOW - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    firms = [{"latitude": 59.051, "longitude": 16.59}]
    filtered = []
    ban = [{"status": "Inget eldningsförbud", "description": None, "revised_utc": None}]
    found = rules.event_candidates([event("a", 59.05), event("b", 60.5), event("c", 59.05, hours=30)], BORDER, firms, ban, [],
                                   area(), NOW, filtered)
    (item,) = found
    assert item.simulated and item.confirmations == ["1 värmedetektioner från FIRMS inom 1 km"]
    assert "räknas som simulerad" in item.notes[0]
    assert any(fact["text"] == "Eldningsförbud: Inget eldningsförbud" for fact in item.facts)
    assert [entry["reason"] for entry in filtered] == ["utanför Flens kommun"]


def test_only_yellow_orange_and_red_flood_and_fire_warnings_and_vma_alarm() -> None:
    warnings = [{"id": "1", "kind": "flood", "level_code": "YELLOW", "level": "Gul", "description": "Höga flöden", "event": "x",
                 "area": "Södermanlands län", "published_utc": "2026-11-03T08:00:00Z", "text": ""},
                {"id": "2", "kind": "flood", "level_code": "MESSAGE", "level": "Meddelande", "description": "", "event": "x",
                 "area": "", "published_utc": None, "text": ""},
                {"id": "3", "kind": "other", "level_code": "RED", "level": "Röd", "description": "", "event": "x",
                 "area": "", "published_utc": None, "text": ""}]
    assert [item.key for item in rules.warning_candidates(warnings)] == ["warning-1"]
    vma = [{"id": "vma-7", "kind": "vma", "headline": "Brand", "preamble": "", "published_utc": None, "areas": ["Flens kommun"]},
           {"id": "news-1", "kind": "news", "headline": "Nyhet", "preamble": "", "published_utc": None, "areas": []}]
    assert [item.key for item in rules.vma_candidates(vma, area())] == ["vma-7"]


# --- alarms and briefing ---------------------------------------------------------------------

def candidate(severity="high"):
    item = rules.Candidate("flow-2587", "flood", severity, "Högt flöde vid Sibro 2", "Sibro 2", 58.95, 16.88)
    item.fact("Vattenföring 12 m³/s", "SMHI", "2026-11-03T11:00:00Z", uncertain=True)
    return item


def test_alarms_are_new_until_the_operator_acts_and_come_back_only_when_they_rise(tmp_path: Path) -> None:
    store = alarms.Store(tmp_path / "state.json")
    store.apply([candidate()], [], [], {})
    assert store.snapshot()["alarms"]["flow-2587"]["state"] == "new"
    store.act("flow-2587", "dismiss", "Känd reglering")
    store.apply([candidate()], [], [], {})
    assert store.snapshot()["alarms"]["flow-2587"]["state"] == "dismissed"
    store.apply([candidate("record")], [], [], {})
    alarm = store.snapshot()["alarms"]["flow-2587"]
    assert alarm["state"] == "new" and [item["action"] for item in alarm["history"]] == ["larm", "avfärdat", "larm"]
    store.apply([], [], [], {})
    assert not alarms.Store(tmp_path / "state.json").snapshot()["alarms"]["flow-2587"]["current"]
    with pytest.raises(KeyError):
        store.act("none", "confirm")
    with pytest.raises(ValueError):
        store.act("flow-2587", "send")


def test_the_briefing_names_each_source_and_marks_what_is_uncertain(tmp_path: Path) -> None:
    store = alarms.Store(tmp_path / "state.json")
    item = candidate()
    item.simulated = True
    store.apply([item], [], [], {})
    store.act("flow-2587", "confirm", "<script>")
    alarm = store.snapshot()["alarms"]["flow-2587"]
    content = briefing.build(alarm, {"rain": [{"name": "Floda A", "mm_24h": 0.0, "latest_utc": "2026-11-03T11:00:00Z"}]}, flenkommun)
    assert content["uncertain"][:2] == ["Larmet bygger på en enda källa.", "Vattenföring 12 m³/s"]
    assert content["contacts"] == flenkommun.CONTACTS["flood"]
    page = briefing.render(content)
    assert "SIMULERAD HÄNDELSE" in page and "(osäkert)" in page and "Floda A" in page and "Exempel" in page
    assert "<script>" not in page and "&lt;script&gt;" in page


# --- the service -----------------------------------------------------------------------------

def grid_answer(url: str) -> bytes:
    """A SYNTHETIC answer of SMHI's forecast grid for the parameter in the URL: 4 rows of 5 points
    over Flen, row by row, the longitude jumping back west at each row's start."""
    parameter = url.split("/parameter/")[1].split("/")[0]
    points = [[16.4 + 0.15 * column, 58.9 + 0.1 * row] for row in range(4) for column in range(5)]
    value = {"wind_speed": 6.0, "wind_from_direction": 225.0, "precipitation_amount_mean": 0.0,
             "thunderstorm_probability": 0.0}.get(parameter)
    values = [value if value is not None else 1000.0 + 4 * (index % 5) for index in range(len(points))]
    return json.dumps({"geometry": {"coordinates": points}, "timeSeries": [{"data": {parameter: values}}]}).encode()


def live_answers() -> dict[str, bytes]:
    return {"createdtime.json": json.dumps({"createdTime": "2026-11-03T11:00:00Z"}).encode(),
            "Basdata/Kommuner": json.dumps({"features": [{"geometry": BORDER}]}).encode(),
            "gis.flen.se": json.dumps({"features": []}).encode(),
            "corrected-archive": ARCHIVE.encode(),
            "parameter/2/station/": flow_answer([45.0, 50.0]),
            "parameter/7/station/": json.dumps({"value": []}).encode(),
            "warning.json": b"[]", "/vmas": b"[]", "/news": b"[]",
            "Eldningsforbud": json.dumps({"features": []}).encode(),
            "fwif1g": json.dumps({"timeSeries": []}).encode(), "snow1g": json.dumps({"timeSeries": []}).encode(),
            "opendata-download-radar": json.dumps({"files": []}).encode(),
            "firms.modaps": b"latitude,longitude,acq_date,acq_time,satellite,instrument,confidence,frp\n"}


def test_a_poll_reads_every_source_and_raises_the_alarms(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FIRMS_MAP_KEY", "KEY")
    monitor = service.Monitor(area(DATA_DIR=tmp_path), fake_fetch(live_answers()), tmp_path, NO_SCENES)
    (monitor.inbox).mkdir()
    (monitor.inbox / "in.tsv").write_text("2026-11-03\t10:15\tbrand\t59.0\t16.6\tEPSG:4326\t\n", encoding="utf-8")
    summary = monitor.poll()
    assert all(item["ok"] for item in summary["sources"]), summary["sources"]
    assert {item["key"] for item in summary["candidates"]} == {"flow-2614", "flow-2587", "flow-1273"}
    assert summary["refused"] == 1
    state = monitor.state()
    assert state["refused"][0]["reason"] == "källa saknas" and state["alarms"][0]["state"] == "new"
    assert "Sibro 2" in monitor.briefing_page("flow-2587") and monitor.briefing_page("none") is None


def test_a_failing_source_is_reported_and_the_others_go_on(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FIRMS_MAP_KEY", "SECRETKEY")
    answers = live_answers()

    def fetch(url: str) -> bytes:
        if "warning.json" in url:
            raise OSError("timed out")
        if "firms.modaps" in url:
            raise OSError(f"refused {url}")
        return fake_fetch(answers)(url)

    summary = service.Monitor(area(DATA_DIR=tmp_path), fetch, tmp_path, NO_SCENES).poll()
    status = {item["source"]: item for item in summary["sources"]}
    assert not status["smhi_warnings"]["ok"] and "timed out" in status["smhi_warnings"]["error"]
    assert not status["firms"]["ok"] and "SECRETKEY" not in status["firms"]["error"]
    assert status["smhi_flow"]["ok"] and len(summary["candidates"]) == 3


@pytest.fixture
def server(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FIRMS_MAP_KEY", "KEY")
    monitor = service.Monitor(area(DATA_DIR=tmp_path), fake_fetch(live_answers()), tmp_path, NO_SCENES)
    monitor.poll()
    handler = type("TestHandler", (service.Handler,), {"monitor": monitor})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def request(port: int, method: str, path: str, body: bytes | None = None, headers: dict[str, str] | None = None):
    connection = HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    return response.status, response.read()


def test_the_screens_are_served_at_the_demos_paths_and_only_their_own_json_can_act(server: int) -> None:
    status, _ = request(server, "GET", "/")
    assert status == 302
    for path, marker in (("/control.html", b"view-toggle"), ("/3d.html", b"globe.js"), ("/2d.html", b"map2d.js"),
                         ("/monitor.html", b"satellites.js"),
                         ("/orbits.js", b"function subpoint"), ("/satmonitor.js", b"createSatelliteMonitor")):
        status, body = request(server, "GET", path)
        assert status == 200 and marker in body, path
    assert request(server, "GET", "/vendor/leaflet-1.9.4/leaflet.js")[0] == 200
    assert request(server, "GET", "/vendor/leaflet-1.9.4/../../index.html")[0] == 404
    assert request(server, "GET", "/vendor/other/x.js")[0] == 404
    status, body = request(server, "GET", "/api/state")
    assert status == 200 and json.loads(body)["area"]["name"] == "Flens kommun"
    assert request(server, "POST", "/api/alarms/flow-2587/confirm", b"note=x",
                   {"Content-Type": "application/x-www-form-urlencoded"})[0] == 415
    assert request(server, "POST", "/api/alarms/flow-2587/confirm", b"{}",
                   {"Content-Type": "application/json", "Origin": "http://evil.example"})[0] == 403
    status, body = request(server, "POST", "/api/alarms/flow-2587/confirm", json.dumps({"note": "Kontrollerat"}).encode(),
                           {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{server}"})
    assert status == 200 and json.loads(body)["state"] == "confirmed"
    assert request(server, "POST", "/api/alarms/none/confirm", b"{}", {"Content-Type": "application/json"})[0] == 404
    status, page = request(server, "GET", "/briefing/flow-2587")
    assert status == 200 and "Bekräftat av operatören".encode() in page


def test_the_config_offers_the_municipal_map_once_fetched_with_osm_under_and_over(tmp_path: Path, monkeypatch) -> None:
    item = {**flenkommun.MUNICIPAL_BASEMAPS[0], "dir": tmp_path / "flen"}
    monitor = service.Monitor(area(MUNICIPAL_BASEMAPS=[item]), fake_fetch({}), tmp_path, NO_SCENES)
    monkeypatch.setattr(service.offline_tiles, "available", lambda: False)
    maps = monitor.config()["maps"]
    assert maps["municipal"] == [] and maps["offline"] is None and maps["online"]["url"].startswith("https://tile.openstreetmap.org/")
    (item["dir"] / "12" / "2200").mkdir(parents=True)
    (item["dir"] / "12" / "2200" / "1200.png").write_bytes(b"PNG")
    (item["dir"] / "SOURCE.json").write_text(json.dumps({"min_zoom": 8, "max_zoom": 16, "bbox_west_south_east_north": [16.4, 58.85, 17.06, 59.25]}))
    monkeypatch.setattr(service.offline_tiles, "available", lambda: True)
    maps = monitor.config()["maps"]
    assert maps["municipal"][0]["url"] == "/basemap/flen/{z}/{x}/{y}.png" and "intern användning" in maps["municipal"][0]["attribution"]
    assert maps["offline"]["url"] == "/tiles/{z}/{x}/{y}.png" and maps["overlay"]["url"] == "/tiles-overlay/{z}/{x}/{y}.png"


def test_the_radar_image_is_an_empty_one_until_the_radar_is_fetched(server: int) -> None:
    status, body = request(server, "GET", "/api/radar.png")
    assert status == 200 and body.startswith(b"\x89PNG")
    status, body = request(server, "GET", "/api/config")
    layers = json.loads(body)["layers"]
    assert layers["radar"]["url"] == "/api/radar.png" and layers["flood"]["layers"] == "12"


def test_mission_control_switches_the_main_screen_between_3d_and_2d(server: int) -> None:
    assert json.loads(request(server, "GET", "/api/view")[1])["view"] == "3d"
    assert request(server, "POST", "/api/view", json.dumps({"view": "4d"}).encode(), {"Content-Type": "application/json"})[0] == 400
    assert request(server, "POST", "/api/view", b'{"view": "2d"}', {"Content-Type": "text/plain"})[0] == 415
    status, body = request(server, "POST", "/api/view", b'{"view": "2d"}', {"Content-Type": "application/json"})
    assert status == 200 and json.loads(body) == {"view": "2d"}
    assert json.loads(request(server, "GET", "/api/state")[1])["view"] == "2d"
    for name, other in (("globe.js", '"/2d.html"'), ("map2d.js", '"/3d.html"')):
        assert other in (Path(service.WEB_DIR) / name).read_text(encoding="utf-8")


def test_byt_stops_the_service_only_when_started_from_the_start_page(server: int, monkeypatch) -> None:
    assert request(server, "POST", "/api/demo/menu", b"{}", {"Content-Type": "application/json"})[0] == 409
    monkeypatch.setenv("TECHSEED_DEMO_MENU_EXIT", "3")
    assert request(server, "POST", "/api/demo/menu", b"{}", {"Content-Type": "text/plain"})[0] == 415
    assert request(server, "POST", "/api/demo/menu", b"{}", {"Content-Type": "application/json"})[0] == 202


def test_the_screens_set_text_from_the_sources_as_text() -> None:
    for name in ("control.js", "satellites.js", "map2d.js"):
        script = (Path(service.WEB_DIR) / name).read_text(encoding="utf-8")
        assert "innerHTML" not in script and "insertAdjacentHTML" not in script, name
    globe = (Path(service.WEB_DIR) / "globe.js").read_text(encoding="utf-8")
    assert "description: escapeText(" in globe and "name: escapeText(" in globe
    flat = (Path(service.WEB_DIR) / "map2d.js").read_text(encoding="utf-8")
    assert flat.count("bindTooltip(") == flat.count("bindTooltip(tip(") > 0 and "html: label" in flat


# --- satellites ------------------------------------------------------------------------------

LINE1 = "1 37849U 11061A   26306.91494491  .00000105  00000+0  70340-4 0  9990"
LINE2 = "2 37849  98.7339 238.0297 0001412  86.3640 273.7695 14.19533328772063"


def test_current_elements_are_fetched_once_a_day_and_kept_when_a_fetch_fails(tmp_path: Path) -> None:
    asked = []
    records = [{"NORAD_CAT_ID": "37849", "EPOCH": "2026-11-02 21:57:31.240224", "TLE_LINE1": LINE1, "TLE_LINE2": LINE2},
               {"NORAD_CAT_ID": "99999", "EPOCH": "2026-11-02 21:57:31", "TLE_LINE1": LINE1, "TLE_LINE2": LINE2}]
    fetch = lambda path: asked.append(path) or records  # noqa: E731
    path = tmp_path / "current.json"
    data = satellites.satellites(flenkommun, fetch, path, NOW)
    assert data["available"] and [item["name"] for item in data["satellites"]] == ["Suomi NPP"]
    assert data["satellites"][0]["elements"] == [{"epoch_utc": "2026-11-02T21:57:31.240224Z", "line1": LINE1, "line2": LINE2}]
    assert "Inga aktuella banelement för NOAA-20" in data["note"] and "/class/gp/NORAD_CAT_ID/" in asked[0]
    satellites.satellites(flenkommun, fetch, path, NOW + timedelta(hours=23))
    assert len(asked) == 1

    def failing(path):
        raise OSError("down")

    later = satellites.satellites(flenkommun, failing, path, NOW + timedelta(hours=25))
    assert later["available"] and "kunde inte hämtas" in later["note"]
    assert not satellites.satellites(flenkommun, failing, tmp_path / "none.json", NOW)["available"]


# --- radar, fire risk and forecast -----------------------------------------------------------

def radar_tiff(value: int) -> bytes:
    """A SYNTHETIC radar image in SMHI's layout: 8-bit values on 2 km pixels in SWEREF 99 TM, over Flen."""
    import io

    from PIL import Image, TiffImagePlugin

    info = TiffImagePlugin.ImageFileDirectory_v2()
    info[33922] = (0.0, 0.0, 0.0, 500000.0, 6650000.0, 0.0)
    info.tagtype[33922] = 12
    info[33550] = (2000.0, 2000.0, 0.0)
    info.tagtype[33550] = 12
    out = io.BytesIO()
    Image.new("L", (100, 100), value).save(out, format="TIFF", tiffinfo=info)
    return out.getvalue()


def radar_answers(value: int) -> dict[str, bytes]:
    files = [{"key": f"radar_261103{hour:02d}{minute:02d}", "formats": [{"key": "tif", "link": f"https://radar.invalid/{hour:02d}{minute:02d}.tif"}]}
             for hour in (11, 12) for minute in range(0, 60, 5)]
    return {"product/comp/2026/11/03": json.dumps({"files": files}).encode(), "radar.invalid": radar_tiff(value)}


def test_the_radar_keeps_the_last_hour_in_the_municipality_and_draws_it() -> None:
    from app.monitoring import radar

    # 192 is about 46.8 dBZ, some 30 mm/h by Z = 200 R^1.6.
    station = radar.Radar(flenkommun.BBOX, fake_fetch(radar_answers(192)))
    stats = station.update(BORDER, NOW)
    assert stats["frames"] == 12 and stats["latest_utc"] == "2026-11-03T12:00:00Z"
    assert 28 < stats["max_mm_h"] < 33 and 28 < stats["hour_mm"] < 33
    # In the border, to the grid's half pixel (0.0025 degrees east-west).
    lat, lon = stats["max_at"]
    assert 58.85 - 0.002 <= lat <= 59.24 + 0.002 and 16.4 - 0.003 <= lon <= 17.05 + 0.003 and station.png.startswith(b"\x89PNG")
    # No echo: no rain.
    assert radar.Radar(flenkommun.BBOX, fake_fetch(radar_answers(0))).update(BORDER, NOW)["max_mm_h"] == 0.0


def test_a_cloudburst_needs_the_radar_s_limit_and_is_confirmed_by_a_gauge() -> None:
    stats = {"frames": 12, "latest_utc": "2026-11-03T11:55:00Z", "max_mm_h": 31.0, "hour_mm": 30.5, "max_at": [59.06, 16.6]}
    assert rules.cloudburst_candidates({**stats, "max_mm_h": 12.0}, [], [], area()) == []
    (burst,) = rules.cloudburst_candidates(stats, [{"name": "Floda A", "mm_last_hour": 14.0}], [], area())
    assert burst.kind == "flood" and burst.confirmations == ["Floda A: 14 mm senaste timmen (SMHI)"]
    assert all(fact["uncertain"] for fact in burst.facts[:2])
    (alone,) = rules.cloudburst_candidates(stats, [{"name": "Floda A", "mm_last_hour": 0.0}], [], area())
    assert alone.as_json()["single_source"]


def test_fire_risk_is_read_and_raised_from_class_five_today_or_tomorrow() -> None:
    answer = {"approvedTime": "2026-07-01T06:00:00Z", "timeSeries": [
        {"validTime": f"2026-07-0{day}T12:00:00Z", "parameters": [{"name": "fwiindex", "values": [index]}, {"name": "grassfire", "values": [grass]},
                                                                    {"name": "fwi", "values": [20.0]}]}
        for day, index, grass in ((1, 4, 3), (2, 5, 6), (3, 6, 6))]}
    days = sources.read_fire_risk(59.06, 16.73, fake_fetch({"fwif1g": json.dumps(answer).encode()}))
    assert [(day["day_utc"], day["fwi_word"]) for day in days] == [("2026-07-01", "stor"), ("2026-07-02", "mycket stor"),
                                                                     ("2026-07-03", "extremt stor")]
    found = rules.fire_risk_candidates(days, area(), datetime(2026, 7, 1, 8, tzinfo=timezone.utc))
    assert [item.title for item in found] == ["Förhöjd brandrisk 2026-07-02: extremt stor"]
    off = [{**day, "fwi_class": -1, "grass_class": -1, "fwi_word": None, "grass_word": None} for day in days]
    assert rules.fire_risk_candidates(off, area(), datetime(2026, 7, 1, tzinfo=timezone.utc)) == []


def test_the_forecast_sums_the_rain_of_the_next_days() -> None:
    steps = [{"time": (NOW + timedelta(hours=hour)).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "data": {"precipitation_amount_mean": 1.5, "air_temperature": 5.0 + hour / 10, "wind_speed_of_gust": 8.0}}
             for hour in range(0, 60, 6)]
    (item,) = sources.read_forecast(59.06, 16.73, fake_fetch({"snow1g": json.dumps({"timeSeries": steps}).encode()}))
    assert (item["rain_24h_mm"], item["rain_48h_mm"], item["max_step_mm"]) == (7.5, 13.5, 1.5)


# --- wind and weather chart ------------------------------------------------------------------

def test_the_forecast_grid_gives_the_area_s_wind_and_the_weather_chart_once_a_run() -> None:
    from app.monitoring import weather

    asked = []
    answers = live_answers()

    def fetch(url: str) -> bytes:
        asked.append(url)
        return fake_fetch(answers)(url)

    station = weather.Weather(flenkommun.BBOX, fetch)
    data = station.update(NOW)
    assert data["valid_utc"] == "2026-11-03T13:00:00Z" and len(data["wind"]) == 20
    assert data["wind"][0] == {"latitude": 58.9, "longitude": 16.4, "speed_ms": 6.0, "from_deg": 225}
    assert data["chart"]["lines"] and data["chart"]["rain_png"].startswith("data:image/png;base64,") and data["chart"]["thunder"] == []
    assert station.summary()["centre_wind"]["speed_ms"] == 6.0
    count = len(asked)
    station.update(NOW + timedelta(minutes=10))
    assert len(asked) == count + 1  # only createdtime.json: the same run and hour
    station.update(NOW + timedelta(hours=1))
    assert len(asked) > count + 2


def test_thunder_is_marked_once_per_hundred_kilometres_from_thirty_percent() -> None:
    import numpy as np

    from app.monitoring import weather

    lat, lon = np.meshgrid([59.0, 59.1, 61.0], [16.0, 16.1, 16.2], indexing="ij")
    probability = np.array([[50, 60, 0], [10, 0, 0], [35, 0, 20]], dtype=float)
    assert weather.thunder_marks(lat, lon, probability) == [[59.0, 16.1], [61.0, 16.0]]


def test_mission_control_shows_or_hides_the_layers(server: int) -> None:
    layers = json.loads(request(server, "GET", "/api/view")[1])["layers"]
    assert layers == service.LAYERS and layers["chart"] is False and layers["facilities"] is True and layers["s1wetness"] is False
    assert request(server, "POST", "/api/layers", b'{"chart": "yes"}', {"Content-Type": "application/json"})[0] == 400
    assert request(server, "POST", "/api/layers", b'{"rain": true}', {"Content-Type": "application/json"})[0] == 400
    status, body = request(server, "POST", "/api/layers", b'{"chart": true, "names": false}', {"Content-Type": "application/json"})
    assert status == 200 and json.loads(body)["layers"]["chart"] is True and json.loads(body)["layers"]["names"] is False
    status, body = request(server, "GET", "/api/weather")
    assert status == 200 and len(json.loads(body)["wind"]) == 20
    assert request(server, "GET", "/wind_barbs.js")[0] == 200


def test_the_road_numbers_are_clipped_to_the_municipality() -> None:
    import io

    from PIL import Image

    tile = io.BytesIO()
    Image.new("RGBA", (256, 256), (200, 0, 0, 255)).save(tile, "PNG")
    # The tile z12 x2236 y1210 holds Flen's town (59.06 N, 16.59 E); the square border covers its west part.
    border = {"type": "Polygon", "coordinates": [[[16.40, 59.0], [16.6, 59.0], [16.6, 59.2], [16.40, 59.2], [16.40, 59.0]]]}
    clipped = Image.open(io.BytesIO(service.clip_to_border(tile.getvalue(), border, 12, 2236, 1210)))
    west_x, _ = geo.tile_pixel(59.06, 16.59, 12, 2236, 1210)
    assert clipped.getpixel((max(0, int(west_x) - 5), 128))[3] == 255
    assert clipped.getpixel((min(255, int(west_x) + 45), 128))[3] == 0
    assert service.clip_to_border(tile.getvalue(), None, 12, 2236, 1210) == tile.getvalue()


# --- the municipality's GIS, the weather stations, the satellite image, reading aloud and IoT ----

def test_the_gis_keeps_only_what_the_check_allows_and_finds_what_an_alarm_threatens(tmp_path: Path) -> None:
    import numpy as np

    from app.monitoring import gis

    def fetch(url: str) -> bytes:
        if "/10/query" in url:  # preschools, one of them twice
            points = [{"attributes": {"Namn": "Björkliden förskola"}, "geometry": {"x": 16.6099, "y": 59.0575}}] * 2
        elif "Samhallsservice" in url:  # care units: only those for the elderly are kept
            points = [{"attributes": {"Namn": "Hemgården", "Beskrivnin": "Äldre", "Beskrivn_1": "Särskilt boende"},
                       "geometry": {"x": 16.6, "y": 59.06}},
                      {"attributes": {"Namn": "Gökstigen", "Beskrivnin": "Funktionsnedsättning", "Beskrivn_1": "Gruppbostad"},
                       "geometry": {"x": 16.6, "y": 59.06}}]
        elif "/5/query" in url:  # health care as a multipoint
            points = [{"attributes": {"Vårdcentral": "Flen"}, "geometry": {"points": [[16.59, 59.06]]}}]
        elif "Prim%C3%A4rkarta_Flen" in url:
            points = [{"geometry": {"rings": [[[16.588, 59.058], [16.589, 59.058], [16.589, 59.059], [16.588, 59.058]]]}}]
        else:
            points = []
        assert "Adress" not in url and "Fastighet" not in url
        return json.dumps({"features": points}).encode()

    assets = gis.Assets(area(), tmp_path, fetch)
    data = assets.load()
    assert [(item["name"], item["category"]) for item in data["facilities"]] == [
        ("Björkliden förskola", "Förskola"), ("Flen", "Vårdcentral"), ("Hemgården", "Äldreomsorg: Särskilt boende")]
    near = assets.exposure({"key": "radar-cloudburst", "latitude": 59.058, "longitude": 16.59})
    # The preschool lies 1.1 km away: outside.
    assert near["where"] == "inom 1,0 km" and near["buildings"] == 1 and len(near["facilities"]) == 2
    assert assets.exposure({"key": "vma-1", "latitude": None}) is None
    square = [[[[16.0, 59.0], [17.0, 59.0], [17.0, 60.0], [16.0, 60.0], [16.0, 59.0]],
               [[16.4, 59.4], [16.6, 59.4], [16.6, 59.6], [16.4, 59.6], [16.4, 59.4]]]]
    assert gis.inside(np.array([[59.2, 16.2], [59.5, 16.5], [58.5, 16.5]]), square).tolist() == [True, False, False]


def test_the_weather_stations_give_their_latest_values() -> None:
    def fetch(url: str) -> bytes:
        if "/parameter/1/" in url:
            return json.dumps({"position": [{"latitude": 59.06, "longitude": 16.39}],
                               "value": [{"date": MS(NOW - timedelta(hours=1)), "value": "4.0"}, {"date": MS(NOW), "value": "5.5"}]}).encode()
        if "/parameter/5/" in url:  # the rain by the day: its period's end as "to"
            return json.dumps({"position": [{"latitude": 59.06, "longitude": 16.39}],
                               "value": [{"from": MS(NOW - timedelta(days=1)), "to": MS(NOW), "ref": "2026-11-02", "value": "2.5"}]}).encode()
        raise OSError("no such parameter")

    (station,) = sources.read_weather_stations({"96040": {"name": "Floda A", "parameters": [1, 4, 5]}}, fetch)
    assert station["values"] == {"temp_c": 5.5, "rain_day_mm": 2.5} and station["times"]["temp_c"] == "2026-11-03T12:00:00Z"
    assert sources.read_weather_stations({"1": {"name": "Tyst", "parameters": [4]}}, fetch) == []


def test_the_latest_clear_sentinel2_datatake_is_chosen_and_laid_together(tmp_path: Path) -> None:
    import io

    from PIL import Image

    from app.monitoring import sentinel2

    def item(name, when, cloud):
        return {"id": name, "properties": {"datetime": when, "eo:cloud_cover": cloud, "platform": "Sentinel-2A"}}

    found = [item("A1", "2026-11-01T10:21:00Z", 100), item("A2", "2026-11-01T10:21:01Z", 98),
             item("B1", "2026-10-29T10:20:00Z", 40), item("B2", "2026-10-29T10:20:02Z", 30)]
    takes = sentinel2.datatakes(found)
    assert [take["items"] for take in takes] == [["A1", "A2"], ["B1", "B2"]] and takes[1]["cloud"] == 35
    assert sentinel2.choose(takes, NOW)["items"] == ["B1", "B2"]
    assert sentinel2.choose([{**takes[0], "time_utc": "2026-10-10T10:00:00Z"}], NOW)["cloud"] == 99

    def png(colour):
        out = io.BytesIO()
        Image.new("RGBA", (4, 4), colour).save(out, "PNG")
        return out.getvalue()

    asked = []
    latest = sentinel2.Latest(flenkommun.BBOX, tmp_path, lambda url: asked.append(url) or png((0, 200, 0, 255)),
                              lambda url, body: json.dumps({"features": found}).encode())
    meta = latest.update(NOW)
    assert meta["items"] == ["B1", "B2"] and meta["recent"] and latest.png.startswith(b"\x89PNG")
    assert all("assets=B04" in url and "rescale=1000%2C3600" in url for url in asked) and len(asked) == 2
    assert latest.update(NOW + timedelta(minutes=10)) == meta and len(asked) == 2


def test_the_latest_landsat_image_is_asked_for_its_own_bands_and_named_as_the_screens_name_it(tmp_path: Path) -> None:
    import io

    from PIL import Image

    from app.monitoring import sentinel2

    out = io.BytesIO()
    Image.new("RGBA", (4, 4), (0, 200, 0, 255)).save(out, "PNG")
    found = [{"id": "LC09_1", "properties": {"datetime": "2026-10-29T10:00:00Z", "eo:cloud_cover": 10, "platform": "landsat-9"}}]
    asked, searched = [], []
    latest = sentinel2.Latest(flenkommun.BBOX, tmp_path, lambda url: asked.append(url) or out.getvalue(),
                              lambda url, body: searched.append(body) or json.dumps({"features": found}).encode(),
                              kind=sentinel2.LANDSAT)
    meta = latest.update(NOW)
    assert searched[0]["collections"] == ["landsat-c2-l2"] and meta["platform"] == "Landsat 9"
    assert "U.S. Geological Survey" in meta["attribution"] and (tmp_path / "landsat").is_dir()
    assert "collection=landsat-c2-l2" in asked[0] and "assets=red" in asked[0] and "rescale=7273%2C16364" in asked[0]


def test_the_config_offers_the_highest_flow_the_cloudburst_overlays_once_fetched_and_the_terrain(tmp_path: Path, monkeypatch) -> None:
    overlay = {**next(item for item in flenkommun.MUNICIPAL_BASEMAPS if item["id"] == "skyfall100"), "dir": tmp_path / "skyfall100"}
    terrain = tmp_path / "terrain"
    monitor = service.Monitor(area(MUNICIPAL_BASEMAPS=[overlay], TERRAIN_DIR=terrain), fake_fetch({}), tmp_path, NO_SCENES)
    monkeypatch.setattr(service.offline_tiles, "available", lambda: False)
    config = monitor.config()
    assert config["layers"]["flood_highest"]["layers"] == "9" and config["layers"]["overlays"] == [] and config["terrain"] is None
    overlay["dir"].mkdir()
    (overlay["dir"] / "SOURCE.json").write_text(json.dumps({"min_zoom": 12, "max_zoom": 16, "bbox_west_south_east_north": [16.54, 59.02, 16.68, 59.1]}))
    terrain.mkdir()
    (terrain / "layer.json").write_text("{}")
    config = monitor.config()
    assert [item["url"] for item in config["layers"]["overlays"]] == ["/basemap/skyfall100/{z}/{x}/{y}.png"]
    assert config["maps"]["municipal"] == [] and config["terrain"] == "/terrain/"


def test_the_terrain_route_serves_the_terrain_and_nothing_outside_it(tmp_path: Path) -> None:
    terrain = tmp_path / "terrain"
    (terrain / "0" / "0").mkdir(parents=True)
    (terrain / "layer.json").write_text('{"tiles": []}')
    (terrain / "0" / "0" / "0.terrain").write_bytes(b"\x1f\x8bmesh")
    (tmp_path / "secret.json").write_text("{}")
    monitor = service.Monitor(area(DATA_DIR=tmp_path, TERRAIN_DIR=terrain), fake_fetch({}), tmp_path, NO_SCENES)
    handler = type("TestHandler", (service.Handler,), {"monitor": monitor})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        port = httpd.server_address[1]
        assert request(port, "GET", "/terrain/layer.json") == (200, b'{"tiles": []}')
        assert request(port, "GET", "/terrain/0/0/0.terrain") == (200, b"\x1f\x8bmesh")
        assert request(port, "GET", "/terrain/../secret.json")[0] == 404
        assert request(port, "GET", "/basemap/skyfall500/14/1/1.png")[0] == 404
    finally:
        httpd.shutdown()


def test_the_satellite_monitor_follows_sentinel1_sentinel2_and_landsat() -> None:
    names = {item["name"]: item["instrument"] for item in flenkommun.SATELLITES.values()}
    assert {names[name] for name in names if name.startswith("Sentinel-1")} == {"SAR"}
    assert {names[name] for name in names if name.startswith("Sentinel-2")} == {"MSI"}
    assert {names[name] for name in names if name.startswith("Landsat")} == {"OLI"}


def test_new_alarms_are_read_aloud_only_with_upplasning_on(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FIRMS_MAP_KEY", "KEY")
    monitor = service.Monitor(area(DATA_DIR=tmp_path), fake_fetch(live_answers()), tmp_path, NO_SCENES)
    said = []
    monitor.say = lambda texts: said.extend(texts)
    monitor.poll()
    assert said == []
    monitor.speech = True
    monitor.store.state["alarms"].clear()
    monitor.poll()
    assert any(text.startswith("Nytt larm i Flens kommun: ") for text in said)
    count = len(said)
    monitor.poll()
    assert len(said) == count  # the same alarms are not read again


def test_the_service_serves_the_objects_the_image_and_the_iot_and_switches_reading_aloud(server: int) -> None:
    status, body = request(server, "GET", "/api/assets")
    assert status == 200 and set(json.loads(body)) == {"facilities", "places", "attribution"}
    status, body = request(server, "GET", "/api/satellite.png")
    assert status == 200 and body.startswith(b"\x89PNG")
    state = json.loads(request(server, "GET", "/api/state")[1])
    assert state["speech"] is False and state["iot"]["sensors"] == []
    assert request(server, "POST", "/api/speech", b'{"speech": 1}', {"Content-Type": "application/json"})[0] == 400
    status, body = request(server, "POST", "/api/speech", b'{"speech": true}', {"Content-Type": "application/json"})
    assert status == 200 and json.loads(body) == {"speech": True}


def test_sentinel1_shows_water_outside_the_lakes_in_red_and_groups_a_pass() -> None:
    import io

    import numpy as np
    from PIL import Image

    from app.monitoring import sentinel1

    # SYNTHETIC backscatter: land at -10 dB, a lake at -22 dB, a flooded field and one speck at -24 dB.
    vv = np.full((40, 40), 0.1, dtype="f4")
    lake = np.zeros((40, 40), dtype=bool)
    lake[0:10, 0:10] = True
    vv[lake] = 0.0063
    vv[20:26, 20:26] = 0.004
    vv[5, 35] = 0.004
    grey, water, stats = sentinel1.images(vv, lake)
    mask = np.array(Image.open(io.BytesIO(water)))
    assert mask[23, 23].tolist() == [255, 0, 0, 220] and mask[5, 5, 3] == 0 and mask[5, 35, 3] == 0
    assert stats["separable"] and abs(stats["threshold_db"] + 22.0) < 0.1 and stats["new_water_pct"] > 2
    assert np.array(Image.open(io.BytesIO(grey))).shape == (40, 40, 4)
    found = sentinel1.passes([
        {"id": "S1C_IW_A", "properties": {"datetime": "2026-11-03T05:14:36Z", "sat:orbit_state": "descending"}},
        {"id": "S1C_IW_B", "properties": {"datetime": "2026-11-03T05:14:11Z", "sat:orbit_state": "descending"}},
        {"id": "S1D_IW_C", "properties": {"datetime": "2026-11-02T16:37:13Z", "sat:orbit_state": "ascending"}}])
    assert [item["items"] for item in found] == [["S1C_IW_A", "S1C_IW_B"], ["S1D_IW_C"]]
    assert found[0]["time_utc"] == "2026-11-03T05:14:11Z" and found[0]["platform"] == "Sentinel-1C"


def test_the_stations_are_blue_red_while_alarming_and_the_objects_yellow() -> None:
    for name in ("map2d.js", "globe.js"):
        script = (Path(service.WEB_DIR) / name).read_text(encoding="utf-8")
        assert 'STATION_MARKS = { normal: "#1565c0", alarm: "#c62828" }' in script and "#ffd600" in script, name
        assert "alarming(state, `flow-${flow.station}`)" in script and "alarming(state, `rain-${station.station}`)" in script, name


def test_heavy_rain_at_a_station_alarms_and_mission_control_lists_only_detections_and_alarms() -> None:
    stations = [{"station": "96040", "name": "Floda A", "latitude": 59.06, "longitude": 16.39,
                 "values": {"rain_1h_mm": 12.5}, "times": {"rain_1h_mm": "2026-11-03T11:00:00Z"}},
                {"station": "19025", "name": "Höksta", "latitude": 59.4, "longitude": 16.2, "values": {"temp_c": 4.0}, "times": {}}]
    (alarm,) = rules.station_rain_candidates(stations, area())
    assert alarm.key == "rain-96040" and alarm.title == "Kraftigt regn vid Floda A: 12,5 mm på en timme"
    control = (Path(service.WEB_DIR) / "control.js").read_text(encoding="utf-8")
    assert "passerade" not in control and "radar.new_water_pct >= waterLogPct" in control and "drawDetections(state);" in control
    assert 'id="detections"' in (Path(service.WEB_DIR) / "control.html").read_text(encoding="utf-8")
    assert "monitor-log" not in (Path(service.WEB_DIR) / "satellites.html").read_text(encoding="utf-8")


def test_the_wetness_sets_each_pixel_between_its_dry_and_its_wet_and_leaves_out_lakes() -> None:
    import io

    import numpy as np
    from PIL import Image

    from app.monitoring import sentinel1

    dry, wet = np.full((6, 6), -20.0), np.full((6, 6), -10.0)
    now = np.full((6, 6), -15.0)
    now[:, 3:] = -10.0
    wet[0, 0] = -19.5  # forest or rock: too little between dry and wet
    count = np.full((6, 6), 10)
    lakes = np.zeros((6, 6), dtype=bool)
    lakes[5, 5] = True
    png, stats = sentinel1.wetness(now, dry, wet, count, lakes)
    image = np.array(Image.open(io.BytesIO(png)))
    assert image[0, 0, 3] == 0 and image[5, 5, 3] == 0 and image[2, 1, 3] == sentinel1.WETNESS_ALPHA
    assert image[2, 5, 0] < image[2, 1, 0]  # the wetter half is blue-green, with little red
    assert stats["wetness_cover_pct"] == round(100 * 34 / 36) and sentinel1.coarse(np.ones((10, 10), "f4")).shape == (2, 2)


def test_the_simulated_level_sensors_follow_their_station_and_alarm_above_its_record(tmp_path: Path) -> None:
    from app.monitoring import levels

    points = tmp_path / "level-points.geojson"
    points.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [16.7, 58.86]},
         "properties": {"id": "ng-02", "name": "NG2 Tärnövägen", "road": "Tärnövägen", "river": "Nyköpingsån", "station": "1273:2"}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [16.6, 58.9]},
         "properties": {"id": "ng-04", "name": "NG4 Nyköpingsån", "station": "2587:2"}}]}))
    loaded = levels.load(points)
    assert [point["station"] for point in loaded] == ["1273", "2587"] and levels.load(tmp_path / "none.geojson") == []
    flows = [{"station": "1273", "name": "Hallbosjön", "readings": [{"time_utc": "2026-11-04T08:00:00Z", "value": 55.0}]}]
    found = levels.readings(loaded, flows, {"1273": {"record": 51.5}, "2587": {"record": 15.2}})
    assert found[0]["alarm"] and found[0]["percent"] == 107 and found[0]["simulated"] and found[0]["station_name"] == "Hallbosjön"
    assert not found[1]["alarm"] and found[1]["value"] is None and found[1]["percent"] is None
    assert not levels.readings(loaded, flows, {"1273": {"record": 60.0}})[0]["alarm"]


def test_meteosat_s_cloud_mask_keeps_the_last_day_and_asks_again_only_for_a_newer_product(tmp_path: Path, monkeypatch) -> None:
    import sys

    import numpy

    from app.monitoring import meteosat, sources as monitoring_sources
    from tools import fetch_meteosat_clm, fetch_meteosat_cth

    products = ["MSG3-SEVI-MSGCLMK-0100-0100-20261104081500.000000000Z-NA"]
    searched = []

    class Collection:
        def search(self, dtstart, dtend):
            searched.append(dtstart)
            return list(products)

    store = SimpleNamespace(get_collection=lambda name: Collection())
    monkeypatch.setitem(sys.modules, "eumdac", SimpleNamespace(AccessToken=lambda pair: pair, DataStore=lambda token: store))
    key = tmp_path / "credentials"
    monkeypatch.setattr(fetch_meteosat_cth, "CREDENTIALS", key)
    mask = meteosat.CloudMask(flenkommun.BBOX, tmp_path)
    try:
        mask.update(NOW)
    except monitoring_sources.MissingKey as error:
        assert "EUMETSAT" in str(error)
    else:
        raise AssertionError("no key, no Meteosat")
    key.write_text("key,secret")

    def download(product, token, target):
        target.write_bytes(b"zip")
        return target

    monkeypatch.setattr(fetch_meteosat_cth, "download", download)
    # Four pixels in the area: two cloudy, one clear, one without data.
    monkeypatch.setattr(fetch_meteosat_clm, "read_grib", lambda data, positions: (2, numpy.array([2, 2, 1, 3]), [0] * 4, [0] * 4))
    monkeypatch.setattr(fetch_meteosat_clm, "area_index", lambda lats, lons, size, bbox: numpy.array([0, 1, 2, 3]))
    now = datetime(2026, 11, 4, 9, 30, tzinfo=timezone.utc)
    meta = mask.update(now)
    assert meta["cloud_pct"] == 67 and meta["satellite"] == "Meteosat-10" and meta["time_utc"] == "2026-11-04T08:15:00Z"
    assert "EUMETSAT" in meta["attribution"] and (tmp_path / "meteosat-clm" / "index.npy").is_file()
    assert mask.update(now + timedelta(minutes=5)) == meta and len(searched) == 1
    products.insert(0, "MSG3-SEVI-MSGCLMK-0100-0100-20261104083000.000000000Z-NA")
    later = mask.update(now + timedelta(minutes=15))
    assert [item["time_utc"] for item in later["series"]] == ["2026-11-04T08:15:00Z", "2026-11-04T08:30:00Z"]
    assert meteosat.CloudMask(flenkommun.BBOX, tmp_path).meta["series"] == later["series"]
    assert not list((tmp_path / "meteosat-clm").glob("**/*.zip"))
