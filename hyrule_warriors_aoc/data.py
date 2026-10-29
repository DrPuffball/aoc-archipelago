"""
Static game data for Hyrule Warriors: Age of Calamity.

Corrections are one-line edits here (or in the data_*.py tables). Entries marked UNVERIFIED are best
guesses; the logic is built so a wrong guess can only make seeds *stricter* than the real game,
never unbeatable (see rules.py).

ID layout is append-only and reserved by range so adding data never shifts existing IDs:
  items:     characters 0-49, per-character upgrades 50-399, global upgrades 400-449, features 450-499,
             weapons 500-699, filler 700-799 (800-849 reserved, unused)
  locations: missions 0-99, quests 100-699, challenges 700-999, koroks 1000-1199, weapons 1200-1399
"""

from __future__ import annotations

from typing import NamedTuple

GAME_NAME = "Hyrule Warriors Age of Calamity"

BASE_ID = 20_201_120  # release date, only used as a unique base
ITEM_ID_BASE = BASE_ID
LOCATION_ID_BASE = BASE_ID + 1000

# ---------------------------------------------------------------------------------------
# Characters (append-only order: it defines item IDs)
# ---------------------------------------------------------------------------------------

BASE_CHARACTERS = [
    "Link", "Impa", "Zelda",
    "Mipha", "Daruk", "Revali", "Urbosa", "Hestu", "Sidon", "Yunobo", "Teba", "Riju",
    "Master Kohga", "King Rhoam",
    "Great Fairies", "Monk Maz Koshia", "Terrako", "Calamity Ganon",
]
# Expansion Pass characters (UNVERIFIED names/availability); only used when include_dlc is on.
DLC_CHARACTERS = ["Purah & Robbie", "Sooga"]
ALL_CHARACTERS = BASE_CHARACTERS + DLC_CHARACTERS

# ---------------------------------------------------------------------------------------
# Main story missions
# ---------------------------------------------------------------------------------------


class Mission(NamedTuple):
    name: str
    chapter: int
    # Names of the *slots* (vanilla mission at that position) that must be cleared first.
    # With vanilla order the slot is the mission itself. Extra prerequisites are always safe.
    prerequisites: tuple[str, ...]


_CHAMPIONS = (
    "Mipha, the Zora Princess",
    "Daruk, the Goron Hero",
    "Revali, the Rito Warrior",
    "Urbosa, the Gerudo Chief",
)

MISSIONS: list[Mission] = [
    Mission("The Battle of Hyrule Field", 1, ()),
    Mission("Road to the Ancient Lab", 1, ("The Battle of Hyrule Field",)),
    Mission("Mipha, the Zora Princess", 2, ("Road to the Ancient Lab",)),
    Mission("Daruk, the Goron Hero", 2, ("Road to the Ancient Lab",)),
    Mission("Revali, the Rito Warrior", 2, ("Road to the Ancient Lab",)),
    Mission("Urbosa, the Gerudo Chief", 2, ("Road to the Ancient Lab",)),
    Mission("The Yiga Clan Attacks!", 2, _CHAMPIONS),
    Mission("Freeing Korok Forest", 3, ("The Yiga Clan Attacks!",)),
    Mission("The Road Home, Besieged", 3, ("Freeing Korok Forest",)),
    # Chapter 4 ordering UNVERIFIED (chained); extra prerequisites are safe.
    Mission("Akkala Tower", 4, ("The Road Home, Besieged",)),
    Mission("Destroy the Yiga Clan!", 4, ("Akkala Tower",)),
    Mission("When Courage Fails", 4, ("Destroy the Yiga Clan!",)),
    Mission("Calamity Strikes", 5, ("When Courage Fails",)),
    Mission("Water and Fire", 5, ("Calamity Strikes",)),
    Mission("Air and Lightning", 5, ("Calamity Strikes",)),
    Mission("Relentless as a Waterfall", 6, ("Water and Fire", "Air and Lightning")),
    Mission("Each Step Like Thunder", 6, ("Water and Fire", "Air and Lightning")),
    Mission("The Great Plateau", 7, ("Relentless as a Waterfall", "Each Step Like Thunder")),
    Mission("All Hyrule, United", 7, ("The Great Plateau",)),
    Mission("The Future of Hyrule", 7, ("All Hyrule, United",)),
]
# Characters the story forces into the party in the base game (UNVERIFIED; only used with story_party: vanilla).
MISSION_PARTY: dict[str, tuple[str, ...]] = {
    "Mipha, the Zora Princess": ("Mipha",),
    "Daruk, the Goron Hero": ("Daruk",),
    "Revali, the Rito Warrior": ("Revali",),
    "Urbosa, the Gerudo Chief": ("Urbosa",),
    "Freeing Korok Forest": ("Hestu",),
    "Calamity Strikes": ("Mipha", "Daruk", "Revali", "Urbosa"),
    "Water and Fire": ("Sidon", "Yunobo"),
}

