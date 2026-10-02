#!/usr/bin/env python3
"""Fetch the browser libraries for the 3D map into app/frontend/vendor/ (not versioned).

Downloads pinned npm packages, checks each tarball against the SHA-512 pinned
here, and unpacks only the files the GUI uses:

- CesiumJS (Apache-2.0): `Build/Cesium` as `vendor/cesium-<version>/`;
- satellite.js (MIT): its browser bundle as `vendor/satellite.js-<version>/`.

Run once after cloning, and before an exhibition, so the 3D map works offline.
Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import shutil
import tarfile
from pathlib import Path
from urllib.request import Request, urlopen

VENDOR = Path(__file__).resolve().parents[1] / "app" / "frontend" / "vendor"
PACKAGES = {
    "cesium": {
        "version": "1.146.0",
        "integrity": "sha512-hvKkURnmc8OZ8qKNrwawl/YijwAItaWLbpAdIVNAUXODCLMjpod4PbdLuwo8Ab6ETL915MUGV2NocHFCRCeqqA==",
        "keep": "package/Build/Cesium/",
        "license": "package/LICENSE.md",
    },
    "satellite.js": {
        "version": "7.1.0",
        "integrity": "sha512-U6nRml9Nb7dV9LJPiMNPyna7U7ry+1nXYkOeCEG7K/YbojQQLHHmcjPisp03VNY+HLcbQHqbt7t4t1vQMaKCLQ==",
        "keep": "package/dist/",
        "license": "package/LICENSE",
    },
}


def integrity_of(data: bytes) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")


def download(name: str, version: str) -> bytes:
    url = f"https://registry.npmjs.org/{name}/-/{name.split('/')[-1]}-{version}.tgz"
    with urlopen(Request(url, headers={"User-Agent": "techseed-geospatial-intelligence/0.1"}), timeout=300) as response:
        return response.read()


def unpack(data: bytes, keep: str, license_member: str, target: Path) -> int:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    count = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            name = member.name
            if member.isfile() and (name.startswith(keep) or name == license_member):
                relative = Path(name[len(keep):]) if name.startswith(keep) else Path(Path(name).name)
                if ".." in relative.parts or relative.is_absolute():
                    raise ValueError(f"unsafe path in package: {name}")
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, destination.open("wb") as stream:
                    shutil.copyfileobj(source, stream)
                count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.parse_args(argv)
    for name, spec in PACKAGES.items():
        data = download(name, spec["version"])
        found = integrity_of(data)
        if found != spec["integrity"]:
            raise SystemExit(f"{name} {spec['version']}: checksum {found} does not match the pinned {spec['integrity']}")
        target = VENDOR / f"{name}-{spec['version']}"
        files = unpack(data, spec["keep"], spec["license"], target)
        print(f"{name} {spec['version']}: {files} files -> {target.relative_to(VENDOR.parents[2])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
