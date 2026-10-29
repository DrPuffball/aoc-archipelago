"""
Korok seed counts, from published guides (two independent pulls agree: 122 in story missions, 12 in
challenges, 134 total). Names are synthetic ("Korok: <mission> #n") because the guides only give counts.
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
    return f"Korok: {source} #{index}"