# Heroes a story mission brings along as AI allies (mission parameter table t009cc294 +75..+79, read from the game's
# data). The game will not let you pick them for that mission [confirmed in game: Calamity Strikes locks out the
# four Champions], so the party has to come from the other heroes.
MISSION_SUPPORT: dict[str, tuple[str, ...]] = {
    "Revali, the Rito Warrior": ("Zelda",),
    "The Yiga Clan Attacks!": ("Zelda",),
    "The Road Home, Besieged": ("Zelda",),
    "When Courage Fails": ("Zelda",),
    "Calamity Strikes": ("Mipha", "Daruk", "Revali", "Urbosa", "Hestu"),
    "Water and Fire": ("Mipha", "Daruk"),
    "Air and Lightning": ("Revali", "Urbosa"),
    "Relentless as a Waterfall": ("Sidon", "Purah & Robbie"),
    "Each Step Like Thunder": ("Urbosa", "Riju", "Purah & Robbie"),
    "The Great Plateau": ("Purah & Robbie",),
    "All Hyrule, United": ("Mipha", "Daruk", "Revali", "Urbosa"),
}

MISSION_BY_NAME = {m.name: m for m in MISSIONS}
MISSION_NAMES = [m.name for m in MISSIONS]
FINAL_MISSION = "The Future of Hyrule"

# ---------------------------------------------------------------------------------------
# Weapons. Names are the game's own (read from the player's dump, 164 distinct). Wielders are
# assigned by weapon family (champion weapons, Yiga weapons, ...); everything else is Link's. A weapon
# the wrong character "owns" can only make a check stricter, never impossible.
# Which mission a weapon first drops in is NOT known yet (that is in the binary parameter tables), so
# the gate is the wielder's introduction mission.
# ---------------------------------------------------------------------------------------

_WEAPON_GATE = {
    "Mipha": "Mipha, the Zora Princess", "Daruk": "Daruk, the Goron Hero",
    "Revali": "Revali, the Rito Warrior", "Urbosa": "Urbosa, the Gerudo Chief",
    "Hestu": "Freeing Korok Forest", "Sidon": "Water and Fire", "Yunobo": "Water and Fire",
    "Teba": "Air and Lightning", "Riju": "Air and Lightning",
    "Master Kohga": "The Great Plateau", "Great Fairies": "The Great Plateau",
    "Monk Maz Koshia": "The Great Plateau", "Terrako": "The Great Plateau",
}


class Weapon(NamedTuple):
    name: str
    character: str  # "" = no particular wielder
    gate_mission: str  # mission that must be cleared before the weapon can plausibly be obtained
    dlc: bool = False
    verified: bool = False


