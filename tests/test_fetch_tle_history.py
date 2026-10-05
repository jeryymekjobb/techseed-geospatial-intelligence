"""Tests for the Space-Track fetcher (tools/fetch_tle_history.py) against a fake
Space-Track on localhost: the login, the session cookie, the one query, the
output files, and that the login never shows up in output or errors."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from tools import fetch_tle_history as tle

IDENTITY, PASSWORD = "user@example.com", "s3cret-pw"
LINE1 = "1 37849U 11061A   14212.50000000  .00000000  00000-0  00000-0 0  9990"
LINE2 = "2 37849  98.7000 150.0000 0001000  90.0000 270.0000 14.19500000 14000"
RECORDS = [
    {"NORAD_CAT_ID": "37849", "OBJECT_NAME": "SUOMI NPP", "EPOCH": "2014-07-31 12:00:00", "TLE_LINE1": LINE1, "TLE_LINE2": LINE2},
    {"NORAD_CAT_ID": "37849", "OBJECT_NAME": "SUOMI NPP", "EPOCH": "2014-07-30 12:00:00", "TLE_LINE1": LINE1, "TLE_LINE2": LINE2},
    {"NORAD_CAT_ID": "27424", "OBJECT_NAME": "AQUA", "EPOCH": "2014-08-01 00:00:00", "TLE_LINE1": LINE1, "TLE_LINE2": "too short"},
    {"NORAD_CAT_ID": "99999", "OBJECT_NAME": "OTHER", "EPOCH": "2014-08-01 00:00:00", "TLE_LINE1": LINE1, "TLE_LINE2": LINE2},
]


class FakeSpaceTrack(BaseHTTPRequestHandler):
    calls: list[str] = []
    reply: bytes = json.dumps(RECORDS).encode()

    def log_message(self, *args: object) -> None:
        pass

    def send(self, body: bytes, status: int = 200, cookie: str | None = None) -> None:
        self.send_response(status)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        form = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
        self.calls.append("login")
        if form == {"identity": [IDENTITY], "password": [PASSWORD]}:
            self.send(b'""', cookie="chocolatechip=abc; Path=/")
        else:
            self.send(b'{"Login":"Failed"}')

    def do_GET(self) -> None:  # noqa: N802
        self.calls.append(self.path)
        if self.path == "/ajaxauth/logout":
            self.send(b'"Successfully logged out"')
        elif "chocolatechip=abc" not in (self.headers.get("Cookie") or ""):
            self.send(b'{"error":"You must be logged in"}', 401)
        else:
            self.send(self.reply)


@pytest.fixture()
def space_track():
    FakeSpaceTrack.calls = []
    FakeSpaceTrack.reply = json.dumps(RECORDS).encode()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeSpaceTrack)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def credentials_file(tmp_path: Path, text: str = f"identity={IDENTITY}\npassword={PASSWORD}\n") -> Path:
    path = tmp_path / "spacetrackrc"
    path.write_text(text, encoding="utf-8")
    return path


def test_credentials_are_read_from_key_value_lines(tmp_path: Path) -> None:
    path = credentials_file(tmp_path, f"# Space-Track\n\nidentity = {IDENTITY}\npassword={PASSWORD}\n")
    assert tle.read_credentials(path) == {"identity": IDENTITY, "password": PASSWORD}
    with pytest.raises(tle.FetchError, match="lacks password"):
        tle.read_credentials(credentials_file(tmp_path, f"identity={IDENTITY}\n"))
    with pytest.raises(tle.FetchError, match="cannot read"):
        tle.read_credentials(tmp_path / "missing")


def test_one_query_for_every_satellite_and_the_period() -> None:
    path = tle.query_path("2014-07-27", "2014-08-17")
    assert path.startswith("/basicspacedata/query/class/gp_history/NORAD_CAT_ID/25994,27424,37849,39084,25544/")
    assert "/EPOCH/2014-07-27--2014-08-17/" in path and path.endswith("/format/json")


def test_fetch_logs_in_queries_once_and_logs_out(space_track: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "tle"
    assert tle.main(["--credentials", str(credentials_file(tmp_path)), "--base-url", space_track, "--out", str(out)]) == 0

    assert FakeSpaceTrack.calls[0] == "login" and FakeSpaceTrack.calls[-1] == "/ajaxauth/logout"
    assert [call for call in FakeSpaceTrack.calls if call.startswith("/basicspacedata")] == [tle.query_path(tle.DEFAULT_START, tle.DEFAULT_END)]
    satellites = json.loads((out / "tle-2014.json").read_text(encoding="utf-8"))["satellites"]
    assert set(satellites) == set(tle.SATELLITES)
    npp = satellites["37849"]
    assert npp["name"] == "Suomi NPP"
    assert [item["epoch_utc"] for item in npp["elements"]] == ["2014-07-30T12:00:00Z", "2014-07-31T12:00:00Z"]
    assert npp["elements"][0] == {"epoch_utc": "2014-07-30T12:00:00Z", "line1": LINE1, "line2": LINE2}
    assert satellites["27424"]["elements"] == []  # the malformed element set is dropped
    source = json.loads((out / "SOURCE.json").read_text(encoding="utf-8"))
    assert source["element_sets"]["Suomi NPP"] == 2 and source["terms"] == tle.TERMS_URL
    output = capsys.readouterr().out
    assert "Suomi NPP: 2 element sets" in output and "warning: no element sets for Terra, Aqua, Landsat 8, ISS" in output
    for written in [output, (out / "tle-2014.json").read_text(), (out / "SOURCE.json").read_text()]:
        assert PASSWORD not in written and IDENTITY not in written


def test_a_refused_login_stops_without_showing_the_login(space_track: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = credentials_file(tmp_path, f"identity={IDENTITY}\npassword=wrong-{PASSWORD}\n")
    with pytest.raises(SystemExit) as stopped:
        tle.main(["--credentials", str(path), "--base-url", space_track, "--out", str(tmp_path / "tle")])
    assert stopped.value.code == 1
    error = capsys.readouterr().err
    assert "refused the login" in error and PASSWORD not in error and IDENTITY not in error
    assert not (tmp_path / "tle").exists()
    assert not any(call.startswith("/basicspacedata") for call in FakeSpaceTrack.calls)


def test_a_bad_answer_is_an_error(space_track: str, tmp_path: Path) -> None:
    FakeSpaceTrack.reply = b"<html>maintenance</html>"
    with pytest.raises(tle.FetchError, match="JSON"):
        tle.fetch(tle.read_credentials(credentials_file(tmp_path)), "2014-07-27", "2014-08-17", space_track)
    assert FakeSpaceTrack.calls[-1] == "/ajaxauth/logout"  # logged out even after a bad answer


def test_an_unreachable_server_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(tle.FetchError, match="could not be reached") as raised:
        tle.fetch(tle.read_credentials(credentials_file(tmp_path)), "2014-07-27", "2014-08-17", "http://127.0.0.1:9")
    assert PASSWORD not in str(raised.value)
