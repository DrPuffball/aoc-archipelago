"""
Save file (``svdt``) layout for Hyrule Warriors: Age of Calamity v1.4.1 (save format byte 0x89).

Read from the game's own data and checked against real saves (see tools/RESEARCH.md):
  * Mission records: 400 x 0x84 bytes at MISSION_RECORDS; record N belongs to the mission whose
    name is entry N of the game's mission text table (LinkData2.bin). A mission is cleared when
    any of the six u32 at record+4 is non-zero. Verified: every cleared record of a 100% save is a
    named mission, and the user's saves grow by exactly one record per logged clear.
  * Rupees, materials and heroes: offsets from the public save editor (marcrobledo.com,
    v20260405), checked against real saves. Hero unlocked flag at +0x1c is observed, not from
    the editor.
"""

from __future__ import annotations

SAVE_SIZE = 0x100000
SAVE_FORMAT = 0x89  # byte 0 of the file

MISSION_RECORDS = 0x2CF34
MISSION_RECORD_SIZE = 0x84
MISSION_RECORD_COUNT = 400
# Each record holds a clear time (u32) per difficulty slot (save: +4 + 4*slot; live: +4*slot), 6 slots. Slot order
# Easy, Normal, Hard, Very Hard [slot 0 = Easy confirmed: the user plays Easy and their clears land in slot 0; the
# 2022 save's story clears sit in slot 1; slot 3 = Very Hard confirmed: a Very Hard Daruk clear, 2026-10-27]; Apocalyptic, added in an update, is above Very Hard (slot 4
# [guess]); slot 5 unknown (counts as higher).
DIFFICULTY_SLOTS = 6
DIFFICULTIES = ("Easy", "Normal", "Hard", "Very Hard", "Apocalyptic")  # Apocalyptic (later update) = slot 4 [guess]

RUPEES = 0x2C3A4  # u32
RUPEES_MAX = 9_999_999
MATERIALS = 0x2C14E  # u16 per material index
MATERIAL_SEEN = 0x2C2DD  # u8 per material index
MATERIAL_MAX = 999
HEROES = 0x2BCAD  # 30 bytes per hero
HERO_SIZE = 30
HERO_LEVEL = 0x00  # level - 1
HERO_UNLOCKED = 0x1C
HERO_LEVEL_MAX = 100
# Cumulative XP needed for each level (index = level - 1), LinkData2 table 007bd714 (100 rows of 12 bytes: XP, XP/10,
# a small per-level value 4..21). Matches the in-game samples (level 2 in (2024, 2664], level 3 in (5218, 5545]) and
# the 100% save (level 100 = 3706825). Save hero row: +1..+3 = XP (u24); live row: +0x04 = XP (u32).
HERO_XP_TABLE = (
    0, 2500, 5400, 8500, 11800, 15425, 19275, 23350, 27650, 32175,
    37375, 42845, 48585, 54595, 60875, 67425, 74245, 81335, 88695, 96325,
    105225, 114445, 123985, 133845, 144025, 154525, 165345, 176485, 187945, 199725,
    213625, 227905, 242565, 257605, 273025, 288825, 305005, 321565, 338505, 355825,
    376325, 397275, 418675, 440525, 462825, 485575, 508775, 532425, 556525, 581075,
    609825, 639100, 668900, 699225, 730075, 761450, 793350, 825775, 858725, 892200,
    932200, 972825, 1014075, 1055950, 1098450, 1141575, 1185325, 1229700, 1274700, 1320325,
    1375325, 1431075, 1487575, 1544825, 1602825, 1661575, 1721075, 1781325, 1842325, 1904075,
    1978575, 2053975, 2130275, 2207475, 2285575, 2364575, 2444475, 2525275, 2606975, 2689575,
    2786575, 2884625, 2983725, 3083875, 3185075, 3287325, 3390625, 3494975, 3600375, 3706825,
)

# Hearts by level (same LinkData2 table 007bd714, third column; matches every level-up the probe recorded).
# ATK (+0x0A) and DEF (+0x0C) of the live hero row rise by 3 per level [read from 10 recorded level-ups].
HERO_HEARTS_TABLE = (
    4, 5, 5, 5, 6, 6, 6, 6, 7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 9, 9,
    9, 9, 9, 9, 10, 10, 10, 10, 10, 10, 11, 11, 11, 11, 11, 11, 12, 12, 12, 12,
    12, 12, 13, 13, 13, 13, 13, 13, 14, 14, 14, 14, 14, 14, 14, 15, 15, 15, 15, 15,
    15, 15, 16, 16, 16, 16, 16, 16, 16, 17, 17, 17, 17, 17, 17, 17, 18, 18, 18, 18,
    18, 18, 18, 19, 19, 19, 19, 19, 19, 19, 19, 20, 20, 20, 20, 20, 20, 20, 20, 21,
)
HERO_STAT_PER_LEVEL = 3

HERO_XP_SAVE = 0x01

# Hero slot in the save -> AP character name (slot order from the save editor).
# Weapon kind of each hero's basic weapon in the owned-weapons pool (first id of the hero's range, read from the
# 100% save: Revali 221-225, Impa 241-243, Sidon 251-255 ...; Impa's starter Kakariko Kodachi is 241, Sidon's
# Fishing Harpoon 251). Link's 4 is the starter the game itself gave him in a new game.
HERO_STARTER_KIND = {
    "Link": 4, "Zelda": 181, "King Rhoam": 191, "Mipha": 201, "Daruk": 211, "Revali": 221, "Urbosa": 231,
    "Impa": 241, "Sidon": 251, "Yunobo": 261, "Teba": 271, "Riju": 281, "Hestu": 291, "Great Fairies": 301,
    "Master Kohga": 311, "Monk Maz Koshia": 321, "Terrako": 331, "Calamity Ganon": 341,
    "Purah & Robbie": 381, "Sooga": 391,
}

HERO_SLOTS = {
    "Link": 0, "Zelda": 1, "King Rhoam": 2, "Mipha": 3, "Daruk": 4, "Revali": 5, "Urbosa": 6,
    "Impa": 7, "Sidon": 8, "Yunobo": 9, "Teba": 10, "Riju": 11, "Hestu": 12, "Great Fairies": 13,
    "Master Kohga": 14, "Monk Maz Koshia": 15, "Terrako": 16, "Calamity Ganon": 17,
    "Purah & Robbie": 19, "Sooga": 20,
}

# Base-game materials handed out by "Material Bundle" (indices from the save editor; no trophies,
# no DLC, no Korok seeds or other special items).
# Hearty Meal filler: cooking ingredients (material index = reward-table id - 1, RESEARCH session 13).
HEARTY_MEAL = {0: 5, 22: 5}  # Hearty Durian x5, Hyrule Herb x5
# Weapon levels: 20 at first; A Monumental Undertaking raises the cap to 25, The Legendary Blacksmith to 30 (wikis).
WEAPON_LEVEL_CAP, WEAPON_LEVEL_CAP_MONUMENT = 20, 25
BUNDLE_MATERIALS = tuple(list(range(0, 52)) + list(range(64, 147)))

