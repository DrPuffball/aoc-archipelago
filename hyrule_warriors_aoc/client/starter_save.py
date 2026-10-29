"""
Starter save: skip the forced first mission (The Battle of Hyrule Field with Link and Impa) so a seed can start on
any mission with its own starting heroes.

The template (starter_save.bin, zlib) is a fresh New Game save with only The Battle of Hyrule Field cleared
(build_template); every hero is locked (prepare() unlocks the seed's starting heroes; the client gives every hero a
starter weapon and level-1 stats once the game runs, live_hook.prime_hero). The game loads it with Continue and goes
to the world map, so the opening never runs.

The client switches the save on disk when a seed connects with the game closed (plan_switch): a new seed gets the
starter save, a seed played before gets its own save back, and the save being replaced is parked under the seed it
belongs to (SaveShelf, AoC_Archipelago/saves), so going back to a seed restores its save. A save with progress the
client has never seen with any seed is only replaced by /starter_save. A backup of every replaced save is also kept.
"""

from __future__ import annotations

import os
import pkgutil
import struct
import time
import zlib
from pathlib import Path

from .. import data_save as L
from .savefile import SaveFormatError, check_save, cleared_missions

TEMPLATE_FILE = "starter_save.bin"
# Mission state lists in the save (one byte per mission record): profile list (1 locked, 2 open, 3 cleared) and the
# map-state block (0 locked). Found by matching the early save against the 100% save (RESEARCH session 18).
STATE_LISTS = ((0x2C3B1, 1), (0x3B691, 0))
KEPT_RECORDS = (1,)  # The Battle of Hyrule Field: cleared, or the game replays its opening [confirmed in game]
STORY_HEADER = slice(0x09, 0x90)  # save header (time, progress byte 0x0C) and Table A story flags 0x14-0x8F
RUNE_FLAGS_SAVE = (0x1B, 0x1C)  # Table A: Magnesis, Stasis (Road to the Ancient Lab gives them)
FIRST_MISSION = "The Battle of Hyrule Field"


def build_template(fresh: bytes, played: bytes) -> bytes:
    """The template: a fresh New Game save (made as the opening starts, handoff/saves/09_newgame_prologue_20261028.svdt)
    plus only what makes The Battle of Hyrule Field cleared, taken from a played save
    (08_newgame_after_road_to_lab.svdt): the header (save time, progress byte), the story flags (Table A, with
    Magnesis/Stasis off), Hyrule Field's mission record and its "cleared" map state; every hero locked. Everything else
    (quests, rods, heroes' levels, weapons) is a fresh game's [confirmed in game 2026-10-28: Continue goes to the world
    map, Hyrule Field cleared, no quests done]. A previous template built from the played save alone carried its
    quests and rods over."""
    check_save(fresh)
    check_save(played)
    data = bytearray(fresh)
    data[STORY_HEADER] = played[STORY_HEADER]
    for flag in RUNE_FLAGS_SAVE:
        data[flag] = 0
    size = L.MISSION_RECORD_SIZE
    for record in KEPT_RECORDS:
        data[L.MISSION_RECORDS + record * size:L.MISSION_RECORDS + (record + 1) * size] =             played[L.MISSION_RECORDS + record * size:L.MISSION_RECORDS + (record + 1) * size]
    for offset, locked in STATE_LISTS:
        for record in range(L.MISSION_RECORD_COUNT):
            data[offset + record] = 3 if record in KEPT_RECORDS else locked
    for slot in L.HERO_SLOTS.values():  # prepare() unlocks the seed's starting heroes
        data[L.HEROES + slot * L.HERO_SIZE + L.HERO_UNLOCKED] = 0
    return bytes(data)


def template() -> bytes:
    raw = pkgutil.get_data(__package__, TEMPLATE_FILE)
    if raw is None:
        raise FileNotFoundError(TEMPLATE_FILE)
    data = zlib.decompress(raw)
    check_save(data)
    return data


