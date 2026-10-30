"""Tests for tools/fetch_smhi_weather.py with SYNTHETIC SMHI archive text (not observations)."""

from __future__ import annotations

from datetime import date

from tools import fetch_smhi_weather as smhi


def archive(parameter_name: str, unit: str, rows: list[str]) -> str:
    return "\n".join([
        "﻿Stationsnamn;Stationsnummer;Stationsnät;Mäthöjd (meter över marken)",
        "Test A;99999;SMHIs stationsnät;10.0",
        "",
        "Parameternamn;Beskrivning;Enhet",
        f"{parameter_name};test;{unit}",
        "",
        "Tidsperiod (fr.o.m);Tidsperiod (t.o.m);Höjd (meter över havet);Latitud (decimalgrader);Longitud (decimalgrader)",
        "2000-01-01 00:00:00;2026-01-01 00:00:00;50.0;59.9;16.6",
        "",
        "Datum;Tid (UTC);Värde;Kvalitet;;Tidsutsnitt:",
        *rows,
    ])


def test_archive_metadata_and_rows_are_parsed() -> None:
    parsed = smhi.parse_archive(archive("Vindhastighet", "meter per sekund", [
        "2014-08-04;12:00:00;6.8;G;;Kvalitetskontrollerade historiska data",
        "2014-08-04;13:00:00;5.1;Y",
    ]))

    assert (parsed["station_name"], parsed["station_id"], parsed["unit"]) == ("Test A", "99999", "meter per sekund")
    assert (parsed["latitude"], parsed["longitude"], parsed["altitude_m"]) == (59.9, 16.6, 50.0)
    assert parsed["rows"] == [("2014-08-04", "12:00", "6.8", "G"), ("2014-08-04", "13:00", "5.1", "Y")]


def test_parameters_merge_per_hour_within_the_period() -> None:
    archives = {
        1: smhi.parse_archive(archive("Lufttemperatur", "celsius", [
            "2014-07-28;23:00:00;15.0;G", "2014-08-04;12:00:00;34.4;G",
        ])),
        4: smhi.parse_archive(archive("Vindhastighet", "meter per sekund", ["2014-08-04;12:00:00;1.6;G"])),
    }

    rows = smhi.merge(archives, date(2014, 7, 29), date(2014, 8, 14))

    assert len(rows) == 1
    assert rows[0]["time_utc"] == "2014-08-04T12:00:00Z"
    assert (rows[0]["temp_c"], rows[0]["temp_c_quality"], rows[0]["wind_speed_ms"]) == ("34.4", "G", "1.6")
    assert rows[0]["precip_mm"] == ""  # parameter not supplied
    assert smhi.slug_for("Sala A", "96560") == "sala-a-96560"
    assert smhi.slug_for("Kloten A", "95540") == "kloten-a-95540"


def test_the_period_and_the_parameters_can_be_chosen() -> None:
    assert smhi.archive_url(7, "2222813", "latest-months") == (
        f"{smhi.API}/parameter/7/station/2222813/period/latest-months/data.csv")
    assert smhi.archive_url(7, "2222813").endswith("/period/corrected-archive/data.csv")
    # A precipitation gauge: only parameter 7, the other columns stay empty.
    archives = {7: smhi.parse_archive(archive("Nederbördsmängd", "millimeter", ["2026-08-16;08:00:00;10.6;Y"]))}
    rows = smhi.merge(archives, date(2026, 8, 14), date(2026, 8, 22))
    assert (rows[0]["precip_mm"], rows[0]["precip_mm_quality"], rows[0]["temp_c"]) == ("10.6", "Y", "")


def test_both_periods_are_read_and_the_latest_months_win_an_hour_they_share(tmp_path, monkeypatch) -> None:
    texts = {
        smhi.archive_url(7, "99999", "corrected-archive"): archive("Nederbördsmängd", "millimeter",
                                                                    ["2012-01-01;00:00:00;0.2;G", "2026-07-01;00:00:00;1.0;G"]),
        smhi.archive_url(7, "99999", "latest-months"): archive("Nederbördsmängd", "millimeter",
                                                                ["2026-07-01;00:00:00;1.4;Y", "2026-10-20;12:00:00;3.0;Y"]),
    }
    monkeypatch.setattr(smhi, "download", lambda url: texts[url])
    assert smhi.main(["99999", "--start", "2012-01-01", "--end", "2026-10-21", "--out", str(tmp_path),
                      "--period", "both", "--parameters", "7"]) == 0
    import csv
    with (tmp_path / "test-a-99999.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [[row["time_utc"], row["precip_mm"], row["precip_mm_quality"]] for row in rows] == [
        ["2012-01-01T00:00:00Z", "0.2", "G"], ["2026-07-01T00:00:00Z", "1.4", "Y"], ["2026-10-20T12:00:00Z", "3.0", "Y"]]


def test_local_time_rows_move_to_utc_by_the_season() -> None:
    moved = smhi.local_rows_to_utc([
        ("2026-08-16", "10:00", "7.9", "Y"),   # summer time: UTC+2
        ("2020-12-29", "00:30", "1.0", "Y"),   # normal time: UTC+1, into the day before
        ("2023-10-29", "02:00", "0.2", "Y"),   # October's repeated hour, first summer time ...
        ("2023-10-29", "02:00", "0.4", "Y"),   # ... then normal time
        ("2023-10-29", "03:00", "0.6", "Y"),
    ])
    assert moved == [
        ("2026-08-16", "08:00", "7.9", "Y"), ("2020-12-28", "23:30", "1.0", "Y"),
        ("2023-10-29", "00:00", "0.2", "Y"), ("2023-10-29", "01:00", "0.4", "Y"), ("2023-10-29", "02:00", "0.6", "Y"),
    ]
    assert smhi.summer_time_utc(2026)[0].isoformat() == "2026-03-29T01:00:00+00:00"
    assert {"2222813", "2222814", "2222818", "2222811", "2222812", "2222819"} <= smhi.LOCAL_TIME_STATIONS
    assert "127130" not in smhi.LOCAL_TIME_STATIONS  # SMHI's own Brämön A keeps UTC


def test_skanes_water_utility_gauges_move_forward_by_the_season() -> None:
    moved = smhi.back_rows_to_utc([("2024-01-27", "16:00", "2.0", "Y"), ("2024-07-01", "23:00", "1.0", "Y")])
    assert moved == [("2024-01-27", "17:00", "2.0", "Y"), ("2024-07-02", "01:00", "1.0", "Y")]
    assert {"22128144", "22128520", "22128522", "22128523", "22128524"} == smhi.UTC_BACK_BY_LOCAL_STATIONS
    assert "53530" not in smhi.UTC_BACK_BY_LOCAL_STATIONS  # SMHI's own Hörby A keeps UTC
    assert not smhi.UTC_BACK_BY_LOCAL_STATIONS & smhi.LOCAL_TIME_STATIONS
