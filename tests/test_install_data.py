"""Local data installation with synthetic payloads only; no real data or services."""

import hashlib
import json
import stat
from zipfile import ZipFile, ZipInfo

import pytest

from tools import install_data


def package(tmp_path, payload=None, change=None, extra=None):
    payload = {"data/example/input.json": b"synthetic fixture"} if payload is None else payload
    manifest = {"format_version": 1, "package_version": "synthetic-1", "code_revision": "test-only",
                "scenarios": ["vastmanland2014"],
                "files": [{"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                          for name, data in payload.items()]}
    if change:
        change(manifest)
    target = tmp_path / "package.zip"
    with ZipFile(target, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, data in payload.items():
            archive.writestr(name, data)
        if extra:
            archive.writestr(*extra)
    return target


def test_dry_run_install_and_repeat_are_safe(tmp_path):
    source = package(tmp_path)
    root = tmp_path / "clone"
    root.mkdir()
    assert install_data.install(source, root, True)[1] == 1
    assert list(root.iterdir()) == []
    assert install_data.install(source, root)[1] == 1
    installed = root / "data/example/input.json"
    stamp = installed.stat().st_mtime_ns
    assert installed.read_bytes() == b"synthetic fixture"
    assert install_data.install(source, root)[1] == 0
    assert installed.stat().st_mtime_ns == stamp


def test_conflict_prevents_all_writes(tmp_path):
    root = tmp_path / "clone"
    (root / "data").mkdir(parents=True)
    (root / "data/existing").write_bytes(b"local settings")
    source = package(tmp_path, {"data/new": b"synthetic", "data/existing": b"different"})
    with pytest.raises(ValueError, match="refusing to overwrite"):
        install_data.install(source, root)
    assert not (root / "data/new").exists()
    assert (root / "data/existing").read_bytes() == b"local settings"


@pytest.mark.parametrize("path", ["../escape", "/data/file", "data/../escape", "data//file",
    "data\\escape", "C:/data/file", "data/a:stream", "data/NUL.txt", "data/CON", "data/file.",
    "data/file ", "data/.env", "data/display-profiles.json", "data/node-sim.log", "data/credentials",
    "app/backend/server.py", "app/frontend/vendor/unknown/file.js", "data/control\x00"])
def test_unsafe_or_local_only_paths_are_rejected(path):
    with pytest.raises(ValueError):
        install_data.safe_path(path)


@pytest.mark.parametrize("change", [
    lambda m: m.update(format_version=99),
    lambda m: m.update(package_version=""),
    lambda m: m.update(scenarios=["unknown"]),
    lambda m: m["files"][0].update(size=999),
    lambda m: m["files"][0].update(size=True),
    lambda m: m["files"][0].update(sha256="invalid"),
    lambda m: m["files"].append(m["files"][0].copy()),
])
def test_invalid_manifest_is_rejected_without_writes(tmp_path, change):
    root = tmp_path / "clone"
    root.mkdir()
    source = package(tmp_path, change=change)
    with pytest.raises(ValueError):
        install_data.install(source, root)
    assert list(root.iterdir()) == []


def test_checksum_failure_prevents_all_writes_even_in_dry_run(tmp_path):
    root = tmp_path / "clone"
    root.mkdir()
    source = package(tmp_path, change=lambda m: m["files"][0].update(sha256="0" * 64))
    for dry_run in (False, True):
        with pytest.raises(ValueError, match="checksum mismatch"):
            install_data.install(source, root, dry_run)
    assert list(root.iterdir()) == []


def test_unlisted_file_and_archive_links_are_rejected(tmp_path):
    root = tmp_path / "clone"
    root.mkdir()
    source = package(tmp_path, extra=("data/extra", b"synthetic"))
    with pytest.raises(ValueError, match="unlisted"):
        install_data.install(source, root)
    link = ZipInfo("data/link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    source = package(tmp_path, extra=(link, b"outside"))
    with pytest.raises(ValueError, match="regular file"):
        install_data.install(source, root)


def test_destination_symlink_is_never_followed(tmp_path):
    root = tmp_path / "clone"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "data").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("creating symlinks is not permitted on this machine")
    with pytest.raises(ValueError, match="link"):
        install_data.install(package(tmp_path), root)
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("payload", [
    {"data/a": b"synthetic", "data/a/b": b"synthetic"},
    {"data/A/one": b"synthetic", "data/a/two": b"synthetic"},
    {"data/A": b"synthetic", "data/a": b"synthetic"},
])
def test_colliding_paths_are_rejected(tmp_path, payload):
    with ZipFile(package(tmp_path, payload)) as archive:
        with pytest.raises(ValueError):
            install_data.inspect(archive)


def test_cli_reports_errors_and_dry_run(tmp_path, capsys):
    assert install_data.main([str(tmp_path / "missing.zip"), "--root", str(tmp_path)]) == 1
    source = package(tmp_path)
    assert install_data.main([str(source), "--root", str(tmp_path), "--dry-run"]) == 0
    assert "Would install 1 files" in capsys.readouterr().out
    assert not (tmp_path / "data").exists()
