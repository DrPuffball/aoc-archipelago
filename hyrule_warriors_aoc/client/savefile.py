"""
Read checks out of, and write received items into, the game's save file (``svdt``).

Pure byte logic with no Archipelago imports, so it can be unit-tested on its own. The layout is in
data_save.py. Writing is only safe while the game is closed: the game keeps the whole save in
memory and overwrites the file the next time it saves (see delivery.py).
"""

from __future__ import annotations

import random
import struct

from .. import data_save as L


class SaveFormatError(ValueError):
    pass


def check_save(data: bytes) -> None:
    if len(data) != L.SAVE_SIZE:
        raise SaveFormatError(f"save is {len(data)} bytes, expected {L.SAVE_SIZE}")
    if data[0] != L.SAVE_FORMAT:
        raise SaveFormatError(f"unknown save format 0x{data[0]:02x} (this client knows 0x{L.SAVE_FORMAT:02x}, game v1.4.x)")


def cleared_records(data: bytes) -> set[int]:
    out = set()
    for i in range(L.MISSION_RECORD_COUNT):
        if any(struct.unpack_from("<6I", data, L.MISSION_RECORDS + i * L.MISSION_RECORD_SIZE + 4)):
            out.add(i)
    return out


def cleared_missions(data: bytes) -> set[str]:
    """Names of every mission (story or challenge) the save shows as cleared."""
    records = cleared_records(data)
    return {name for name, ids in L.MISSION_RECORD_IDS.items() if all(i in records for i in ids)}


def completed_quests(data: bytes) -> set[str]:
    """Names of every quest (request: upgrade, service, shop) the save marks done."""
    return {name for name, i in L.QUEST_STATE_IDS.items() if data[L.QUEST_STATE_SAVE + i] == L.QUEST_DONE}


def owned_weapons(data: bytes) -> set[str]:
    """Names of every weapon the save holds at least one copy of."""
    kinds = set()
    for i in range((max(L.HERO_SLOTS.values()) + 1) * L.SAVE_WEAPONS_PER_HERO):
        kind = struct.unpack_from("<H", data, L.SAVE_WEAPONS + i * L.SAVE_WEAPON_RECORD)[0]
        if kind:
            kinds.add(kind)
    return {name for name, ks in L.WEAPON_KINDS.items() if kinds & set(ks)}


# --- reading/writing single fields -------------------------------------------------------

def rupees(data: bytes) -> int:
    return struct.unpack_from("<I", data, L.RUPEES)[0]


def _hero(slot: int) -> int:
    return L.HEROES + slot * L.HERO_SIZE


def hero_unlocked(data: bytes, character: str) -> bool:
    return data[_hero(L.HERO_SLOTS[character]) + L.HERO_UNLOCKED] == 1


def hero_level(data: bytes, character: str) -> int:
    return data[_hero(L.HERO_SLOTS[character]) + L.HERO_LEVEL] + 1


def material(data: bytes, index: int) -> int:
    return struct.unpack_from("<H", data, L.MATERIALS + index * 2)[0]


class SavePatch:
    """Edits a copy of the save. Every method returns a one-line description of what it did."""

    def __init__(self, data: bytes) -> None:
        check_save(data)
        self.data = bytearray(data)

    def add_rupees(self, amount: int) -> str:
        new = min(L.RUPEES_MAX, rupees(self.data) + amount)
        struct.pack_into("<I", self.data, L.RUPEES, new)
        return f"+{amount} rupees (now {new})"

    def add_material(self, index: int, amount: int) -> None:
        new = min(L.MATERIAL_MAX, material(self.data, index) + amount)
        struct.pack_into("<H", self.data, L.MATERIALS + index * 2, new)
        self.data[L.MATERIAL_SEEN + index] = 1  # the editor does this for first-time materials

    def material_bundle(self, seed: int, kinds: int = 3, amount: int = 5) -> str:
        picks = random.Random(seed).sample(L.BUNDLE_MATERIALS, kinds)
        for index in picks:
            self.add_material(index, amount)
        from ..data_materials import MATERIAL_NAMES
        return f"+{amount} each: {', '.join(MATERIAL_NAMES.get(i, f'material {i}') for i in picks)}"

    def hearty_meal(self) -> str:
        for index, amount in L.HEARTY_MEAL.items():
            self.add_material(index, amount)
        return "Hearty Meal: cooking ingredients"

    def level_up(self, characters: list[str]) -> str:
        """+1 level for the lowest-level hero among `characters` that the save has unlocked."""
        known = [c for c in characters if c in L.HERO_SLOTS and hero_unlocked(self.data, c)]
        known = [c for c in known if hero_level(self.data, c) < L.HERO_LEVEL_MAX]
        if not known:
            return "no hero to level up"
        hero = min(known, key=lambda c: (hero_level(self.data, c), c))
        self.set_level(hero, hero_level(self.data, hero) + 1)
        return f"{hero} level {hero_level(self.data, hero)}"

    def set_level(self, character: str, level: int) -> bool:
        """Raise a hero to `level` with the matching XP (never lowers). Returns True if it changed."""
        level = min(level, L.HERO_LEVEL_MAX)
        row = _hero(L.HERO_SLOTS[character])
        if hero_level(self.data, character) >= level:
            return False
        self.data[row + L.HERO_LEVEL] = level - 1
        xp = int.from_bytes(self.data[row + L.HERO_XP_SAVE:row + L.HERO_XP_SAVE + 3], "little")
        xp = max(xp, L.HERO_XP_TABLE[level - 1])
        self.data[row + L.HERO_XP_SAVE:row + L.HERO_XP_SAVE + 3] = xp.to_bytes(3, "little")
        return True

    def unlock_hero(self, character: str) -> str | None:
        """EXPERIMENTAL: sets the unlocked byte only. Returns None if already unlocked or unknown."""
        if character not in L.HERO_SLOTS or hero_unlocked(self.data, character):
            return None
        self.data[_hero(L.HERO_SLOTS[character]) + L.HERO_UNLOCKED] = 1
        return f"unlocked {character}"
