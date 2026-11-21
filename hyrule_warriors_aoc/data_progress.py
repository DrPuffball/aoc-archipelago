"""
Progress checks (0.9.90, user 2026-11-19; all off by default): hero levels, weapon levels, enemies defeated (trophy
totals) and materials gathered (totals, not what is held now).

Levels: a check per hero every `interval` levels up to `max` ("Hero Level: Link Lv 10"). Weapon levels: a check per hero
when any of their weapons reaches the level ("Weapon Level: Link Lv 10"). The game caps weapon levels at 20, 25 after
A Monumental Undertaking and 30 after The Legendary Blacksmith (data_save), so weapon levels go to 30 at most.

Gathering: thresholds per tier come from how often the game hands each material out (quest costs on GameWith's quest
list, read 2026-11-19: Bokoblin Trophy x100-x500, Lizalfos x50-x300, Moblin x5-x25, Chuchu/Keese up to x35-x50,
Octorok/Pebblit x5-x20, Wizzrobe x1-x10, Guardian x2-x5, Lynel/Hinox/Talus x1-x3; gems x1-x5, Star Fragment x1,
Flint x5-x50; story clears give 10 of each "replay" material, LinkData2 009cba94). A trophy is earned per defeat of its
monster (credited after the battle), so trophy totals count defeats. Names carry the step ("Gathered: Ruby (2)"), the
counts go to slot_data (they scale with the options).
"""

from __future__ import annotations

import struct

from .data_materials import MATERIAL_NAMES

WEAPON_LEVEL_LIMIT = 30  # The Legendary Blacksmith's cap; nothing in the game goes higher
HERO_LEVEL_LIMIT = 100
GATHER_TIERS = 3  # at most this many checks per material / enemy


def hero_level_location(hero: str, level: int) -> str:
    return f"Hero Level: {hero} Lv {level}"


def weapon_level_location(hero: str, level: int) -> str:
    return f"Weapon Level: {hero} Lv {level}"


def gathered_location(material: str, tier: int) -> str:
    return f"Gathered: {material} ({tier})"


def defeated_location(enemy: str, tier: int) -> str:
    return f"Defeated: {enemy} ({tier})"


def level_steps(interval: int, top: int) -> list[int]:
    """The levels that hold checks: every `interval` levels up to `top`, never level 1 (where heroes start)."""
    return [lv for lv in range(interval, top + 1, interval) if lv >= 2]


# --- Enemies: name -> (trophy material index, base counts per tier, source) -----------------------------------------
# Source = where the logic can count on meeting them: "story" (Bokoblins, Moblins, Lizalfos: nearly every mission),
# "guardian" (Akkala Tower on), or a challenge built around them (only when that challenge is in the seed). Enemies
# not seen in story missions yet (UNCONFIRMED_ENEMIES) hold no checks: an enemy that a seed never shows would make its
# check impossible.
# Counts calibrated on a real save (2026-11-19, test seed 95227 after ~5 story missions: Bokoblin 1727, Lizalfos 727,
# Moblin 21, Guardian 21, Keese 18, Octorok 16, Wizzrobe 11, Chuchu 9, Lynel 3; Pebblit, Hinox, Talus, Molduga 0):
# tier 1 is about one or two missions of play, tier 2 about five, tier 3 about twelve.
ENEMIES: dict[str, tuple[int, tuple[int, int, int], str]] = {
    "Bokoblin": (158, (500, 2000, 5000), "story"),
    "Lizalfos": (159, (200, 800, 2000), "story"),
    "Moblin": (156, (10, 30, 75), "story"),
    "Keese": (161, (10, 30, 75), "story"),
    "Octorok": (162, (10, 30, 75), "story"),
    "Chuchu": (160, (5, 20, 50), "story"),
    "Guardian": (151, (10, 30, 75), "guardian"),
    "Wizzrobe": (157, (5, 15, 40), "A Feast for Wizzrobes"),
    "Lynel": (155, (2, 6, 15), "Taming the Savage Lynel"),
    "Molduga": (152, (1, 3, 6), "Molduga Sighting"),
}
ALSO_IN_STORY = {"Wizzrobe", "Lynel"}  # met in story missions too (the save above): the whole story is another way
UNCONFIRMED_ENEMIES = ("Stone Pebblit", "Hinox", "Stone Talus")  # not seen in story missions yet: no checks
# Story-mission gates per tier for the two broad sources (a challenge source gates every tier on that challenge)
SOURCE_GATES = {"story": ("Road to the Ancient Lab", "The Yiga Clan Attacks!", "Akkala Tower"),
                "guardian": ("Akkala Tower", "Calamity Strikes", None)}  # None = the whole story

