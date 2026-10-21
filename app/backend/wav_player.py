"""Play one WAV synchronously on Windows in a disposable child process.

The speech worker terminates this process to stop playback; no system-wide audio
or unrelated player process is affected. No third-party playback package is needed.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("wav", type=Path)
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        parser.error("this WAV player is for Windows only")
    import winsound

    try:
        winsound.PlaySound(str(args.wav), winsound.SND_FILENAME | winsound.SND_NODEFAULT)
    except (OSError, RuntimeError):
        print("Windows could not play the WAV file; check the file and audio device.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
