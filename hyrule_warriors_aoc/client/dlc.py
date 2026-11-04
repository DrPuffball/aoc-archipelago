"""Is the Expansion Pass installed? Read from the emulator's own records: Ryujinx's games/<title id>/dlc.json, or Eden's
game-list cache (cache/game_list/<title id>.pv.txt, "DLC (3, 3, 4, 4)") minus add-ons turned off in its settings."""
from __future__ import annotations

import json
import os
import re

AOC_TITLE_ID = "01002b00111a2000"
AOC_BASE = 0x01002B00111A2000
DLC_BASE = 0x01002B00111A3000  # DLC n of the game = DLC_BASE + n
# Expansion Pass waves (DLC title ids, as dlc.json stores them: decimal)
DLC_WAVES = {0x01002B00111A3003: "Pulse of the Ancients", 0x01002B00111A3004: "Guardian of Remembrance"}


def ryujinx_data_dirs() -> list[str]:
    """Ryujinx data folders: portable installs of running Ryujinx programs first, then %APPDATA%\\Ryujinx."""
    from .ryujinx import ryujinx_exe_dirs
    dirs = [os.path.join(d, "portable") for d in ryujinx_exe_dirs()]
    if os.environ.get("APPDATA"):
        dirs.append(os.path.join(os.environ["APPDATA"], "Ryujinx"))
    return [d for d in dirs if os.path.isdir(d)]


def enabled_dlc(data_dir: str) -> set[int] | None:
    """DLC title ids enabled for Age of Calamity in this Ryujinx data folder (None: no DLC list there)."""
    path = os.path.join(data_dir, "games", AOC_TITLE_ID, "dlc.json")
    try:
        with open(path, encoding="utf-8") as f:
            entries = json.load(f)
    except (OSError, ValueError):
        return None
    return {int(nca.get("title_id", 0)) for entry in entries if isinstance(entry, dict)
            for nca in entry.get("dlc_nca_list", ()) if isinstance(nca, dict) and nca.get("is_enabled")}


def eden_enabled_dlc(root: str) -> set[int] | None:
    """DLC title ids Eden lists for Age of Calamity (its game-list cache: "DLC (1, 1, 2, 2, 3, 3, 4, 4)", read live
    2026-11-02), unless add-ons named "DLC" are turned off for the game in its settings. None: no cache yet."""
    try:
        with open(os.path.join(root, "cache", "game_list", AOC_TITLE_ID.upper() + ".pv.txt"), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    line = next((ln for ln in text.splitlines() if ln.strip().startswith("DLC")), "")
    found = {DLC_BASE + int(n) for n in re.findall(r"\d+", line)}
    try:
        with open(os.path.join(root, "config", "qt-config.ini"), encoding="utf-8") as f:
            config = f.read()
    except OSError:
        return found
    # [DisabledAddOns]: k\title_id=<decimal id> and k\disabled\i\d=<add-on name>
    keys = re.findall(r"^(\d+)\\title_id=(\d+)\s*$", config, re.M)
    for k, title in keys:
        if int(title) == AOC_BASE and re.search(rf"^{k}\\disabled\\\d+\\d=DLC\s*$", config, re.M):
            return set()  # the game's DLC is turned off in Eden
    return found


def missing_waves(data_dirs: list[str] | None = None, eden_roots: list[str] | None = None) -> list[str] | None:
    """Expansion Pass waves not enabled in the emulator in use; None when it can't tell, including when no single
    emulator is running (another emulator's list says nothing about the one you play on)."""
    from .ryujinx import emulator_processes
    if data_dirs is None and eden_roots is None:
        from .savewatch import eden_data_roots
        running = {name for _, name in emulator_processes()}
        if len(running) != 1:
            return None
        sources = [("Eden", eden_data_roots())] if running == {"Eden"} else [("Ryujinx", ryujinx_data_dirs())]
    else:
        sources = [("Ryujinx", data_dirs or []), ("Eden", eden_roots or [])]
    for emulator, dirs in sources:
        for d in dirs:
            found = enabled_dlc(d) if emulator == "Ryujinx" else eden_enabled_dlc(d)
            if found is not None:
                return [name for tid, name in DLC_WAVES.items() if tid not in found]
    return None
