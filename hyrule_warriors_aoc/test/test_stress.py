import itertools

from BaseClasses import CollectionState
from Fill import distribute_items_restrictive
from test.bases import WorldTestBase
from worlds.AutoWorld import call_all

SEEDS_PER_COMBO = 2

SIDES = [[], ["Weapons"], ["Challenges", "Quests"], ["Weapons", "Challenges", "Quests"]]


class TestManySeeds(WorldTestBase):
    """Fill many random seeds for many option combinations; each must be fully reachable and beatable."""

    game = "Hyrule Warriors Age of Calamity"
    run_default_tests = False  # this class does its own, repeated, fills

    def test_every_combination_is_beatable_across_seeds(self) -> None:
        combos = itertools.product(SIDES, [False, True], ["vanilla", "shuffle_all", "items"], [0, 2], [0, 1], [(4, 100), (1, 20)], [0, 1], [0, 1, 2, 3])
        for side, dlc, order, gating, logic, (starters, density), party, goal in combos:
            if (gating or goal == 1) and not side:
                continue
            self.options = {
                "side_content": side,
                "include_dlc": dlc,
                "mission_order": "vanilla" if order == "items" else order,
                "mission_unlocks": "items" if order == "items" else "story_order",
                "starting_mission_unlocks": 1 if starters == 1 else 2,
                "side_missions_per_unlock": gating,
                "challenge_logic": logic,
                "weapon_check_logic": logic,
                "starting_character_count": starters,
                "side_check_density": density,
                "story_party": party,
                "goal": goal,
                "goal_side_missions": 40,
                "locked_features": ["Shops", "Cooking"],
                "local_filler": bool(party),
                "featured_challenge": bool(goal),
                "mission_hint_every": 3,
            }
            for seed in range(SEEDS_PER_COMBO):
                with self.subTest(**self.options, seed=seed):
                    self.world_setup(seed)
                    distribute_items_restrictive(self.multiworld)
                    call_all(self.multiworld, "post_fill")
                    self.assertTrue(self._beatable_and_fully_reachable())

    def _beatable_and_fully_reachable(self) -> bool:
        locations = list(self.multiworld.get_locations(self.player))
        state = CollectionState(self.multiworld)
        while locations:
            sphere = [loc for loc in locations if loc.can_reach(state)]
            if not sphere:
                self.fail(f"Unreachable locations: {[loc.name for loc in locations][:10]}")
            for loc in sphere:
                locations.remove(loc)
                if loc.item:
                    state.collect(loc.item, True, loc)
        return self.multiworld.has_beaten_game(state, self.player)
