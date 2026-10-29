"""Client settings kept between runs (AoC_Archipelago/settings.json): only what the player has to tell the client,
such as where Ryujinx keeps its data when it can't be found automatically."""

from __future__ import annotations

import json
import os
from pathlib import Path

SETTINGS_FILE = Path.home() / "AoC_Archipelago" / "settings.json"


def load_settings() -> dict:
    try:
        return dict(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {}


def save_setting(key: str, value) -> None:
    settings = load_settings()
    settings[key] = value
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=1), encoding="utf-8")
    os.replace(tmp, SETTINGS_FILE)
