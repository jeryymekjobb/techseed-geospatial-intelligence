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