WEAPON_TABLE = """
# name | wielder (blank = any) | dlc
Tree Branch | Link | 
Soup Ladle | Link | 
Traveler's Sword | Link | 
Soldier's Broadsword | Link | 
Knight's Broadsword | Link | 
Royal Broadsword | Link | 
Forest Dweller's Sword | Link | 
Zora Sword | Link | 
Feathered Edge | Link | 
Ancient Short Sword | Link | 
Royal Guard's Sword | Link | 
Boko Club | Link | 
Spiked Boko Club | Link | 
Dragonbone Boko Club | Link | 
Lizal Boomerang | Link | 
Lizal Forked Boomerang | Link | 
Lizal Tri-Boomerang | Link | 
Guardian Sword | Link | 
Guardian Sword+ | Link | 
Guardian Sword++ | Link | 
Lynel Sword | Link | 
Mighty Lynel Sword | Link | 
Savage Lynel Sword | Link | 
Boomerang | Link | 
Spring-Loaded Hammer | Link | 
Bokoblin Arm | Link | 
Lizalfos Arm | Link | 
Master Sword | Link | 
Training Sword | Link | 
Lucky Ladle | Link | 
Prototype Ancient Short Sword | Link | 
Korok Leaf | Link | 
Farming Hoe | Link | 
Boat Oar | Link | 
Iron Sledgehammer | Link | 
Woodcutter's Axe | Link | 
Double Axe | Link | 
Giant Boomerang | Link | 
Traveler's Claymore | Link | 
Zora Longsword | Link | 
Gerudo Claymore | Link | 
Eightfold Longblade | Link | 
Edge of Duality | Link | 
Ancient Bladesaw | Link | 
Royal Guard's Claymore | Link | 
Boko Bat | Link | 
Spiked Boko Bat | Link | 
Dragonbone Boko Bat | Link | 
Moblin Club | Link | 
Spiked Moblin Club | Link | 
Dragonbone Moblin Club | Link | 
Ancient Battle Axe | Link | 
Ancient Battle Axe+ | Link | 
Ancient Battle Axe++ | Link | 
Lynel Crusher | Link | 
Mighty Lynel Crusher | Link | 
Savage Lynel Crusher | Link | 
Windcleaver | Link | 
Moblin Arm | Link | 
Wooden Mop | Link | 
Farmer's Pitchfork | Link | 
Throwing Spear | Link | 
Soldier's Spear | Link | 
Knight's Halberd | Link | 
Royal Halberd | Link | 
Forest Dweller's Spear | Link | 
Drillshaft | Link | 
Feathered Spear | Link | 
Gerudo Spear | Link | 
Serpentine Spear | Link | 
Ancient Spear | Link | 
Royal Guard's Spear | Link | 
Boko Spear | Link | 
Spiked Boko Spear | Link | 
Dragonbone Boko Spear | Link | 
Moblin Spear | Link | 
Spiked Moblin Spear | Link | 
Dragonbone Moblin Spear | Link | 
Lizal Spear | Link | 
Enhanced Lizal Spear | Link | 
Forked Lizal Spear | Link | 
Guardian Spear | Link | 
Guardian Spear+ | Link | 
Guardian Spear++ | Link | 
Lynel Spear | Link | 
Mighty Lynel Spear | Link | 
Savage Lynel Spear | Link | 
Ancient Memory Part | Zelda | 
Ancient Power Boost | Zelda | 
Ancient Overclock Unit | Zelda | 
Sacred Bow | Zelda | 
Sealing Bow | Zelda | 
Bow of Light | Zelda | 
Soldier's Claymore | Link | 
Knight's Claymore | Link | 
Royal Claymore | Link | 
Traveler's Spear | Link | 
Zora Spear | Link | 
Lightscale Trident | Mipha | 
Serene Champion's Spear | Mipha | 
Cobble Crusher | Daruk | 
Stone Smasher | Daruk | 
Boulder Breaker | Daruk | 
Steadfast Champion's Greatsword | Daruk | 
Traveler's Bow | Link | 
Soldier's Bow | Link | 
Great Eagle Bow | Revali | 
Soaring Champion's Bow | Revali | 
Gerudo Scimitar | Urbosa | 
Moonlight Scimitar | Urbosa | 
Scimitar of the Seven | Urbosa | 
Nimble Champion's Sword | Urbosa | 
Kakariko Kodachi | Impa | 
Faithful Kodachi | Impa | 
Devoted Kodachi | Impa | 
Fishing Harpoon | Sidon | 
Silverscale Spear | Sidon | 
Ceremonial Trident | Sidon | 
Gallant Hero's Spear | Sidon | 
Raw Rock Roast | Yunobo | 
Medium-Rare Rock Roast | Yunobo | 
Rock Roast Flambé | Yunobo | 
Stalwart Hero's Feast | Yunobo | 
Wooden Bow | Teba | 
Swallow Bow | Teba | 
Falcon Bow | Teba | 
Swift Hero's Bow | Teba | 
Gerudo Bridle | Riju | 
Starlight Bridle | Riju | 
Bridle of the Seven | Riju | 
Thunderous Hero's Bridle | Riju | 
Maracas | Hestu | 
Shaka Maracas | Hestu | 
Shakalaka Maracas | Hestu | 
Dazzling Bangles | Great Fairies | 
Luxurious Bangles | Great Fairies | 
Extravagant Bangles | Great Fairies | 
Eightfold Blade | Master Kohga | 
Vicious Sickle | Master Kohga | 
Demon Carver | Master Kohga | 
Monk's Bands | Monk Maz Koshia | 
Bands of Enlightenment | Monk Maz Koshia | 
Bands of Truth | Monk Maz Koshia | 
Blessed Screw | Terrako | 
Benevolent Spring | Terrako | 
Gear of the Protector | Terrako | 
Cursed Bone Shard | Calamity Ganon | 
Malevolent Spine | Calamity Ganon | 
Heart of Annihilation | Calamity Ganon | 
Guardian Flail | Link | dlc
Ancient Bladed Flail | Link | dlc
Fortified Flail | Link | dlc
Master Cycle | Zelda | dlc
Master Cycle Hunter | Zelda | dlc
Master Cycle Sentinel | Zelda | dlc
Battle-Tested Screw |  | dlc
Battle-Tested Spring |  | dlc
Battle-Tested Gear |  | dlc
Prototype Sheikah Arms | Purah & Robbie | dlc
Refined Sheikah Arms | Purah & Robbie | dlc
Ultimate Sheikah Arms | Purah & Robbie | dlc
Swords of Ferocity | Sooga | dlc
Swords of Devotion | Sooga | dlc
Swords of Valiance | Sooga | dlc
"""