# Mission name -> record indices. Two-part story missions have two records; all must be set.
MISSION_RECORD_IDS: dict[str, tuple[int, ...]] = {
    'The Battle of Hyrule Field': (1,),
    'Road to the Ancient Lab': (2,),
    'Mipha, the Zora Princess': (3, 4),
    'Daruk, the Goron Hero': (5, 6),
    'Revali, the Rito Warrior': (7,),
    'Urbosa, the Gerudo Chief': (8,),
    'The Yiga Clan Attacks!': (9,),
    'Freeing Korok Forest': (10, 11),
    'The Road Home, Besieged': (12,),
    'Akkala Tower': (13,),
    'Destroy the Yiga Clan!': (14, 15),
    'When Courage Fails': (16,),
    'Calamity Strikes': (17,),
    'Water and Fire': (18, 19),
    'Air and Lightning': (20, 21),
    'Relentless as a Waterfall': (22, 23),
    'Each Step Like Thunder': (24, 25),
    'The Great Plateau': (26,),
    'All Hyrule, United': (27,),
    'The Future of Hyrule': (28,),
    'Meditative Training': (30,),
    'Forest Dance Festival': (100,),
    'Anti-Flame Training: I': (101,),
    'Anti-Flame Training: II': (102,),
    'Anti-Flame Training: III': (103,),
    'Anti-Ice Training: I': (104,),
    'Anti-Ice Training: II': (105,),
    'Anti-Ice Training: III': (106,),
    'Anti-Lightning Training: I': (107,),
    'Anti-Lightning Training: II': (108,),
    'Anti-Lightning Training: III': (109,),
    'Anti-Flame & Ice Training': (110,),
    'Anti-Flame & Lightning Training': (111,),
    'Anti-Ice & Lightning Training': (112,),
    'Anti-Element Training': (113,),
    'Coliseum: Beginner': (114,),
    'Coliseum: Intermediate': (115,),
    'Coliseum: Expert': (116,),
    "Hyrule's Greatest Warrior": (117,),
    "Heart's Escort": (118,),
    'Wisdom of the Storm': (119,),
    'Escorting the Injured': (120,),
    'Polishing His Technique': (121,),
    'Winged Escort': (122,),
    'The Chief-in-Training': (123,),
    'Fish Out of Water': (124,),
    'Hero of the Rito': (125,),
    'Leave None Behind': (126,),
    'The Royal Escort': (127,),
    "Messenger's Escort": (128,),
    "Prince's Escort": (129,),
    "King's Escort": (130,),
    'Daily Drills: Hyrule': (131,),
    'Daily Drills: Zora': (132,),
    'Daily Drills: Goron': (133,),
    'Daily Drills: Rito': (134,),
    'Daily Drills: Gerudo': (135,),
    'Link: One-Handed Weapons': (136,),
    'Link: Two-Handed Weapons': (137,),
    'Link: Spears': (138,),
    "Zelda's Training": (139,),
    "King Rhoam's Training": (140,),
    "Mipha's Training": (141,),
    "Daruk's Training": (142,),
    "Revali's Training": (143,),
    "Urbosa's Training": (144,),
    "Impa's Training": (145,),
    "Zelda's Training: Bows": (146,),
    "Sidon's Training": (147,),
    "Yunobo's Training": (148,),
    "Teba's Training": (149,),
    "Riju's Training": (150,),
    "Hestu's Training": (151,),
    'Great Fairy Training': (152,),
    "Master Kohga's Training": (153,),
    "Monk's Training": (154,),
    "Terrako's Training": (155,),
    "Ganon's Training": (156,),
    'Mastering Magnesis': (157,),
    'Mastering Remote Bombs': (158,),
    'Mastering Cryonis': (159,),
    'Mastering Stasis': (160,),
    'Invading Terrors': (161,),
    'Lost Treasures': (162,),
    'Fairy Fountain: Desert Sands': (163,),
    'Hair-Width Trial: Beginner': (164,),
    'Hair-Width Trial: Intermediate': (165,),
    'Hair-Width Trial: Expert': (166,),
    'Hair-Width Trial: Expert+': (167,),
    'The Breach of Demise': (168,),
    "Innkeeper's Request": (169,),
    'Territorial Battle': (170,),
    'Reclaim the Land': (171,),
    'The So-Called Knight': (172,),
    'Sibling Bonds': (173,),
    'Win Back the Mighty Bananas!': (174,),
    'Generational Conflict': (175,),
    'Rampaging Malice': (176,),
    'Apprentice Yunobo': (177,),
    "Impa's Damage Control": (178,),
    'Fight Lightning with Lightning': (179,),
    'Nap Quest!': (180,),
    'Miss Vai Battle Pageant': (181,),
    'Guardian Showdown': (182,),
    'Hunting Partners': (183,),
    'Shadow of Ganon': (184,),
    'Remnants of the Calamity': (185,),
    'Trial of the Ancients': (186,),
    'Chief-of-the-Dunes Battle': (187,),
    'Strike It Rich': (188,),
    'Goron-Style Barbecue': (189,),
    'Sidon vs. the Octoroks': (190,),
    'Lizalfos Infestation': (191,),
    'Molduga Sighting': (192,),
    'Molduking Sighting': (193,),
    'Igneo Talus Titan Sighting': (194,),
    'Blight Ganons Resurgent': (195,),
    'Footsteps of the Giant': (196,),
    'Taming the Savage Lynel': (197,),
    'Hunting for Gemstones': (198,),
    'The Heart of the Calamity': (199,),
    'A Show of Strength': (200,),
    'Stronger Yet': (201,),
    'True Strength': (202,),
    'Harbingers of the Calamity': (203,),
    'A Feast for Wizzrobes': (204,),
    'Mysterious Arrivals': (205,),
    'Defend the Sands!': (206,),
    'Swift Spear of the Zora': (207,),
    'Tough Bulwark of the Gorons': (208,),
    'Fierce Gale of the Rito': (209,),
    'Mighty Thunder of the Gerudo': (210,),
    'Outpost Defenders': (211,),
    'The Master Kohga Chronicles!': (212,),
    'Zora Mettle': (213,),
    'Goron Spirit': (214,),
    'Rito Discipline': (215,),
    'Gerudo Fury': (216,),
    'Defend Akkala Citadel': (217,),
    'Defend Hyrule Castle': (218,),
    'Defend the Spring of Courage': (219,),
    'Fairy Fountain: Deep Snows': (220,),
    'Fairy Fountain: Grassy Plains': (221,),
    'Cross the Hebra Mountains': (222,),
    'Cross the Volcano': (223,),
    'Fleeing the Weather': (224,),
    'Through the Desert': (225,),
    'Guardian Graveyard': (226,),
    'A Royal Investigation': (227,),
    'A Hidden Treasure': (228,),
    'Fruit for the Princess!': (229,),
    'Escape the Lost Woods': (230,),
    'Mountain Rescue': (231,),
    'Fairy Fountain: Battlefield': (232,),
    'Might of a Divine Beast': (233,),
    'Defending Cephla Lake': (234,),
    'A Tidal Wave of Foes': (235,),
    'The Power of Three': (236,),
    'Volcanic Defense': (237,),
    'Volcanic Might': (238,),
    'A Shield Forged in Iron': (239,),
    'A Fiery Reckoning': (240,),
    'Protector of the Forest': (241,),
    'Like the Wind': (242,),
    'Swift as Thought': (243,),
    'Through the Storm': (244,),
    'Pursue the Yiga Clan!': (245,),
    'Two Chiefs': (246,),
    'Molduga Deluge': (247,),
    'The Last Light You See': (248,),
    'Echoing Footsteps': (249,),
    'Explosive—Handle With Care': (250,),
    "Defend Zora's Domain": (251,),
    'Like Grains of Sand': (252,),
    'Fire Hazards': (253,),
    'In the Clutches of the Yiga!': (254,),
    'Defeating Destiny': (255,),
    'Questionable Escort Mission': (256,),
    'Elemental Uproar': (257,),
    'Hold the Line': (258,),
    'The Guardians Counterattack': (259,),
    'Deep Woods, Deep Shadow': (260,),
    'The Fiercest of Foes': (261,),
    'Unnatural Disaster': (262,),
    'The Siege of Fort Hateno': (263,),
    'Versus Astor': (264,),
    'Versus Harbinger Ganon': (265,),
    'Versus Calamity Ganon': (266,),
    "EX To Zelda's Side": (300,),
    'EX Battle of Goponga Village': (301,),
    'EX Battle for Kakariko Village': (302,),
    'EX Searching Hyrule Forest': (303,),
    'EX Liberate the Ancient Lab': (304,),
    'EX The Princess and the King': (305,),
    "EX The Yiga Clan's Retreat": (306,),
    'EX Guardian of Remembrance': (307,),
    'EX Alert: Forgotten Temple': (320,),
    'EX Alert: Hyrule Field': (321,),
    'EX Alert: Hyrule Outpost': (322,),
    'EX Alert: Great Hyrule Forest': (323,),
    'EX Alert: Akkala Citadel': (324,),
    'EX Alert: Breach of Demise': (325,),
    'EX Alert: Crenel Peak': (326,),
    'EX Alert: Mount Daphnes': (327,),
    'EX Alert: Goponga Village': (328,),
    'EX Alert: Kakariko Village': (329,),
    'EX Alert: Lanayru Road': (330,),
    'EX Link: Flails': (350,),
    'EX Zelda: Master Cycle': (351,),
    'EX Battle-Tested Guardian Training': (352,),
    'EX Ancient Threats': (353,),
    "EX Purah & Robbie's Study": (354,),
    'EX Handle the Horde': (355,),
    'EX Rupee Rescue': (356,),
    'EX Battle Research: Skills': (357,),
    'EX Battle Research: Items': (358,),
    'EX Road to Akkala Citadel': (359,),
    'EX Conquering Hyrule': (360,),
    'EX The Final Battle': (361,),
    "EX The Knight's Nightmare": (362,),
    'EX Survival of the Fittest': (363,),
    'EX Request from the Lab': (364,),
    "EX Zelda's Culinary Research": (365,),
    'EX Evacuating Hyrule': (366,),
    "EX Purah & Robbie's Training": (367,),
    "EX Sooga's Training": (368,),
    'EX Facing Mutated Ganon': (369,),
    'EX A Moblin Feast': (370,),
    'EX The Budget Battle': (371,),
    "EX Sooga's Daily Routine": (372,),
    'EX Coliseum: Master': (373,),
    'EX Utmost Strength': (374,),
}


