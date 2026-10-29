"""
Quest rewards that become Archipelago items (every quest type not covered by the per-hero upgrade families).

Each group is one progressive item; its copies stand for the group's quests in order (item k gives quest k's reward,
each copy worth its share when the seed has fewer copies than quests, like Combo Upgrades). Two kinds:
  store  the reward is a stored byte the game writes at hand-in (tools/quest_survey_20261026.txt). The client forces
         every known byte to what the received items give, current and saved copy, so the vanilla hand-in is undone.
         The quests stay checks.
  quest  the service follows the quest state (shops, stables; the Smithy was confirmed this way). Buying the quest is
         its check; the client keeps a bought quest done (service open) only once its item is in, and closes it again
         (not available) until then, so buying alone never opens the service.
  unlock the reward's address is unknown: the quest itself is locked (kept not available) until its item arrives,
         then opened, so its reward can only be earned after the item. These quests stay checks.
A quest whose bytes are not known yet (writes None) is left vanilla and not counted; the group's item only covers
the quests before it. Labels: [survey] = seen written by that quest's hand-in; [guess] = inferred (neighbouring bytes
or a counter rising per quest of the type).
"""

from __future__ import annotations

from typing import NamedTuple

# Blocks off the save manager P = [module + 0x2780A48]: field -> distance to its saved copy (read from live memory:
# every survey byte holds the same value at both places).
PROFILE, FLAGS, RESEARCH = 0x588, 0x5A0, 0x578
BLOCK_SAVED_COPY = {PROFILE: 3 * 0xC30, FLAGS: 0x19B0, RESEARCH: 0x790}

Write = tuple[int, int, int]  # (block, offset, value)


class RewardGroup(NamedTuple):
    item: str
    kind: str  # "store" or "quest"
    quests: tuple[str, ...]
    writes: tuple[tuple[Write, ...] | None, ...] = ()  # per quest (store kind)
    dlc: bool = False  # Expansion Pass quests: only with include_dlc

    @property
    def known(self) -> tuple[str, ...]:
        """Quests the client can enforce, in order (store kind stops at the first unknown one)."""
        if self.kind in ("quest", "unlock", "hearts"):
            return self.quests
        out = []
        for quest, writes in zip(self.quests, self.writes):
            if writes is None:
                break
            out.append(quest)
        return tuple(out)


def _counter(offset: int, n: int) -> tuple[tuple[Write, ...], ...]:
    """A profile byte that counts the type's quests handed in (first value [survey], later ones [guess])."""
    return tuple(((PROFILE, offset, i + 1),) for i in range(n))