def _build_weapons() -> list[Weapon]:
    out: list[Weapon] = []
    for line in WEAPON_TABLE.strip().splitlines():
        if not line or line.startswith("#"):
            continue
        name, who, dlc = (part.strip() for part in line.split("|"))
        out.append(Weapon(name, who, _WEAPON_GATE.get(who, "The Battle of Hyrule Field"), dlc == "dlc"))
    return out


WEAPONS: list[Weapon] = _build_weapons()
WEAPON_BY_NAME = {w.name: w for w in WEAPONS}

# ---------------------------------------------------------------------------------------
# Upgrades. Counts are design choices set by options; what each does in game is defined by the
# hook (UNVERIFIED against the real skill tree).
# ---------------------------------------------------------------------------------------

# Per-character upgrade families: item name prefix -> option attribute holding the copies per character.
CHARACTER_UPGRADES = {
    "Heart Container": "heart_containers",
    "Combo Upgrade": "combo_upgrades",
    "Special Gauge Upgrade": "special_gauge_upgrades",
    "Enhanced Ability": "enhanced_abilities",
}
GLOBAL_UPGRADES = {
    "Progressive Weapon Capacity": "weapon_capacity_upgrades",
    "Progressive Seal Slot": "seal_slot_upgrades",
    "Weapon Fusion": "weapon_fusion",
}