# Heroes a mission puts in the party (mission parameter table t009cc294, bytes +71..+79 of each record;
# read from the game's data). Used so hero locks never block a mission the seed lets you play. Which of these
# are forced and which only support is UNVERIFIED for a few late story missions, so all of them are kept.
MISSION_FORCED_HEROES: dict[str, tuple[str, ...]] = {
    'The Battle of Hyrule Field': ('Impa', 'Link'),
    'Road to the Ancient Lab': ('Impa', 'Link', 'Zelda'),
    'Mipha, the Zora Princess': ('Link', 'Mipha'),
    'Daruk, the Goron Hero': ('Daruk', 'Link'),
    'Revali, the Rito Warrior': ('Link', 'Zelda'),
    'Urbosa, the Gerudo Chief': ('Link', 'Urbosa'),
    'The Yiga Clan Attacks!': ('Link', 'Zelda'),
    'Freeing Korok Forest': ('Hestu', 'Link', 'Zelda'),
    'The Road Home, Besieged': ('Link', 'Zelda'),
    'Akkala Tower': ('Link', 'Zelda'),
    'When Courage Fails': ('Zelda',),
    'Calamity Strikes': ('Daruk', 'Hestu', 'Mipha', 'Revali', 'Urbosa'),
    'Water and Fire': ('Daruk', 'Mipha', 'Sidon', 'Yunobo'),
    'Air and Lightning': ('Revali', 'Riju', 'Teba', 'Urbosa'),
    'Relentless as a Waterfall': ('Daruk', 'Purah & Robbie', 'Sidon'),
    'Each Step Like Thunder': ('Link', 'Purah & Robbie', 'Riju', 'Urbosa', 'Zelda'),
    'The Great Plateau': ('Purah & Robbie',),
    'All Hyrule, United': ('Daruk', 'Mipha', 'Revali', 'Urbosa'),
    'The Future of Hyrule': ('Link', 'Zelda'),
    'Forest Dance Festival': ('Hestu', 'Urbosa'),
    "Hyrule's Greatest Warrior": ('Link', 'Master Kohga', 'Revali'),
    "Heart's Escort": ('Link', 'Mipha'),
    'Wisdom of the Storm': ('Urbosa', 'Yunobo'),
    'Escorting the Injured': ('Mipha', 'Sidon'),
    'Polishing His Technique': ('Daruk', 'Yunobo'),
    'Winged Escort': ('Revali', 'Teba'),
    'The Chief-in-Training': ('Riju', 'Sooga', 'Urbosa'),
    'Hero of the Rito': ('Teba',),
    'The Royal Escort': ('Link', 'Sooga', 'Zelda'),
    "Prince's Escort": ('Sidon',),
    "King's Escort": ('King Rhoam',),
    'Daily Drills: Hyrule': ('Impa',),
    'Daily Drills: Zora': ('Mipha',),
    'Daily Drills: Goron': ('Daruk',),
    'Daily Drills: Rito': ('Revali',),
    'Daily Drills: Gerudo': ('Urbosa',),
    'Link: One-Handed Weapons': ('Link',),
    'Link: Two-Handed Weapons': ('Daruk', 'Link'),
    'Link: Spears': ('Link',),
    "Zelda's Training": ('Zelda',),
    "King Rhoam's Training": ('King Rhoam', 'Link'),
    "Mipha's Training": ('Mipha',),
    "Daruk's Training": ('Daruk',),
    "Revali's Training": ('Revali',),
    "Urbosa's Training": ('Urbosa',),
    "Impa's Training": ('Impa',),
    "Zelda's Training: Bows": ('Zelda',),
    "Sidon's Training": ('Sidon',),
    "Yunobo's Training": ('Yunobo',),
    "Teba's Training": ('Teba',),
    "Riju's Training": ('Riju',),
    "Hestu's Training": ('Hestu', 'Impa'),
    'Great Fairy Training': ('Great Fairies', 'Hestu'),
    "Master Kohga's Training": ('Master Kohga',),
    "Monk's Training": ('Monk Maz Koshia',),
    "Terrako's Training": ('King Rhoam', 'Terrako'),
    "Ganon's Training": ('Calamity Ganon',),
    'Invading Terrors': ('Mipha',),
    'Fairy Fountain: Desert Sands': ('Great Fairies',),
    'The So-Called Knight': ('Link', 'Revali', 'Sidon'),
    'Sibling Bonds': ('Mipha', 'Sidon'),
    'Win Back the Mighty Bananas!': ('Master Kohga',),
    'Generational Conflict': ('Daruk', 'Mipha', 'Revali', 'Riju', 'Sidon', 'Teba', 'Urbosa', 'Yunobo'),
    'Rampaging Malice': ('Daruk',),
    'Apprentice Yunobo': ('Daruk', 'Yunobo'),
    "Impa's Damage Control": ('Impa', 'Purah & Robbie'),
    'Fight Lightning with Lightning': ('Mipha', 'Riju'),
    'Nap Quest!': ('Master Kohga',),
    'Miss Vai Battle Pageant': ('King Rhoam', 'Link', 'Revali', 'Sidon', 'Teba'),
    'Guardian Showdown': ('Terrako',),
    'Hunting Partners': ('Hestu', 'Revali'),
    'Shadow of Ganon': ('Link', 'Urbosa'),
    'Trial of the Ancients': ('Monk Maz Koshia',),
    'Sidon vs. the Octoroks': ('Sidon',),
    'Defend the Sands!': ('Sooga',),
    'Swift Spear of the Zora': ('Mipha',),
    'Tough Bulwark of the Gorons': ('Daruk',),
    'Fierce Gale of the Rito': ('Revali',),
    'Mighty Thunder of the Gerudo': ('Urbosa',),
    'The Master Kohga Chronicles!': ('Impa', 'Master Kohga'),
    'Zora Mettle': ('Mipha', 'Sidon'),
    'Goron Spirit': ('Daruk', 'Yunobo'),
    'Rito Discipline': ('Revali', 'Teba'),
    'Gerudo Fury': ('Riju', 'Urbosa'),
    'Fairy Fountain: Deep Snows': ('Great Fairies',),
    'Fairy Fountain: Grassy Plains': ('Great Fairies',),
    'Guardian Graveyard': ('King Rhoam',),
    'A Royal Investigation': ('Zelda',),
    'A Hidden Treasure': ('Sooga',),
    'Fruit for the Princess!': ('Impa', 'Link', 'Sooga'),
    'Fairy Fountain: Battlefield': ('Great Fairies',),
    'Defending Cephla Lake': ('Sidon',),
    'In the Clutches of the Yiga!': ('Master Kohga', 'Sooga'),
    "EX To Zelda's Side": ('Impa', 'Terrako', 'Zelda'),
    'EX Battle of Goponga Village': ('Mipha', 'Sidon'),
    'EX Battle for Kakariko Village': ('Daruk', 'Yunobo'),
    'EX Searching Hyrule Forest': ('Revali', 'Teba'),
    'EX Liberate the Ancient Lab': ('Riju', 'Urbosa'),
    'EX The Princess and the King': ('Daruk', 'King Rhoam', 'Mipha', 'Revali', 'Sidon', 'Urbosa'),
    "EX The Yiga Clan's Retreat": ('Master Kohga', 'Sooga'),
    'EX Guardian of Remembrance': ('Purah & Robbie', 'Terrako', 'Zelda'),
    'EX Link: Flails': ('Link',),
    'EX Zelda: Master Cycle': ('Zelda',),
    "EX Purah & Robbie's Study": ('Purah & Robbie',),
    'EX Battle Research: Skills': ('Purah & Robbie',),
    'EX Battle Research: Items': ('Purah & Robbie',),
    'EX Conquering Hyrule': ('Daruk', 'King Rhoam', 'Link', 'Mipha', 'Zelda'),
    "EX The Knight's Nightmare": ('Link',),
    'EX Request from the Lab': ('Purah & Robbie',),
    'EX Evacuating Hyrule': ('Impa', 'Link', 'Zelda'),
    "EX Purah & Robbie's Training": ('Purah & Robbie',),
    "EX Sooga's Training": ('Sooga',),
    'EX The Budget Battle': ('King Rhoam', 'Purah & Robbie', 'Terrako'),
    "EX Sooga's Daily Routine": ('Impa', 'Master Kohga', 'Sooga'),
}


# Story party override (story_party: free). The game loads the mission parameter table above into memory; a story
# record's forced party is the 4 bytes at +71 of its 104-byte row (hero slot + 1; 0 = none; >= 40 Divine Beasts).
# Vanilla bytes per story record, so the hook can put them back:
PARTY_ROW_SIZE, PARTY_OFFSET = 104, 71
VANILLA_STORY_PARTY: dict[int, str] = {
    1: '01080000',  # The Battle of Hyrule Field
    2: '01080200',  # Road to the Ancient Lab
    3: '01000400',  # Mipha, the Zora Princess
    5: '01000500',  # Daruk, the Goron Hero
    7: '01000000',  # Revali, the Rito Warrior
    8: '01000700',  # Urbosa, the Gerudo Chief
    9: '00000100',  # The Yiga Clan Attacks!
    11: '0102000d',  # Freeing Korok Forest
    12: '01000000',  # The Road Home, Besieged
    13: '01020000',  # Akkala Tower
    18: '0000090a',  # Water and Fire
    20: '00000c0b',  # Air and Lightning
    23: '00000005',  # Relentless as a Waterfall
    25: '01020000',  # Each Step Like Thunder
    28: '01020000',  # The Future of Hyrule
}
# Support heroes (AI allies, +75..+79) of those records: the game won't let them be picked there, so the override
# never puts them in the party.
STORY_SUPPORT: dict[int, tuple[str, ...]] = {
    7: ('Zelda',), 9: ('Zelda',), 12: ('Zelda',), 18: ('Mipha', 'Daruk'), 20: ('Revali', 'Urbosa'),
    23: ('Sidon', 'Purah & Robbie'), 25: ('Urbosa', 'Riju', 'Purah & Robbie'),
}

# Starting weapon type per hero (the hero record's equipped-weapon byte): every hero's weapon types start at their own
# base, read from the saves (100% save: Rhoam 61, Impa 111, Sidon 121 ... Sooga 241; Zelda 51 and Urbosa 101 in the
# user's save). Link's three weapon classes share 1..50.
HERO_STARTER_WEAPON: dict[str, int] = {
    "Link": 1, "Zelda": 51, "King Rhoam": 61, "Mipha": 71, "Daruk": 81, "Revali": 91, "Urbosa": 101, "Impa": 111,
    "Sidon": 121, "Yunobo": 131, "Teba": 141, "Riju": 151, "Hestu": 161, "Great Fairies": 171, "Master Kohga": 181,
    "Monk Maz Koshia": 191, "Terrako": 201, "Calamity Ganon": 211, "Purah & Robbie": 231, "Sooga": 241,
}

# Mission unlock table (LinkData2 t009dc714, 400 rows x 36): +4..+0xB up to four records that must be cleared,
# +0xC a further record (shown-on-map condition, guessed). Vanilla bytes +4..+0xE of each story mission's first record.
UNLOCK_ROW_SIZE, UNLOCK_OFFSET = 36, 4
VANILLA_STORY_UNLOCK = {
    1: '00000000000000000000',  # The Battle of Hyrule Field
    2: '01000000000000000000',  # Road to the Ancient Lab
    3: '02000000000000000200',  # Mipha, the Zora Princess
    5: '02000000000000000200',  # Daruk, the Goron Hero
    7: '02000000000000000200',  # Revali, the Rito Warrior
    8: '02000000000000000200',  # Urbosa, the Gerudo Chief
    9: '04000600070008000000',  # The Yiga Clan Attacks!
    10: '09000000000000000000',  # Freeing Korok Forest
    12: '0b000000000000000000',  # The Road Home, Besieged
    13: '0c000000000000000000',  # Akkala Tower
    14: '0d000000000000000000',  # Destroy the Yiga Clan!
    16: '0f000000000000000000',  # When Courage Fails
    17: '10000000000000000000',  # Calamity Strikes
    18: '11000000000000000c00',  # Water and Fire
    20: '11000000000000000c00',  # Air and Lightning
    22: '13001500000000000000',  # Relentless as a Waterfall
    24: '17000000000000000000',  # Each Step Like Thunder
    26: '19000000000000000000',  # The Great Plateau
    27: '1a000000000000000000',  # All Hyrule, United
    28: '1b000000000000000000',  # The Future of Hyrule
}