# --- Materials ------------------------------------------------------------------------------------------------------
RARITY_THRESHOLDS = {
    "common": (20, 60, 150),
    "uncommon": (5, 15, 40),
    "rare": (2, 6, 15),
    "very rare": (1, 3, 8),
}
# Materials that only come from challenges, the Expansion Pass or special sources hold no gathering checks (a Story
# Only seed has none of those), nor do Korok seeds (their own checks) and fairies.
_EXCLUDED = {"Hylian Rice", "Fresh Milk", "Cane Sugar", "Hearty Bass", "Fairy", "Restless Cricket", "Octo Balloon",
             "Monster Extract", "Korok Seed", "Terrako Component", "Ethereal Stone", "Keese Eyeball"}
# Monster parts and ancient parts: dropped by enemies -> (rarity, the enemy whose source gates it). Parts of the
# unconfirmed enemies (Hinox parts) are left out with them.
_DROPS: dict[str, tuple[str, str]] = {
    "Bokoblin Horn": ("common", "Bokoblin"), "Bokoblin Fang": ("common", "Bokoblin"),
    "Bokoblin Guts": ("uncommon", "Bokoblin"),
    "Moblin Horn": ("uncommon", "Moblin"), "Moblin Fang": ("uncommon", "Moblin"), "Moblin Guts": ("rare", "Moblin"),
    "Lizalfos Horn": ("uncommon", "Lizalfos"), "Lizalfos Talon": ("uncommon", "Lizalfos"),
    "Lizalfos Tail": ("uncommon", "Lizalfos"), "Icy Lizalfos Tail": ("rare", "Lizalfos"),
    "Red Lizalfos Tail": ("rare", "Lizalfos"), "Yellow Lizalfos Tail": ("rare", "Lizalfos"),
    "Lynel Horn": ("rare", "Lynel"), "Lynel Hoof": ("rare", "Lynel"), "Lynel Guts": ("very rare", "Lynel"),
    "Molduga Fin": ("rare", "Molduga"), "Molduga Guts": ("very rare", "Molduga"),
    "Ancient Screw": ("uncommon", "Guardian"), "Ancient Spring": ("uncommon", "Guardian"),
    "Ancient Gear": ("uncommon", "Guardian"), "Ancient Shaft": ("rare", "Guardian"),
    "Chuchu Jelly": ("common", "Chuchu"), "White Chuchu Jelly": ("uncommon", "Chuchu"),
    "Red Chuchu Jelly": ("uncommon", "Chuchu"), "Yellow Chuchu Jelly": ("uncommon", "Chuchu"),
    "Keese Wing": ("common", "Keese"), "Ice Keese Wing": ("uncommon", "Keese"),
    "Fire Keese Wing": ("uncommon", "Keese"), "Electric Keese Wing": ("uncommon", "Keese"),
    "Octorok Tentacle": ("uncommon", "Octorok"), "Octorok Eyeball": ("rare", "Octorok"),
}
# Story-reward materials: 10 per replay clear, all "common" (gems and other first-clear-only rewards are left out)
_REWARD_RARITY: dict[str, str] = {}


def _story_reward_sources() -> dict[str, list[str]]:
    """Material -> story missions whose clear gives it again on every replay: the second reward list (10 each;
    LinkData2 009cba94 +0x10/+0x32). The first list is the one-time first-clear reward (gems, a few rare items), so a
    material found only there can't be farmed and holds no gathering check."""
    from .data import MISSIONS
    from .data_mission_rewards import vanilla_row
    from .data_save import MISSION_RECORD_IDS
    out: dict[str, list[str]] = {}
    for m in MISSIONS:
        for rec in MISSION_RECORD_IDS[m.name]:
            row = vanilla_row(rec)
            counts = struct.unpack_from("<5H", row, 0x10)
            ids = list(row[0x32:0x37])
            for i, c in zip(ids, counts):
                name = MATERIAL_NAMES.get(i - 1) if i else None
                if name and c and m.name not in out.setdefault(name, []):
                    out[name].append(m.name)
    return out


REWARD_SOURCES = _story_reward_sources()
TROPHIES = {idx for idx, _, _ in ENEMIES.values()}

# material name -> (index, rarity, gate): gate = ("missions", [story missions]) or ("enemy", enemy name)
MATERIALS: dict[str, tuple[int, str, tuple[str, object]]] = {}
for _idx, _name in sorted(MATERIAL_NAMES.items()):
    if _name.startswith("UNUSED") or "(PotA)" in _name or _idx in TROPHIES or _name in _EXCLUDED:
        continue
    if _name in _DROPS:
        rarity, enemy = _DROPS[_name]
        MATERIALS[_name] = (_idx, rarity, ("enemy", enemy))
    elif _name in REWARD_SOURCES:
        MATERIALS[_name] = (_idx, _REWARD_RARITY.get(_name, "common"), ("missions", REWARD_SOURCES[_name]))


def scaled(base: int, percent: int) -> int:
    """A threshold scaled by the option's percentage (at least 1)."""
    return max(1, round(base * percent / 100))
