#!/usr/bin/env python3
"""Fetch the Piper voices for reading the log aloud into data/voices/ (not versioned).

Downloads the Swedish voices of app/backend/speech.py from rhasspy/piper-voices on Hugging Face,
checks each model and its config against the SHA-256 pinned here, and keeps each voice's model
card beside it. Both voices are trained on the NST Swedish data of Språkbanken at the National
Library of Norway: nst under CC0, alma under CC BY 4.0 (the satellite monitor shows the credit).

Run once after cloning, and before an exhibition, so the voices work offline. Only the Python
standard library is used.

    .venv/bin/python -m tools.fetch_piper_voices
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

from app.backend.speech import VOICE_DIR, VOICES

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/sv/sv_SE"
SHA256 = {
    "sv_SE-nst-medium.onnx": "df011f56825a59dd1efc080c38a65a1ef70407e60f63050e9246f43a3d7e471e",
    "sv_SE-nst-medium.onnx.json": "d45dd74cbb4eca58694bf04a97e243044092476f28a55ae26424f0653086980a",
    "sv_SE-alma-medium.onnx": "f75455eb6afeb1db9e2905d5bd7e4115afcd3710e0d399b6a40981766d32fedc",
    "sv_SE-alma-medium.onnx.json": "6924380892f769afa92fc6b28ff91d558690d7fb4e3ef8cbf821cefadc8f38fe",
}


def url(voice: str, name: str) -> str:
    return f"{BASE}/{voice}/medium/{name}"


def fetch(address: str) -> bytes:
    with urlopen(Request(address, headers={"User-Agent": "techseed-geospatial-demo"}), timeout=120) as response:
        return response.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=VOICE_DIR, help="where the voices go (default: data/voices)")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    for voice, model in VOICES.items():
        for name in (f"{model}.onnx", f"{model}.onnx.json"):
            target = args.out / name
            if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == SHA256[name]:
                print(f"{name}: finns redan")
                continue
            data = fetch(url(voice, name))
            digest = hashlib.sha256(data).hexdigest()
            if digest != SHA256[name]:
                raise SystemExit(f"{name}: fel kontrollsumma {digest}")
            target.write_bytes(data)
            print(f"{name}: hämtad ({len(data) / 1e6:.1f} MB)")
        (args.out / f"{model}.MODEL_CARD").write_bytes(fetch(url(voice, "MODEL_CARD")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