# Challenge rows of the same table, vanilla bytes +4..+0x17: five prerequisite records (story missions and other
# challenges), a zero u16, then up to three quests that must be done (quest state index; read from data: Trial of the
# Ancients needs The Trial of Monsters/Stones/the Mighty Foe, Terrako's Training needs Terrako's Return).
# Bytes from +0x18 (EX ids, region bits) are left alone.
CHALLENGE_UNLOCK_SIZE = 20
VANILLA_CHALLENGE_UNLOCK = {
    30: '0000000000000000000000000000000000000000',  # Meditative Training
    100: '97000000000000000f0000000000000000000000',  # Forest Dance Festival
    101: '8e00000000000000000000000000000000000000',  # Anti-Flame Training: I
    102: '0d00650000000000000000000000000000000000',  # Anti-Flame Training: II
    103: '66000000000000000f0000006801000000000000',  # Anti-Flame Training: III
    104: '8f00000000000000000000000000000000000000',  # Anti-Ice Training: I
    105: '0d00680000000000000000000000000000000000',  # Anti-Ice Training: II
    106: '69000000000000000f0000006801000000000000',  # Anti-Ice Training: III
    107: '9000000000000000000000000000000000000000',  # Anti-Lightning Training: I
    108: '0d006b0000000000000000000000000000000000',  # Anti-Lightning Training: II
    109: '6c000000000000000f0000006801000000000000',  # Anti-Lightning Training: III
    110: '67006a0000000000000000000000000000000000',  # Anti-Flame & Ice Training
    111: '67006d0000000000000000000000000000000000',  # Anti-Flame & Lightning Training
    112: '6a006d0000000000000000000000000000000000',  # Anti-Ice & Lightning Training
    113: '6e006f0070000000000000000000000000000000',  # Anti-Element Training
    114: '0d00000000000000000000000000000000000000',  # Coliseum: Beginner
    115: '1100720000000000000000000000000000000000',  # Coliseum: Intermediate
    116: '1a00730000000000000000000000000000000000',  # Coliseum: Expert
    117: '1c00ba00e8000000000000000000000000000000',  # Hyrule's Greatest Warrior
    118: 'a100000000000000000000004200000000000000',  # Heart's Escort
    119: 'b300000000000000000000000000000000000000',  # Wisdom of the Storm
    120: '93000000000000000f0000000000000000000000',  # Escorting the Injured
    121: '1a00bd0000000000000000000000000000000000',  # Polishing His Technique
    122: '95000000000000000f0000000000000000000000',  # Winged Escort
    123: '96000000000000000f0000000000000000000000',  # The Chief-in-Training
    124: '8400000000000000000000000000000000000000',  # Fish Out of Water
    125: '1a007a0000000000000000000000000000000000',  # Hero of the Rito
    126: '0900000000000000000000000000000000000000',  # Leave None Behind
    127: '8000000000000000000000000000000000000000',  # The Royal Escort
    128: '0c00000000000000000000000000000000000000',  # Messenger's Escort
    129: '1700000000000000000000000000000000000000',  # Prince's Escort
    130: '8c00000000000000000000000000000000000000',  # King's Escort
    131: '8000000000000000000000000000000000000000',  # Daily Drills: Hyrule
    132: '0b00000000000000000000000000000000000000',  # Daily Drills: Zora
    133: 'df00000000000000000000000000000000000000',  # Daily Drills: Goron
    134: '0900000000000000000000000000000000000000',  # Daily Drills: Rito
    135: 'e100000000000000000000000000000000000000',  # Daily Drills: Gerudo
    136: '0100000000000000060000000100020013000000',  # Link: One-Handed Weapons
    137: '0100000000000000060000000100000000000000',  # Link: Two-Handed Weapons
    138: '0100000000000000060000000000000000000000',  # Link: Spears
    139: '0900000000000000000000000000000000000000',  # Zelda's Training
    140: '1a00000000000000000000000000000000000000',  # King Rhoam's Training
    141: '0400000000000000000000000000000000000000',  # Mipha's Training
    142: '0600000000000000000000000000000000000000',  # Daruk's Training
    143: '0700000000000000000000000000000000000000',  # Revali's Training
    144: '0800000000000000000000000000000000000000',  # Urbosa's Training
    145: '0900000000000000000000000000000000000000',  # Impa's Training
    146: '1900000000000000000000000000000000000000',  # Zelda's Training: Bows
    147: '1300000000000000000000000000000000000000',  # Sidon's Training
    148: '1300000000000000000000000000000000000000',  # Yunobo's Training
    149: '1500000000000000000000000000000000000000',  # Teba's Training
    150: '1500000000000000000000000000000000000000',  # Riju's Training
    151: '0b00000000000000000000000000000000000000',  # Hestu's Training
    152: 'e800000000000000000000000000000000000000',  # Great Fairy Training
    153: '1900000000000000000000000000000000000000',  # Master Kohga's Training
    154: 'ba00000000000000000000000000000000000000',  # Monk's Training
    155: '1c00000000000000000000005801000000000000',  # Terrako's Training
    156: '0a01000000000000000000000000000000000000',  # Ganon's Training
    157: '0200000000000000040000000000000000000000',  # Mastering Magnesis
    158: '0200000000000000000000000000000000000000',  # Mastering Remote Bombs
    159: '0200000000000000030000000000000000000000',  # Mastering Cryonis
    160: '0200000000000000050000000000000000000000',  # Mastering Stasis
    161: '1c00000000000000000000000000000000000000',  # Invading Terrors
    162: 'fc00000000000000000000000000000000000000',  # Lost Treasures
    163: '0d00000000000000000000006401000000000000',  # Fairy Fountain: Desert Sands
    164: '0200000000000000060000000000000000000000',  # Hair-Width Trial: Beginner
    165: '0d00a40000000000000000000000000000000000',  # Hair-Width Trial: Intermediate
    166: '1a00a50000000000000000000000000000000000',  # Hair-Width Trial: Expert
    167: 'a600000000000000000000000000000000000000',  # Hair-Width Trial: Expert+
    168: '8a00000000000000000000000000000000000000',  # The Breach of Demise
    169: '0d00000000000000000000000000000000000000',  # Innkeeper's Request
    170: '1100000000000000000000000000000000000000',  # Territorial Battle
    171: '1b00000000000000000000000000000000000000',  # Reclaim the Land
    172: '7a00000000000000000000000000000000000000',  # The So-Called Knight
    173: '1a00be0000000000000000000000000000000000',  # Sibling Bonds
    174: '1000000000000000000000000000000000000000',  # Win Back the Mighty Bananas!
    175: '7a007b00b100d500000000000000000000000000',  # Generational Conflict
    176: '1c00000000000000000000000000000000000000',  # Rampaging Malice
    177: '94000000000000000f0000000000000000000000',  # Apprentice Yunobo
    178: '1900000000000000000000000000000000000000',  # Impa's Damage Control
    179: '19007b0000000000000000000000000000000000',  # Fight Lightning with Lightning
    180: '9900000000000000000000000000000000000000',  # Nap Quest!
    181: '7500000000000000000000000000000000000000',  # Miss Vai Battle Pageant
    182: '9b00000000000000000000000000000000000000',  # Guardian Showdown
    183: '1c00000000000000000000000000000000000000',  # Hunting Partners
    184: '1c00000000000000000000005601000000000000',  # Shadow of Ganon
    185: '7500cb0004010000000000000000000000000000',  # Remnants of the Calamity
    186: '0f00000000000000000000006501660167010000',  # Trial of the Ancients
    187: 'f500000000000000000000000000000000000000',  # Chief-of-the-Dunes Battle
    188: '0d00000000000000000000000000000000000000',  # Strike It Rich
    189: '1900b10000000000000000000000000000000000',  # Goron-Style Barbecue
    190: '1900d50000000000000000000000000000000000',  # Sidon vs. the Octoroks
    191: '0200000000000000000000000000000000000000',  # Lizalfos Infestation
    192: 'f900000000000000000000000000000000000000',  # Molduga Sighting
    193: '0000000000000000000000000000000000000000',  # Molduking Sighting
    194: '0000000000000000000000000000000000000000',  # Igneo Talus Titan Sighting
    195: 'b600ff0000000000000000000000000000000000',  # Blight Ganons Resurgent
    196: 'c600ab0000000000000000000d00000000000000',  # Footsteps of the Giant
    197: 'c600ab0000000000000000000000000000000000',  # Taming the Savage Lynel
    198: '1b00000000000000000000000000000000000000',  # Hunting for Gemstones
    199: '0a01000000000000000000000000000000000000',  # The Heart of the Calamity
    200: 'ce00000000000000000000000000000000000000',  # A Show of Strength
    201: '1100c80000000000000000000000000000000000',  # Stronger Yet
    202: 'ec00f000f400f700000000000000000000000000',  # True Strength
    203: 'da00000000000000000000000000000000000000',  # Harbingers of the Calamity
    204: '0f00000000000000000000000000000000000000',  # A Feast for Wizzrobes
    205: 'c300000000000000000000000000000000000000',  # Mysterious Arrivals
    206: '0f00000000000000000000000000000000000000',  # Defend the Sands!
    207: '0c00e90000000000000000000000000000000000',  # Swift Spear of the Zora
    208: '0c00ed0000000000000000000000000000000000',  # Tough Bulwark of the Gorons
    209: 'f100000000000000000000000000000000000000',  # Fierce Gale of the Rito
    210: 'e100000000000000000000000000000000000000',  # Mighty Thunder of the Gerudo
    211: '0c00000000000000000000000000000000000000',  # Outpost Defenders
    212: '1c00000000000000000000005501000000000000',  # The Master Kohga Chronicles!
    213: 'c600000000000000000000000000000000000000',  # Zora Mettle
    214: 'ab00000000000000000000000000000000000000',  # Goron Spirit
    215: 'ab00000000000000000000000000000000000000',  # Rito Discipline
    216: 'c600000000000000000000000000000000000000',  # Gerudo Fury
    217: '1a00000000000000000000000000000000000000',  # Defend Akkala Citadel
    218: '1c00000000000000000000000000000000000000',  # Defend Hyrule Castle
    219: '920000000000000000000000ed00000000000000',  # Defend the Spring of Courage
    220: '0d00000000000000000000006401000000000000',  # Fairy Fountain: Deep Snows
    221: '0d00000000000000000000006401000000000000',  # Fairy Fountain: Grassy Plains
    222: '8600000000000000000000000000000000000000',  # Cross the Hebra Mountains
    223: 'de00000000000000000000000000000000000000',  # Cross the Volcano
    224: '1500000000000000000000000000000000000000',  # Fleeing the Weather
    225: '0c00000000000000000000000000000000000000',  # Through the Desert
    226: 'a100b00000000000000000000000000000000000',  # Guardian Graveyard
    227: 'b700b800d4000000000000000000000000000000',  # A Royal Investigation
    228: 'a200000000000000000000000000000000000000',  # A Hidden Treasure
    229: 'ae00000000000000000000000000000000000000',  # Fruit for the Princess!
    230: '1000000000000000000000000000000000000000',  # Escape the Lost Woods
    231: '7c007e0000000000000000005700000000000000',  # Mountain Rescue
    232: 'a300dc00dd000000000000000000000000000000',  # Fairy Fountain: Battlefield
    233: '0900000000000000000000000000000000000000',  # Might of a Divine Beast
    234: '1900000000000000000000000000000000000000',  # Defending Cephla Lake
    235: '0000000000000000000000000000000000000000',  # A Tidal Wave of Foes
    236: '1c00e900ea000000000000000000000000000000',  # The Power of Three
    237: '0900000000000000000000000000000000000000',  # Volcanic Defense
    238: '1900000000000000000000000000000000000000',  # Volcanic Might
    239: '0000000000000000000000000000000000000000',  # A Shield Forged in Iron
    240: '1c00ed00ee000000000000000000000000000000',  # A Fiery Reckoning
    241: '0c00000000000000000000000000000000000000',  # Protector of the Forest
    242: '1900000000000000000000000000000000000000',  # Like the Wind
    243: '0000000000000000000000000000000000000000',  # Swift as Thought
    244: '1c00f100f2000000000000000000000000000000',  # Through the Storm
    245: '0f00000000000000000000000000000000000000',  # Pursue the Yiga Clan!
    246: '1900000000000000000000000000000000000000',  # Two Chiefs
    247: '1c00f500f6000000000000000000000000000000',  # Molduga Deluge
    248: '0000000000000000000000000000000000000000',  # The Last Light You See
    249: '0b00000000000000000000000000000000000000',  # Echoing Footsteps
    250: '9e00000000000000000000000000000000000000',  # Explosive—Handle With Care
    251: '8100000000000000000000000000000000000000',  # Defend Zora's Domain
    252: '1700000000000000000000000000000000000000',  # Like Grains of Sand
    253: '1700d300a9000000000000000000000000000000',  # Fire Hazards
    254: 'e600000000000000000000000000000000000000',  # In the Clutches of the Yiga!
    255: 'b000000000000000000000000000000000000000',  # Defeating Destiny
    256: '8100000000000000000000000000000000000000',  # Questionable Escort Mission
    257: '1700d500e0000000000000000000000000000000',  # Elemental Uproar
    258: 'c400c50000000000000000000000000000000000',  # Hold the Line
    259: '8200b20000000000000000000000000000000000',  # The Guardians Counterattack
    260: 'da00000000000000000000000000000000000000',  # Deep Woods, Deep Shadow
    261: '0a01000000000000000000000000000000000000',  # The Fiercest of Foes
    262: '0a01000000000000000000000000000000000000',  # Unnatural Disaster
    263: '0a01000000000000000000000000000000000000',  # The Siege of Fort Hateno
    264: 'cd00000000000000000000000000000000000000',  # Versus Astor
    265: 'b9000201ca000000000000000000000000000000',  # Versus Harbinger Ganon
    266: '0801090100000000000000000000000000000000',  # Versus Calamity Ganon
    300: '1100000000000000000000000000000000000000',  # EX To Zelda's Side
    301: '2c01130000000000000000000000000000000000',  # EX Battle of Goponga Village
    302: '2c01130000000000000000000000000000000000',  # EX Battle for Kakariko Village
    303: '2c01150000000000000000000000000000000000',  # EX Searching Hyrule Forest
    304: '2c01150000000000000000000000000000000000',  # EX Liberate the Ancient Lab
    305: '2d012f011a000000000000000000000000000000',  # EX The Princess and the King
    306: '2e0130011a000000000000000000000000000000',  # EX The Yiga Clan's Retreat
    307: '3101320100000000000000000000000000000000',  # EX Guardian of Remembrance
    320: '0000000000000000000000000000000000000000',  # EX Alert: Forgotten Temple
    321: '0200000000000000000000000000000000000000',  # EX Alert: Hyrule Field
    322: '0900000000000000000000000000000000000000',  # EX Alert: Hyrule Outpost
    323: '0b00000000000000000000000000000000000000',  # EX Alert: Great Hyrule Forest
    324: '0d00000000000000000000000000000000000000',  # EX Alert: Akkala Citadel
    325: '0200000000000000000000000000000000000000',  # EX Alert: Breach of Demise
    326: '0c00000000000000000000000000000000000000',  # EX Alert: Crenel Peak
    327: '3301000000000000000000000000000000000000',  # EX Alert: Mount Daphnes
    328: '2d01000000000000000000000000000000000000',  # EX Alert: Goponga Village
    329: '2e01000000000000000000000000000000000000',  # EX Alert: Kakariko Village
    330: '3101000000000000000000000000000000000000',  # EX Alert: Lanayru Road
    350: '0100000000000000000000000000000000000000',  # EX Link: Flails
    351: '0200000000000000000000000000000000000000',  # EX Zelda: Master Cycle
    352: '1c00400100000000000000000000000000000000',  # EX Battle-Tested Guardian Training
    353: '1700000000000000000000000000000000000000',  # EX Ancient Threats
    354: '1900000000000000000000000000000000000000',  # EX Purah & Robbie's Study
    355: '1c00000000000000000000000000000000000000',  # EX Handle the Horde
    356: '1c00000000000000000000000000000000000000',  # EX Rupee Rescue
    357: '1c00000000000000000000000000000000000000',  # EX Battle Research: Skills
    358: '1c00000000000000000000000000000000000000',  # EX Battle Research: Items
    359: '1700000000000000000000000000000000000000',  # EX Road to Akkala Citadel
    360: '0701060100000000000000000000000000000000',  # EX Conquering Hyrule
    361: '6801000000000000000000000000000000000000',  # EX The Final Battle
    362: '1900670100000000000000000000000000000000',  # EX The Knight's Nightmare
    363: '1c00400100000000000000000000000000000000',  # EX Survival of the Fittest
    364: '6101000000000000000000000000000000000000',  # EX Request from the Lab
    365: '1900000000000000000000000000000000000000',  # EX Zelda's Culinary Research
    366: '3101000000000000000000000000000000000000',  # EX Evacuating Hyrule
    367: '3301000000000000000000000000000000000000',  # EX Purah & Robbie's Training
    368: '3201000000000000000000000000000000000000',  # EX Sooga's Training
    369: '750176010a010000000000000000000000000000',  # EX Facing Mutated Ganon
    370: '3301000000000000000000000000000000000000',  # EX A Moblin Feast
    371: '6f019b0000000000000000000000000000000000',  # EX The Budget Battle
    372: '7001000000000000000000000000000000000000',  # EX Sooga's Daily Routine
    373: '3301740000000000000000000000000000000000',  # EX Coliseum: Master
    374: '3301ca0000000000000000000000000000000000',  # EX Utmost Strength
}

