"""Import a local ZIP data package without overwriting existing files.

Usage: python -m tools.install_data package.zip [--dry-run] [--root REPOSITORY]

The ZIP contains manifest.json and only the payload files listed in it. Manifest:
{"format_version": 1, "package_version": "...", "code_revision": "...",
 "scenarios": ["vastmanland2014"],
 "files": [{"path": "data/...", "size": 123, "sha256": "64 lowercase hex digits"}]}

Paths use forward slashes. Only data/ and the pinned, unversioned browser library
directories are accepted. Profiles, logs, hidden files and credential filenames
are excluded. The publisher must separately check content and distribution rights.
Hashes establish integrity, not authenticity: use a trusted package source.
Code revision is reported, not enforced; this tool cannot establish compatibility
or completeness. It never downloads data, runs code or changes PostGIS.
All inputs are verified before writing; an interrupted install may be partial.
Do not modify the package or destination concurrently with installation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
from zipfile import ZipFile, BadZipFile

from app.backend.scenarios import AVAILABLE, REPO_ROOT
from tools.fetch_web_vendor import PACKAGES

MAX_MANIFEST = 4 * 1024 * 1024
MAX_TOTAL = 64 * 1024**3
RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.I)


def safe_path(name: str) -> PurePosixPath:
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("Invalid package path")
    parts = name.split("/")
    for part in parts:
        if (part in ("", ".", "..") or part.startswith(".") or part.endswith((" ", "."))
                or any(ord(c) < 32 or c in '<>:"|?*' for c in part) or RESERVED.match(part)):
            raise ValueError(f"Unsafe package path: {name}")
        if (part.casefold() in {"display-profiles.json", "credentials", "credentials.json", "secrets.json"}
                or part.casefold().endswith(".log")):
            raise ValueError(f"Local settings, credentials and logs are not package inputs: {name}")
    path = PurePosixPath(name)
    vendor = {f"{key}-{spec['version']}" for key, spec in PACKAGES.items()}
    if not ((parts[0] == "data" and len(parts) > 1) or
            (parts[:3] == ["app", "frontend", "vendor"] and len(parts) > 4 and parts[3] in vendor)):
        raise ValueError(f"Path is outside the supported data directories: {name}")
    return path


def digest(stream) -> str:
    value = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        value.update(block)
    return value.hexdigest()


def destination(root: Path, name: str) -> Path:
    path = root.joinpath(*safe_path(name).parts)
    if path.resolve() != path:
        raise ValueError(f"Destination resolves through a link: {name}")
    for component in (path, *path.parents):
        if component == root:
            break
        if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
            raise ValueError(f"Destination contains a link: {name}")
        if component != path and component.exists() and not component.is_dir():
            raise ValueError(f"Destination parent is not a directory: {name}")
    return path


def inspect(archive: ZipFile) -> dict:
    entries = archive.infolist()
    names = [entry.filename for entry in entries]
    name_set = set(names)
    if len(set(name.casefold() for name in names)) != len(names):
        raise ValueError("Duplicate or case-colliding ZIP entries")
    for entry in entries:
        mode = entry.external_attr >> 16
        if entry.is_dir() or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)):
            raise ValueError("Only regular file ZIP entries are supported")
    if "manifest.json" not in names or archive.getinfo("manifest.json").file_size > MAX_MANIFEST:
        raise ValueError("Missing or oversized manifest.json")
    manifest = json.loads(archive.read("manifest.json"))
    if (not isinstance(manifest, dict) or type(manifest.get("format_version")) is not int
            or manifest["format_version"] != 1):
        raise ValueError("Unsupported manifest format")
    for key in ("package_version", "code_revision"):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            raise ValueError(f"Manifest requires {key}")
    scenarios = manifest.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios or any(s not in AVAILABLE for s in scenarios):
        raise ValueError("Manifest requires known scenario names")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("Manifest requires a nonempty files list")
    seen = set()
    components = {}
    total = 0
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("Invalid file record")
        path = str(safe_path(item.get("path")))
        for component in (PurePosixPath(path), *PurePosixPath(path).parents):
            spelling = str(component)
            previous = components.setdefault(spelling.casefold(), spelling)
            if previous != spelling:
                raise ValueError("Case-colliding package paths")
        if path.casefold() in seen:
            raise ValueError("Duplicate manifest path")
        seen.add(path.casefold())
        size = item.get("size")
        if type(size) is not int or size < 0:
            raise ValueError(f"Invalid size: {path}")
        total += size
        if total > MAX_TOTAL:
            raise ValueError("Package exceeds the 64 GiB limit")
        if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError(f"Invalid SHA-256: {path}")
        if path not in name_set or archive.getinfo(path).file_size != size:
            raise ValueError(f"Missing file or size mismatch: {path}")
    if name_set != {"manifest.json", *(item["path"] for item in files)}:
        raise ValueError("ZIP contains unlisted files")
    for path in seen:
        if any(str(parent) in seen for parent in PurePosixPath(path).parents):
            raise ValueError("Conflicting file and directory paths")
    return manifest


def install(package: Path, root: Path, dry_run: bool = False) -> tuple[dict, int]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Repository root must be a directory")
    with ZipFile(package) as archive:
        manifest = inspect(archive)
        pending = []
        for item in manifest["files"]:
            path = destination(root, item["path"])
            with archive.open(item["path"]) as stream:
                if digest(stream) != item["sha256"]:
                    raise ValueError(f"Package checksum mismatch: {item['path']}")
            if path.exists():
                if not path.is_file():
                    raise ValueError(f"Destination is not a file: {item['path']}")
                with path.open("rb") as stream:
                    if path.stat().st_size != item["size"] or digest(stream) != item["sha256"]:
                        raise ValueError(f"Existing file differs; refusing to overwrite: {item['path']}")
            else:
                pending.append(item)
        if not dry_run:
            # Stage verified bytes before touching the destination. Temporary storage
            # is removed on success or failure, including errors during extraction.
            with tempfile.TemporaryDirectory(prefix="techseed-data-") as scratch:
                for number, item in enumerate(pending):
                    with archive.open(item["path"]) as source, (Path(scratch) / str(number)).open("wb") as target:
                        shutil.copyfileobj(source, target)
                for number, item in enumerate(pending):
                    path = destination(root, item["path"])
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("xb") as target, (Path(scratch) / str(number)).open("rb") as source:
                        shutil.copyfileobj(source, target)
    return manifest, len(pending)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("package", type=Path)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--dry-run", action="store_true", help="verify the complete package without writing files")
    args = parser.parse_args(argv)
    try:
        manifest, count = install(args.package, args.root, args.dry_run)
    except (ValueError, OSError, BadZipFile, RuntimeError) as exc:
        print(f"Data installation failed: {exc}")
        return 1
    print(f"Package {manifest['package_version']} (code {manifest['code_revision']}), scenarios: {', '.join(manifest['scenarios'])}")
    print(f"{'Would install' if args.dry_run else 'Installed'} {count} files; identical existing files left unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
