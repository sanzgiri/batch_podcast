"""Preset and pronunciation-dict loading.

Presets live in src/lib/tts_engine/data/presets/<name>.json
Pronunciations live in src/lib/tts_engine/data/pronunciations/<name>.json

A pronunciation argument may also be a direct file path (absolute or relative
to CWD), which takes precedence over the bundled dicts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"
PRESETS_DIR = _DATA_DIR / "presets"
PRON_DIR = _DATA_DIR / "pronunciations"


def load_preset(name: str) -> dict:
    """Load a named preset from the bundled presets directory."""
    path = PRESETS_DIR / f"{name}.json"
    if not path.is_file():
        avail = list_presets()
        raise FileNotFoundError(f"unknown preset '{name}'. available: {', '.join(avail)}")
    with open(path) as fh:
        return json.load(fh)


def load_pronunciations(name_or_path: str) -> dict:
    """Load a pronunciation dict by name (bundled) or file path."""
    if os.path.isfile(name_or_path):
        path = Path(name_or_path)
    else:
        path = PRON_DIR / f"{name_or_path}.json"
        if not path.is_file():
            avail = list_pronunciation_dicts()
            raise FileNotFoundError(
                f"no pronunciation file: '{name_or_path}'. available: {', '.join(avail)}"
            )
    with open(path) as fh:
        data = json.load(fh)
    # Drop any _comment-style keys
    return {k: v for k, v in data.items() if not k.startswith("_")}


def list_presets() -> list[str]:
    """List available bundled preset names."""
    if not PRESETS_DIR.is_dir():
        return []
    return sorted(f.stem for f in PRESETS_DIR.iterdir() if f.suffix == ".json")


def list_pronunciation_dicts() -> list[str]:
    """List available bundled pronunciation dict names."""
    if not PRON_DIR.is_dir():
        return []
    return sorted(f.stem for f in PRON_DIR.iterdir() if f.suffix == ".json")
