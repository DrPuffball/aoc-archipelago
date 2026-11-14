"""
The Royal Ancient Lab (Expansion Pass): 35 research nodes, read from the game's own table and bought live on 2026-11-03/04.

What the game does [confirmed live on Eden]:
  state list   [P+0x550]+0x4AE2 + node, mirror [P+0x5A0]+0x3AA5 + node: 1 locked, 2 open, 3 done. Writing 2 opens a node.
  node table   rows 0x40 apart; found by its first row's costs. +0x1B condition target, +0x23 five material costs (u16),
               +0x2D condition mission record, +0x2F reward weapon kind, +0x31 attack bonus, +0x33 reward material count,
               +0x35 five material index+1, +0x3A condition type, +0x3D condition weapon type, +0x3E weapon capacity bonus.
               The game reloads the table each time the lab opens, so edits must be kept up while it's open.
  Zeroing +0x2F / +0x31 / +0x3E makes a purchase give no weapon, attack or capacity (the node still costs materials and
  still finishes) [confirmed 2026-11-04], which is how a node becomes a pure check.

Each node's check is its state reaching 3. Its reward is one of:
  weapon  an existing "Weapon: <name>" item; the table's weapon field is zeroed
  flag    a stored byte the client forces to what the received items give
  count   the same, a counter shared by several nodes (weapon capacity, relic trials)
  attack  a progressive item: a counter (+1 per node) plus +10 attack on each of the hero's lab weapons (record +0x76)
  hero    the node's ally field (+0x3C) is zeroed; the hero is a Character item
  none    the reward's bytes aren't known: the node is a check and keeps the game's reward (status in tools/QUEST_MAP.md)
The small material a node pays out (+0x33) always stays: later nodes cost those materials, so taking it could lock a seed.
"""

from __future__ import annotations

from typing import NamedTuple

from .data_rewards import FLAGS, PROFILE, WARDROBE

LAB_NODE_COUNT = 35
LAB_STATES = (0x550, 0x4AE2)  # block, offset
LAB_MIRROR = (0x5A0, 0x3AA5)
LAB_ROW_SIZE = 0x40
LAB_ROW_ANCHOR = 26  # the row found by its costs (2, 5, 10 at +0x23, 0xA9 at +0) is node 26
LAB_WEAPON_FIELD, LAB_ATTACK_FIELD, LAB_CAPACITY_FIELD = 0x2F, 0x31, 0x3E
RELIC_BYTE = (WARDROBE, 0xF555)  # 0, 1, 2 with the two relic nodes

# Condition types (row +0x3A), in the game's text order.
COND_NONE, COND_WEAPON_KOS, COND_WEAPON_COPIES, COND_WEAPON_DODGES, COND_BOMBS, COND_MAGNESIS, COND_STASIS, COND_CRYONIS, \
    COND_MISSION, COND_FIRE_ROD = range(10)

FLAILS = ("Guardian Flail", "Ancient Bladed Flail", "Fortified Flail")
CYCLES = ("Master Cycle", "Master Cycle Hunter", "Master Cycle Sentinel")


class LabNode(NamedTuple):
    index: int
    name: str
    effect: str  # the game's reward line
    tier: int  # how deep in the tree: story clears the logic asks for first, since every node is open from the start
    kind: str = "none"  # "weapon", "flag", "count", "state" or "none"
    item: str | None = None  # the item that gives its reward
    writes: tuple[tuple[int, int, int], ...] = ()  # flag kind: (block, offset, value)
    condition: tuple[int, int] = (COND_NONE, 0)  # (type, target)


def _flag(index: int, name: str, effect: str, tier: int, block: int, offset: int,
          condition: tuple[int, int] = (COND_NONE, 0)) -> LabNode:
    return LabNode(index, name, effect, tier, "flag", f"{effect} ({name})", ((block, offset, 1),), condition)