# Order = item ids (append only).
REWARD_GROUPS: list[RewardGroup] = [
    RewardGroup("Inner Power", "store", ("Inner Power",), (((PROFILE, 0xC78, 1),),)),  # [guess] batch 1
    RewardGroup("Inner Knowing", "store", ("Inner Knowing",), (((PROFILE, 0xC79, 1),),)),  # [survey]
    RewardGroup("Inner Protection", "store", ("Inner Protection",), (((PROFILE, 0xC7A, 1),),)),  # [guess] batch 1
    RewardGroup("Progressive Hot Springs", "store",
                ("Roast and Relaxation", "Chilly Path to a Hot Bath", "A Light in the Dark"), _counter(0x79E, 3)),
    RewardGroup("Progressive Tailored Clothes", "store",
                ("The Finest Tailor in the Land", "Time for an Upgrade", "Blessing of the Great Fairies"),
                _counter(0x79F, 3)),
    RewardGroup("Progressive Tactics Research", "store",
                ("A Read on the Enemy", "Eager Learners in Hateno Village", "Hyrule Institute of Tactics Research"),
                _counter(0x7A0, 3)),
    RewardGroup("Progressive Remote Bombs Upgrade", "store",
                ("Explosive Endeavors", "Strange and Unusual Monsters"), _counter(0x7A1, 2)),
    # Types 12-14 were bought together (batch 1): +0x7A2..+0x7A4 all went to 1 [guess which is which, by type order].
    RewardGroup("Progressive Magnesis Upgrade", "store", ("Shocking Fear", "Zappy 'n' Bouncy"), _counter(0x7A2, 2)),
    RewardGroup("Progressive Stasis Upgrade", "store", ("A Stasis on Research", "There Must Be Rice"),
                _counter(0x7A3, 2)),
    RewardGroup("Progressive Cryonis Upgrade", "store", ("Keep a Cool Head", "Personal Distractions"),
                _counter(0x7A4, 2)),
    RewardGroup("Progressive Rod Mastery", "store", ("It Takes Two", "The Research of Rods"), _counter(0x7A5, 2)),
    RewardGroup("Weapon Appraisal", "store", ("An Eye for Weapons",), (((PROFILE, 0x870, 1),),)),  # [survey]
    RewardGroup("Korok Hiding Place", "store", ("A Most Peculiar Korok",), (((PROFILE, 0xC7C, 1),),)),  # [survey]
    RewardGroup("Progressive Treasure Detector", "store", ("The Treasure Detector", "Upgrading the Detector"),
                (((PROFILE, 0xC7D, 1),), ((PROFILE, 0xC7E, 1),))),  # [survey], [guess] batch 1
    RewardGroup("Progressive Trade Routes", "store",
                ("Great Bridge Repairs",), (((FLAGS, 0x5D9, 1), (FLAGS, 0x5DD, 1)),)),
    RewardGroup("Progressive Forging Discount", "store", ("Quarry Recruiting",), (((FLAGS, 0x5E0, 1),),)),
    RewardGroup("Progressive Blacksmith Vigor", "store", ("Off to the Hot Springs",), (((FLAGS, 0x63E, 1),),)),
    RewardGroup("Progressive Max Weapon Level", "store", ("A Monumental Undertaking",),
                (((FLAGS, 0x63F, 1), (FLAGS, 0x651, 1)),)),
    RewardGroup("Progressive Seal Removal", "store", ("Caring for the Statues", "Secret of the Rito Artisans"),
                (((FLAGS, 0x1A04, 1),), ((FLAGS, 0x1A05, 1),))),
    RewardGroup("Progressive Rust Removal", "store",
                ("From Rusty to Trusty", "Better Rust-Busting"), (((FLAGS, 0x1A06, 1),), ((FLAGS, 0x641, 1),))),
    RewardGroup("Progressive Combat Training", "store",
                ("Tactics for Small Foes",), (((FLAGS, 0x642, 1),),)),
    RewardGroup("Progressive Sheikah Sensor Research", "store",
                ("Feed the Research",), (((RESEARCH, 0x780, 1), (RESEARCH, 0x781, 1), (RESEARCH, 0x783, 1)),)),
    # Type 16 services (shops; Relief for Soldier Stress improves the soldiers' meditation). The Smithy (Brawny
    # Blacksmiths) and the Military Training Camp (Entrance Test) are open from the start instead.
    RewardGroup("Progressive Shop Unlock", "quest",
                ("Brilliance for the Boutique", "Gotta Have a Sign", "Shop-Quick Store", "Pumpkin Burglars",
                 "Wanted: Shop Assistant", "An End to Fighting", "Dyeing to Make Contact", "Relief for Soldier Stress")),
    # Type 17 stables ("he reopened his stable"); following the quest state like the shops is a [guess].
    RewardGroup("Progressive Stable Unlock", "quest",
                ("Wedding Worry", "On the Hook", "Swanked-Up Stable", "Help Them on Their Way", "Curry Connoisseur",
                 "Anything but Bugs", "Hoping for Heat Relief")),
    # "unlock" groups: the reward's address is unknown, so the quest itself is the lock. The client keeps it hidden
    # until its item (share) arrives, then opens it; completing it gives the game's own reward and sends its check.
    RewardGroup("Progressive Regional Discount", "unlock",
                ("Lighting the Way", "What Bad Weather?", "Floria Bridge Protection", "The Marita Exchange",
                 "Rebuilding Akkala Bridge", "Goods on the Move in Hyrule!", "The Lazy Guards")),
    RewardGroup("Progressive Blacksmith Upgrade", "unlock",
                ("Shiny New Tools", "Road to Rust Research", "Tales of the Molten Forge", "The Legendary Blacksmith")),
    RewardGroup("Progressive Sheikah Sensor", "unlock",
                ("Needed: Researchers!", "Sweeten the Research", "Fuel Up with Plants")),
    RewardGroup("Progressive Training Camp Lesson", "unlock", ("Facing Powerful Enemies", "The Instructor's Problem")),
    RewardGroup("Progressive Cooking Lesson", "unlock",
                ("Snowbound Cook", "Master Monster Roasts", "Expert Cooking Lesson", "The Master Chef")),
    RewardGroup("Progressive Recipe", "unlock",
                ("A Feast of Greens", "A Birthday Treat", "Superb Fish Dish", "Cooking for the Common Cold",
                 "Best-Ever Batter", "Who's Shocked by Lightning?", "Stumped by Shrooms", "A Balm for the Soul",
                 "Just like Mama Made", "Extreme Survival Cuisine", "Bounty of the Sea", "The Blessing of Deya Lake",
                 "Dish for a Diva", "Really New Recipe", "Unexpected Discovery", "Fine Bites from Lurelin Village",
                 "Bee Very Careful", "Needs a Splash of...", "A Bird in the Hand", "Extreme Foraging",
                 "The Pumpkin Hunt", "Relieving Meat Fatigue", "Mystery Meal for the Merchant",
                 "The Legendary Recipe", "Afternoon Tea at Hyrule Castle")),
    RewardGroup("Progressive Maz Koshia Trial", "unlock",
                ("Offering Help on the Road", "The Trial of Monsters", "The Trial of Stones", "The Trial of the Mighty Foe")),
    RewardGroup("Progressive Research Quest", "unlock",
                ("A Rumor about Skull Lake", "Cold Desert Nights", "Search Party for Parts", "Gathering the Facts",
                 "The Eye That Sees Far", "Let's Dance", "A Secret in Song", "Right under Our Noses",
                 "No Extreme Too Extreme", "Searching Eventide Island", "Fang for Your Buck",
                 "Visiting a Special Shop", "Research of a Lifetime", "A Painter's Inspiration")),
    RewardGroup("Progressive Divine Beast Upgrade", "unlock",
                ("Regulating the Reservoir", "Surveying the Volcano", "Revitalize Those in the Skies",
                 "Patrolling the Desert")),
    RewardGroup("Progressive Dye Colors", "unlock",
                ("A Sparkling Solution", "Custom-Made Color", "A Color Seen in a Dream")),
    RewardGroup("Apple Capacity Up", "unlock", ("The Korok Ballet",)),
    RewardGroup("Progressive Region Hope", "unlock",
                ("The Hope of Central Hyrule", "The Hope of Hebra", "The Hope of Akkala", "The Hope of Eldin",
                 "The Hope of Lanayru", "The Hope of Necluda", "The Hope of Faron", "The Hope of Gerudo")),
    # Type 46: +1 bonus heart for every hero per quest (the per-hero hearts array the client already forces).
    RewardGroup("Progressive Heart for All", "hearts",
                ("Painter's Pilgrimage", "Peace Offering for Hyrule", "The Lonely Goddess")),
    RewardGroup("Progressive EX Reward Quest", "unlock",
                ("EX A Royal Gift for Mipha", "EX A Royal Gift for Sidon", "EX A Royal Gift for Daruk",
                 "EX A Royal Gift for Yunobo", "EX A Royal Gift for Revali", "EX A Royal Gift for Teba",
                 "EX A Royal Gift for Urbosa", "EX A Royal Gift for Riju", "EX The Text of Tomorrow",
                 "EX Hasty Recovery", "EX Spear Master", "EX A Giant Leap", "EX Awkward Allies",
                 "EX Analysis and Countermeasures", "EX Keeping a Promise", "EX Survive the Training",
                 "EX The Art of Flight", "EX Law of the Gerudo", "EX Hard Defenses", "EX Unstoppable Sidon",
                 "EX Goron-Sized Appetites", "EX Aim True at the Calamity", "EX Sand-Seal Bonding",
                 "EX Korok Curiosity", "EX The Dazzling Crown", "EX Trial of Kema Kosassa", "EX Violent Obsessions",
                 "EX Master Kohga's Lightning Training", "EX Relic Lessons"), dlc=True),
]
# Item names say what the reward does, with the quest(s) behind it in brackets [effects read from Zelda Dungeon / Zelda
# Wiki quest pages]. The old names (seeds generated before 0.9.52, older YAMLs) are accepted through canonical().
ITEM_RENAMES = {
    "Inner Power": "Weak-Point Gauge Depletion Up (Inner Power)",
    "Inner Knowing": "Special Gauge Recovery Up (Inner Knowing)",
    "Inner Protection": "Stagger Resistance Up (Inner Protection)",
    "Progressive Hot Springs":
        "Progressive Heart Recovery Up (Roast and Relaxation, Chilly Path to a Hot Bath, A Light in the Dark)",
    "Progressive Tailored Clothes": "Progressive Damage Taken Down (The Finest Tailor in the Land, Time for an Upgrade, "
                                    "Blessing of the Great Fairies)",
    "Progressive Tactics Research": "Progressive Enemy XP Up (A Read on the Enemy, Eager Learners in Hateno Village, "
                                    "Hyrule Institute of Tactics Research)",
    "Progressive Remote Bombs Upgrade":
        "Progressive Remote Bombs Cooldown Down (Explosive Endeavors, Strange and Unusual Monsters)",
    "Progressive Magnesis Upgrade": "Progressive Magnesis Cooldown Down (Shocking Fear, Zappy 'n' Bouncy)",
    "Progressive Stasis Upgrade": "Progressive Stasis Cooldown Down (A Stasis on Research, There Must Be Rice)",
    "Progressive Cryonis Upgrade": "Progressive Cryonis Cooldown Down (Keep a Cool Head, Personal Distractions)",
    "Progressive Rod Mastery": "Progressive Rod Uses Up (It Takes Two, The Research of Rods)",
    "Weapon Appraisal": "Better Weapon Drops (An Eye for Weapons)",
    "Korok Hiding Place": "Korok Battle Info (A Most Peculiar Korok)",
    "Progressive Treasure Detector": "Progressive Treasure Detector (The Treasure Detector, Upgrading the Detector)",
    "Progressive Trade Routes": "West Hyrule Shop Discount (Great Bridge Repairs)",
    "Progressive Forging Discount": "Blacksmith Guild Discount (Quarry Recruiting)",
    "Progressive Blacksmith Vigor": "Better Fusion Success (Off to the Hot Springs)",
    "Progressive Max Weapon Level": "Max Weapon Level 25 (A Monumental Undertaking)",
    "Progressive Seal Removal": "Progressive Seal Removal (Caring for the Statues, Secret of the Rito Artisans)",
    "Progressive Rust Removal": "Progressive Rust Removal (From Rusty to Trusty, Better Rust-Busting)",
    "Progressive Combat Training": "Training Camp Discount (Tactics for Small Foes)",
    "Progressive Sheikah Sensor Research": "Sheikah Sensor Capacity Up (Feed the Research)",
    "Apple Capacity Up": "Apple Capacity Up (The Korok Ballet)",
    "Progressive Heart for All":
        "Progressive Heart for All (Painter's Pilgrimage, Peace Offering for Hyrule, The Lonely Goddess)",
}
REWARD_GROUPS = [g._replace(item=ITEM_RENAMES.get(g.item, g.item)) for g in REWARD_GROUPS]
REWARD_BY_ITEM = {g.item: g for g in REWARD_GROUPS}
HEART_FOR_ALL = ITEM_RENAMES["Progressive Heart for All"]


