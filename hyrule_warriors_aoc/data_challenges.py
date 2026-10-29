"""
Challenge missions: 197 from published guides + 15 more found in the game text = 212 (names verified against the dump).

Format of CHALLENGE_TABLE: one line per challenge, "section | name | restrictions".
  section       Level band from the in-game list (1 = Lv1-10 ... 10 = Lv91-100, 11 = Divine Beast
                Battles, 12 = DLC Vicious Monster Battles).
  restrictions  Optional, ';'-separated:
                  only=<Character>      only that character may be used (needs that character)
                  needs=<Character>     that character must be in the party
                  without=<Character>   that character is unavailable (no logic effect: any 4 characters work)
                A '~' before '=' (only~=) means the restriction is INFERRED from the "X's Training" naming
                pattern rather than seen in a guide, and should be verified.

Unlock conditions for challenges were not given in any source we could read. Logic therefore uses
the level-band gates in LEVEL_BAND_GATES, with a safe default (see options.ChallengeLogic).
"""

from __future__ import annotations

from typing import NamedTuple


class Challenge(NamedTuple):
    name: str
    band: int
    only: tuple[str, ...] = ()
    needs: tuple[str, ...] = ()
    inferred: bool = False

    @property
    def is_ex(self) -> bool:
        return self.name.startswith("EX ") or self.band == 12

    @property
    def required_characters(self) -> tuple[str, ...]:
        return self.only + self.needs


