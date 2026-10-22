"""Build a local data ZIP from an explicitly reviewed JSON file list.

python -m tools.package_data selection.json package.zip --dry-run
python -m tools.package_data selection.json package.zip

Selection format: {"package_version": "...", "code_revision": "...",
"scenarios": ["vastmanland2014"], "files": ["data/path/to/file", ...]}.
Paths are repository-relative and use forward slashes. Every file must be listed;
directories are never scanned. The caller must approve content and distribution
rights separately. This tool makes no such determination. Profiles, logs and
credential filenames are rejected by the shared import rules. No credentials,
Docker volumes or raw data are collected automatically.

Preview validates inputs and calculates hashes but creates no files. Existing
output files are never overwritten. Do not modify inputs while packaging.

A package for Windows without Docker must carry each scenario's offline map and 3D
terrain, which cannot be built there (no tilemaker, no ctb-tile). The tool warns, without
refusing, when a listed scenario's map (data/tiles/<file>.mbtiles and its .SOURCE.json) or
terrain (its layer.json and tiles) is not in the selection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from app.backend.scenarios import REPO_ROOT
from tools import install_data


def selection_manifest(selection: Path, root: Path) -> dict:
    if selection.stat().st_size > install_data.MAX_MANIFEST:
        raise ValueError("Selection exceeds the manifest size limit")
    selected = json.loads(selection.read_text(encoding="utf-8"))
    if not isinstance(selected, dict) or not isinstance(selected.get("files"), list) or not selected["files"]:
        raise ValueError("Selection requires a nonempty files list")
    files = []
    for name in selected["files"]:
        path = install_data.destination(root, name)
        if not path.is_file():
            raise ValueError(f"Selected input is not a regular file: {name}")
        with path.open("rb") as stream:
            checksum = install_data.digest(stream)
        files.append({"path": name, "size": path.stat().st_size, "sha256": checksum})
    return {"format_version": 1, "package_version": selected.get("package_version"),
            "code_revision": selected.get("code_revision"), "scenarios": selected.get("scenarios"), "files": files}


def missing_map_inputs(manifest: dict) -> list[str]:
    """Each listed scenario's offline map and 3D terrain that the selection lacks (repository-relative paths),
    for a warning: Windows without Docker cannot build them."""
    import importlib

    from app.backend.scenarios import AVAILABLE

    paths = {item["path"] for item in manifest["files"]}
    missing = []
    for name in manifest.get("scenarios") or []:
        if name not in AVAILABLE:
            continue
        settings = importlib.import_module(f"app.backend.scenarios.{name}")
        tiles = Path(settings.TILES_FILE)
        terrain = Path(settings.TERRAIN_DIR).resolve().relative_to(REPO_ROOT.resolve()).as_posix()
        for path in (f"data/tiles/{tiles.name}", f"data/tiles/{tiles.stem}.SOURCE.json", f"{terrain}/layer.json"):
            if path not in paths:
                missing.append(path)
        if not any(path.startswith(f"{terrain}/") and not path.endswith("layer.json") for path in paths):
            missing.append(f"{terrain}/ (the terrain's tiles)")
    return list(dict.fromkeys(missing))


def build(selection: Path, output: Path, root: Path, dry_run: bool = False) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Repository root must be a directory")
    if output.exists() or output.is_symlink():
        raise ValueError("Output already exists; refusing to overwrite")
    manifest = selection_manifest(selection, root)
    encoded = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    if len(encoded) > install_data.MAX_MANIFEST:
        raise ValueError("Generated manifest exceeds the size limit")
    # Validate the manifest with the importer's rules even in preview mode.
    # A lightweight catalogue supplies sizes without reading payloads again.
    class Catalogue:
        def __init__(self):
            from zipfile import ZipInfo
            self.entries = []
            for name, size in [("manifest.json", len(encoded)), *((f["path"], f["size"]) for f in manifest["files"])]:
                entry = ZipInfo(name)
                entry.file_size = size
                self.entries.append(entry)
            self.by_name = {entry.filename: entry for entry in self.entries}

        def infolist(self):
            return self.entries

        def getinfo(self, name):
            return self.by_name[name]

        def read(self, name):
            return encoded

    install_data.inspect(Catalogue())
    if dry_run:
        return manifest
    if not output.parent.is_dir():
        raise ValueError("Output directory must already exist")
    with tempfile.TemporaryDirectory(prefix="techseed-package-") as scratch:
        staged = Path(scratch) / "package.zip"
        with ZipFile(staged, "w", compression=ZIP_DEFLATED, allowZip64=True) as archive:
            archive.writestr("manifest.json", encoded)
            for item in manifest["files"]:
                path = install_data.destination(root, item["path"])
                archive.write(path, item["path"])
        # Check the actual ZIP and bytes, not just the original selection.
        with ZipFile(staged) as archive:
            install_data.inspect(archive)
            for item in manifest["files"]:
                with archive.open(item["path"]) as stream:
                    if install_data.digest(stream) != item["sha256"]:
                        raise ValueError(f"Input changed while packaging: {item['path']}")
        try:
            with output.open("xb") as target, staged.open("rb") as source:
                shutil.copyfileobj(source, target)
        except FileExistsError:
            raise ValueError("Output already exists; refusing to overwrite") from None
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("selection", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = build(args.selection, args.output, args.root, args.dry_run)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Data packaging failed: {exc}")
        return 1
    print(f"{'Would package' if args.dry_run else 'Packaged'} {len(manifest['files'])} explicitly selected files "
          f"for {', '.join(manifest['scenarios'])}; version {manifest['package_version']}.")
    for path in missing_map_inputs(manifest):
        print(f"Warning: {path} is not in the selection; Windows without Docker cannot build it (offline map or 3D terrain).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
