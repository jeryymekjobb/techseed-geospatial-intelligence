"""Native map startup tests use synthetic files and never launch a map server."""

import json
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import start_native_tiles as native


def fixture(tmp_path):
    root = tmp_path / "repo with spaces å"
    modules = tmp_path / "runtime/node_modules"
    package = modules / "tileserver-gl"
    (package / "src").mkdir(parents=True)
    (package / "src/main.js").write_text("// synthetic entry")
    (package / "package.json").write_text(json.dumps({"name": "tileserver-gl", "version": native.VERSION}))
    fonts = modules / "tileserver-gl-styles/fonts/Noto Sans Regular"
    fonts.mkdir(parents=True)
    (fonts / "0-255.pbf").write_bytes(b"synthetic font")
    (root / "data/tiles").mkdir(parents=True)
    (root / "data/tiles/demo.mbtiles").write_bytes(b"synthetic map")
    (root / "tiles/styles").mkdir(parents=True)
    for name in ("techseed", "techseed-overlay"):
        (root / f"tiles/styles/{name}.json").write_text("{}")
    return root, modules


def test_config_preserves_both_styles_and_uses_absolute_local_paths(tmp_path):
    root, modules = fixture(tmp_path)
    config = native.configuration("demo.mbtiles", modules, root)
    assert config["data"] == {"v3": {"mbtiles": "demo.mbtiles"}}
    assert set(config["styles"]) == {"techseed", "techseed-overlay"}
    assert all(Path(value).is_absolute() for value in config["options"]["paths"].values())
    assert config["options"]["paths"]["styles"] == (root / "tiles/styles").as_posix()


@pytest.mark.parametrize("version", ["0.0.0", "5.5.0"])
def test_runtime_version_must_match(tmp_path, version):
    root, modules = fixture(tmp_path)
    (modules / "tileserver-gl/package.json").write_text(json.dumps({"name": "tileserver-gl", "version": version}))
    with pytest.raises(ValueError, match="Expected the full"):
        native.configuration("demo.mbtiles", modules, root)


def test_missing_map_or_fonts_are_reported(tmp_path):
    root, modules = fixture(tmp_path)
    with pytest.raises(ValueError, match="scenario map"):
        native.configuration("missing.mbtiles", modules, root)
    (modules / "tileserver-gl-styles/fonts/Noto Sans Regular/0-255.pbf").unlink()
    with pytest.raises(ValueError, match="font"):
        native.configuration("demo.mbtiles", modules, root)


def test_command_is_loopback_only_and_keeps_paths_as_arguments(tmp_path):
    args = native.command("C:/Program Files/nodejs/node.exe", tmp_path / "entry file.js", tmp_path / "config file.json", 8081)
    assert args[:3] == ["C:/Program Files/nodejs/node.exe", str(tmp_path / "entry file.js"), "--config"]
    assert args[args.index("--bind") + 1] == "127.0.0.1"
    assert args[-1] == "http://127.0.0.1:8081/"


def test_preview_never_launches_or_writes(tmp_path, monkeypatch):
    root, modules = fixture(tmp_path)
    original = native.configuration
    monkeypatch.setattr(native, "configuration", lambda name, path: original("demo.mbtiles", path, root))
    def forbidden(*args, **kwargs):
        raise AssertionError("preview must not launch a process or create temporary files")
    monkeypatch.setattr(native, "run", forbidden)
    monkeypatch.setattr(native.tempfile, "TemporaryDirectory", forbidden)
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    assert native.main(["vastmanland2014", "--node-modules", str(modules), "--dry-run"]) == 0
    assert sorted(str(p) for p in tmp_path.rglob("*")) == before


def test_foreground_run_cleans_its_config_and_stops_only_its_child(tmp_path, monkeypatch):
    root, modules = fixture(tmp_path)
    config = native.configuration("demo.mbtiles", modules, root)
    calls = []
    monkeypatch.setattr(native.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="v22.1.0"))
    class Probe:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def settimeout(self, value): pass
        def connect_ex(self, address): return 1
    monkeypatch.setattr(native.socket, "socket", Probe)
    class Child:
        waits = 0
        def poll(self): return None
        def wait(self, timeout=None):
            self.waits += 1
            if self.waits == 1:
                raise KeyboardInterrupt
            return 0
        def terminate(self): calls.append("terminate own child")
    configs = []
    def launch(command, **kwargs):
        path = Path(command[command.index("--config") + 1])
        assert json.loads(path.read_text(encoding="utf-8")) == config
        configs.append(path)
        return Child()
    monkeypatch.setattr(native.subprocess, "Popen", launch)
    assert native.run("node", modules / "tileserver-gl/src/main.js", config, 8081) == 0
    assert calls == ["terminate own child"]
    assert not configs[0].exists()


def test_unsupported_node_never_starts_server(monkeypatch):
    monkeypatch.setattr(native.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="v18.0.0"))
    with pytest.raises(ValueError, match="requires Node.js"):
        native.run("node", Path("entry.js"), {}, 8081)


def test_occupied_port_never_starts_or_stops_a_service(monkeypatch):
    monkeypatch.setattr(native.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="v22.1.0"))
    def forbidden(*args, **kwargs):
        raise AssertionError("must not start a server on an occupied port")
    monkeypatch.setattr(native.subprocess, "Popen", forbidden)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with pytest.raises(ValueError, match="already in use"):
            native.run("node", Path("entry.js"), {}, listener.getsockname()[1])


def test_nested_npm_dependency_layout_is_supported(tmp_path):
    root, modules = fixture(tmp_path)
    styles = modules / "tileserver-gl-styles"
    nested = modules / "tileserver-gl/node_modules/tileserver-gl-styles"
    nested.parent.mkdir()
    styles.rename(nested)
    assert native.configuration("demo.mbtiles", modules, root)["options"]["paths"]["root"] == nested.as_posix()