CHALLENGE_TABLE = """
1 | Mastering Remote Bombs
1 | Daruk's Training | only=Daruk
1 | Urbosa's Training | only=Urbosa
1 | Lizalfos Infestation
1 | EX Link: Flails | only=Link
1 | EX Zelda: Master Cycle | only=Zelda
1 | Mipha's Training | only=Mipha
1 | Revali's Training | only=Revali
1 | Explosive—Handle With Care
1 | Mastering Cryonis
1 | Anti-Flame Training: I
1 | Anti-Lightning Training: I
1 | Anti-Ice Training: I
1 | Link: One-Handed Weapons | only=Link
1 | Link: Two-Handed Weapons | only=Link
1 | Link: Spears | only=Link
1 | Mastering Magnesis
2 | Leave None Behind
2 | Zelda's Training | only=Zelda
2 | Mastering Stasis
2 | Daily Drills: Rito
2 | Impa's Training | only=Impa
2 | Hair-Width Trial: Beginner
2 | The Breach of Demise
2 | Cross the Hebra Mountains
2 | Cross the Volcano
3 | Daily Drills: Zora
3 | Daily Drills: Goron
3 | Fish Out of Water
3 | Hestu's Training | only=Hestu
3 | Great Fairy Training | only=Great Fairies
3 | Messenger's Escort
3 | Through the Desert
3 | Anti-Ice Training: II
3 | Innkeeper's Request
3 | Swift Spear of the Zora | only=Mipha
3 | Fairy Fountain: Grassy Plains
3 | Mountain Rescue
3 | Echoing Footsteps
3 | Anti-Flame Training: II
3 | Daily Drills: Hyrule
3 | Fierce Gale of the Rito | only=Revali
3 | Mighty Thunder of the Gerudo | needs=Urbosa
3 | Outpost Defenders
3 | Fairy Fountain: Deep Snows
3 | Anti-Lightning Training: II
3 | The Royal Escort | only=Link
3 | Daily Drills: Gerudo
3 | Strike It Rich
3 | Molduga Sighting
3 | Tough Bulwark of the Gorons | needs=Daruk
3 | Fairy Fountain: Desert Sands
3 | Hair-Width Trial: Intermediate
3 | Fairy Fountain: Battlefield
3 | Coliseum: Beginner
4 | Monk's Training | only~=Monk Maz Koshia
4 | A Feast for Wizzrobes
4 | Defend the Sands!
4 | Escape the Lost Woods
4 | Win Back the Mighty Bananas!
4 | A Show of Strength
4 | Chief-of-the-Dunes Battle
4 | Fruit for the Princess!
4 | In the Clutches of the Yiga!
4 | Trial of the Ancients
4 | Territorial Battle
4 | Stronger Yet
4 | Coliseum: Intermediate
4 | Teba's Training | only~=Teba
4 | Riju's Training | only~=Riju
5 | Anti-Flame Training: III
5 | Anti-Lightning Training: III
5 | Sidon's Training | only~=Sidon
5 | Yunobo's Training | only~=Yunobo
5 | Fleeing the Weather
5 | Forest Dance Festival
5 | Anti-Ice Training: III
5 | The Chief-in-Training
5 | Winged Escort
5 | Anti-Flame & Lightning Training
5 | Anti-Ice & Lightning Training
5 | Escorting the Injured
5 | Prince's Escort
5 | Like Grains of Sand
5 | Anti-Flame & Ice Training
5 | The So-Called Knight
5 | Apprentice Yunobo
5 | Questionable Escort Mission
5 | Zelda's Training: Bows | only~=Zelda
5 | Lost Treasures
5 | Defend Zora's Domain
5 | Fire Hazards
5 | Master Kohga's Training | only~=Master Kohga
5 | Generational Conflict
5 | Elemental Uproar
5 | Impa's Damage Control
5 | Fight Lightning with Lightning
5 | Defend the Spring of Courage
5 | A Hidden Treasure
5 | King Rhoam's Training | only~=King Rhoam
5 | Nap Quest!
5 | Sidon vs. the Octoroks
5 | Anti-Element Training
5 | Goron-Style Barbecue
5 | EX Road to Akkala Citadel
6 | Wisdom of the Storm
6 | Hero of the Rito
6 | King's Escort
6 | Sibling Bonds
6 | Hunting for Gemstones
6 | EX Purah & Robbie's Study
6 | Polishing His Technique
6 | Defend Akkala Citadel
6 | EX Sooga's Training | only~=Sooga
6 | Hair-Width Trial: Expert
6 | Reclaim the Land
6 | The Guardians Counterattack
6 | Gerudo Fury
6 | EX Ancient Threats
6 | Coliseum: Expert
6 | Footsteps of the Giant
6 | Zora Mettle
6 | Rito Discipline
6 | Terrako's Training | only~=Terrako
6 | Ganon's Training | only~=Calamity Ganon
6 | Invading Terrors
6 | Hair-Width Trial: Expert+
6 | Taming the Savage Lynel
6 | The Master Kohga Chronicles!
6 | Goron Spirit
6 | EX Battle-Tested Guardian Training
6 | EX Request from the Lab
6 | Rampaging Malice
6 | Hunting Partners
6 | Defend Hyrule Castle
6 | EX Purah & Robbie's Training | only~=Purah & Robbie
6 | EX The Knight's Nightmare
6 | EX Zelda's Culinary Research
6 | Shadow of Ganon
6 | Guardian Graveyard
7 | A Royal Investigation
7 | Hyrule's Greatest Warrior
7 | Guardian Showdown
7 | Heart's Escort
7 | Harbingers of the Calamity
7 | EX Sooga's Daily Routine
7 | Miss Vai Battle Pageant
7 | Defeating Destiny
7 | EX Evacuating Hyrule
7 | Blight Ganons Resurgent
7 | Deep Woods, Deep Shadow
7 | Remnants of the Calamity
7 | Hold the Line
7 | True Strength
7 | Mysterious Arrivals
7 | Versus Astor
7 | Versus Harbinger Ganon
7 | EX The Budget Battle
8 | Versus Calamity Ganon
8 | The Fiercest of Foes
8 | EX Conquering Hyrule
8 | The Heart of the Calamity
8 | The Siege of Fort Hateno
8 | EX A Moblin Feast
8 | Unnatural Disaster
9 | EX Battle Research: Skills
9 | EX Battle Research: Items
9 | EX Coliseum: Master
9 | EX Handle the Horde
9 | EX Rupee Rescue
9 | EX Survival of the Fittest
9 | EX Utmost Strength
10 | EX The Final Battle
10 | EX Facing Mutated Ganon
11 | Might of a Divine Beast
11 | Volcanic Defense
11 | Protector of the Forest
11 | Pursue the Yiga Clan!
11 | Defending Cephla Lake
11 | Volcanic Might
11 | Like the Wind
11 | Two Chiefs
11 | Molduga Deluge
11 | The Power of Three
11 | A Fiery Reckoning
11 | Through the Storm
12 | EX Alert: Hyrule Field
12 | EX Alert: Hyrule Outpost
12 | EX Alert: Great Hyrule Forest
12 | EX Alert: Akkala Citadel
12 | EX Alert: Breach of Demise
12 | EX Alert: Crenel Peak
12 | EX Alert: Goponga Village
12 | EX Alert: Mount Daphnes
12 | EX Alert: Kakariko Village
12 | EX Alert: Lanayru Road
12 | EX Alert: Forgotten Temple
# Found in the game's own mission text (dump v1); bands are conservative guesses (None-gate bands unlock after the story).
1 | Meditative Training | only~=Zelda
9 | Molduking Sighting
9 | Igneo Talus Titan Sighting
9 | The Last Light You See
11 | A Tidal Wave of Foes
11 | A Shield Forged in Iron
11 | Swift as Thought
12 | EX To Zelda's Side
12 | EX Battle of Goponga Village
12 | EX Battle for Kakariko Village
12 | EX Searching Hyrule Forest
12 | EX Liberate the Ancient Lab
12 | EX The Princess and the King
12 | EX The Yiga Clan's Retreat
12 | EX Guardian of Remembrance
"""


