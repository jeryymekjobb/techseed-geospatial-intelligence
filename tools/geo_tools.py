"""Run the GDAL and osmium steps of the fetch and build tools in Docker or natively.

Each step is an argument list, such as ["gdalwarp", "-q", ..., "out.tif"], run in a work
directory. `docker` (the default, as on Ubuntu) joins the steps into the same shell script as
before and runs it in a container with the work directory at /data; `native` runs them one by
one from PATH, for example from a conda-forge environment with `gdal` and `osmium-tool` on
Windows without Docker. --tools or TECHSEED_TOOLS chooses. The native route sets the same GDAL
options in the environment and cleans up the same files, in Python instead of `rm -f`.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

TOOLS = ("docker", "native")


def choice(value: str | None = None) -> str:
    value = value or os.environ.get("TECHSEED_TOOLS", "docker")
    if value not in TOOLS:
        raise ValueError(f"Tools must be {' or '.join(TOOLS)} (TECHSEED_TOOLS)")
    return value


def add_argument(parser) -> None:
    parser.add_argument("--tools", choices=TOOLS, help="run GDAL/osmium in Docker (default) or natively from PATH (TECHSEED_TOOLS)")


def shell_script(steps: list[list[str]], cleanup: list[str] = (), directory: str = "/data") -> str:
    """The steps as a shell script for a container, failing at the first error; `cleanup` holds file
    names or patterns removed at the end."""
    lines = ["set -e", f"cd {directory}", *(shlex.join(step) for step in steps)]
    if cleanup:
        lines.append("rm -f " + " ".join(cleanup))
    return "\n".join(lines)


def run_native(steps: list[list[str]], directory: Path, cleanup: list[str] = (),
               environment: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run the steps from PATH in the directory, stopping at the first that fails; the result carries
    that step's exit code and every step's error output, as the container's run would."""
    errors = []
    for step in steps:
        if shutil.which(step[0]) is None:
            return subprocess.CompletedProcess(step, 127, "", "".join(errors) + f"{step[0]}: not found on PATH; install GDAL/osmium "
                                               "(for example from conda-forge) or use --tools docker\n")
        result = subprocess.run(step, cwd=directory, env={**os.environ, **(environment or {})}, capture_output=True, text=True)
        errors.append(result.stderr)
        if result.returncode != 0:
            return subprocess.CompletedProcess(step, result.returncode, result.stdout, "".join(errors))
    for pattern in cleanup:
        for path in Path(directory).glob(pattern):
            if path.is_file():
                path.unlink()
    return subprocess.CompletedProcess(steps[-1] if steps else [], 0, "", "".join(errors))