# Quest (request) states: one byte per quest, 1101 entries; 1 = not available yet, 2 = available, 3 = done.
# Live: [P + 0x560] + 0x809 (current; saved copy +0x2550). Save: 0xB34. Index = the quest's entry in the game's
# quest text table (LinkData2 0x878494, 1000 quests x three strings, base and Expansion Pass). Confirmed: The Frontiers of Knowledge = 25.
QUEST_STATE_LIVE, QUEST_STATE_SAVE, QUEST_STATE_COUNT, QUEST_DONE = 0x809, 0xB34, 1101, 3
QUEST_HIDDEN = 1
QUEST_STATE_IDS = {
    'Hyrule Swordfighting Academy': 1,
    'Keeping the Village Peace': 2,
    'Study the Blade': 3,
    'The Blade that Pierces the Eye': 4,
    'Heartfelt Thanks': 5,
    'Making a Monster': 6,
    'The Hateno Defense Squad': 7,
    'The Volunteer Army': 8,
    "The Treasure Hunter's Technique": 9,
    'Refuel Motivation': 10,
    'A Spear-ited Combatant': 11,
    'Teach a Hylian to Fish': 12,
    "Mount Taran's Solitary Masters": 13,
    'Training Ground Pest Problem': 14,
    'Training Ground Upgrade': 15,
    'Proof of Sword Mastery': 16,
    'Full Bellies Fight Better': 17,
    'A Strike to Pierce Stone': 18,
    'A Well-Tended Goddess': 19,
    'A Flower-Adorned Goddess': 20,
    'A Moss-Covered Goddess': 21,
    'A Frozen-Solid Goddess': 22,
    'Frog Side Effects': 23,
    "The Knight's Gauntlet": 24,
    'The Frontiers of Knowledge': 25,
    'Preparing for Field Work': 26,
    'Ancient-Material Delivery': 27,
    'Soothing Tensions': 28,
    'Research Funding': 29,
    "King Dorephan's Defenses": 30,
    'Bolstering Goron City': 31,
    'Joint Training with the Rito': 32,
    'Joint Training with the Gerudo': 33,
    'A Modest Celebration': 34,
    'An Otherworldly Guardian': 35,
    'Giving Peace of Mind': 36,
    'A Princess in Distress': 37,
    'A Buffet of Delicacies': 38,
    'In Case of Emergency...': 39,
    'Research Materials': 40,
    'Living Things of Hyrule': 41,
    'Eternal Blooms': 42,
    "Woodcutter's Discipline": 43,
    'Perils of Mount Hylia': 44,
    'For the Future of Hyrule': 45,
    "The King's Secret Technique": 46,
    'A Flower Fit for a King': 47,
    'A King Serves His People': 48,
    'Scars of the Calamity': 49,
    'Medicine Is the Best Medicine': 50,
    'The Royal Treasury': 51,
    'Parental Support': 52,
    'Royal Inspection': 53,
    'Strategic Fortifications': 54,
    'Bounding Across the Waves': 55,
    'Climbing the Waterfall': 56,
    "The Zora Who Wouldn't Swim": 57,
    'Diving Safety': 58,
    'Diving as Battle Training': 59,
    'Armor that Shines Like a Jewel': 60,
    'A Fruitful Offering': 61,
    'Lauding a Champion': 62,
    'Feeding the Laborers': 63,
    'Imported Goods': 64,
    'To the Zora Voe and Vai': 65,
    'Armor for Whom?': 66,
    'A Battle against the Heat': 67,
    'Playing with Fire': 68,
    'Playing Cucco': 69,
    'These Muscles of Mine(rs)': 70,
    'To Stand atop the Lava': 71,
    'A Perfectly Honed Body': 72,
    'A Goron-Style Massage': 73,
    'An Irresistible Aroma': 74,
    'The Creative Fires': 75,
    'Fine Goron Dining': 76,
    'Gut-Check Challenge': 77,
    'Enduring Death Mountain': 78,
    'Upgrading the Flight Range': 79,
    'Learning to Become the Wind': 80,
    'A Fly-by-Night Operation': 81,
    'The Rito Flying Tournament': 82,
    'A Wish for a Fishy Dish': 83,
    'The Poem-Parsing Traveler': 84,
    'Soured Honeymoon': 85,
    'Beyond the Wall of Thunder': 86,
    'The Lodge at Hebra Trailhead': 87,
    'An Offering to the Rito Goddess': 88,
    'Across Tanagar Canyon': 89,
    'Flight Across Hyrule': 90,
    "Urbosa's Desert Training": 91,
    'Conducive to Conducting': 92,
    'Duel on Ploymus Mountain': 93,
    'Shocking Design Choices': 94,
    'Stealth Mission': 95,
    'The Tyrant of the Sand Sea': 96,
    'Conducting an Experiment': 97,
    'Colorful Kara Kara Bazaar': 98,
    'A Sweet Desert Garden': 99,
    'The Summer Breeze Festival': 100,
    "The Spa's New Service": 101,
    'Gerudo Nail Artistry': 102,
    'Traps for Kakariko Village': 103,
    'To Bring the Village Together': 104,
    'Village Training Secrets': 105,
    'Just the Right Light': 106,
    'The Kakariko Village Dojo': 107,
    "Opening the Mind's Eye": 108,
    "Kakariko's Best Babysitter": 109,
    'The Lights of Home': 110,
    'The Great Cucco Escape': 111,
    'The Mission of the Sheikah': 112,
    'Helping Out at Hateno Pasture': 113,
    'Plum Tuckered Out': 114,
    "Sidon's Waterfall Workshop": 115,
    'Chasing Mipha': 116,
    'Scouting the Training Ground': 117,
    'For the Future': 118,
    'Training at Lulu Lake': 119,
    'A Gift from the Sky': 120,
    'The Zora Researcher': 121,
    'A Thirst for the Desert': 122,
    'Lightning-Proof Luncheon': 123,
    'All the Heartiest Seafood': 124,
    'Blessing of the Rains': 125,
    'Feast or Fiction?': 126,
    'Goron Rations': 127,
    'To Eat a Stone Pebblit?': 128,
    'A Crucible of Endurance': 129,
    'What Do Guardians Taste Like?': 130,
    'Not a Light Meal': 131,
    'Eating a Varied Diet': 132,
    'The Rock-Hard Grill': 133,
    'Defend the Goron Hot Springs': 134,
    'A Goron Wrestling Tournament': 135,
    'The Rock Hurler': 136,
    "Daruk's Boot Camp": 137,
    'Fighting Fire With...': 138,
    'The White Bird of Talonto Peak': 139,
    'Flight Training at Lake Totori': 140,
    'The Strongest String': 141,
    'At All Hours': 142,
    'Rito Rations': 143,
    'Remodeling the Flight Range': 144,
    'Truffle Hunting in the Forest': 145,
    'Faster and Farther Than Anyone': 146,
    'A Surprise Reward': 147,
    'Cultivating Warm Safflina': 148,
    "Teba's Training Retreat": 149,
    'Flight-Range Field Trip': 150,
    'The Missing Sand Seals': 151,
    'Quality Time with Patricia': 152,
    'The Sapphire Seal Pageant': 153,
    'Fruitful Advice': 154,
    'Seal the Deal': 155,
    'Treats for Patricia': 156,
    '"Voe and You" Is in Session': 157,
    'Rebuilding Lipstique': 158,
    'My Beloved Yellow': 159,
    'The Wonders of Chuchu Jelly': 160,
    'Surviving the Gerudo Highlands': 161,
    'Surveying the Desert Ruins': 162,
    'Pinwheel, No-Spinwheel': 163,
    'Frown-Reversal Magic': 164,
    'Out of the Woods': 165,
    'A Leaf on the Breeze': 166,
    'Think Yourself Clever?': 167,
    'The Korok Who Cried Monster': 168,
    'Otherworldly Objects': 169,
    'The Mushroom Shop': 170,
    'Finding Courage': 171,
    'Helping with Heights': 172,
    "It's Shakala Time": 173,
    'Party for the Leafy Spirits': 174,
    'Luminous Earrings': 175,
    'Glorious Ring': 176,
    'Stunning Bracelet': 177,
    'Superb Necklace': 178,
    'Shimmering Horseshoe': 179,
    "It's Raining Rupees": 180,
    'No Stone Unturned': 181,
    'Encouraging Tourism': 182,
    'Dusty Desert Road': 183,
    'Only the Best': 184,
    'Lushify the Spring': 185,
    'Never Enough Fairies': 186,
    'Spicy Asceticism': 187,
    'Chilly Asceticism': 188,
    'Hoppy Asceticism': 189,
    'Hungry Asceticism': 190,
    'Big Moves to Boost Morale': 191,
    'No Matter the Cost': 192,
    'Market Apeel': 193,
    'Bonananza': 194,
    'An Unlikely Passion': 195,
    'A Thief in Our Midst': 196,
    'Veggie Vigor': 197,
    'From the Ground Up': 198,
    'Trial of Dah Hesho': 199,
    'Trial of Soh Kofi': 200,
    "Trial of Ke'nai Shakah": 201,
    'Trial of Muwo Jeem': 202,
    'Trial of Tutsuwa Nima': 203,
    'Trial of Chaas Qeta': 204,
    'Trial of Pumaag Nitae': 205,
    'Trial of Noya Neha': 206,
    'Trial of Shoqa Tatone': 207,
    'Trial of Sasa Kai': 208,
    'Trial of Goma Asaagh': 209,
    "Trial of Saas Ko'sah": 210,
    'Testing... Testing... One, Two...': 211,
    'Learning from the Best': 212,
    'Preserving for Posterity': 213,
    'Unrelenting Power': 214,
    'Fragmented Memories': 215,
    'Terrako, Enlightened': 216,
    'Terrako, Empowered': 217,
    'Tough as Nails': 218,
    'Tougher than Nails': 219,
    'Slightly Less Tougher than Nails...': 220,
    'Made with Love': 221,
    'To Brighten Her Day': 222,
    'Seething Malice': 223,
    'Hardhearted Malice': 224,
    'Slumbering Malice': 225,
    'Beastly Malice': 226,
    'Reigning Malice': 227,
    'Otherworldly Malice': 228,
    'Explosive Life Force': 229,
    'Nocturnal Life Force': 230,
    'Teeming Life Force': 231,
    'Hidden Life Force': 232,
    'Pursuing Ancient Power': 233,
    'Pursuing Supreme Power': 234,
    'Inner Power': 235,
    'Inner Knowing': 236,
    'Inner Protection': 237,
    'Roast and Relaxation': 238,
    'Chilly Path to a Hot Bath': 239,
    'A Light in the Dark': 240,
    'The Finest Tailor in the Land': 241,
    'Time for an Upgrade': 242,
    'Blessing of the Great Fairies': 243,
    'A Read on the Enemy': 244,
    'Eager Learners in Hateno Village': 245,
    'Hyrule Institute of Tactics Research': 246,
    'Explosive Endeavors': 247,
    'Strange and Unusual Monsters': 248,
    'Shocking Fear': 249,
    "Zappy 'n' Bouncy": 250,
    'A Stasis on Research': 251,
    'There Must Be Rice': 252,
    'Keep a Cool Head': 253,
    'Personal Distractions': 254,
    'More Rattle, More Dance!': 255,
    'The Korok Ballet': 256,
    'Good Cheer': 257,
    'Parade for the Champions': 258,
    'Forest Minuet': 259,
    'Birthday Waltz': 260,
    'It Takes Two': 261,
    'The Sweetest Salsa': 262,
    'Gerudo Canyon Festival': 263,
    'Fantastic Flamenco': 264,
    'Brilliance for the Boutique': 265,
    'Gotta Have a Sign': 266,
    'Shop-Quick Store': 267,
    'Pumpkin Burglars': 268,
    'Wanted: Shop Assistant': 269,
    'An End to Fighting': 270,
    'Wedding Worry': 271,
    'On the Hook': 272,
    'Swanked-Up Stable': 273,
    'Help Them on Their Way': 274,
    'Curry Connoisseur': 275,
    'Anything but Bugs': 276,
    'Hoping for Heat Relief': 277,
    'Great Bridge Repairs': 278,
    'What Bad Weather?': 279,
    'The Lazy Guards': 280,
    'Floria Bridge Protection': 281,
    'Lighting the Way': 282,
    'Rebuilding Akkala Bridge': 283,
    'The Marita Exchange': 284,
    'Goods on the Move in Hyrule!': 285,
    'Brawny Blacksmiths': 286,
    'Quarry Recruiting': 287,
    'Shiny New Tools': 288,
    'Fiery Inspiration': 289,
    'Off to the Hot Springs': 290,
    'A Monumental Undertaking': 291,
    'Tales of the Molten Forge': 292,
    'The Legendary Blacksmith': 293,
    'Caring for the Statues': 294,
    'Secret of the Rito Artisans': 295,
    'From Rusty to Trusty': 296,
    'Better Rust-Busting': 297,
    'Road to Rust Research': 298,
    'Needed: Researchers!': 299,
    'Feed the Research': 300,
    'Sweeten the Research': 301,
    'Fuel Up with Plants': 302,
    'Entrance Test': 303,
    'Tactics for Small Foes': 304,
    "The Instructor's Problem": 305,
    'Facing Powerful Enemies': 306,
    'Hot Meals in a Pot': 307,
    'Snowbound Cook': 308,
    'Master Monster Roasts': 309,
    'Expert Cooking Lesson': 310,
    'Stumped by Shrooms': 311,
    'The Pumpkin Hunt': 312,
    'A Balm for the Soul': 313,
    'Needs a Splash of...': 314,
    'Really New Recipe': 315,
    'Relieving Meat Fatigue': 316,
    'Just like Mama Made': 317,
    'Dish for a Diva': 318,
    'A Feast of Greens': 319,
    'Fine Bites from Lurelin Village': 320,
    'Bounty of the Sea': 321,
    'A Bird in the Hand': 322,
    'Bee Very Careful': 323,
    'Extreme Foraging': 324,
    'Afternoon Tea at Hyrule Castle': 325,
    'Mystery Meal for the Merchant': 326,
    'Unexpected Discovery': 327,
    'Cooking for the Common Cold': 328,
    'Superb Fish Dish': 329,
    "Who's Shocked by Lightning?": 330,
    'Extreme Survival Cuisine': 331,
    'A Birthday Treat': 332,
    'Best-Ever Batter': 333,
    'The Blessing of Deya Lake': 334,
    'The Legendary Recipe': 335,
    'Search Party for Parts': 336,
    'Gathering the Facts': 337,
    'The Eye That Sees Far': 338,
    "Let's Dance": 339,
    'A Secret in Song': 340,
    'Right under Our Noses': 341,
    'No Extreme Too Extreme': 342,
    'Searching Eventide Island': 343,
    "Terrako's Return": 344,
    'An Eye for Weapons': 345,
    'A Most Peculiar Korok': 346,
    'The Treasure Detector': 347,
    'Upgrading the Detector': 348,
    'The Hope of All Hyrule': 349,
    'Fang for Your Buck': 350,
    'Regulating the Reservoir': 351,
    'Surveying the Volcano': 352,
    'Revitalize Those in the Skies': 353,
    'Patrolling the Desert': 354,
    'Dyeing to Make Contact': 355,
    'Offering Help on the Road': 356,
    'The Trial of Monsters': 357,
    'The Trial of Stones': 358,
    'The Trial of the Mighty Foe': 359,
    'The Research of Rods': 360,
    'Relief for Soldier Stress': 361,
    'A Rumor about Skull Lake': 362,
    'Cold Desert Nights': 363,
    'Visiting a Special Shop': 364,
    "Painter's Pilgrimage": 365,
    'Peace Offering for Hyrule': 366,
    'The Lonely Goddess': 367,
    'The Hope of Central Hyrule': 368,
    'The Hope of Hebra': 369,
    'The Hope of Akkala': 370,
    'The Hope of Eldin': 371,
    'The Hope of Lanayru': 372,
    'The Hope of Necluda': 373,
    'The Hope of Faron': 374,
    'The Hope of Gerudo': 375,
    'Research of a Lifetime': 376,
    'The Master Chef': 377,
    "A Painter's Inspiration": 378,
    'A Sparkling Solution': 379,
    'Custom-Made Color': 380,
    'A Color Seen in a Dream': 381,
    'EX Seeking Wooden Swords': 401,
    "EX The Squad's Training Retreat": 402,
    'EX A Spear Experiment': 403,
    'EX The Copy Tournament': 404,
    'EX Secret Plans': 405,
    'EX Reunion with the Swordmaster': 406,
    'EX Stamina Woes': 407,
    'EX Break the Obstacles': 408,
    'EX Horsemanship and Horsepower': 409,
    'EX Snow Business': 410,
    'EX Safe Roads, Safe Rides': 411,
    'EX Ride Across Hyrule!': 412,
    'EX The More the Merrier': 413,
    'EX Respect the Elements': 414,
    'EX Harder Than a Guardian?': 415,
    'EX The Ultimate Guardian Showdown!': 416,
    'EX All Enemies Welcome': 417,
    'EX Undeniable Proof': 418,
    'EX Battle-Tested Research': 419,
    'EX Searching for Monster Data': 420,
    'EX Curious Materials': 421,
    'EX Lessons of the Past': 422,
    'EX Regular Maintenance': 423,
    'EX No Detail Too Small': 424,
    'EX A Shocking Run': 431,
    'EX Endless Perseverance': 432,
    'EX Burning Desire': 433,
    "EX Sooga's Swords": 434,
    'EX Taking Aim': 435,
    'EX Secret Wisdom': 436,
    "EX The Right Hand's Hassle": 437,
    'EX Unsung Hero': 438,
    'EX Secret Meetings': 439,
    'EX Monster Troubles': 440,
    'EX A Long-Awaited Battle': 441,
    'EX The Right Hand Strikes Again': 442,
    'EX The Only Option': 443,
    "EX The Relic's Clue": 444,
    'EX The Science of Battle': 445,
    'EX Food for Thought': 446,
    'EX Light as a Feather': 447,
    'EX The Fruits of Ancient-Tech Research': 448,
    'EX A Century of Memories': 449,
    'EX Despicable Distractions': 450,
    'EX A Morsel of Morale': 451,
    'EX All Work and Some Play': 452,
    'EX Peak Condition': 453,
    'EX Perfect Harmony': 454,
    'EX A Royal Gift for Mipha': 455,
    'EX A Royal Gift for Sidon': 456,
    'EX A Royal Gift for Daruk': 457,
    'EX A Royal Gift for Yunobo': 458,
    'EX A Royal Gift for Revali': 459,
    'EX A Royal Gift for Teba': 460,
    'EX A Royal Gift for Urbosa': 461,
    'EX A Royal Gift for Riju': 462,
    'EX The Text of Tomorrow': 463,
    'EX Hasty Recovery': 464,
    'EX Spear Master': 465,
    'EX A Giant Leap': 466,
    'EX Awkward Allies': 467,
    'EX Analysis and Countermeasures': 468,
    'EX Keeping a Promise': 469,
    'EX Survive the Training': 470,
    'EX The Art of Flight': 471,
    'EX Law of the Gerudo': 472,
    'EX Hard Defenses': 473,
    'EX Unstoppable Sidon': 474,
    'EX Goron-Sized Appetites': 475,
    'EX Aim True at the Calamity': 476,
    'EX Sand-Seal Bonding': 477,
    'EX Korok Curiosity': 478,
    'EX The Dazzling Crown': 479,
    "EX Master Kohga's Lightning Training": 480,
    'EX Trial of Kema Kosassa': 481,
    'EX Relic Lessons': 482,
    'EX Violent Obsessions': 483,
}