# Heroes each challenge puts in the party, read from the game's own mission parameter table (record bytes +71..+74;
# see data_save.py). Merged into `needs` below, so logic never expects a challenge before its heroes arrive.
GAME_PARTY: dict[str, tuple[str, ...]] = {
    "Daruk's Training": ('Daruk',),
    "Urbosa's Training": ('Urbosa',),
    'EX Link: Flails': ('Link',),
    'EX Zelda: Master Cycle': ('Zelda',),
    "Mipha's Training": ('Mipha',),
    "Revali's Training": ('Revali',),
    'Link: One-Handed Weapons': ('Link',),
    'Link: Two-Handed Weapons': ('Link',),
    'Link: Spears': ('Link',),
    "Zelda's Training": ('Zelda',),
    "Impa's Training": ('Impa',),
    "Hestu's Training": ('Hestu',),
    'Great Fairy Training': ('Great Fairies',),
    'Swift Spear of the Zora': ('Mipha',),
    'Fierce Gale of the Rito': ('Revali',),
    'Mighty Thunder of the Gerudo': ('Urbosa',),
    'The Royal Escort': ('Link',),
    'Tough Bulwark of the Gorons': ('Daruk',),
    "Monk's Training": ('Monk Maz Koshia',),
    'Fruit for the Princess!': ('Impa', 'Link'),
    "Teba's Training": ('Teba',),
    "Riju's Training": ('Riju',),
    "Sidon's Training": ('Sidon',),
    "Yunobo's Training": ('Yunobo',),
    'The Chief-in-Training': ('Riju',),
    'Winged Escort': ('Teba',),
    'Escorting the Injured': ('Sidon',),
    'The So-Called Knight': ('Link',),
    'Apprentice Yunobo': ('Daruk', 'Yunobo'),
    "Zelda's Training: Bows": ('Zelda',),
    "Master Kohga's Training": ('Master Kohga',),
    'Generational Conflict': ('Riju', 'Sidon', 'Teba', 'Yunobo'),
    "Impa's Damage Control": ('Impa',),
    'Fight Lightning with Lightning': ('Riju',),
    "King Rhoam's Training": ('King Rhoam',),
    'Nap Quest!': ('Master Kohga',),
    'Sidon vs. the Octoroks': ('Sidon',),
    'Wisdom of the Storm': ('Urbosa',),
    'Hero of the Rito': ('Teba',),
    'Sibling Bonds': ('Mipha', 'Sidon'),
    'Polishing His Technique': ('Yunobo',),
    "EX Sooga's Training": ('Sooga',),
    'Gerudo Fury': ('Riju', 'Urbosa'),
    'Zora Mettle': ('Mipha', 'Sidon'),
    'Rito Discipline': ('Revali', 'Teba'),
    "Terrako's Training": ('Terrako',),
    "Ganon's Training": ('Calamity Ganon',),
    'Invading Terrors': ('Mipha',),
    'The Master Kohga Chronicles!': ('Impa', 'Master Kohga'),
    'Goron Spirit': ('Daruk', 'Yunobo'),
    'Rampaging Malice': ('Daruk',),
    'Hunting Partners': ('Hestu', 'Revali'),
    "EX Purah & Robbie's Training": ('Purah & Robbie',),
    'Shadow of Ganon': ('Link', 'Urbosa'),
    'Guardian Graveyard': ('King Rhoam',),
    'A Royal Investigation': ('Zelda',),
    'Guardian Showdown': ('Terrako',),
    "Heart's Escort": ('Mipha',),
    "EX Sooga's Daily Routine": ('Sooga',),
    'EX Evacuating Hyrule': ('Impa', 'Link', 'Zelda'),
    'EX The Budget Battle': ('Purah & Robbie', 'Terrako'),
    'Defending Cephla Lake': ('Sidon',),
    "EX To Zelda's Side": ('Terrako',),
    'EX Battle of Goponga Village': ('Mipha', 'Sidon'),
    'EX Battle for Kakariko Village': ('Daruk', 'Yunobo'),
    'EX Searching Hyrule Forest': ('Revali', 'Teba'),
    'EX Liberate the Ancient Lab': ('Riju', 'Urbosa'),
    'EX The Princess and the King': ('King Rhoam',),
    "EX The Yiga Clan's Retreat": ('Master Kohga', 'Sooga'),
    'EX Guardian of Remembrance': ('Terrako', 'Zelda'),
}


