"""Native orchestration tests use fake processes; no real services or database writes."""

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.backend import postgres
from tools import native_services as native, start_demo, startup_check


def test_database_check_is_native_read_only_and_does_not_change_parent_env(monkeypatch):
    monkeypatch.setenv("TECHSEED_DB_MODE", "docker")
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="3.4", stderr="")
    monkeypatch.setattr(native.subprocess, "run", run)
    native.check_database("vastmanland2014")
    command, options = calls[0]
    assert command[0] == "psql" and "docker" not in command
    assert options["input"] == "SELECT PostGIS_Version();\n"
    assert options["env"]["TECHSEED_DB_MODE"] == "native"
    assert options["encoding"] == "utf-8" and options["timeout"] == 15
    assert postgres.mode() == "docker"


def test_database_failure_is_not_an_implicit_load_or_docker_fallback(monkeypatch):
    monkeypatch.setattr(native.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1, stdout=""))
    with pytest.raises(ValueError, match="check failed"):
        native.check_database("vastmanland2014")


@pytest.mark.parametrize("failure", [None, "second_spawn", "early_exit", "body"])
def test_native_process_ownership_and_cleanup(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(native, "prepared", lambda *args: ({}, ["node", "entry.js"], "mosquitto"))
    monkeypatch.setattr(native, "check_database", lambda name: None)
    children = []
    stopped = []
    configs = []
    class Child:
        done = False
        def poll(self): return 1 if failure == "early_exit" or self.done else None
        def terminate(self):
            stopped.append(self)
            self.done = True
        def wait(self, timeout=None): return 0
    def launch(command, **kwargs):
        if failure == "second_spawn" and children:
            raise OSError("synthetic start failure")
        config = Path(command[command.index("--config") + 1] if "--config" in command else command[-1])
        assert config.is_file()
        configs.append(config)
        child = Child()
        children.append(child)
        return child
    monkeypatch.setattr(native.subprocess, "Popen", launch)
    monkeypatch.setattr(native, "port_busy", lambda port: len(children) == 2)
    def exercise():
        with native.running("vastmanland2014", native.Options(tmp_path)) as env:
            assert env["TECHSEED_DB_MODE"] == "native"
            assert env["IOT_MQTT_BROKER"] == "127.0.0.1:1883"
            if failure == "body":
                raise RuntimeError("synthetic body failure")
    if failure:
        with pytest.raises((ValueError, OSError, RuntimeError)):
            exercise()
    else:
        exercise()
    assert stopped == ([] if failure == "early_exit" else list(reversed(children)))
    assert all(not path.exists() for path in configs)


def test_busy_native_port_is_left_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "prepared", lambda *a: ({}, ["node", "entry.js"], "mosquitto"))
    monkeypatch.setattr(native, "check_database", lambda name: None)
    monkeypatch.setattr(native, "port_busy", lambda port: True)
    def forbidden(*args, **kwargs):
        raise AssertionError("must not start or replace a service")
    monkeypatch.setattr(native.subprocess, "Popen", forbidden)
    with pytest.raises(ValueError, match="in use"):
        with native.running("vastmanland2014", native.Options(tmp_path)):
            pass


def test_native_startup_checks_never_probe_docker(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "prepared", lambda *a: None)
    monkeypatch.setattr(native, "check_database", lambda name: None)
    monkeypatch.setattr(startup_check, "data_checks", lambda settings: [])
    monkeypatch.setattr(startup_check, "find_chrome", lambda: "chrome")
    def forbidden(*args, **kwargs):
        raise AssertionError("native checks must not call Docker probes")
    monkeypatch.setattr(startup_check, "probe", forbidden)
    monkeypatch.setattr(native, "port_busy", lambda port: False)
    checks = startup_check.native_installation_checks("vastmanland2014", native.Options(tmp_path))
    assert all(check.passed for check in checks)
    assert all("Docker" not in check.name for check in checks)