# Combo upgrades: 28 levels (one byte each) at profile [P+0x588] + 0x73B (copy 3 at +3*0xC30); save 0x2C014.
# Each upgrade quest raises one category by 1 (quest table LinkData2 file 0086ee94, 1000 x 80, byte +0x2B =
# category + 1; cost amounts u16 at +0x10, material ids + 1 at +0x26). Confirmed: The Frontiers of Knowledge -> 5.
UPGRADE_LEVELS, UPGRADE_CATEGORIES = 0x73B, 28
# Per-hero quest rewards, one byte per hero slot (21) in the profile (saved copy +3*0xC30), read live by the game
# [confirmed in game: setting Mipha's entry to 1 gave her a 5th heart / a 2nd special gauge]: bonus hearts (heart
# quests, quest table type 3 / +0x2E = 1) and extra special gauges (type 4, hero = row +0x2F - 1; Frog Side Effects
# wrote Link's entry). Type 3 / +0x2E = 2 is something else (unknown yet). Save = profile + 0x2BC06.
HERO_BONUS = {"Heart Container": 0xAFC, "Special Gauge Upgrade": 0xB19}
# Most the vanilla quests give per hero: hearts +1 and +2 (type 3, row +0x2E = amount), gauges +1 twice (type 4).
HERO_BONUS_MAX = {"Heart Container": 3, "Special Gauge Upgrade": 2}
# Quest type 46 gives every hero +1 heart (same array); those stay vanilla, so their count is added on top.
ALL_HERO_HEART_QUESTS = ("Painter's Pilgrimage", "Peace Offering for Hyrule", "The Lonely Goddess")
HERO_BONUS_COUNT = 21
# Enhanced abilities: one flag per combo category at profile + 0x121 (saved copy too) [confirmed in game: Mipha's
# "Armor that Shines Like a Jewel" set profile + 0x129, category 8]. Categories per hero from the quest table
# (type 2, +0x2C = category + 1); EX ones only with the Expansion Pass. Categories 6 and 26 have no known hero.
ABILITY_FLAGS = 0x121
ABILITY_CATEGORIES: dict[str, tuple[int, ...]] = {
    "Link": (0, 1, 2), "Zelda": (5,), "King Rhoam": (7,), "Mipha": (8,), "Daruk": (9,), "Revali": (10,),
    "Urbosa": (11,), "Impa": (12,), "Sidon": (13,), "Yunobo": (14,), "Teba": (15,), "Riju": (16,), "Hestu": (17,),
    "Great Fairies": (18,), "Master Kohga": (19,), "Monk Maz Koshia": (20,), "Terrako": (21,), "Calamity Ganon": (22,),
}
ABILITY_CATEGORIES_DLC: dict[str, tuple[int, ...]] = {"Link": (23,), "Zelda": (24,), "Purah & Robbie": (25,), "Sooga": (27,)}
# Weapon capacity: profile + 0x7A6 = level, slots = 20 + level [confirmed in game]; the dance quests (type 15) set it
# to their tier (row +0x31), at most 4.
WEAPON_CAPACITY_LEVEL, WEAPON_CAPACITY_MAX = 0x7A6, 4
# Category -> hero, read from each category's quest texts. 7 and 27 unclear (texts mention Dorephan / the Yiga);
# 10 is probably Daruk (guess).
UPGRADE_CATEGORY_HERO = {
    0: 'Link',
    1: 'Link',
    2: 'Link',
    5: 'Zelda',
    7: 'King Rhoam',
    8: 'Mipha',
    9: 'Daruk',
    10: 'Revali',
    11: 'Urbosa',
    12: 'Impa',
    13: 'Sidon',
    14: 'Yunobo',
    15: 'Teba',
    16: 'Riju',
    17: 'Hestu',
    18: 'Great Fairies',
    19: 'Master Kohga',
    20: 'Monk Maz Koshia',
    21: 'Terrako',
    22: 'Calamity Ganon',
    23: 'Link',
    24: 'Zelda',
    25: 'Purah & Robbie',
    27: 'Sooga',
}
def quest_hero(quest: str) -> str | None:
    """The hero a combo-upgrade quest belongs to (the game greys it out while that hero isn't yours)."""
    return UPGRADE_CATEGORY_HERO.get(QUEST_UPGRADE_CATEGORY.get(quest, -1))