def _parse() -> list[Challenge]:
    challenges: list[Challenge] = []
    for line in CHALLENGE_TABLE.strip().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        band, name = int(parts[0]), parts[1]
        only: list[str] = []
        needs: list[str] = []
        inferred = False
        for restriction in parts[2:]:
            for token in restriction.split(";"):
                token = token.strip()
                if not token:
                    continue
                key, _, value = token.partition("=")
                if key.endswith("~"):
                    inferred = True
                    key = key[:-1]
                if key == "only":
                    only.append(value)
                elif key == "needs":
                    needs.append(value)
                elif key == "without":
                    pass  # no logic effect: the player always has several characters
                else:
                    raise ValueError(f"bad restriction {token!r} in {line!r}")
        needs += [h for h in GAME_PARTY.get(name, ()) if h not in only and h not in needs]
        challenges.append(Challenge(name, band, tuple(only), tuple(needs), inferred))
    return challenges


CHALLENGES: list[Challenge] = _parse()
CHALLENGE_BY_NAME = {c.name: c for c in CHALLENGES}

assert len(CHALLENGES) == 212, len(CHALLENGES)
assert len(CHALLENGE_BY_NAME) == 212, "duplicate challenge names"
assert sum(1 for c in CHALLENGES if c.is_ex) == 25 + 11 + 8


