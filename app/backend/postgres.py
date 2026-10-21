"""Shared psql configuration. Docker remains the default, including on Ubuntu.

Set TECHSEED_DB_MODE=native explicitly to use a separately installed PostgreSQL/
PostGIS. Optional TECHSEED_PSQL_PATH, TECHSEED_DB_HOST, TECHSEED_DB_PORT and
TECHSEED_DB_USER select the client and connection (defaults: psql, 127.0.0.1,
5432, firemap). TECHSEED_DB_PASSFILE selects an existing libpq password file;
otherwise libpq uses its standard per-user password file. Never put passwords in
these options or the repository. Native mode disables prompting and PGPASSWORD,
uses UTF-8 and a connection timeout, and starts or installs no database service.
Actual native Windows/PostGIS connectivity is not yet verified.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.backend.scenarios import REPO_ROOT


def mode() -> str:
    value = os.environ.get("TECHSEED_DB_MODE", "docker")
    if value not in ("docker", "native"):
        raise ValueError("TECHSEED_DB_MODE must be docker or native")
    return value


def command(database: str, *, interactive: bool = False, quiet: bool = True) -> list[str]:
    if mode() == "docker":
        if interactive:
            return ["docker", "compose", "exec", "-T", "postgis", "psql", "-U", "firemap", "-d", database,
                    "-q", "-A", "-t", "-X", "-v", "ON_ERROR_STOP=0"]
        result = ["docker", "compose", "exec", "-T", "postgis", "psql", "-v", "ON_ERROR_STOP=1",
                  "-U", "firemap", "-d", database]
        return result + (["-q", "-A", "-t"] if quiet else [])
    port = os.environ.get("TECHSEED_DB_PORT", "5432")
    if not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError("TECHSEED_DB_PORT must be between 1 and 65535")
    result = [os.environ.get("TECHSEED_PSQL_PATH", "psql"),
              "--host=" + os.environ.get("TECHSEED_DB_HOST", "127.0.0.1"),
              "--port=" + port, "--username=" + os.environ.get("TECHSEED_DB_USER", "firemap"),
              "--dbname=" + database, "-w", "-X", "-v", f"ON_ERROR_STOP={0 if interactive else 1}"]
    return result + (["-q", "-A", "-t"] if quiet or interactive else [])


def environment() -> dict[str, str] | None:
    if mode() == "docker":
        return None  # preserve the existing inherited Docker environment
    env = dict(os.environ)
    env.pop("PGPASSWORD", None)
    env["PGCLIENTENCODING"] = "UTF8"
    env["PGCONNECT_TIMEOUT"] = "5"
    passfile = env.get("TECHSEED_DB_PASSFILE")
    if passfile:
        path = Path(passfile).expanduser().resolve()
        if not path.is_file() or path.is_relative_to(REPO_ROOT.resolve()):
            raise ValueError("TECHSEED_DB_PASSFILE must name an existing password file outside the repository")
        env["PGPASSFILE"] = str(path)
    return env


def unavailable_message() -> str:
    if mode() == "native":
        return "PostGIS svarar inte (kontrollera lokal PostgreSQL/PostGIS, anslutning och lösenordsfil)."
    return "PostGIS svarar inte (är `docker compose up -d postgis` igång?)"