QUEST_UPGRADE_CATEGORY = {
    'Hyrule Swordfighting Academy': 0,
    'Keeping the Village Peace': 0,
    'Study the Blade': 0,
    'The Blade that Pierces the Eye': 0,
    'Heartfelt Thanks': 0,
    'Making a Monster': 1,
    'The Hateno Defense Squad': 1,
    'The Volunteer Army': 1,
    "The Treasure Hunter's Technique": 1,
    'Refuel Motivation': 1,
    'A Spear-ited Combatant': 2,
    'Teach a Hylian to Fish': 2,
    "Mount Taran's Solitary Masters": 2,
    'Training Ground Pest Problem': 2,
    'Training Ground Upgrade': 2,
    'The Frontiers of Knowledge': 5,
    'Preparing for Field Work': 5,
    'Soothing Tensions': 5,
    'Research Funding': 5,
    "King Dorephan's Defenses": 6,
    'Bolstering Goron City': 6,
    'Joint Training with the Rito': 6,
    'Joint Training with the Gerudo': 6,
    'A Modest Celebration': 6,
    "Woodcutter's Discipline": 7,
    'Perils of Mount Hylia': 7,
    'For the Future of Hyrule': 7,
    "The King's Secret Technique": 7,
    'A Flower Fit for a King': 7,
    'Bounding Across the Waves': 8,
    'Climbing the Waterfall': 8,
    "The Zora Who Wouldn't Swim": 8,
    'Diving Safety': 8,
    'Diving as Battle Training': 8,
    'A Battle against the Heat': 9,
    'Playing with Fire': 9,
    'Playing Cucco': 9,
    'These Muscles of Mine(rs)': 9,
    'To Stand atop the Lava': 9,
    'Upgrading the Flight Range': 10,
    'Learning to Become the Wind': 10,
    'A Fly-by-Night Operation': 10,
    'The Rito Flying Tournament': 10,
    'A Wish for a Fishy Dish': 10,
    "Urbosa's Desert Training": 11,
    'Conducive to Conducting': 11,
    'Duel on Ploymus Mountain': 11,
    'Shocking Design Choices': 11,
    'Stealth Mission': 11,
    'Traps for Kakariko Village': 12,
    'To Bring the Village Together': 12,
    'Village Training Secrets': 12,
    'Just the Right Light': 12,
    'The Kakariko Village Dojo': 12,
    "Sidon's Waterfall Workshop": 13,
    'Chasing Mipha': 13,
    'Scouting the Training Ground': 13,
    'For the Future': 13,
    'Training at Lulu Lake': 13,
    'Goron Rations': 14,
    'To Eat a Stone Pebblit?': 14,
    'A Crucible of Endurance': 14,
    'What Do Guardians Taste Like?': 14,
    'Not a Light Meal': 14,
    'The White Bird of Talonto Peak': 15,
    'Flight Training at Lake Totori': 15,
    'The Strongest String': 15,
    'At All Hours': 15,
    'Rito Rations': 15,
    'The Missing Sand Seals': 16,
    'Quality Time with Patricia': 16,
    'The Sapphire Seal Pageant': 16,
    'Fruitful Advice': 16,
    'Seal the Deal': 16,
    'Pinwheel, No-Spinwheel': 17,
    'Frown-Reversal Magic': 17,
    'Out of the Woods': 17,
    'A Leaf on the Breeze': 17,
    'Think Yourself Clever?': 17,
    'Luminous Earrings': 18,
    'Glorious Ring': 18,
    'Stunning Bracelet': 18,
    'Superb Necklace': 18,
    'Shimmering Horseshoe': 18,
    'Spicy Asceticism': 19,
    'Chilly Asceticism': 19,
    'Hoppy Asceticism': 19,
    'Hungry Asceticism': 19,
    'Big Moves to Boost Morale': 19,
    'Trial of Dah Hesho': 20,
    'Trial of Soh Kofi': 20,
    "Trial of Ke'nai Shakah": 20,
    'Trial of Muwo Jeem': 20,
    'Trial of Tutsuwa Nima': 20,
    'Testing... Testing... One, Two...': 21,
    'Learning from the Best': 21,
    'Preserving for Posterity': 21,
    'Unrelenting Power': 21,
    'Fragmented Memories': 21,
    'Hardhearted Malice': 22,
    'Slumbering Malice': 22,
    'Beastly Malice': 22,
    'EX Seeking Wooden Swords': 23,
    "EX The Squad's Training Retreat": 23,
    'EX A Spear Experiment': 23,
    'EX The Copy Tournament': 23,
    'EX Secret Plans': 23,
    'EX Stamina Woes': 24,
    'EX Break the Obstacles': 24,
    'EX Horsemanship and Horsepower': 24,
    'EX Snow Business': 24,
    'EX Safe Roads, Safe Rides': 24,
    'EX The More the Merrier': 25,
    'EX Respect the Elements': 25,
    'EX Harder Than a Guardian?': 25,
    'EX The Ultimate Guardian Showdown!': 25,
    'EX All Enemies Welcome': 25,
    'EX A Shocking Run': 27,
    'EX Endless Perseverance': 27,
    'EX Burning Desire': 27,
    "EX Sooga's Swords": 27,
    'EX Taking Aim': 27,
    'EX The Only Option': 26,
    "EX The Relic's Clue": 26,
    'EX The Science of Battle': 26,
    'EX Food for Thought': 26,
    'EX Light as a Feather': 26,
}

