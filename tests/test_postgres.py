"""Database mode tests use fake clients only; no PostgreSQL server is changed."""

import io
from types import SimpleNamespace

import pytest

from app.backend import postgres, scenario, spatial
from tools import load_postgis


@pytest.fixture(autouse=True)
def clean_options(monkeypatch):
    for name in ("TECHSEED_DB_MODE", "TECHSEED_DB_HOST", "TECHSEED_DB_PORT", "TECHSEED_DB_USER",
                 "TECHSEED_PSQL_PATH", "TECHSEED_DB_PASSFILE"):
        monkeypatch.delenv(name, raising=False)


def test_default_docker_commands_are_unchanged():
    assert postgres.command("firemap", interactive=True) == [
        "docker", "compose", "exec", "-T", "postgis", "psql", "-U", "firemap", "-d", "firemap",
        "-q", "-A", "-t", "-X", "-v", "ON_ERROR_STOP=0"]
    base = ["docker", "compose", "exec", "-T", "postgis", "psql", "-v", "ON_ERROR_STOP=1", "-U", "firemap", "-d", "firemap"]
    assert postgres.command("firemap") == base + ["-q", "-A", "-t"]
    assert postgres.command("firemap", quiet=False) == base
    assert postgres.environment() is None
    assert spatial.Psql().command == postgres.command(scenario.DATABASE, interactive=True)


def test_native_options_are_explicit_arguments(monkeypatch):
    monkeypatch.setenv("TECHSEED_DB_MODE", "native")
    monkeypatch.setenv("TECHSEED_PSQL_PATH", "C:/Program Files/PostgreSQL/16/bin/psql.exe")
    monkeypatch.setenv("TECHSEED_DB_HOST", "localhost")
    monkeypatch.setenv("TECHSEED_DB_PORT", "5433")
    monkeypatch.setenv("TECHSEED_DB_USER", "demo")
    command = postgres.command("scenario_db")
    assert command == ["C:/Program Files/PostgreSQL/16/bin/psql.exe", "--host=localhost", "--port=5433",
                       "--username=demo", "--dbname=scenario_db", "-w", "-X", "-v", "ON_ERROR_STOP=1", "-q", "-A", "-t"]
    assert "ON_ERROR_STOP=0" in postgres.command("scenario_db", interactive=True)
    assert "docker" not in spatial.Psql().command


def test_native_environment_uses_utf8_and_password_file_not_password_env(tmp_path, monkeypatch):
    passfile = tmp_path / "private/pgpass.conf"
    passfile.parent.mkdir()
    passfile.write_text("synthetic password file placeholder", encoding="utf-8")
    monkeypatch.setenv("TECHSEED_DB_MODE", "native")
    monkeypatch.setenv("TECHSEED_DB_PASSFILE", str(passfile))
    monkeypatch.setenv("PGPASSWORD", "synthetic-secret")
    env = postgres.environment()
    assert env["PGPASSFILE"] == str(passfile)
    assert env["PGCLIENTENCODING"] == "UTF8" and env["PGCONNECT_TIMEOUT"] == "5"
    assert "PGPASSWORD" not in env
    assert "synthetic-secret" not in " ".join(postgres.command("firemap"))


def test_native_without_explicit_password_file_uses_libpq_defaults(monkeypatch):
    monkeypatch.setenv("TECHSEED_DB_MODE", "native")
    monkeypatch.delenv("PGPASSFILE", raising=False)
    assert "PGPASSFILE" not in postgres.environment()


def test_explicit_password_file_must_be_outside_repository(tmp_path, monkeypatch):
    passfile = tmp_path / "pgpass.conf"
    passfile.write_text("synthetic placeholder", encoding="utf-8")
    monkeypatch.setattr(postgres, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("TECHSEED_DB_MODE", "native")
    monkeypatch.setenv("TECHSEED_DB_PASSFILE", str(passfile))
    with pytest.raises(ValueError, match="outside the repository"):
        postgres.environment()


@pytest.mark.parametrize("port", ["0", "65536", "not-a-port", "-1", "١٢"])
def test_invalid_native_ports_fail_without_falling_back_to_docker(monkeypatch, port):
    monkeypatch.setenv("TECHSEED_DB_MODE", "native")
    monkeypatch.setenv("TECHSEED_DB_PORT", port)
    with pytest.raises(ValueError, match="PORT"):
        postgres.command("firemap")


def test_unknown_mode_and_missing_password_file_are_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("TECHSEED_DB_MODE", "unknown")
    with pytest.raises(ValueError, match="MODE"):
        postgres.command("firemap")
    monkeypatch.setenv("TECHSEED_DB_MODE", "native")
    monkeypatch.setenv("TECHSEED_DB_PASSFILE", str(tmp_path / "missing"))
    with pytest.raises(ValueError, match="PASSFILE"):
        postgres.environment()


def test_loader_uses_native_client_utf8_and_requested_database(monkeypatch):
    monkeypatch.setenv("TECHSEED_DB_MODE", "native")
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="Örnsköldsvik", stderr="")
    monkeypatch.setattr(load_postgis.subprocess, "run", run)
    assert load_postgis.run_psql("SELECT 'Åäö';", database="postgres") == "Örnsköldsvik"
    command, kwargs = calls[0]
    assert "--dbname=postgres" in command and "docker" not in command
    assert kwargs["encoding"] == "utf-8" and kwargs["input"] == "SELECT 'Åäö';"
    assert kwargs["env"]["PGCLIENTENCODING"] == "UTF8"


def test_persistent_native_client_uses_utf8_and_no_shell(monkeypatch):
    monkeypatch.setenv("TECHSEED_DB_MODE", "native")
    calls = []
    process = SimpleNamespace(poll=lambda: None, stdin=io.StringIO(),
                              stdout=io.StringIO("Örnsköldsvik\n__techseed_end_1__\n"))
    def launch(command, **kwargs):
        calls.append((command, kwargs))
        return process
    monkeypatch.setattr(spatial.subprocess, "Popen", launch)
    assert spatial.Psql().query("SELECT 'Åäö'") == "Örnsköldsvik"
    command, kwargs = calls[0]
    assert command[0] == "psql" and "-w" in command
    assert kwargs["encoding"] == "utf-8" and not kwargs.get("shell")
    assert kwargs["env"]["PGCLIENTENCODING"] == "UTF8"
    assert "Åäö" in process.stdin.getvalue()
