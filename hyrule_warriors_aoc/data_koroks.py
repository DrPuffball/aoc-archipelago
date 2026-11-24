"""
Korok seed counts, from published guides (two independent pulls agree: 122 in story missions, 12 in
challenges, 134 total). Names are synthetic ("Korok Seed: <mission> #n") because the guides only give counts.
"""

from __future__ import annotations

KOROKS_IN_MISSIONS: dict[str, int] = {
    "The Battle of Hyrule Field": 7,
    "Road to the Ancient Lab": 6,
    "Mipha, the Zora Princess": 4,
    "Daruk, the Goron Hero": 8,
    "Revali, the Rito Warrior": 8,
    "Urbosa, the Gerudo Chief": 9,
    "The Yiga Clan Attacks!": 8,
    "Freeing Korok Forest": 10,
    "The Road Home, Besieged": 3,
    "Akkala Tower": 5,
    "Destroy the Yiga Clan!": 8,
    "When Courage Fails": 5,
    "Calamity Strikes": 7,
    "Water and Fire": 3,
    "Air and Lightning": 5,
    "Relentless as a Waterfall": 6,
    "Each Step Like Thunder": 4,
    "The Great Plateau": 7,
    "All Hyrule, United": 6,
    "The Future of Hyrule": 3,
}

KOROKS_IN_CHALLENGES: dict[str, int] = {
    "Mipha's Training": 1,
    "Cross the Hebra Mountains": 1,
    "Anti-Ice Training: II": 1,
    "Innkeeper's Request": 1,
    "Winged Escort": 1,
    "Defend Zora's Domain": 1,
    "Elemental Uproar": 2,
    "Polishing His Technique": 1,
    "Hair-Width Trial: Expert+": 1,
    "Hunting Partners": 1,
    "Defend Hyrule Castle": 1,
}

assert sum(KOROKS_IN_MISSIONS.values()) == 122
assert sum(KOROKS_IN_CHALLENGES.values()) == 12


def korok_location(source: str, index: int) -> str:
    return f"Korok Seed: {source} #{index}"


# Where the game keeps each Korok seed (found 2026-11-18 on Eden, Hyrule Field pickups, checked against the 100% save):
# one byte per seed, 20 slots per story mission in story order (block r = KOROKS_IN_MISSIONS entry r), 1 = found.
# Save: KOROK_FLAGS_SAVE; live: [P+0x560]+KOROK_FLAGS_LIVE (the last-saved copy sits 0x2550 later). Slots of each
# mission's seeds are the ones the 100% save has set; seed #n of a mission is its n-th slot. Block 20 (after the 20
# story blocks) holds the 12 challenge seeds: CHALLENGE_KOROK_SLOTS, mapped 2026-11-18 on Eden by lighting the slots in
# binary patterns and reading each challenge's Korok icons in the Challenges list [confirmed in game].
KOROK_FLAGS_SAVE, KOROK_FLAGS_LIVE, KOROK_BLOCK = 0x8DD, 0x5B2, 20
KOROK_SLOTS: dict[str, tuple[int, ...]] = {
    "The Battle of Hyrule Field": (0, 1, 2, 3, 4, 5, 6),
    "Road to the Ancient Lab": (0, 1, 2, 3, 5, 6),
    "Mipha, the Zora Princess": (0, 2, 3, 5),
    "Daruk, the Goron Hero": (0, 1, 2, 3, 4, 5, 6, 7),
    "Revali, the Rito Warrior": (1, 2, 3, 4, 5, 6, 7, 8),
    "Urbosa, the Gerudo Chief": (0, 1, 2, 3, 4, 5, 6, 7, 8),
    "The Yiga Clan Attacks!": (0, 1, 2, 3, 5, 6, 7, 8),
    "Freeing Korok Forest": (0, 1, 2, 3, 4, 5, 6, 10, 11, 13),
    "The Road Home, Besieged": (0, 2, 3),
    "Akkala Tower": (0, 1, 2, 3, 4),
    "Destroy the Yiga Clan!": (0, 1, 2, 3, 4, 5, 6, 7),
    "When Courage Fails": (0, 1, 3, 4, 5),
    "Calamity Strikes": (0, 1, 2, 3, 4, 5, 6),
    "Water and Fire": (0, 3, 5),
    "Air and Lightning": (0, 3, 4, 5, 6),
    "Relentless as a Waterfall": (0, 1, 2, 3, 4, 5),
    "Each Step Like Thunder": (0, 1, 2, 3),
    "The Great Plateau": (0, 2, 3, 4, 5, 6, 7),
    "All Hyrule, United": (0, 1, 2, 3, 4, 5),
    "The Future of Hyrule": (0, 1, 2),
}
assert all(len(KOROK_SLOTS[m]) == n for m, n in KOROKS_IN_MISSIONS.items())
CHALLENGE_KOROK_BLOCK = 20
CHALLENGE_KOROK_SLOTS: dict[str, tuple[int, ...]] = {
    "Innkeeper's Request": (0,),
    "Mipha's Training": (1,),
    "Anti-Ice Training: II": (2,),
    "Defend Zora's Domain": (3,),
    "Elemental Uproar": (4, 5),
    "Polishing His Technique": (6,),
    "Winged Escort": (7,),
    "Cross the Hebra Mountains": (8,),
    "Hunting Partners": (9,),
    "Hair-Width Trial: Expert+": (10,),
    "Defend Hyrule Castle": (11,),
}
assert all(len(CHALLENGE_KOROK_SLOTS[c]) == n for c, n in KOROKS_IN_CHALLENGES.items())


def korok_flags() -> list[tuple[str, int, int]]:
    """Every Korok seed as (location name, block, slot): story missions, then challenges."""
    out = [(korok_location(m, n + 1), r, s) for r, (m, slots) in enumerate(KOROK_SLOTS.items()) for n, s in enumerate(slots)]
    return out + [(korok_location(c, n + 1), CHALLENGE_KOROK_BLOCK, s)
                  for c, slots in CHALLENGE_KOROK_SLOTS.items() for n, s in enumerate(slots)]


# The rune each Korok seed needs, by (mission or challenge, number) [game data 2026-11-23: the Korok table, LinkData2 entry
# 3878, row 20 * mission + slot + 1: kind 15 = moving target (Stasis), 0 = under a bomb rock; the seeds behind cracked
# walls (Calamity Strikes, Defend Hyrule Castle) by position]. Every other kind (stump, pinwheel, flower, still balloon,
# light, crate) needs none.
KOROK_RUNES: dict[tuple[str, int], tuple[str, ...]] = {
    ("Revali, the Rito Warrior", 7): ("Stasis",),
    ("Revali, the Rito Warrior", 8): ("Remote Bombs",),
    ("Urbosa, the Gerudo Chief", 7): ("Stasis",),
    ("Urbosa, the Gerudo Chief", 9): ("Remote Bombs",),
    ("The Road Home, Besieged", 3): ("Remote Bombs",),
    ("Destroy the Yiga Clan!", 2): ("Stasis",),
    ("When Courage Fails", 1): ("Stasis",),
    ("Calamity Strikes", 5): ("Remote Bombs",),
    ("Water and Fire", 2): ("Stasis",),
    ("Air and Lightning", 4): ("Stasis",),
    ("Air and Lightning", 5): ("Remote Bombs",),
    ("The Great Plateau", 7): ("Remote Bombs",),
    ("All Hyrule, United", 6): ("Stasis",),
    ("Defend Hyrule Castle", 1): ("Remote Bombs",),
}