def canonical(name: str) -> str:
    """Current item name for an old one (rooms generated before the rename send the old names)."""
    return ITEM_RENAMES.get(name, name)


# Items outside quest_reward_items that drive quests the same way (locked_features, weapon_fusion, seal_slot_upgrades).
_SHOPS = REWARD_BY_ITEM["Progressive Shop Unlock"]
_SEALS = REWARD_BY_ITEM[ITEM_RENAMES["Progressive Seal Removal"]]
FEATURE_GROUPS = {
    "Feature: Cooking": RewardGroup("Feature: Cooking", "unlock", ("Hot Meals in a Pot",)),  # learn to cook
    "Feature: Shops": RewardGroup("Feature: Shops", "quest", _SHOPS.quests),  # every shop at once
    "Feature: Terrako Guardian": RewardGroup("Feature: Terrako Guardian", "unlock", ("Terrako's Return",)),
    "Weapon Fusion": RewardGroup("Weapon Fusion", "quest", ("Brawny Blacksmiths",)),  # the Smithy (fusion)
    # The game has no seal-slot upgrade; seal removal (two quests) is the real one.
    "Progressive Seal Slot": RewardGroup("Progressive Seal Slot", "store", _SEALS.quests, _SEALS.writes),
}
# Locked feature -> challenges kept closed on the map until its item arrives.
FEATURE_CHALLENGES = {"Fairy Fountains": ("Fairy Fountain: Grassy Plains", "Fairy Fountain: Deep Snows",
                                          "Fairy Fountain: Desert Sands", "Fairy Fountain: Battlefield")}
ALL_GROUPS = {**REWARD_BY_ITEM, **FEATURE_GROUPS}
# Quests opened at the start of every seed (marked done by the client; they hold no check).
OPEN_SERVICE_QUESTS = ("Brawny Blacksmiths", "Entrance Test")
# Quests that unlock a hero who is a Character item; the client keeps the hero locked until the item arrives.
HERO_QUESTS = {"Terrako's Return": "Terrako"}


def reward_quest_count(group: RewardGroup) -> int:
    return len(group.known)


def given_quests(group: RewardGroup, received: int, copies: int) -> int:
    """How many of the group's quests the received copies stand for (each copy worth its share)."""
    if copies <= 0:
        return 0
    return -(-min(received, copies) * reward_quest_count(group) // copies)


def reward_writes(group: RewardGroup, given: int) -> dict[tuple[int, int], int]:
    """(block, offset) -> value the game should hold when the first `given` known quests are rewarded."""
    values: dict[tuple[int, int], int] = {}
    for i, quest in enumerate(group.known):
        for block, offset, value in group.writes[i]:
            key = (block, offset)
            values[key] = max(values.get(key, 0), value if i < given else 0)
    return values