def prepare(starting_heroes: list[str], open_missions: list[str]) -> bytes:
    """The template for one seed: its starting heroes unlocked, its first mission(s) open on the map (the live client
    keeps all of this in step once the game runs)."""
    data = bytearray(template())
    for hero in starting_heroes:
        if hero in L.HERO_SLOTS:
            data[L.HEROES + L.HERO_SLOTS[hero] * L.HERO_SIZE + L.HERO_UNLOCKED] = 1
    for mission in open_missions:
        record = L.MISSION_RECORD_IDS[mission][0]
        for offset, _ in STATE_LISTS:
            if data[offset + record] != 3:  # never un-clear Hyrule Field
                data[offset + record] = 2
    return bytes(data)


def is_fresh(data: bytes) -> bool:
    """No progress worth keeping: nothing cleared beyond the forced first mission (also how a starter save starts).
    Any seed in progress has more."""
    return cleared_missions(data) <= {FIRST_MISSION}


def plan_switch(me: str, owner: str | None, fresh: bool, have_parked: bool, can_starter: bool,
                force: bool = False) -> tuple[str, bool, str]:
    """What to do with the save on disk when seed `me` connects (the game is closed): (action, park the current save
    first?, why). Actions: "none" (it is already this seed's), "claim" (adopt it as this seed's, nothing written),
    "restore" (this seed's parked save goes back in), "starter" (a new seed's starter save), "refuse".
    Nothing is ever lost: a save with progress is parked under its owner before it is replaced, and an unknown save
    with progress is only replaced by /starter_save (force), parked as "unclaimed"."""
    if owner == me:
        return "none", False, "this save is already this seed's"
    new = "restore" if have_parked else "starter" if can_starter else None
    if owner is None:
        if fresh:
            return new or "claim", False, "a fresh save"
        if force and new:
            return new, True, "forced (the old save is parked as unclaimed)"
        if can_starter or have_parked:
            return "refuse", False, ("the save holds progress from a game the client hasn't seen with any seed; "
                                     "connect that game's seed once to claim it, or type /starter_save to set it "
                                     "aside")
        return "claim", False, "the save this seed is played on"
    if new:
        return new, True, f"switching from seed {owner} (its save is kept and comes back when you connect it again)"
    return "refuse", False, f"the save belongs to seed {owner} and this seed has no save of its own to switch to"


class SaveShelf:
    """Which seed each save file belongs to, and every seed's save while another seed uses the file
    (AoC_Archipelago/saves). A seed is its ledger name (seed_slot)."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.owners_file = folder / "owners.json"

    def owners(self) -> dict[str, str]:
        try:
            import json
            return dict(json.loads(self.owners_file.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return {}

    def owner(self, path: str) -> str | None:
        return self.owners().get(os.path.normcase(path))

    def set_owner(self, path: str, seed: str) -> None:
        import json
        owners = self.owners()
        owners[os.path.normcase(path)] = seed
        self.folder.mkdir(parents=True, exist_ok=True)
        tmp = self.owners_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(owners, indent=1), encoding="utf-8")
        os.replace(tmp, self.owners_file)

    def parked_file(self, seed: str) -> Path:
        return self.folder / f"{seed}.svdt"

    def has_parked(self, seed: str) -> bool:
        return self.parked_file(seed).is_file()

    def park(self, seed: str, data: bytes) -> Path:
        self.folder.mkdir(parents=True, exist_ok=True)
        target = self.parked_file(seed)
        if target.is_file():  # the one parked before stays as a backup
            target.replace(target.with_name(f"{seed}.{time.strftime('%Y%m%d_%H%M%S')}.svdt"))
        target.write_bytes(data)
        return target

    def take(self, seed: str) -> bytes:
        """This seed's parked save (kept on the shelf as a copy until the next park)."""
        data = self.parked_file(seed).read_bytes()
        check_save(data)
        return data


def install(save_path: str, copies: list[str], data: bytes, backups: Path) -> None:
    """Replace the save (every Ryujinx copy), keeping a backup of what was there."""
    backups.mkdir(parents=True, exist_ok=True)
    with open(save_path, "rb") as f:
        (backups / f"svdt_before_starter_{time.strftime('%Y%m%d_%H%M%S')}").write_bytes(f.read())
    for path in copies:
        tmp = path + ".aptmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
