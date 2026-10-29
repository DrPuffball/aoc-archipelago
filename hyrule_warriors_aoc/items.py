from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification

from .data import (
    ALL_CHARACTERS,
    CHARACTER_UPGRADES,
    FEATURES,
    FILLER_ITEMS,
    GAME_NAME,
    MISSIONS,
    GLOBAL_UPGRADES,
    ITEM_ID_BASE,
    RUNE_CHALLENGES,
    ITEM_RUNES,
    RUNES,
    WEAPONS,
)

from .data_rewards import REWARD_BY_ITEM, REWARD_GROUPS
from .data_challenges import CALAMITY, RESCUES
from .options import MissionUnlocks, SheikahRunes

if TYPE_CHECKING:
    from .world import AgeOfCalamityWorld


class AgeOfCalamityItem(Item):
    game = GAME_NAME


CHARACTER_PREFIX = "Character: "
WEAPON_PREFIX = "Weapon: "


def character_item(name: str) -> str:
    return f"{CHARACTER_PREFIX}{name}"


def weapon_item(name: str) -> str:
    return f"{WEAPON_PREFIX}{name}"


def upgrade_item(family: str, character: str) -> str:
    return f"{family}: {character}"


def rune_item(rune: str) -> str:
    return f"Rune: {rune}"


UNLOCK_PREFIX = "Unlock: "


def unlock_item(mission: str) -> str:
    return f"{UNLOCK_PREFIX}{mission}"


# Append-only ID ranges: characters 0-49, per-character upgrades 50-399 (50 per family),
# global upgrades 400-449, features 450-499, weapons 500-699, filler 700-799, runes 800-849,
# mission unlocks 850-899 (every story mission; Hyrule Field's is 869), quest reward groups 900-949.
ITEM_NAME_TO_ID: dict[str, int] = {}


def _register(names: list[str], start: int, limit: int) -> None:
    assert len(names) <= limit, (start, len(names))
    for i, name in enumerate(names):
        assert name not in ITEM_NAME_TO_ID, name
        ITEM_NAME_TO_ID[name] = ITEM_ID_BASE + start + i


_register([character_item(c) for c in ALL_CHARACTERS], 0, 50)
for _f, _family in enumerate(CHARACTER_UPGRADES):
    _register([upgrade_item(_family, c) for c in ALL_CHARACTERS], 50 + 50 * _f, 50)
_register(list(GLOBAL_UPGRADES), 400, 50)
_register([f"Feature: {f}" for f in FEATURES], 450, 50)
_register([weapon_item(w.name) for w in WEAPONS], 500, 200)
_register(list(FILLER_ITEMS), 700, 100)
_register([rune_item(r) for r in RUNES], 800, 50)
_register([unlock_item(m.name) for m in MISSIONS[1:]], 850, 19)
_register([unlock_item(MISSIONS[0].name)], 869, 1)  # 0.9.54-0.9.56 seeds only (Hyrule Field is first again since)
_register([g.item for g in REWARD_GROUPS], 900, 50)

UPGRADE_FAMILIES = set(CHARACTER_UPGRADES)


def classify(world: AgeOfCalamityWorld, name: str) -> ItemClassification:
    if name in FILLER_ITEMS:
        return ItemClassification.filler
    if name.startswith(CHARACTER_PREFIX):
        # Characters only matter to logic through restricted challenges, quests and weapon checks.
        return ItemClassification.progression if world.characters_matter else ItemClassification.useful
    if name.startswith("Rune: "):
        # Progression only when a Mastering <rune> challenge (or another rune challenge) is in the seed.
        needed = set(RUNE_CHALLENGES) & set(world.active_challenges)
        return ItemClassification.progression if needed else ItemClassification.useful
    if name.startswith(UNLOCK_PREFIX):
        return ItemClassification.progression
    if name in getattr(world, "reward_progression", ()):  # an item a checked quest or challenge waits on
        return ItemClassification.progression
    if name in REWARD_BY_ITEM:
        # Only a shop/stable item whose quest another quest needs first gates anything (stored rewards never do).
        return ItemClassification.progression if name in world.reward_progression else ItemClassification.useful
    if name.startswith("Feature: "):
        # Progression only when a checked quest or challenge waits on it (reward_progression, above).
        return ItemClassification.useful
    return ItemClassification.useful


def create_item(world: AgeOfCalamityWorld, name: str) -> AgeOfCalamityItem:
    return AgeOfCalamityItem(name, classify(world, name), ITEM_NAME_TO_ID[name], world.player)


def get_filler_item_name(world: AgeOfCalamityWorld) -> str:
    weights = {k: v for k, v in world.options.filler_weights.value.items() if v > 0 and k in FILLER_ITEMS}
    if not weights:
        weights = {k: 1 for k in FILLER_ITEMS}
    return world.random.choices(list(weights), list(weights.values()))[0]


