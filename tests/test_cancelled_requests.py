"""A request the browser cancels while the backend is answering (map tiles during a
camera flight) is dropped quietly instead of filling the log with a traceback."""

from __future__ import annotations

import socket
import struct
import sys
import threading
import time
from http.server import ThreadingHTTPServer

import pytest

from app.backend import lantmateriet, offline_tiles, server


class RecordingServer(ThreadingHTTPServer):
    errors: list[str] = []

    def handle_error(self, request, client_address) -> None:  # noqa: ANN001 - signature of the base class
        self.errors.append(repr(sys.exc_info()[1]))


@pytest.fixture()
def address(monkeypatch: pytest.MonkeyPatch):
    # A tile far larger than the socket buffers, so the write is still going when the client leaves.
    monkeypatch.setattr(offline_tiles, "tile", lambda z, x, y: (b"\0" * (32 << 20), "image/png"))
    RecordingServer.errors = []
    handler = type("TestHandler", (server.Handler,), {"settings": lantmateriet.Settings(None, None, None, None)})
    httpd = RecordingServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd.server_address
    httpd.shutdown()
    httpd.server_close()


def test_a_cancelled_tile_is_not_reported_as_an_error(address) -> None:
    for _ in range(3):
        client = socket.create_connection(address)
        client.sendall(b"GET /tiles/1/1/1.png HTTP/1.1\r\nHost: test\r\n\r\n")
        client.recv(1024)  # the answer has started
        client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))  # reset on close
        client.close()
    time.sleep(1.0)
    assert RecordingServer.errors == []
