#!/usr/bin/env python3
"""Record the fire-map playback to a video file.

Starts the backend on a free local port, opens the GUI in a headless Chrome with
the kiosk options (`?at=`, `?autoplay=1`, `?speed=`, `?horizon=`), records until
the playback ends or `--duration` seconds have passed, and saves a WebM video.
The WebM starts with the few seconds in which the page loads. With ffmpeg on the
PATH an MP4 is also written that starts when the playback starts.

Needs Playwright in the repository's `.venv` (see tools/requirements-record.txt)
and Google Chrome installed; the OSM map tiles are loaded from the internet.

    .venv/bin/python -m tools.record_demo --start 2014-08-04T06:00:00Z --speed 10800 --out ~/Videos/brandkarta.webm
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import threading
import time
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode


def size(text: str) -> tuple[int, int]:
    width, height = (int(part) for part in text.lower().split("x"))
    return width, height


def kiosk_url(base: str, start: str | None, speed: int, horizon: str | None) -> str:
    options: dict[str, str] = {"autoplay": "1", "speed": str(speed)}
    if start:
        options["at"] = start
    if horizon:
        options["horizon"] = horizon
    return f"{base}/?{urlencode(options)}"


def start_backend() -> tuple[ThreadingHTTPServer, str]:
    from app.backend import server

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def ffmpeg_command(ffmpeg: str, webm: Path, mp4: Path, skip_seconds: float) -> list[str]:
    return [
        ffmpeg, "-y", "-loglevel", "error", "-ss", f"{max(0.0, skip_seconds):.2f}", "-i", str(webm),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", str(mp4),
    ]


def to_mp4(webm: Path, skip_seconds: float) -> Path | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    mp4 = webm.with_suffix(".mp4")
    subprocess.run(ffmpeg_command(ffmpeg, webm, mp4, skip_seconds), check=True)
    return mp4


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--start", help="UTC start time of the playback, for example 2014-08-04T06:00:00Z (default: the beginning)")
    parser.add_argument("--speed", type=int, default=3600, help="simulated seconds per second (3600 = 1 hour/s)")
    parser.add_argument("--horizon", choices=["3", "6", "12", "24"], help="forecast horizon in hours")
    parser.add_argument("--duration", type=float, help="stop after this many seconds of recording (default: until the playback ends)")
    parser.add_argument("--size", type=size, default=(1920, 1080), help="video size, for example 1920x1080")
    parser.add_argument("--settle", type=float, default=4.0, help="seconds to wait for map tiles before the playback is recorded")
    parser.add_argument("--out", type=Path, default=Path(f"brandkarta-{datetime.now():%Y%m%d-%H%M}.webm"))
    args = parser.parse_args(argv)
    if args.start:
        datetime.fromisoformat(args.start.replace("Z", "+00:00"))  # fail early on a bad time

    from playwright.sync_api import sync_playwright

    out = args.out.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    httpd, base = start_backend()
    width, height = args.size
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(
                viewport={"width": width, "height": height},
                record_video_dir=str(out.parent / ".recording"),
                record_video_size={"width": width, "height": height},
            )
            page = context.new_page()
            page_opened = time.monotonic()
            # Load the GUI paused first so tiles and layers are in place when recording matters.
            page.goto(kiosk_url(base, args.start, args.speed, args.horizon).replace("autoplay=1&", ""), wait_until="networkidle")
            page.wait_for_selector("body[data-ready='true']", timeout=60_000)
            time.sleep(args.settle)
            page.click("#play")
            started = time.monotonic()
            loading_seconds = started - page_opened
            while True:
                if page.evaluate("document.body.dataset.playback") == "finished":
                    time.sleep(2.0)  # keep the final state on screen briefly
                    break
                if args.duration is not None and time.monotonic() - started >= args.duration:
                    break
                time.sleep(0.5)
            video = page.video
            context.close()
            browser.close()
            recorded = Path(video.path())
        recorded.replace(out)
        shutil.rmtree(out.parent / ".recording", ignore_errors=True)
    finally:
        httpd.shutdown()
        httpd.server_close()
    print(f"Video: {out} (the first {loading_seconds:.0f} s show the page loading)")
    mp4 = to_mp4(out, loading_seconds)
    print(f"MP4: {mp4}" if mp4 else "MP4: not written (ffmpeg is not installed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
