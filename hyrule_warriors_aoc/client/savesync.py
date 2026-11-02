"""Keep one seed's save the same in every emulator (Ryujinx and Eden), so a player can switch between them.

Only while no game is running: the newest copy is written over the others (each overwritten file is backed up first).
A copy with fewer story clears than the one it would replace (a New Game) is never written unless forced.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from .savefile import SaveFormatError, check_save, cleared_missions
from .savewatch import save_copies


def emulator_of(path: str) -> str:
    return "Eden" if f"{os.sep}eden{os.sep}" in os.path.normcase(path) else "Ryujinx"


def _newest_time(path: str) -> float:
    return max(os.path.getmtime(p) for p in save_copies(path))


def _clears(data: bytes) -> int:
    try:
        return len(cleared_missions(data))
    except (SaveFormatError, ValueError, IndexError):
        return 0


def sync_saves(paths: list[str], backup_dir: Path, force: bool = False) -> list[str]:
    """paths: one save per emulator, all belonging to the same seed. Writes the newest over the others where they
    differ. Returns what happened, one line each."""
    paths = [p for p in paths if os.path.isfile(p)]
    if len(paths) < 2:
        return []
    src = max(paths, key=_newest_time)
    data = Path(src).read_bytes()
    check_save(data)
    done = []
    for path in paths:
        if path == src:
            continue
        targets = save_copies(path)
        if all(Path(t).read_bytes() == data for t in targets):
            continue
        old = Path(path).read_bytes()
        if not force and _clears(data) < _clears(old):
            done.append(f"Not synced: the {emulator_of(src)} save has fewer story clears ({_clears(data)}) than the "
                        f"{emulator_of(path)} save ({_clears(old)}) - a New Game? Type /sync_saves force to copy it "
                        "anyway.")
            continue
        folder = backup_dir / f"{time.strftime('%Y%m%d_%H%M%S')}_{emulator_of(path)}"
        folder.mkdir(parents=True, exist_ok=True)
        for i, target in enumerate(targets):
            shutil.copy2(target, folder / f"svdt_{i}")
            tmp = target + ".aoc_tmp"
            Path(tmp).write_bytes(data)
            os.replace(tmp, target)
        done.append(f"Save synced: {emulator_of(src)} -> {emulator_of(path)} (old copy kept in {folder})")
    return done
