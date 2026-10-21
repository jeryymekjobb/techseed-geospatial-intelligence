"""Packaging uses explicitly selected synthetic files, never live demo data."""

import json
from zipfile import ZipFile

import pytest

from tools import install_data, package_data


def fixture(tmp_path):
    root = tmp_path / "source"
    (root / "data/example").mkdir(parents=True)
    (root / "data/example/a.json").write_bytes(b"synthetic A")
    (root / "data/example/b.json").write_bytes(b"synthetic B")
    selection = tmp_path / "selection.json"
    selected = {"package_version": "synthetic-1", "code_revision": "test-only",
                "scenarios": ["vastmanland2014"], "files": ["data/example/a.json"]}
    selection.write_text(json.dumps(selected), encoding="utf-8")
    return root, selection, selected, tmp_path / "package.zip"


def test_preview_writes_nothing_and_build_roundtrips(tmp_path):
    root, selection, selected, output = fixture(tmp_path)
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    preview = package_data.build(selection, output, root, True)
    assert sorted(str(p) for p in tmp_path.rglob("*")) == before
    assert preview["files"][0]["path"] == selected["files"][0]
    assert package_data.build(selection, output, root) == preview
    with ZipFile(output) as archive:
        assert set(archive.namelist()) == {"manifest.json", "data/example/a.json"}
        assert install_data.inspect(archive) == preview
    destination = tmp_path / "destination"
    destination.mkdir()
    assert install_data.install(output, destination)[1] == 1
    assert (destination / "data/example/a.json").read_bytes() == b"synthetic A"
    assert not (destination / "data/example/b.json").exists()


def test_existing_output_is_preserved_even_in_preview(tmp_path):
    root, selection, _, output = fixture(tmp_path)
    output.write_bytes(b"existing local file")
    for dry_run in (True, False):
        with pytest.raises(ValueError, match="refusing to overwrite"):
            package_data.build(selection, output, root, dry_run)
    assert output.read_bytes() == b"existing local file"


@pytest.mark.parametrize("paths", [["data/example"], ["data/missing"], ["../outside"],
    ["data/display-profiles.json"], ["data/example/a.json", "data/example/a.json"]])
def test_invalid_selections_never_create_output(tmp_path, paths):
    root, selection, selected, output = fixture(tmp_path)
    selected["files"] = paths
    selection.write_text(json.dumps(selected), encoding="utf-8")
    with pytest.raises(ValueError):
        package_data.build(selection, output, root)
    assert not output.exists()


@pytest.mark.parametrize("key,value", [("package_version", ""), ("code_revision", None),
                                       ("scenarios", ["unknown"]), ("files", [])])
def test_manifest_metadata_is_validated_in_preview(tmp_path, key, value):
    root, selection, selected, output = fixture(tmp_path)
    selected[key] = value
    selection.write_text(json.dumps(selected), encoding="utf-8")
    with pytest.raises(ValueError):
        package_data.build(selection, output, root, True)
    assert not output.exists()


def test_source_links_are_rejected(tmp_path):
    root, selection, selected, output = fixture(tmp_path)
    link = root / "data/example/link"
    try:
        link.symlink_to(root / "data/example/a.json")
    except OSError:
        pytest.skip("creating symlinks is not permitted")
    selected["files"] = ["data/example/link"]
    selection.write_text(json.dumps(selected), encoding="utf-8")
    with pytest.raises(ValueError, match="link"):
        package_data.build(selection, output, root)
    assert not output.exists()


def test_cli_preview_and_error(tmp_path, capsys):
    root, selection, _, output = fixture(tmp_path)
    assert package_data.main([str(selection), str(output), "--root", str(root), "--dry-run"]) == 0
    assert "Would package 1 explicitly selected files" in capsys.readouterr().out
    assert not output.exists()
    assert package_data.main([str(tmp_path / "missing"), str(output)]) == 1


def test_changed_source_is_detected_before_publishing(tmp_path, monkeypatch):
    root, selection, _, output = fixture(tmp_path)
    original = ZipFile.write

    def changed_write(archive, path, *args, **kwargs):
        path.write_bytes(b"changed synthetic input")
        return original(archive, path, *args, **kwargs)

    monkeypatch.setattr(ZipFile, "write", changed_write)
    with pytest.raises(ValueError):
        package_data.build(selection, output, root)
    assert not output.exists()