# Recommended level of each mission as the game stores it (mission parameter table byte +64; roughly the displayed
# level / 2). Used by challenge_logic: by_level to gate each challenge behind the first story mission of at least
# its level. 0 = not set in the data (falls back to the challenge's band).
GAME_LEVEL: dict[str, int] = {
    'Mastering Remote Bombs': 1,
    "Daruk's Training": 1,
    "Urbosa's Training": 1,
    'Lizalfos Infestation': 1,
    'EX Link: Flails': 2,
    'EX Zelda: Master Cycle': 2,
    "Mipha's Training": 1,
    "Revali's Training": 1,
    'Explosive—Handle With Care': 1,
    'Mastering Cryonis': 2,
    'Anti-Flame Training: I': 3,
    'Anti-Lightning Training: I': 3,
    'Anti-Ice Training: I': 3,
    'Link: One-Handed Weapons': 1,
    'Link: Two-Handed Weapons': 3,
    'Link: Spears': 3,
    'Mastering Magnesis': 3,
    'Leave None Behind': 4,
    "Zelda's Training": 1,
    'Mastering Stasis': 5,
    'Daily Drills: Rito': 5,
    "Impa's Training": 1,
    'Hair-Width Trial: Beginner': 6,
    'The Breach of Demise': 6,
    'Cross the Hebra Mountains': 6,
    'Cross the Volcano': 7,
    'Daily Drills: Zora': 9,
    'Daily Drills: Goron': 9,
    'Fish Out of Water': 10,
    "Hestu's Training": 10,
    'Great Fairy Training': 11,
    "Messenger's Escort": 11,
    'Through the Desert': 11,
    'Anti-Ice Training: II': 12,
    "Innkeeper's Request": 12,
    'Swift Spear of the Zora': 12,
    'Fairy Fountain: Grassy Plains': 12,
    'Mountain Rescue': 12,
    'Echoing Footsteps': 12,
    'Anti-Flame Training: II': 12,
    'Daily Drills: Hyrule': 12,
    'Fierce Gale of the Rito': 12,
    'Mighty Thunder of the Gerudo': 12,
    'Outpost Defenders': 12,
    'Fairy Fountain: Deep Snows': 12,
    'Anti-Lightning Training: II': 13,
    'The Royal Escort': 13,
    'Daily Drills: Gerudo': 13,
    'Strike It Rich': 13,
    'Molduga Sighting': 13,
    'Tough Bulwark of the Gorons': 13,
    'Fairy Fountain: Desert Sands': 13,
    'Hair-Width Trial: Intermediate': 14,
    'Fairy Fountain: Battlefield': 14,
    'Coliseum: Beginner': 14,
    "Monk's Training": 16,
    'A Feast for Wizzrobes': 16,
    'Defend the Sands!': 16,
    'Escape the Lost Woods': 17,
    'Win Back the Mighty Bananas!': 17,
    'A Show of Strength': 17,
    'Chief-of-the-Dunes Battle': 18,
    'Fruit for the Princess!': 18,
    'In the Clutches of the Yiga!': 18,
    'Trial of the Ancients': 18,
    'Territorial Battle': 19,
    'Stronger Yet': 19,
    'Coliseum: Intermediate': 19,
    "Teba's Training": 19,
    "Riju's Training": 19,
    'Anti-Flame Training: III': 20,
    'Anti-Lightning Training: III': 20,
    "Sidon's Training": 20,
    "Yunobo's Training": 20,
    'Fleeing the Weather': 20,
    'Forest Dance Festival': 20,
    'Anti-Ice Training: III': 20,
    'The Chief-in-Training': 20,
    'Winged Escort': 21,
    'Anti-Flame & Lightning Training': 21,
    'Anti-Ice & Lightning Training': 21,
    'Escorting the Injured': 21,
    "Prince's Escort": 21,
    'Like Grains of Sand': 21,
    'Anti-Flame & Ice Training': 22,
    'The So-Called Knight': 22,
    'Apprentice Yunobo': 22,
    'Questionable Escort Mission': 22,
    "Zelda's Training: Bows": 22,
    'Lost Treasures': 22,
    "Defend Zora's Domain": 22,
    'Fire Hazards': 22,
    "Master Kohga's Training": 23,
    'Generational Conflict': 23,
    'Elemental Uproar': 23,
    "Impa's Damage Control": 24,
    'Fight Lightning with Lightning': 24,
    'Defend the Spring of Courage': 24,
    'A Hidden Treasure': 23,
    "King Rhoam's Training": 24,
    'Nap Quest!': 24,
    'Sidon vs. the Octoroks': 24,
    'Anti-Element Training': 24,
    'Goron-Style Barbecue': 24,
    'EX Road to Akkala Citadel': 24,
    'Wisdom of the Storm': 26,
    'Hero of the Rito': 26,
    "King's Escort": 26,
    'Sibling Bonds': 26,
    'Hunting for Gemstones': 26,
    "EX Purah & Robbie's Study": 26,
    'Polishing His Technique': 27,
    'Defend Akkala Citadel': 26,
    "EX Sooga's Training": 20,
    'Hair-Width Trial: Expert': 26,
    'Reclaim the Land': 27,
    'The Guardians Counterattack': 27,
    'Gerudo Fury': 28,
    'EX Ancient Threats': 19,
    'Coliseum: Expert': 27,
    'Footsteps of the Giant': 28,
    'Zora Mettle': 27,
    'Rito Discipline': 28,
    "Terrako's Training": 22,
    "Ganon's Training": 29,
    'Invading Terrors': 28,
    'Hair-Width Trial: Expert+': 28,
    'Taming the Savage Lynel': 29,
    'The Master Kohga Chronicles!': 28,
    'Goron Spirit': 28,
    'EX Battle-Tested Guardian Training': 22,
    'EX Request from the Lab': 28,
    'Rampaging Malice': 28,
    'Hunting Partners': 28,
    'Defend Hyrule Castle': 29,
    "EX Purah & Robbie's Training": 22,
    "EX The Knight's Nightmare": 29,
    "EX Zelda's Culinary Research": 29,
    'Shadow of Ganon': 29,
    'Guardian Graveyard': 29,
    'A Royal Investigation': 30,
    "Hyrule's Greatest Warrior": 31,
    'Guardian Showdown': 31,
    "Heart's Escort": 31,
    'Harbingers of the Calamity': 31,
    "EX Sooga's Daily Routine": 32,
    'Miss Vai Battle Pageant': 32,
    'Defeating Destiny': 32,
    'EX Evacuating Hyrule': 31,
    'Blight Ganons Resurgent': 33,
    'Deep Woods, Deep Shadow': 33,
    'Remnants of the Calamity': 33,
    'Hold the Line': 33,
    'True Strength': 34,
    'Mysterious Arrivals': 34,
    'Versus Astor': 34,
    'Versus Harbinger Ganon': 34,
    'EX The Budget Battle': 36,
    'Versus Calamity Ganon': 36,
    'The Fiercest of Foes': 37,
    'EX Conquering Hyrule': 36,
    'The Heart of the Calamity': 38,
    'The Siege of Fort Hateno': 38,
    'EX A Moblin Feast': 38,
    'Unnatural Disaster': 39,
    'EX Battle Research: Skills': 41,
    'EX Battle Research: Items': 41,
    'EX Coliseum: Master': 42,
    'EX Handle the Horde': 42,
    'EX Rupee Rescue': 42,
    'EX Survival of the Fittest': 43,
    'EX Utmost Strength': 44,
    'EX The Final Battle': 46,
    'EX Facing Mutated Ganon': 49,
    'Might of a Divine Beast': 6,
    'Volcanic Defense': 6,
    'Protector of the Forest': 9,
    'Pursue the Yiga Clan!': 11,
    'Defending Cephla Lake': 17,
    'Volcanic Might': 17,
    'Like the Wind': 17,
    'Two Chiefs': 17,
    'Molduga Deluge': 25,
    'The Power of Three': 30,
    'A Fiery Reckoning': 30,
    'Through the Storm': 30,
    'EX Alert: Hyrule Field': 10,
    'EX Alert: Hyrule Outpost': 22,
    'EX Alert: Great Hyrule Forest': 23,
    'EX Alert: Akkala Citadel': 32,
    'EX Alert: Breach of Demise': 11,
    'EX Alert: Crenel Peak': 30,
    'EX Alert: Goponga Village': 28,
    'EX Alert: Mount Daphnes': 38,
    'EX Alert: Kakariko Village': 29,
    'EX Alert: Lanayru Road': 33,
    'EX Alert: Forgotten Temple': 41,
    'Meditative Training': 0,
    'Molduking Sighting': 0,
    'Igneo Talus Titan Sighting': 0,
    'The Last Light You See': 0,
    'A Tidal Wave of Foes': 0,
    'A Shield Forged in Iron': 0,
    'Swift as Thought': 0,
    "EX To Zelda's Side": 16,
    'EX Battle of Goponga Village': 21,
    'EX Battle for Kakariko Village': 21,
    'EX Searching Hyrule Forest': 21,
    'EX Liberate the Ancient Lab': 17,
    'EX The Princess and the King': 26,
    "EX The Yiga Clan's Retreat": 25,
    'EX Guardian of Remembrance': 29,
}
STORY_LEVEL: dict[str, int] = {
    'The Battle of Hyrule Field': 1,
    'Road to the Ancient Lab': 2,
    'Mipha, the Zora Princess': 2,
    'Daruk, the Goron Hero': 2,
    'Revali, the Rito Warrior': 2,
    'Urbosa, the Gerudo Chief': 2,
    'The Yiga Clan Attacks!': 7,
    'Freeing Korok Forest': 10,
    'The Road Home, Besieged': 10,
    'Akkala Tower': 12,
    'Destroy the Yiga Clan!': 16,
    'When Courage Fails': 17,
    'Calamity Strikes': 18,
    'Water and Fire': 20,
    'Air and Lightning': 20,
    'Relentless as a Waterfall': 21,
    'Each Step Like Thunder': 23,
    'The Great Plateau': 24,
    'All Hyrule, United': 27,
    'The Future of Hyrule': 29,
}


