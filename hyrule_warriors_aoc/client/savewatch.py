"""Detect clears by watching the game's save file (``svdt``) instead of game memory.

The save is a plain, unencrypted 1 MiB file with one record per mission (data_save.py). The game
writes it when it saves (manual save or autosave), not the instant the results screen closes, so
detection waits for that. It needs no hook and survives restarts.
"""
from __future__ import annotations

import glob
import os
from collections.abc import Callable

from ..data import MISSION_NAMES
from ..data_save import QUEST_STATE_IDS, WEAPON_KINDS
from .savefile import SaveFormatError, check_save, cleared_missions, completed_quests

_STORY = set(MISSION_NAMES)


def ryujinx_data_roots() -> list[str]:
    """Where Ryujinx may keep its data: the folder set with /ryujinx_folder, a portable install next to a running
    Ryujinx (<program folder>/portable), and the default user folders."""
    from .ryujinx import ryujinx_exe_dirs
    from .settings import load_settings
    roots = []
    if folder := load_settings().get("ryujinx_folder"):
        roots.append(folder)
    roots += [os.path.join(d, "portable") for d in ryujinx_exe_dirs()]
    roots += [os.path.expandvars(r"%APPDATA%\Ryujinx"), os.path.expanduser("~/.config/Ryujinx")]
    return [r for r in dict.fromkeys(roots) if os.path.isdir(r)]


def find_save_files() -> list[str]:
    """Ryujinx keeps each save in bis/user/save/<id>/0 (committed) and /1 (working copy)."""
    roots = ryujinx_data_roots()
    out = []
    for root in roots:
        for path in glob.glob(os.path.join(root, "bis", "user", "save", "*", "0", "svdt")):
            try:
                with open(path, "rb") as f:
                    check_save(f.read())
                out.append(path)
            except (OSError, SaveFormatError):
                continue
    return out


def save_copies(path: str) -> list[str]:
    """The committed copy plus Ryujinx's working copy next to it, if there is one."""
    folder = os.path.dirname(path)
    other = os.path.join(os.path.dirname(folder), "1" if os.path.basename(folder) == "0" else "0", "svdt")
    return [path] + ([other] if os.path.isfile(other) else [])


def message_for(name: str) -> dict:
    if name in _STORY:
        return {"type": "mission_cleared", "mission": name}
    if name in QUEST_STATE_IDS:
        return {"type": "quest_completed", "quest": name}
    if name in WEAPON_KINDS:
        return {"type": "weapon_obtained", "weapon": name}
    return {"type": "challenge_cleared", "challenge": name}


class SaveWatcher:
    """Polls the save file; ``poll()`` returns client messages for missions cleared since the last read."""

    def __init__(self, path: str, ignore: set[str] | None = None,
                 on_ignore_change: Callable[[set[str]], None] | None = None) -> None:
        self.path = path
        # Clears that were already in the save when this seed started. A mission that later shows as not
        # cleared (a New Game) leaves this set, so clearing it again counts.
        self.ignore = set(ignore or ())
        self.on_ignore_change = on_ignore_change
        self._mtime = 0.0
        self._seen: set[str] | None = None
        self.error = ""

    def read(self) -> set[str] | None:
        try:
            with open(self.path, "rb") as f:
                data = f.read()
            check_save(data)
        except (OSError, SaveFormatError) as e:
            self.error = str(e)
            return None
        self.error = ""
        return cleared_missions(data) | completed_quests(data)

    def poll(self) -> list[dict]:
        try:
            mtime = os.stat(self.path).st_mtime
        except OSError:
            return []
        if mtime == self._mtime:
            return []
        cleared = self.read()
        if cleared is None:
            return []
        self._mtime = mtime
        if self.ignore - cleared:
            self.ignore &= cleared
            if self.on_ignore_change:
                self.on_ignore_change(self.ignore)
        # On the first read everything already cleared is reported (resync after a restart);
        # the client ignores locations it has already checked.
        new = cleared - (self._seen or set()) - self.ignore
        self._seen = cleared
        return [message_for(n) for n in sorted(new)]