LAB_NODES: list[LabNode] = [
    LabNode(0, "The Battle-Tested Guardian", "Ally with the Battle-Tested Guardian", 0, "hero", condition=(COND_MISSION, 0)),
    LabNode(1, "A Helping Claw", "Obtain Guardian Flail", 1, "weapon", "Weapon: Guardian Flail"),
    LabNode(2, "The Blazing-Blue Blades", "Obtain Ancient Bladed Flail", 2, "weapon", "Weapon: Ancient Bladed Flail"),
    LabNode(3, "Magnificent Mass", "Obtain Fortified Flail", 2, "weapon", "Weapon: Fortified Flail"),
    LabNode(4, "Applied Research: Clawsome Power", "Flail Attack Power +10", 2, "attack", "Progressive Flail Attack", condition=(COND_WEAPON_KOS, 1000)),
    LabNode(5, "Applied Research: Royal Guardians", "Flail Attack Power +10", 3, "attack", "Progressive Flail Attack"),
    LabNode(6, "Applied Research: Magnetic Inspiration", "Flail Attack Power +10", 3, "attack", "Progressive Flail Attack", condition=(COND_WEAPON_COPIES, 20)),
    LabNode(7, "Top-Secret Request", "Obtain Master Cycle", 3, "weapon", "Weapon: Master Cycle"),
    LabNode(8, "Riding Free", "Obtain Master Cycle Hunter", 2, "weapon", "Weapon: Master Cycle Hunter"),
    LabNode(9, "Better Safe Than Sorry", "Obtain Master Cycle Sentinel", 2, "weapon", "Weapon: Master Cycle Sentinel"),
    LabNode(10, "Present for the Princess", "Master Cycle Attack Power +10", 2, "attack", "Progressive Master Cycle Attack", condition=(COND_WEAPON_KOS, 1000)),
    LabNode(11, "Safety First", "Master Cycle Attack Power +10", 3, "attack", "Progressive Master Cycle Attack"),
    LabNode(12, "Ride On", "Master Cycle Attack Power +10", 3, "attack", "Progressive Master Cycle Attack", condition=(COND_WEAPON_DODGES, 15)),
    LabNode(13, "The Source of Strength", "Weapon Capacity +10", 3, "count", "Weapon Capacity +10 (The Source of Strength)"),
    LabNode(14, "The Many Sources of Strength", "Weapon Capacity +20", 4, "count",
            "Weapon Capacity +20 (The Many Sources of Strength)"),
    _flag(15, "Working with the Blacksmith Guild", "Higher Max Weapon Level", 4, FLAGS, 0x640),
    _flag(16, "The Deal with Seals", "Remove Hidden Seals", 5, FLAGS, 0x1A08),
    _flag(17, "Gimme, Gimme, Gimme", "Seal Boost", 6, PROFILE, 0xC88),
    _flag(18, "Supporting the Local Economy", "New Merchant Stock", 7, FLAGS, 0x1A09),
    _flag(19, "Hungry Hunches", "Fewer Cooking Ingredients", 8, FLAGS, 0x1A0A),
    _flag(20, "An Abundance of Apples", "Buy Apples", 9, FLAGS, 0x1A0B),
    _flag(21, "Frugal Fruit", "Apple Discount", 9, FLAGS, 0x1A03),
    _flag(22, "An Apple a Day", "More Heart Recovery from Baked Apples", 9, PROFILE, 0xC89, (COND_FIRE_ROD, 100)),
    _flag(23, "Turn Up the Heat", "Longer Rod Effects", 9, PROFILE, 0xC0F),
    # 24, 25, 30: the game reads the reward from the node being done (purchases changed only the node state [read, lab
    # hand-in records]). 0.9.87: kind "state": the client keeps a bought node locked until its item arrives, then done.
    LabNode(24, "Roll Out the Research", "Collect Research Papers", 9, "state", "Collect Research Papers (Roll Out the Research)"),
    LabNode(25, "The Technology of Disassembly", "Better Ancient Item Drops", 9, "state",
            "Better Ancient Item Drops (The Technology of Disassembly)"),
    _flag(26, "Power Play: Bombs Away", "More Remote Bomb Damage", 9, PROFILE, 0xC10, (COND_BOMBS, 100)),
    _flag(27, "Power Play: Magnetic Mayhem", "More Magnesis Damage", 9, PROFILE, 0xC11, (COND_MAGNESIS, 5)),
    _flag(28, "Power Play: Go with the Flow", "More Stasis Damage", 9, PROFILE, 0xC12, (COND_STASIS, 100)),
    _flag(29, "Power Play: Nice and Icy", "More Cryonis Damage", 9, PROFILE, 0xC13, (COND_CRYONIS, 60)),
    LabNode(30, "Sensor of the Heart", "More Sensor-Registered Material Drops", 9, "state",
            "More Sensor-Registered Material Drops (Sensor of the Heart)"),
    _flag(31, "The Menace of Vicious Monsters", "Challenge Vicious Monsters", 9, FLAGS, 0x1A0D),
    LabNode(32, "The Ultimate Relic", "Qualify for the Trial", 9, "count", "Progressive Relic Trial", condition=(COND_MISSION, 28)),
    LabNode(33, "The Relic of Legend", "Qualify for the Trial", 9, "count", "Progressive Relic Trial", condition=(COND_MISSION, 28)),
    _flag(34, "Analyzing Vicious Behavior", "Vicious Monsters in Battle Info", 9, FLAGS, 0x1A0E),
]
LAB_BY_NAME = {n.name: n for n in LAB_NODES}
assert len(LAB_NODES) == LAB_NODE_COUNT and all(n.index == i for i, n in enumerate(LAB_NODES))

