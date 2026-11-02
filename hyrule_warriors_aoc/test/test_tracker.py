import json
import unittest

from BaseClasses import CollectionState
from test.general import setup_solo_multiworld
from worlds.AutoWorld import AutoWorldRegister, call_all

from ..items import character_item, unlock_item

GAME = "Hyrule Warriors Age of Calamity"
UT_STEPS = ("generate_early", "create_regions", "create_items", "set_rules", "connect_entrances", "generate_basic")


def _ut_regen(slot_data: dict, seed: int):
    """What Universal Tracker does: default options, slot_data passed through, generation stopped at generate_basic."""
    world_type = AutoWorldRegister.world_types[GAME]
    multiworld = setup_solo_multiworld(world_type, (), seed)
    multiworld.generation_is_fake = True
    multiworld.re_gen_passthrough = {GAME: world_type.interpret_slot_data(slot_data)}
    for step in UT_STEPS:
        call_all(multiworld, step)
    return multiworld


class TrackerRegenTests(unittest.TestCase):
    """Universal Tracker rebuilds the seed from slot_data: same checks, same logic, whatever its own seed."""

    def check(self, options: dict, seed: int) -> None:
        world_type = AutoWorldRegister.world_types[GAME]
        from test.general import setup_multiworld
        real = setup_multiworld(world_type, seed=seed, options=options)
        world = real.worlds[1]
        slot_data = json.loads(json.dumps(world.fill_slot_data()))  # over the wire
        fake = _ut_regen(slot_data, seed + 1000)
        twin = fake.worlds[1]
        mine = {loc.name for loc in real.get_locations(1) if loc.address is not None}
        theirs = {loc.name for loc in fake.get_locations(1) if loc.address is not None}
        self.assertEqual(mine, theirs)
        self.assertEqual(world.slot_to_mission, twin.slot_to_mission)
        # same logic: with the same items, the same checks are in reach
        for got in (world.starting_characters, world.characters):
            states = []
            for mw in (real, fake):
                state = CollectionState(mw)
                for c in got:
                    state.collect(mw.worlds[1].create_item(character_item(c)), True)
                for m in mw.worlds[1].starting_unlocks:
                    state.collect(mw.worlds[1].create_item(unlock_item(m)), True)
                state.sweep_for_advancements()
                states.append({loc.name for loc in mw.get_locations(1) if loc.address is not None and loc.can_reach(state)})
            self.assertEqual(states[0], states[1])

    def test_default_options(self) -> None:
        for seed in (1, 2):
            self.check({}, seed)

    def test_shuffled_items_and_random_side(self) -> None:
        self.check({"mission_unlocks": "items", "side_unlocks": "shuffled", "side_check_density": 60,
                    "starting_character_count": 2, "first_mission": "random_any",
                    "challenge_checks": True, "quest_checks": True, "weapon_checks": True}, 5)