def test_native_main_cleans_services_after_demo_and_does_not_mutate_default_mode(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setenv("TECHSEED_DB_MODE", "docker")
    monkeypatch.setattr(start_demo, "port_in_use", lambda port: False)
    @contextmanager
    def running(name, options):
        calls.append("start native")
        try:
            yield {"TECHSEED_DB_MODE": "native"}
        finally:
            calls.append("stop native")
    monkeypatch.setattr(native, "running", running)
    def demo(name, at, *, native_env):
        assert native_env["TECHSEED_DB_MODE"] == "native"
        calls.append("demo")
        return 0
    monkeypatch.setattr(start_demo, "run_demo", demo)
    assert start_demo.main(["vastmanland2014", "--services", "native", "--node-modules", str(tmp_path)]) == 0
    assert calls == ["start native", "demo", "stop native"]
    assert postgres.mode() == "docker"


def test_native_run_demo_never_starts_docker_and_passes_native_env(tmp_path, monkeypatch):
    monkeypatch.setattr(start_demo, "NODE_LOG", tmp_path / "nodes.log")
    monkeypatch.setattr(start_demo, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(start_demo, "scenario_settings", lambda name: ("synthetic.mbtiles", "2014-07-31T00:00:00Z"))
    monkeypatch.setattr(start_demo, "served_tiles_file", lambda url: "synthetic.mbtiles")
    monkeypatch.setattr(start_demo, "answers", lambda url: True)
    monkeypatch.setattr(start_demo, "wait_until", lambda check, *args: check() or pytest.fail("not ready"))
    calls = []
    children = []
    class Child:
        returncode = None
        def poll(self): return self.returncode
        def wait(self, timeout=None): self.returncode = start_demo.MENU_EXIT
        def terminate(self): self.returncode = 0
    def launch(command, **kwargs):
        assert kwargs["env"]["TECHSEED_DB_MODE"] == "native"
        child = Child()
        children.append(child)
        return child
    def run(command, **kwargs):
        assert command[0] != "docker"
        calls.append(command)
    monkeypatch.setattr(start_demo.subprocess, "Popen", launch)
    monkeypatch.setattr(start_demo.subprocess, "run", run)
    env = native.child_environment("vastmanland2014")
    assert start_demo.run_demo("vastmanland2014", None, native_env=env) == start_demo.MENU_EXIT
    assert len(children) == 2 and all(child.poll() is not None for child in children)
    assert len(calls) == 1 and "tools.open_screens" in calls[0]


def test_native_mode_requires_runtime_path():
    with pytest.raises(SystemExit) as error:
        start_demo.main(["--services", "native"])
    assert error.value.code == 2


def test_startup_check_native_cli_dispatch(tmp_path, monkeypatch):
    seen = []
    def checks(name, options):
        seen.append((name, options))
        return [startup_check.Check("synthetic native check", True, "ok")]
    monkeypatch.setattr(startup_check, "native_installation_checks", checks)
    assert startup_check.main(["vastmanland2014", "--services", "native", "--node-modules", str(tmp_path),
                               "--node", "node.exe", "--mosquitto", "mosquitto.exe"]) == 0
    assert seen == [("vastmanland2014", native.Options(tmp_path, "node.exe", "mosquitto.exe"))]


def test_native_runtime_rejects_missing_mosquitto_before_start(tmp_path, monkeypatch):
    monkeypatch.setattr(native.start_native_tiles, "configuration", lambda *a: {})
    monkeypatch.setattr(native.start_native_tiles, "runtime_paths", lambda *a: (Path("entry.js"), tmp_path))
    monkeypatch.setattr(native.shutil, "which", lambda name: None)
    with pytest.raises(ValueError, match="Node.js and Mosquitto"):
        native.prepared("vastmanland2014", native.Options(tmp_path))


def test_explicit_native_environment_does_not_change_docker_defaults(monkeypatch):
    monkeypatch.setenv("TECHSEED_DB_MODE", "docker")
    env = native.child_environment("sundsvall2026")
    assert "docker" not in postgres.command("synthetic", environ=env)
    assert postgres.environment(env)["PGCLIENTENCODING"] == "UTF8"
    assert postgres.command("synthetic")[0] == "docker"


def test_the_native_broker_can_take_another_port_for_backend_and_nodes(tmp_path, monkeypatch):
    # The Windows test of 2026-10-22: zenon Data Hub's Mosquitto held port 1883.
    monkeypatch.setattr(native, "prepared", lambda *args: ({}, ["node", "entry.js"], "mosquitto"))
    monkeypatch.setattr(native, "check_database", lambda name: None)
    asked, configs, started = [], [], []
    class Child:
        def poll(self): return None
        def terminate(self): pass
        def wait(self, timeout=None): return 0
    def launch(command, **kwargs):
        config = Path(command[command.index("--config") + 1] if "--config" in command else command[-1])
        configs.append(config.read_text(encoding="utf-8"))
        started.append(command)
        return Child()
    def busy(port):
        asked.append(port)
        return len(started) == 2
    monkeypatch.setattr(native.subprocess, "Popen", launch)
    monkeypatch.setattr(native, "port_busy", busy)
    with native.running("vastmanland2014", native.Options(tmp_path, mqtt_port=18830)) as env:
        assert env["IOT_MQTT_BROKER"] == "127.0.0.1:18830"
    assert asked[:2] == [native.TILES_PORT, 18830]  # both checked free before anything starts
    assert "listener 18830 127.0.0.1" in configs[1]
    with pytest.raises(ValueError, match="between 1 and 65535"):
        with native.running("vastmanland2014", native.Options(tmp_path, mqtt_port=70000)):
            pass


def test_startup_check_names_a_busy_native_port(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "prepared", lambda *a: None)
    monkeypatch.setattr(native, "check_database", lambda name: None)
    monkeypatch.setattr(startup_check, "data_checks", lambda settings: [])
    monkeypatch.setattr(startup_check, "find_chrome", lambda: "chrome")
    monkeypatch.setattr(native, "port_busy", lambda port: port == 1883)
    checks = {check.name: check for check in startup_check.native_installation_checks("vastmanland2014", native.Options(tmp_path))}
    assert not checks["Native MQTT port 1883"].passed and "--mqtt-port" in checks["Native MQTT port 1883"].detail
    assert checks["Native map port 8081"].passed
    moved = startup_check.native_installation_checks("vastmanland2014", native.Options(tmp_path, mqtt_port=18830))
    assert all(check.passed for check in moved)
    seen = []
    monkeypatch.setattr(startup_check, "native_installation_checks", lambda name, options: seen.append(options) or [])
    assert startup_check.main(["vastmanland2014", "--services", "native", "--node-modules", str(tmp_path), "--mqtt-port", "18830"]) == 0
    assert seen == [native.Options(tmp_path, mqtt_port=18830)]


def test_start_demo_passes_the_mqtt_port_on_and_the_nodes_follow_it(tmp_path, monkeypatch):
    run_demo = start_demo.run_demo
    with pytest.raises(SystemExit) as error:
        start_demo.main(["vastmanland2014", "--mqtt-port", "18830"])  # Docker's broker is fixed by compose
    assert error.value.code == 2
    monkeypatch.setattr(start_demo, "port_in_use", lambda port: False)
    seen = []
    @contextmanager
    def running(name, options):
        seen.append(options.mqtt_port)
        yield native.child_environment(name, options.mqtt_port)
    monkeypatch.setattr(native, "running", running)
    monkeypatch.setattr(start_demo, "run_demo", lambda name, at, *, native_env: seen.append(native_env["IOT_MQTT_BROKER"]) or 0)
    assert start_demo.main(["vastmanland2014", "--services", "native", "--node-modules", str(tmp_path), "--mqtt-port", "18830"]) == 0
    assert seen == [18830, "127.0.0.1:18830"]
    # The simulated booth nodes publish to the same broker as the backend listens to.
    monkeypatch.setattr(start_demo, "NODE_LOG", tmp_path / "nodes.log")
    monkeypatch.setattr(start_demo, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(start_demo, "scenario_settings", lambda name: ("synthetic.mbtiles", "2014-07-31T00:00:00Z"))
    monkeypatch.setattr(start_demo, "served_tiles_file", lambda url: "synthetic.mbtiles")
    monkeypatch.setattr(start_demo, "answers", lambda url: True)
    monkeypatch.setattr(start_demo, "wait_until", lambda check, *args: check() or pytest.fail("not ready"))
    commands = []
    class Child:
        returncode = None
        def poll(self): return self.returncode
        def wait(self, timeout=None): self.returncode = start_demo.MENU_EXIT
        def terminate(self): self.returncode = 0
    monkeypatch.setattr(start_demo.subprocess, "Popen", lambda command, **kwargs: commands.append(command) or Child())
    monkeypatch.setattr(start_demo.subprocess, "run", lambda command, **kwargs: None)
    run_demo("vastmanland2014", None, native_env=native.child_environment("vastmanland2014", 18830))
    nodes = next(command for command in commands if "tools.mqtt_node_sim" in command)
    assert nodes[-2:] == ["--broker", "127.0.0.1:18830"]