def add_bonus_checks(world: AgeOfCalamityWorld, surplus: int) -> int:
    """Spread `surplus` extra checks evenly over the story clears and the challenge checks (one at a time around
    all of them, at most BONUS_PER_MISSION / BONUS_PER_CHALLENGE each), so no single clear sends a pile of items;
    each one is sent together with its clear. Returns how many were added."""
    from .locations import (BONUS_PER_CHALLENGE, BONUS_PER_MISSION, bonus_location, challenge_bonus_location,
                            create_location)
    # story slots before the goal, but not The Battle of Hyrule Field: the starter save has it cleared, so its checks
    # would all be sent the moment a player connects
    order = world.mission_order[1:world.options.goal_story_missions.value]
    challenges = sorted(world.checked_challenges)
    caps = [(m, BONUS_PER_MISSION) for m in order] + [(c, BONUS_PER_CHALLENGE) for c in challenges]
    surplus = max(0, min(surplus, sum(cap for _, cap in caps)))
    counts = {name: 0 for name, _ in caps}
    left = surplus
    while left:
        for name, cap in caps:
            if left and counts[name] < cap:
                counts[name] += 1
                left -= 1
    world.bonus_checks, world.challenge_bonus_checks = {}, {}
    for mission in order:
        if counts[mission]:
            region = world.get_region(mission)
            for k in range(1, counts[mission] + 1):
                create_location(world, region, bonus_location(mission, k))
            world.bonus_checks[mission] = counts[mission]
    side = world.get_region("Side Content")
    for challenge in challenges:
        if counts[challenge]:
            for k in range(1, counts[challenge] + 1):
                create_location(world, side, challenge_bonus_location(challenge, k))
            world.challenge_bonus_checks[challenge] = counts[challenge]
    return surplus


def create_all_items(world: AgeOfCalamityWorld) -> None:
    options = world.options
    for character in world.starting_characters:
        world.push_precollected(create_item(world, character_item(character)))

    # The Battle of Hyrule Field comes cleared (on Easy) in the starter save, so its clear is sent the moment a player
    # connects: it holds one of your own filler items, never anything for someone else (user request 2026-10-28).
    from .locations import mission_location
    world.get_location(mission_location(world.mission_order[0])).place_locked_item(
        create_item(world, get_filler_item_name(world)))

    # Heroes, locked features and runes must always exist: without them content stays locked for good. Anything that
    # finds no check (small seeds) is given at the start of the run instead of being lost.
    slots = len(world.multiworld.get_unfilled_locations(world.player))
    for mission in world.starting_unlocks:
        world.push_precollected(create_item(world, unlock_item(mission)))
    wanted = []
    if options.mission_unlocks == MissionUnlocks.option_items:  # first, so they get checks before anything else
        wanted += [unlock_item(m) for m in world.mission_order[1:]
                   if m not in world.starting_unlocks and m not in RESCUES and m != CALAMITY]  # (they open by themselves)
    wanted += [character_item(c) for c in world.characters if c not in world.starting_characters]
    wanted += [f"Feature: {f}" for f in sorted(f for f in FEATURES if f in options.locked_features.value)]
    if options.sheikah_runes == SheikahRunes.option_shuffled:
        wanted += [rune_item(r) for r in ITEM_RUNES]  # Remote Bombs is the Slate: always yours

    # Upgrades are kept whole: every hero gets every copy the options promise. When checks are short, a random share
    # of them is given at the start of the run instead.
    copies = {family: getattr(options, option_name).value for family, option_name in CHARACTER_UPGRADES.items()}
    global_copies = {name: int(getattr(options, option_name).value) for name, option_name in GLOBAL_UPGRADES.items()}
    world.upgrade_copies = copies
    upgrades = [upgrade_item(f, c) for f, n in copies.items() for c in world.characters for _ in range(n)]
    upgrades += [name for name, n in global_copies.items() for _ in range(n)]
    upgrades += [name for name, n in world.reward_copies.items() for _ in range(n)]

    weapon_names = [w for w in world.active_weapons if w not in world.post_goal_weapons]  # those drop as vanilla
    world.random.shuffle(weapon_names)
    weapons = [weapon_item(n) for n in weapon_names[: options.weapon_items.value]]
    # More items than checks: story clears hold extra checks (sent with the clear) instead of handing items out
    slots += add_bonus_checks(world, len(wanted) + len(upgrades) + len(weapons) - slots)
    core = wanted[:slots]
    for name in wanted[slots:]:
        world.push_precollected(create_item(world, name))
    room = slots - len(core)
    extra = upgrades + weapons
    world.random.shuffle(extra)
    optional = extra[:room]
    for name in extra[room:]:
        world.push_precollected(create_item(world, name))

    filler_count = room - len(optional)
    names = core + optional + [get_filler_item_name(world) for _ in range(filler_count)]
    world.multiworld.itempool += [create_item(world, n) for n in names]
