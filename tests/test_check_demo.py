"""Tests for the demo check (tools/check_demo.py) that need no browser: the steps
follow the one-pager's order, the report says what failed, and the backend is
started on a free local port."""

from __future__ import annotations

import socket

from tools import check_demo


def test_the_steps_follow_the_demo_and_end_with_reset() -> None:
    names = [name for name, _ in check_demo.STEPS]
    assert [name.split(" ", 1)[0] for name in names] == [str(number) for number in range(1, 11)]
    assert "SPACE VIEW" in names[1] and "SATELLITE DETECTION" in names[2] and "IOT" in names[4]
    assert "SATCOM" in names[7] and "GOD VIEW" in names[8]
    assert names[-1] == "10 RESET inom 5 s" and check_demo.RESET_LIMIT_S == 5.0


def test_the_report_passes_only_when_every_step_does_and_there_are_no_errors() -> None:
    report = check_demo.Report("http://127.0.0.1:8765", True, "2026-10-05T12:00:00Z")
    assert not report.passed  # no steps yet
    report.steps.append(check_demo.Step("1 Öppning: jorden till branden", "GODKÄND", "kameraresan klar", 12.3))
    report.frames_per_second = 58.6
    assert report.passed
    text = report.text()
    assert "GODKÄND   1 Öppning: jorden till branden (12.3 s): kameraresan klar" in text
    assert "synligt fönster" in text and "Bilder per sekund i 3D under uppspelning: 58.6" in text
    assert text.endswith("RESULTAT: GODKÄND")
    report.javascript_errors.append("huvudskärm: TypeError: x is undefined")
    assert not report.passed and report.text().endswith("RESULTAT: UNDERKÄND")
    report.javascript_errors.clear()
    report.steps.append(check_demo.Step("10 RESET inom 5 s", "UNDERKÄND", "AssertionError: 5.40 s, kravet är 5 s", 6.0))
    assert not report.passed and "UNDERKÄND 10 RESET inom 5 s" in report.text()


def test_the_backend_is_started_on_a_free_local_port() -> None:
    port = check_demo.free_port()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))  # still free
    command = check_demo.backend_command(port)
    assert command[1:] == ["-m", "app.backend.server", "--port", str(port)]
    assert command[0].endswith(".venv/bin/python")


def test_after_a_failure_the_rest_is_not_run() -> None:
    report = check_demo.Report("http://x", False, "2026-10-05T12:00:00Z")
    report.steps.append(check_demo.Step("1 Öppning: jorden till branden", "UNDERKÄND", "RuntimeError: sidan startade inte", 60.0))
    report.skip_rest([name for name, _ in check_demo.STEPS[1:]])
    assert [step.verdict for step in report.steps] == ["UNDERKÄND"] + ["EJ KÖRD"] * 9
    assert not report.passed and "headless" in report.text()


def test_the_report_names_the_computer_and_graphics_and_warns_on_a_low_frame_rate() -> None:
    report = check_demo.Report("http://x", True, "2026-10-05T12:00:00Z", computer="massdator", webgl_renderer="ANGLE (NVIDIA)",
                               canvas_px="1260x856")
    report.steps.append(check_demo.Step("1 Öppning: jorden till branden", "GODKÄND", "ok", 1.0))
    report.frames_per_second = 12.5
    text = report.text()
    assert "på massdator" in text and "Grafik (WebGL i Chrome): ANGLE (NVIDIA); 3D-ytan 1260x856 pixlar" in text
    assert "VARNING: under 20 bilder per sekund" in text
    assert report.passed  # a low frame rate warns but does not fail
    report.frames_per_second = 45.0
    assert "VARNING" not in report.text()


def test_the_tiles_file_is_read_from_the_tiles_service() -> None:
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Tiles(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            body = json.dumps([{"basename": "sundsvall.mbtiles", "id": "sundsvall"}]).encode() if self.path == "/data.json" else b""
            self.send_response(200 if body else 404)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Tiles)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        assert check_demo.served_tiles_file(f"http://127.0.0.1:{port}/styles/basic-preview/256/{{z}}/{{x}}/{{y}}.png") == "sundsvall.mbtiles"
    finally:
        server.shutdown()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed = probe.getsockname()[1]
    assert check_demo.served_tiles_file(f"http://127.0.0.1:{closed}/{{z}}/{{x}}/{{y}}.png") is None


def test_in_a_visible_window_the_screens_go_where_open_screens_puts_them() -> None:
    from tools import open_screens

    window = open_screens.Window("main", "/3d.html", 1190, 192, 2250, 1408)
    assert check_demo.bounds(window) == {"left": 1190, "top": 192, "width": 2250, "height": 1408}