# Reward items of their own (weapons are the existing weapon items). Order = item ids (append only).
LAB_ITEMS: list[str] = list(dict.fromkeys(n.item for n in LAB_NODES if n.item and not n.item.startswith("Weapon: ")
                                          and n.kind != "state"))
LAB_ITEMS += [n.item for n in LAB_NODES if n.kind == "state"]  # 0.9.87, appended so older item ids stay put
LAB_STATE_NODES = {n.item: n.index for n in LAB_NODES if n.kind == "state"}


def lab_state_target(index: int, state: int, held: dict[int, bool], bought: set[str]) -> int:
    """The state the client keeps a lab node at (1 locked, 2 open, 3 done). Every node is open; a "state" node in held
    (index -> its item received) is done with its item, locked once bought without it (so it can't be bought twice),
    else open to buy."""
    if index in held:
        if held[index]:
            return 3
        return 1 if LAB_NODES[index].name in bought or state == 3 else 2
    return 2 if state == 1 else state
LAB_WEAPON_ITEMS = tuple(n.item for n in LAB_NODES if n.kind == "weapon")
LAB_ITEM_COPIES = {item: sum(1 for n in LAB_NODES if n.item == item) for item in LAB_ITEMS}

# What a node's game condition needs, for the logic (user, 2026-11-04: conditions stay in a normal game). The relic nodes ask
# for The Future of Hyrule: when that mission is the goal they hold no checks and keep the game's reward.
FORGOTTEN_TEMPLE, FUTURE_OF_HYRULE = "EX Alert: Forgotten Temple", "The Future of Hyrule"
LAB_MISSION_CONDITION = {"The Battle-Tested Guardian": FORGOTTEN_TEMPLE, "The Ultimate Relic": FUTURE_OF_HYRULE,
                         "The Relic of Legend": FUTURE_OF_HYRULE}
LAB_RUNE_CONDITION = {"Power Play: Magnetic Mayhem": "Magnesis", "Power Play: Go with the Flow": "Stasis",
                      "Power Play: Nice and Icy": "Cryonis"}
LAB_WEAPON_CONDITION = {"Applied Research: Clawsome Power": ("Link", FLAILS),
                        "Applied Research: Magnetic Inspiration": ("Link", FLAILS),
                        "Present for the Princess": ("Zelda", CYCLES), "Ride On": ("Zelda", CYCLES)}

# Attack research: item -> (counter byte, hero, the lab weapons it raises).
LAB_ATTACK = {"Progressive Flail Attack": ((PROFILE, 0xC2C), "Link", FLAILS),
              "Progressive Master Cycle Attack": ((PROFILE, 0xC2D), "Zelda", CYCLES)}
ATTACK_PER_NODE = 10
WEAPON_LAB_ATTACK = 0x76  # weapon record: bonus from attack research


def lab_capacity(received: dict[str, int]) -> int:
    """Weapon capacity the lab items add. It's the same profile byte as the quests' capacity (+0x7A6): the client adds it to
    what Progressive Weapon Capacity gives."""
    return (10 if received.get(LAB_NODES[13].item, 0) else 0) + (20 if received.get(LAB_NODES[14].item, 0) else 0)


def lab_values(received: dict[str, int], seed_items: dict[str, int] | None = None) -> dict[tuple[int, int], int]:
    """(block, offset) -> value the game should hold for what the received lab items give. An item the seed doesn't have
    (seed_items) leaves its reward to the game."""
    values: dict[tuple[int, int], int] = {}
    for node in LAB_NODES:
        for block, offset, value in node.writes:
            values[(block, offset)] = value if received.get(node.item, 0) else 0
    if seed_items is None or "Progressive Relic Trial" in seed_items:
        values[RELIC_BYTE] = min(2, received.get("Progressive Relic Trial", 0))
    for item, (byte, _, _) in LAB_ATTACK.items():
        values[byte] = min(3, received.get(item, 0))
    return values
