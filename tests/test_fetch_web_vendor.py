"""Tests for the 3D map's library fetcher and page wiring (no network needed)."""

from __future__ import annotations

import io
import re
import tarfile
from pathlib import Path

import pytest

from tools import fetch_web_vendor

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"


def tarball(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def test_integrity_matches_the_npm_format() -> None:
    # Known value: `printf abc | openssl dgst -sha512 -binary | base64`.
    assert fetch_web_vendor.integrity_of(b"abc") == (
        "sha512-3a81oZNherrMQXNJriBBMRLm+k6JqX6iCp7u5ktV05ohkpkqJ0/BqDa6PCOj/uu9RU1EI2Q86A4qmslPpUyknw=="
    )


def test_unpack_keeps_only_the_build_and_the_licence(tmp_path: Path) -> None:
    data = tarball({
        "package/Build/Cesium/Cesium.js": b"js",
        "package/Build/Cesium/Assets/a.json": b"{}",
        "package/Source/Core.js": b"source",
        "package/LICENSE.md": b"licence",
    })
    target = tmp_path / "cesium"
    (target / "old.js").parent.mkdir(parents=True)
    (target / "old.js").write_text("stale")

    count = fetch_web_vendor.unpack(data, "package/Build/Cesium/", "package/LICENSE.md", target)

    assert count == 3
    assert sorted(str(path.relative_to(target)) for path in target.rglob("*") if path.is_file()) == [
        "Assets/a.json", "Cesium.js", "LICENSE.md",
    ]


def test_unpack_refuses_paths_out_of_the_target(tmp_path: Path) -> None:
    data = tarball({"package/dist/../../evil.js": b"x"})

    with pytest.raises(ValueError):
        fetch_web_vendor.unpack(data, "package/dist/", "package/LICENSE", tmp_path / "out")


def test_a_wrong_checksum_stops_before_unpacking(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(fetch_web_vendor, "VENDOR", tmp_path)
    monkeypatch.setattr(fetch_web_vendor, "download", lambda name, version: b"tampered")

    with pytest.raises(SystemExit, match="does not match"):
        fetch_web_vendor.main([])
    assert not any(tmp_path.iterdir())


def test_3d_page_loads_the_pinned_cesium_and_both_pages_share_the_panel() -> None:
    page = (FRONTEND / "3d.html").read_text(encoding="utf-8")
    version = fetch_web_vendor.PACKAGES["cesium"]["version"]
    scripts = re.findall(r'<script src="([^"]+)"', page)

    assert f"/vendor/cesium-{version}/Cesium.js" in scripts
    assert f'CESIUM_BASE_URL = "/vendor/cesium-{version}/"' in page
    assert scripts.index("/panel.js") < scripts.index("/map3d.js") < scripts.index("/app3d.js")
    two_d = re.findall(r'<script src="([^"]+)"', (FRONTEND / "index.html").read_text(encoding="utf-8"))
    assert two_d.index("/panel.js") < two_d.index("/map2d.js") < two_d.index("/app.js")