# Game features that can be locked until their item arrives (names UNVERIFIED; the hook decides how each locks).
# "Sheikah Slate Runes" stays for stable item ids but is no longer offered: the sheikah_runes option replaced it.
# The Smithy is open from the start (weapon fusion is too vital to lock): the client marks its quest done.
FEATURES = ["Smithy", "Cooking", "Shops", "Sheikah Slate Runes", "Fairy Fountains", "Terrako Guardian"]
LOCKABLE_FEATURES = [f for f in FEATURES if f not in ("Sheikah Slate Runes", "Smithy")]
SMITHY_QUEST = "Brawny Blacksmiths"

# Sheikah Slate runes (order = item ids, append only). Story flags [confirmed in game, RESEARCH session 18]: Remote
# Bombs 0x19 (also the rune menu itself: off hides every rune), Cryonis 0x1A, Magnesis 0x1B, Stasis 0x1C.
# 0.9.58+: Remote Bombs is always on (you start with the Slate); the other three are the rune items when shuffled.
RUNES = ["Remote Bombs", "Cryonis", "Magnesis", "Stasis"]
ITEM_RUNES = ["Cryonis", "Magnesis", "Stasis"]
ENFORCED_RUNES = ["Magnesis", "Stasis"]  # what seeds before 0.9.58 enforce (their Bombs/Cryonis items were logic only)
RUNE_CHALLENGES = {"Mastering Remote Bombs": "Remote Bombs", "Mastering Cryonis": "Cryonis",
                   "Mastering Magnesis": "Magnesis", "Mastering Stasis": "Stasis",
                   "Explosive—Handle With Care": "Remote Bombs"}

# ---------------------------------------------------------------------------------------
# Filler (repeatable; the hook decides what each grants)
# ---------------------------------------------------------------------------------------

FILLER_ITEMS = [
    "Character XP Gift",
    "Weapon XP Gift",
    "Extra Weapon",
    "Rupee Pouch",
    "Material Bundle",
    "Hearty Meal",
]
DEFAULT_FILLER_WEIGHTS = {
    "Character XP Gift": 30,
    "Weapon XP Gift": 30,
    "Extra Weapon": 10,
    "Rupee Pouch": 15,
    "Material Bundle": 10,
    "Hearty Meal": 5,
}

# ---------------------------------------------------------------------------------------
# Challenge level-band gates (UNVERIFIED heuristic; used only by challenge_logic: by_level).
# Band -> mission whose clearing is assumed to make that level bracket available.
# None = after the whole story. Bands 7+ and DLC fall back to the end of the story.
# ---------------------------------------------------------------------------------------

LEVEL_BAND_GATES: dict[int, str | None] = {
    1: "Road to the Ancient Lab",
    2: "The Yiga Clan Attacks!",
    3: "The Road Home, Besieged",
    4: "When Courage Fails",
    5: "Air and Lightning",
    6: "All Hyrule, United",
    7: None,
    8: None,
    9: None,
    10: None,
    11: "Calamity Strikes",  # Divine Beast battles
    12: None,
}

# Boss Rush goal: Divine Beast battles plus the three "Versus" boss challenges (UNVERIFIED which challenges count as bosses).
BOSS_CHALLENGES = [
    "Might of a Divine Beast", "Volcanic Defense", "Protector of the Forest", "Pursue the Yiga Clan!",
    "Defending Cephla Lake", "Volcanic Might", "Like the Wind", "Two Chiefs", "Molduga Deluge",
    "The Power of Three", "A Fiery Reckoning", "Through the Storm",
    "A Tidal Wave of Foes", "A Shield Forged in Iron", "Swift as Thought",
    "Versus Astor", "Versus Harbinger Ganon", "Versus Calamity Ganon",
]

