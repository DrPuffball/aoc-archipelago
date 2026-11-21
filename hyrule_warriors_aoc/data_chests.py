"""
Treasure chests in story missions (found 2026-11-18 on Eden, Hyrule Field chests, checked against the 100% save).

One byte per chest, 10 slots per story mission in story order (block r = mission r of KOROKS_IN_MISSIONS), 1 = opened.
Save: CHEST_FLAGS_SAVE; live: [P+0x588]+CHEST_FLAGS_LIVE (set the moment the chest opens; the last-saved copy sits
0xE10 later). Counts match the Zelda Dungeon wiki where it gives them (Hyrule Field 5, Akkala Tower 7, Destroy the Yiga
Clan! 8, When Courage Fails 8, Calamity Strikes 9, The Great Plateau 10, All Hyrule, United 10, The Future of Hyrule 8).
Blocks 20-23 belong to the Expansion Pass stages 30-33 (mission parameter table t009cc294 +59 = stage id; EX missions
on story stages share that story mission's chests): mapped 2026-11-18 on Eden by lighting blocks in patterns and reading
the chest icons of each EX mission in the Chapters list [confirmed in game]. EX To Zelda's Side and EX Guardian of
Remembrance share stage 30 and its chests; its slot 4 (set in the 100% save) lights no icon, so it holds no check.
"""

from __future__ import annotations

from .data_koroks import KOROKS_IN_MISSIONS

CHEST_FLAGS_SAVE, CHEST_FLAGS_LIVE, CHEST_BLOCK = 0x2CB4B, 0x3260, 10
CHESTS_IN_MISSIONS: dict[str, int] = {
    "The Battle of Hyrule Field": 5,
    "Road to the Ancient Lab": 6,
    "Mipha, the Zora Princess": 7,
    "Daruk, the Goron Hero": 6,
    "Revali, the Rito Warrior": 8,
    "Urbosa, the Gerudo Chief": 10,
    "The Yiga Clan Attacks!": 8,
    "Freeing Korok Forest": 5,
    "The Road Home, Besieged": 9,
    "Akkala Tower": 7,
    "Destroy the Yiga Clan!": 8,
    "When Courage Fails": 8,
    "Calamity Strikes": 9,
    "Water and Fire": 8,
    "Air and Lightning": 9,
    "Relentless as a Waterfall": 3,
    "Each Step Like Thunder": 9,
    "The Great Plateau": 10,
    "All Hyrule, United": 10,
    "The Future of Hyrule": 8,
}
assert list(CHESTS_IN_MISSIONS) == list(KOROKS_IN_MISSIONS)
assert sum(CHESTS_IN_MISSIONS.values()) == 153
# Expansion Pass chests: mission -> (block, slots); EX To Zelda's Side's chests are EX Guardian of Remembrance's too.
DLC_CHESTS: dict[str, tuple[int, tuple[int, ...]]] = {
    "EX To Zelda's Side": (20, (0, 1, 2, 3, 5, 6)),
    "EX Battle of Goponga Village": (21, (0, 1, 2, 3, 4)),
    "EX Battle for Kakariko Village": (22, (0, 1, 2, 3, 4, 5, 6, 7)),
    "EX The Princess and the King": (23, (0, 1, 2, 3, 4, 5, 6, 7, 8)),
}
SHARED_CHESTS = {"EX To Zelda's Side": "EX Guardian of Remembrance"}  # same stage: either mission reaches them
CHEST_BLOCKS = 24


def chest_flags() -> list[tuple[str, int, int]]:
    """Every chest as (location name, block, slot): story missions, then the Expansion Pass."""
    out = [(chest_location(m, i + 1), r, i) for r, (m, n) in enumerate(CHESTS_IN_MISSIONS.items()) for i in range(n)]
    return out + [(chest_location(m, n + 1), b, s) for m, (b, slots) in DLC_CHESTS.items() for n, s in enumerate(slots)]


def chest_location(mission: str, index: int) -> str:
    return f"Treasure Chest: {mission} #{index}"


# Runes treasure chests may need (0.9.90). Half-buried chests are pulled out with Magnesis and the guides don't say which
# chests are buried, so every chest needs Magnesis. Named in guides (2026-11-18): Remote Bombs for the chest behind
# rocks in Revali (Game8) and behind a cracked wall in Calamity Strikes (Nintendo Life); per mission, as for Koroks.
CHEST_RUNES_ALL: tuple[str, ...] = ("Magnesis",)
CHEST_RUNES: dict[str, tuple[str, ...]] = {
    "Revali, the Rito Warrior": ("Remote Bombs",),
    "Calamity Strikes": ("Remote Bombs",),
}