def challenge_gate(name: str, by_level: bool, boss_goal: bool = False) -> str | None:
    """The story mission whose clear the logic expects before this challenge; None = after the whole story.
    Shared by the generator (rules) and the client (which writes the game's unlock rows to match)."""
    from .data import BOSS_CHALLENGES, FINAL_MISSION, LEVEL_BAND_GATES

    if boss_goal and name in BOSS_CHALLENGES:
        return FINAL_MISSION
    if not by_level:
        return None
    if GAME_LEVEL.get(name):
        return next((m for m, lv in STORY_LEVEL.items() if lv >= GAME_LEVEL[name]), None)
    return LEVEL_BAND_GATES[CHALLENGE_BY_NAME[name].band]


# Calamity Strikes "traps" every Champion who is not playable: afterwards the game greys out anything that needs one -
# in its party, as an AI ally (Escorting the Injured: Sidon + ally Mipha) or as a Divine Beast's pilot - while before
# it a locked Champion could still be an AI ally [confirmed in game 2026-10-28; a received (playable) Champion is never
# trapped: Urbosa, and Mipha as soon as she was made playable; the rescue missions do not free them]. So (user rules)
# Calamity Strikes opens only once all four Champions are yours, and opens Water and Fire / Air and Lightning itself.
CALAMITY = "Calamity Strikes"
CHAMPIONS = ("Mipha", "Daruk", "Revali", "Urbosa")
RESCUES = ("Water and Fire", "Air and Lightning")  # opened by Calamity Strikes' clear (not shuffled, no unlock item)
# Divine Beast battles by Beast (mission parameter byte +79: 0x28 Ruta .. 0x2B Naboris [read live]) -> its Champion
BEAST_BATTLES = {
    "Mipha": ("Might of a Divine Beast", "Defending Cephla Lake", "The Power of Three"),
    "Daruk": ("Volcanic Defense", "Volcanic Might", "A Fiery Reckoning"),
    "Revali": ("Protector of the Forest", "Like the Wind", "Through the Storm"),
    "Urbosa": ("Pursue the Yiga Clan!", "Two Chiefs", "Molduga Deluge"),
}


def champions_needed(name: str) -> tuple[str, ...]:
    """The Champions a challenge needs once Calamity Strikes is cleared (in its party, as an AI ally, or its Divine
    Beast's Champion)."""
    from .data_save import MISSION_FORCED_HEROES
    heroes = set(MISSION_FORCED_HEROES.get(name, ())) | set(CHALLENGE_BY_NAME[name].required_characters)
    heroes |= {hero for hero, battles in BEAST_BATTLES.items() if name in battles}
    return tuple(h for h in CHAMPIONS if h in heroes)