# Weapon kinds (owned-weapons pool +0x10) of each weapon: name = entry 2*kind of the weapon text table
# (LinkData2 0xFF5914, 592 kinds). Some names have two kinds (variants).
WEAPON_KINDS = {
    'Tree Branch': (1,),
    'Soup Ladle': (2,),
    "Traveler's Sword": (3,),
    "Soldier's Broadsword": (4,),
    "Knight's Broadsword": (5,),
    'Royal Broadsword': (6,),
    "Forest Dweller's Sword": (7,),
    'Zora Sword': (8,),
    'Feathered Edge': (9,),
    'Ancient Short Sword': (10,),
    "Royal Guard's Sword": (11,),
    'Boko Club': (12,),
    'Spiked Boko Club': (13,),
    'Dragonbone Boko Club': (14,),
    'Lizal Boomerang': (15,),
    'Lizal Forked Boomerang': (16,),
    'Lizal Tri-Boomerang': (17,),
    'Guardian Sword': (18,),
    'Guardian Sword+': (19,),
    'Guardian Sword++': (20,),
    'Lynel Sword': (21,),
    'Mighty Lynel Sword': (22,),
    'Savage Lynel Sword': (23,),
    'Boomerang': (24,),
    'Spring-Loaded Hammer': (25,),
    'Bokoblin Arm': (26,),
    'Lizalfos Arm': (27,),
    'Master Sword': (28,),
    'Training Sword': (29,),
    'Lucky Ladle': (30,),
    'Prototype Ancient Short Sword': (31,),
    'Korok Leaf': (51,),
    'Farming Hoe': (52,),
    'Boat Oar': (53,),
    'Iron Sledgehammer': (54,),
    "Woodcutter's Axe": (55,),
    'Double Axe': (56,),
    'Giant Boomerang': (57,),
    "Traveler's Claymore": (58,),
    'Zora Longsword': (59,),
    'Gerudo Claymore': (60,),
    'Eightfold Longblade': (61,),
    'Edge of Duality': (62,),
    'Ancient Bladesaw': (63,),
    "Royal Guard's Claymore": (64,),
    'Boko Bat': (65,),
    'Spiked Boko Bat': (66,),
    'Dragonbone Boko Bat': (67,),
    'Moblin Club': (68,),
    'Spiked Moblin Club': (69,),
    'Dragonbone Moblin Club': (70,),
    'Ancient Battle Axe': (71,),
    'Ancient Battle Axe+': (72,),
    'Ancient Battle Axe++': (73,),
    'Lynel Crusher': (74,),
    'Mighty Lynel Crusher': (75,),
    'Savage Lynel Crusher': (76,),
    'Windcleaver': (77,),
    'Moblin Arm': (78,),
    'Wooden Mop': (101,),
    "Farmer's Pitchfork": (102,),
    'Throwing Spear': (103,),
    "Soldier's Spear": (104,),
    "Knight's Halberd": (105,),
    'Royal Halberd': (106,),
    "Forest Dweller's Spear": (107,),
    'Drillshaft': (108,),
    'Feathered Spear': (109,),
    'Gerudo Spear': (110,),
    'Serpentine Spear': (111,),
    'Ancient Spear': (112,),
    "Royal Guard's Spear": (113,),
    'Boko Spear': (114,),
    'Spiked Boko Spear': (115,),
    'Dragonbone Boko Spear': (116,),
    'Moblin Spear': (117,),
    'Spiked Moblin Spear': (118,),
    'Dragonbone Moblin Spear': (119,),
    'Lizal Spear': (120,),
    'Enhanced Lizal Spear': (121,),
    'Forked Lizal Spear': (122,),
    'Guardian Spear': (123,),
    'Guardian Spear+': (124,),
    'Guardian Spear++': (125,),
    'Lynel Spear': (126,),
    'Mighty Lynel Spear': (127,),
    'Savage Lynel Spear': (128,),
    'Ancient Memory Part': (171,),
    'Ancient Power Boost': (172,),
    'Ancient Overclock Unit': (173,),
    'Sacred Bow': (181,),
    'Sealing Bow': (182,),
    'Bow of Light': (183,),
    "Soldier's Claymore": (191,),
    "Knight's Claymore": (192,),
    'Royal Claymore': (193,),
    "Traveler's Spear": (201,),
    'Zora Spear': (202,),
    'Lightscale Trident': (203, 204),
    "Serene Champion's Spear": (205,),
    'Cobble Crusher': (211,),
    'Stone Smasher': (212,),
    'Boulder Breaker': (213, 214),
    "Steadfast Champion's Greatsword": (215,),
    "Traveler's Bow": (221,),
    "Soldier's Bow": (222,),
    'Great Eagle Bow': (223, 224),
    "Soaring Champion's Bow": (225,),
    'Gerudo Scimitar': (231,),
    'Moonlight Scimitar': (232,),
    'Scimitar of the Seven': (233, 234),
    "Nimble Champion's Sword": (235,),
    'Kakariko Kodachi': (241,),
    'Faithful Kodachi': (242,),
    'Devoted Kodachi': (243,),
    'Fishing Harpoon': (251,),
    'Silverscale Spear': (252,),
    'Ceremonial Trident': (253,),
    "Gallant Hero's Spear": (255,),
    'Raw Rock Roast': (261, 264),
    'Medium-Rare Rock Roast': (262,),
    'Rock Roast Flambé': (263,),
    "Stalwart Hero's Feast": (265,),
    'Wooden Bow': (271,),
    'Swallow Bow': (272,),
    'Falcon Bow': (273,),
    "Swift Hero's Bow": (275,),
    'Gerudo Bridle': (281, 284),
    'Starlight Bridle': (282,),
    'Bridle of the Seven': (283,),
    "Thunderous Hero's Bridle": (285,),
    'Maracas': (291,),
    'Shaka Maracas': (292,),
    'Shakalaka Maracas': (293,),
    'Dazzling Bangles': (301,),
    'Luxurious Bangles': (302,),
    'Extravagant Bangles': (303,),
    'Eightfold Blade': (311,),
    'Vicious Sickle': (312,),
    'Demon Carver': (313,),
    "Monk's Bands": (321,),
    'Bands of Enlightenment': (322,),
    'Bands of Truth': (323,),
    'Blessed Screw': (331, 334),
    'Benevolent Spring': (332,),
    'Gear of the Protector': (333,),
    'Cursed Bone Shard': (341,),
    'Malevolent Spine': (342,),
    'Heart of Annihilation': (343,),
    'Guardian Flail': (351,),
    'Ancient Bladed Flail': (352,),
    'Fortified Flail': (353,),
    'Master Cycle': (361,),
    'Master Cycle Hunter': (362,),
    'Master Cycle Sentinel': (363,),
    'Battle-Tested Screw': (371,),
    'Battle-Tested Spring': (372,),
    'Battle-Tested Gear': (373,),
    'Prototype Sheikah Arms': (381,),
    'Refined Sheikah Arms': (382,),
    'Ultimate Sheikah Arms': (383,),
    'Swords of Ferocity': (391, 394),
    'Swords of Devotion': (392,),
    'Swords of Valiance': (393,),
}

# Save-file weapon pool: 81-byte records, 71 per hero slot, weapon kind u16 at SAVE_WEAPONS + 81 * record.
SAVE_WEAPONS, SAVE_WEAPON_RECORD, SAVE_WEAPONS_PER_HERO = 0x11E6, 81, 71

# Each hero's basic weapon (a new game hands several out; the client gives the rest to received heroes). No checks.
BASIC_WEAPONS = frozenset(n for n, kinds in WEAPON_KINDS.items() if set(kinds) & set(HERO_STARTER_KIND.values()))
