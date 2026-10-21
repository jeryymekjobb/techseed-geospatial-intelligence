"""Run a separately installed Mosquitto locally without Docker.

python -m tools.start_native_mqtt --mosquitto "C:/Program Files/mosquitto/mosquitto.exe"

The anonymous broker is for simulated booth nodes on this computer only. It binds
to 127.0.0.1, has no persistence and runs until Ctrl+C. Only the child started here
is stopped. Existing services and the Ubuntu Docker configuration are untouched.
--dry-run prints the configuration without starting processes or writing files.
This tool installs nothing; real Windows broker operation is not yet verified.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile


def configuration(port: int) -> str:
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    return (f"listener {port} 127.0.0.1\n"
            "allow_anonymous true\npersistence false\nlog_dest stdout\n")


def command(executable: str, config: Path) -> list[str]:
    return [executable, "-c", str(config)]


def run(executable: str, port: int) -> int:
    config = configuration(port)
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise ValueError(f"Port {port} is already in use; no existing broker was stopped")
    with tempfile.TemporaryDirectory(prefix="techseed-native-mqtt-") as scratch:
        path = Path(scratch) / "mosquitto.conf"
        path.write_text(config, encoding="utf-8")
        child = subprocess.Popen(command(executable, path))
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
    parser.add_argument("--mosquitto", help="Mosquitto executable (default: PATH)")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = configuration(args.port)
        if args.dry_run:
            print(config, end="")
            return 0
        executable = args.mosquitto or shutil.which("mosquitto")
        if not executable:
            raise ValueError("Mosquitto was not found; install it separately or specify --mosquitto")
        print(f"Local simulated-node MQTT broker at 127.0.0.1:{args.port}; Ctrl+C stops only this broker.")
        return run(executable, args.port)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"start_native_mqtt: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
