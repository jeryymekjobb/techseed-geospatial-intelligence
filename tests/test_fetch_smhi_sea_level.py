"""Tests for SMHI's sea level (tools/fetch_smhi_sea_level.py). SYNTHETIC values in SMHI's CSV layout."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.error import HTTPError

import pytest

from tools import fetch_smhi_sea_level as fetch

STATION_JSON = json.dumps({"key": "30488", "period": [{"key": "corrected-archive"}, {"key": "latest-months"}]})
ARCHIVE_CSV = """﻿Stationsnamn;Stationsid;Stationens latitud;Stationens longitud
Skanör;30488;55.4168;12.8296

Parameternamn;Enhet
Havsvattenstånd;cm

Datum Tid (UTC);Havsvattenstånd;Kvalitet;Mätdjup (m);;Tidsutsnitt
2011-12-31 22:00:00;140.0;G;0;;Tidsperiod (fr.o.m.) = 1992-02-17 08:00:00 (UTC)
2011-12-31 23:00:00;20.0;G;0;;Tidsperiod (t.o.m.) = 2023-10-21 01:00:00 (UTC)
2023-10-21 00:00:00;149.5;G;0;;
2023-10-21 01:00:00;145.0;O;0;;Höjdsystem: RH2000
"""
LATEST_CSV = """Stationsnamn;Stationsid;Stationens latitud;Stationens longitud
Skanör;30488;55.4168;12.8296

Parameternamn;Enhet
Havsvattenstånd;cm

Datum Tid (UTC);Havsvattenstånd;Kvalitet;Mätdjup (m);;Tidsutsnitt
2023-10-21 01:00:00;145.5;G;0;;
2023-10-21 02:00:00;;O;0;;
2023-10-21 03:00:00;140.1;O;0;;
"""


def fake_smhi(responses: dict[str, str]):
    def get(url: str) -> str:
        if url not in responses:
            raise HTTPError(url, 404, "Not Found", None, None)
        return responses[url]
    return get


def test_the_station_s_details_and_height_system_are_read() -> None:
    parsed = fetch.parse(ARCHIVE_CSV)
    assert (parsed["name"], parsed["latitude"], parsed["longitude"], parsed["height_system"]) == ("Skanör", 55.4168, 12.8296, "RH2000")
    assert [(moment.isoformat(), value, quality) for moment, value, quality in parsed["rows"]][2] == \
        ("2023-10-21T00:00:00+00:00", 149.5, "G")


def test_only_the_periods_smhi_offers_are_read_older_first() -> None:
    assert fetch.periods(STATION_JSON) == ["corrected-archive", "latest-months"]
    assert fetch.periods(json.dumps({"period": [{"key": "corrected-archive"}, {"key": "latest-hour"}]})) == ["corrected-archive"]


def test_the_newer_period_s_value_replaces_the_archive_s_for_the_same_hour() -> None:
    get = fake_smhi({fetch.station_url("30488"): STATION_JSON,
                     fetch.data_url("30488", "corrected-archive"): ARCHIVE_CSV,
                     fetch.data_url("30488", "latest-months"): LATEST_CSV})
    fetched = fetch.fetch_station("30488", get)
    rows = [(moment.strftime("%Y-%m-%d %H"), value, quality) for moment, value, quality in fetched["rows"]]
    assert rows[-3:] == [("2023-10-21 00", 149.5, "G"), ("2023-10-21 01", 145.5, "G"), ("2023-10-21 03", 140.1, "O")]
    assert fetched["periods"] == ["corrected-archive", "latest-months"] and fetched["height_system"] == "RH2000"


def test_a_listed_but_empty_period_is_skipped() -> None:
    get = fake_smhi({fetch.station_url("30488"): STATION_JSON, fetch.data_url("30488", "corrected-archive"): ARCHIVE_CSV})
    assert len(fetch.fetch_station("30488", get)["rows"]) == 4


def test_the_period_is_kept_with_the_highest_value_before_it() -> None:
    rows = fetch.parse(ARCHIVE_CSV)["rows"]
    result = fetch.series(rows, date(2012, 1, 1), date(2026, 10, 22))
    assert [value for _, value, _ in result["rows"]] == [149.5, 145.0]
    assert result["earlier_max"] == {"value": 140.0, "time_utc": "2011-12-31T22:00:00Z"} and result["since"] == "2011-12-31"


def test_the_tool_writes_the_csv_and_its_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch, "download", fake_smhi({fetch.station_url("30488"): STATION_JSON,
                                                      fetch.data_url("30488", "corrected-archive"): ARCHIVE_CSV,
                                                      fetch.data_url("30488", "latest-months"): LATEST_CSV}))
    assert fetch.main(["--station", "30488", "--start", "2012-01-01", "--end", "2026-10-22", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "sea-level-30488.csv").read_text(encoding="utf-8").splitlines() == [
        "time_utc,value,quality", "2023-10-21T00:00:00Z,149.5,G", "2023-10-21T01:00:00Z,145.5,G", "2023-10-21T03:00:00Z,140.1,O"]
    source = json.loads((tmp_path / "SOURCE.json").read_text(encoding="utf-8"))
    assert "CC BY 4.0" in source["source"] and source["period"] == {"start": "2012-01-01", "end": "2026-10-22"}
    [station] = source["stations"]
    assert (station["name"], station["height_system"], station["values"], station["quality_counts"]) == ("Skanör", "RH2000", 3, {"G": 2, "O": 1})
    assert station["earlier_max"] == {"value": 140.0, "time_utc": "2011-12-31T22:00:00Z"}


def test_without_stations_the_tool_says_so(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as stopped:
        fetch.main(["--out", str(tmp_path)])
    assert stopped.value.code == 1
