"""Run a separate local TileServer GL without Docker; the existing demo launcher is unchanged.

python -m tools.start_native_tiles vastmanland2014 --node-modules PATH --dry-run

PATH is the node_modules directory of a separately installed, trusted TileServer
GL 5.6.0 runtime. This tool installs nothing. It uses both repository map styles,
binds only to 127.0.0.1 and runs in the foreground until Ctrl+C. Configuration is
temporary, never written over tiles/config.json. Windows rendering is not yet
verified on the target VM. --dry-run validates local files and prints configuration
without launching Node, creating files or probing the network.
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile

from app.backend.scenarios import AVAILABLE, REPO_ROOT

VERSION = "5.6.0"


def runtime_paths(node_modules: Path) -> tuple[Path, Path]:
    package = node_modules.resolve() / "tileserver-gl"
    metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
    if metadata.get("name") != "tileserver-gl" or metadata.get("version") != VERSION:
        raise ValueError(f"Expected the full tileserver-gl {VERSION} runtime, not tileserver-gl-light")
    entry = package / "src/main.js"
    if not entry.is_file():
        raise ValueError(f"Missing TileServer GL entry point: {entry}")
    # npm may hoist dependencies or keep them under the package itself.
    candidates = [node_modules.resolve() / "tileserver-gl-styles", package / "node_modules/tileserver-gl-styles"]
    styles = next((path for path in candidates if (path / "fonts").is_dir()), None)
    if styles is None or not next((styles / "fonts").rglob("*.pbf"), None):
        raise ValueError("TileServer GL font files are missing")
    return entry, styles


def configuration(tiles_file: str, node_modules: Path, root: Path = REPO_ROOT) -> dict:
    root = root.resolve()
    _, runtime_styles = runtime_paths(node_modules)
    if Path(tiles_file).name != tiles_file or not tiles_file.endswith(".mbtiles"):
        raise ValueError("Expected a scenario MBTiles filename")
    tiles = root / "data/tiles" / tiles_file
    if not tiles.is_file() or tiles.stat().st_size == 0:
        raise ValueError(f"Missing or empty scenario map: {tiles}")
    for name in ("techseed", "techseed-overlay"):
        style = root / "tiles/styles" / f"{name}.json"
        if not style.is_file():
            raise ValueError(f"Missing map style: {style}")
    return {"options": {"paths": {"root": runtime_styles.as_posix(),
                                   "fonts": (runtime_styles / "fonts").as_posix(),
                                   "styles": (root / "tiles/styles").as_posix(),
                                   "mbtiles": (root / "data/tiles").as_posix()},
                        "allowedHosts": "127.0.0.1,localhost"},
            "styles": {name: {"style": f"{name}.json"} for name in ("techseed", "techseed-overlay")},
            "data": {"v3": {"mbtiles": tiles_file}}}


def command(node: str, entry: Path, config: Path, port: int) -> list[str]:
    return [node, str(entry), "--config", str(config), "--bind", "127.0.0.1", "--port", str(port),
            "--public_url", f"http://127.0.0.1:{port}/"]


def run(node: str, entry: Path, config: dict, port: int) -> int:
    version = subprocess.run([node, "--version"], check=True, capture_output=True, text=True, timeout=15).stdout.strip()
    if not re.fullmatch(r"v(?:20|22|24)\.\d+\.\d+", version):
        raise ValueError(f"TileServer GL {VERSION} requires Node.js 20, 22 or 24; found {version}")
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise ValueError(f"Port {port} is already in use; no existing service was stopped")
    with tempfile.TemporaryDirectory(prefix="techseed-native-tiles-") as scratch:
        path = Path(scratch) / "config.json"
        path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        child = subprocess.Popen(command(node, entry, path, port), cwd=entry.parent)
        try:
            return child.wait()
        except KeyboardInterrupt:
            return 0
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("scenario", choices=AVAILABLE)
    parser.add_argument("--node-modules", required=True, type=Path)
    parser.add_argument("--node", help="path to node/node.exe (default: PATH)")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    try:
        settings = importlib.import_module(f"app.backend.scenarios.{args.scenario}")
        config = configuration(settings.TILES_FILE, args.node_modules)
        if args.dry_run:
            print(json.dumps(config, ensure_ascii=False, indent=2))
            return 0
        node = args.node or shutil.which("node")
        if not node:
            raise ValueError("Node.js was not found; install the runtime separately")
        entry, _ = runtime_paths(args.node_modules)
        print(f"Local map: {settings.TILES_FILE} at http://127.0.0.1:{args.port}/; Ctrl+C stops only this server.")
        return run(node, entry, config, args.port)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"start_native_tiles: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
