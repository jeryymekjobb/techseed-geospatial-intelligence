"""Local MQTT launcher tests: no Mosquitto process or MQTT messages."""

from pathlib import Path
import socket
import subprocess

import pytest

from tools import start_native_mqtt as mqtt


def test_configuration_is_loopback_only_and_nonpersistent():
    assert mqtt.configuration(1883) == (
        "listener 1883 127.0.0.1\nallow_anonymous true\npersistence false\nlog_dest stdout\n")
    assert mqtt.configuration(1884).startswith("listener 1884 127.0.0.1\n")


@pytest.mark.parametrize("port", [0, 65536, -1, True, "1883"])
def test_invalid_ports_are_rejected(port):
    with pytest.raises(ValueError, match="port"):
        mqtt.configuration(port)


def test_executable_paths_with_spaces_are_single_arguments(tmp_path):
    path = tmp_path / "config with spaces/mosquitto.conf"
    assert mqtt.command("C:/Program Files/mosquitto/mosquitto.exe", path) == [
        "C:/Program Files/mosquitto/mosquitto.exe", "-c", str(path)]


def test_preview_does_not_probe_start_or_write(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("preview must not access processes, network or temporary files")
    monkeypatch.setattr(mqtt.socket, "socket", forbidden)
    monkeypatch.setattr(mqtt.subprocess, "Popen", forbidden)
    monkeypatch.setattr(mqtt.tempfile, "TemporaryDirectory", forbidden)
    assert mqtt.main(["--dry-run"]) == 0
    assert "listener 1883 127.0.0.1" in capsys.readouterr().out


def test_existing_broker_is_not_replaced(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("existing broker must not be replaced")
    monkeypatch.setattr(mqtt.subprocess, "Popen", forbidden)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with pytest.raises(ValueError, match="already in use"):
            mqtt.run("mosquitto", listener.getsockname()[1])


@pytest.mark.parametrize("behavior", ["exit", "interrupt", "timeout"])
def test_config_cleanup_and_owned_process_lifecycle(monkeypatch, behavior):
    class Probe:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def settimeout(self, value): pass
        def connect_ex(self, address): return 1
    monkeypatch.setattr(mqtt.socket, "socket", Probe)
    calls = []
    paths = []
    class Child:
        count = 0
        def poll(self): return 7 if behavior == "exit" else None
        def wait(self, timeout=None):
            self.count += 1
            if self.count == 1 and behavior != "exit":
                raise KeyboardInterrupt
            if timeout and behavior == "timeout":
                raise subprocess.TimeoutExpired("fake-mosquitto", timeout)
            return 7
        def terminate(self): calls.append("terminate")
        def kill(self): calls.append("kill")
    def launch(command):
        path = Path(command[-1])
        assert path.read_text(encoding="utf-8") == mqtt.configuration(1883)
        paths.append(path)
        return Child()
    monkeypatch.setattr(mqtt.subprocess, "Popen", launch)
    assert mqtt.run("fake-mosquitto", 1883) == (7 if behavior == "exit" else 0)
    assert calls == {"exit": [], "interrupt": ["terminate"], "timeout": ["terminate", "kill"]}[behavior]
    assert not paths[0].exists()


def test_missing_executable_returns_an_actionable_error(monkeypatch, capsys):
    monkeypatch.setattr(mqtt.shutil, "which", lambda name: None)
    assert mqtt.main([]) == 1
    assert "specify --mosquitto" in capsys.readouterr().out


def test_invalid_cli_port_does_not_start_a_broker(capsys):
    assert mqtt.main(["--port", "0"]) == 1
    assert "port must be" in capsys.readouterr().out
