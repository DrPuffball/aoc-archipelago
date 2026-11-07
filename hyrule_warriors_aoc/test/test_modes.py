"""Game modes (user, 2026-11-02): Story Only and Challenges Only."""

import json
import unittest

from test.bases import WorldTestBase

from ..client.session import Session
from ..data import MISSIONS
from ..data_challenges import DLC_STORY_MISSIONS


class StoryOnlyTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"game_mode": "story_only"}

    def test_every_check_is_on_story_missions(self) -> None:
        w = self.world
        names = [loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None]
        self.assertFalse([n for n in names if n.startswith(("Quest: ", "Obtain: "))])
        self.assertFalse([n for n in names if n.startswith("Challenge: ") and n[11:].partition(" (Bonus")[0] not in DLC_STORY_MISSIONS])
        self.assertEqual(len(w.story_chain), len(MISSIONS) + len(DLC_STORY_MISSIONS))
        self.assertEqual(w.story_chain[0], MISSIONS[0].name)
        self.assertEqual(w.story_chain[len(w.story_chain) - 1 if w.options.goal_story_missions.value >= len(w.story_chain)
                                       else w.options.goal_story_missions.value - 1], "The Future of Hyrule")
        self.assertTrue(w.options.open_shops and w.options.open_stables and not w.options.weapon_fusion)
        self.assertEqual(w.goal_challenge_pool, [])

    def test_each_clear_opens_the_next(self) -> None:
        w = self.world
        second, third = w.story_chain[1], w.story_chain[2]
        state = self.multiworld.get_all_state(False)
        from ..regions import cleared_event, challenge_event
        before = cleared_event(second) if second in w.slot_to_mission else challenge_event(second)
        state.prog_items[self.player][before] = 0  # (rules checked directly: reached regions stay cached)
        if third in w.slot_to_mission:
            self.assertFalse(w.get_entrance(f"Start {third}").access_rule(state))
        else:
            self.assertFalse(w.get_location(f"Event: Challenge {third}").access_rule(state))
        state.prog_items[self.player][before] = 1
        rule = (w.get_entrance(f"Start {third}") if third in w.slot_to_mission
                else w.get_location(f"Event: Challenge {third}")).access_rule
        self.assertTrue(rule(state) or third == "Calamity Strikes")

    def test_client_follows_the_chain(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        chain = self.world.story_chain
        session.cleared_missions.add(chain[0])
        open_now = set(session.available_missions()) | {n for n in session.dlc_story if session.dlc_story_open(n)}
        self.assertEqual(open_now, {chain[1]})


class ChallengesOnlyTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"game_mode": "challenges_only"}

    def test_every_check_is_on_challenges(self) -> None:
        w = self.world
        names = [loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None]
        self.assertFalse([n for n in names if n.startswith(("Quest: ", "Obtain: "))])
        self.assertEqual([n for n in names if n.startswith("Clear: ")], [f"Clear: {MISSIONS[0].name}"])
        self.assertEqual(w.mission_order, [MISSIONS[0].name])
        self.assertEqual(w.dlc_story, [])
        self.assertEqual(set(w.challenge_open_at), set(w.active_challenges))  # every challenge by the random order
        self.assertEqual(w.options.goal_challenges.value, 25)  # the default (0 would mean 50 here)
        self.assertFalse(w.options.final_mission_goal)

    def test_client_hides_story_and_quests(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        session.cleared_missions.add(MISSIONS[0].name)
        self.assertEqual(session.available_missions(), [])
        states = session.quest_states()
        self.assertTrue(states and all(v in (-1, 3) for v in states.values()))
        session.challenges_done |= set(sorted(session.goal_challenge_pool)[:50])
        self.assertTrue(session.goal_complete)


class ModeServicesTests(WorldTestBase):
    """Both modes: services open, every recipe known, checks evenly over the levels (user, 2026-11-02)."""
    game = "Hyrule Warriors Age of Calamity"
    options = {"game_mode": "challenges_only"}

    def test_services_recipes_and_even_checks(self) -> None:
        w = self.world
        self.assertTrue(w.options.open_shops and w.options.open_dye_shop and w.options.start_with_sheikah_sensor)
        self.assertFalse(w.options.weapon_fusion)
        self.assertTrue([i for i, n in w.group_copies.items() if i.startswith("Recipe (") and n])  # recipe items
        counts = [n for n in w.challenge_bonus_checks.values()]
        if counts:
            self.assertLessEqual(max(counts) - min(counts + [0] * (len(w.checked_challenges) - len(counts))), 1)


class ModeNoRecipeItemsTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"game_mode": "story_only", "quest_reward_items": {"Progressive Recipe": 0}}

    def test_recipes_granted_when_not_items(self) -> None:
        self.assertIn("Progressive Recipe", self.world.pre_granted)


class StoryOnlyNoDlcFailsafeTests(WorldTestBase):
    """Story Only with the DLC on a game without it: the chain skips the DLC story instead of stopping there."""
    game = "Hyrule Warriors Age of Calamity"
    options = {"game_mode": "story_only"}

    def test_chain_skips_dlc_when_dropped(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        session.drop_dlc()
        chain = self.world.story_chain
        cleared = set()
        for name in chain:  # clear the base story in chain order: every base mission must open in turn
            if name in DLC_STORY_MISSIONS:
                continue
            if name != chain[0]:
                self.assertTrue(session.mission_available(name) or name == "Calamity Strikes"
                                or (session.final_goal and name == session.final_mission), name)
            session.cleared_missions.add(name)
            cleared.add(name)


class GoalQuestsTests(WorldTestBase):
    """goal_quests: its own count, on the banner, in logic and the client (user, 2026-11-04)."""
    game = "Hyrule Warriors Age of Calamity"
    options = {"goal_quests": 3, "goal_challenges": 1, "goal_story_missions": 2, "final_mission_goal": False,
               "challenge_checks": True, "quest_checks": True}

    def test_counts_and_banner(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertEqual(session.goal_quests, 3)
        self.assertIn("Quests 0/3", session.goal_banner_text())
        self.assertNotIn("Side", session.goal_banner_text())
        session.side_done |= {f"quest:{q}" for q in sorted(session.goal_quest_pool)[:2]}
        self.assertIn("Quests 2/3", session.goal_banner_text())
        session.side_done.add("quest:not a checked quest")
        self.assertEqual(session.quests_done, 2)
        session.cleared_missions |= set(session.story_names)
        session.cleared_any |= session.goal_challenge_pool
        self.assertFalse(session.goal_complete)
        session.side_done.add(f"quest:{sorted(session.goal_quest_pool)[2]}")
        self.assertTrue(session.goal_complete)


class TestRelicNodesAndTheGoal(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"include_dlc": True, "lab_checks": True, "final_mission_goal": True}

    def test_no_checks_behind_the_goal(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertNotIn("Lab: The Ultimate Relic", names)
        self.assertNotIn("Lab: The Relic of Legend", names)
        self.assertNotIn("Progressive Relic Trial", [item.name for item in self.multiworld.itempool])
        session = Session(json.loads(json.dumps(self.multiworld.worlds[self.player].fill_slot_data())))
        from ..data_lab import RELIC_BYTE
        self.assertNotIn(RELIC_BYTE, session.lab_values())


class TestLabChecks(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"include_dlc": True, "lab_checks": True, "final_mission_goal": False}

    def test_every_node_is_a_check_with_its_items(self) -> None:
        from ..data_lab import LAB_ITEMS, LAB_NODES, LAB_WEAPON_ITEMS
        from ..locations import lab_location
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertTrue({lab_location(n.name) for n in LAB_NODES} <= names)
        pool = [item.name for item in self.multiworld.itempool] + [item.name for item in self.multiworld.precollected_items[self.player]]
        for item in [*LAB_ITEMS, *LAB_WEAPON_ITEMS]:
            self.assertIn(item, pool)

    def test_lab_lists_its_nodes_on_the_cursor_panel(self) -> None:
        from ..data_save import QUEST_STATE_IDS
        session = Session(json.loads(json.dumps(self.multiworld.worlds[self.player].fill_slot_data())))
        name, ids = session.selection_checks(QUEST_STATE_IDS["EX Ancient Tech Lab"], 5)
        self.assertEqual(name, "Royal Ancient Lab")
        self.assertEqual(len(ids), len(session.ids["lab"]))
        self.assertEqual(session.lab_node_of(ids[0]), "The Battle-Tested Guardian")

    def test_direct_rewards_replace_the_unlocks(self) -> None:
        from ..data_rewards import ROYAL_GIFTS
        world = self.multiworld.worlds[self.player]
        self.assertEqual(world.unlock_quests.keys() & set(ROYAL_GIFTS), set())
        self.assertNotIn("EX Hasty Recovery", world.unlock_quests)
        self.assertNotIn("Gathering the Facts", world.unlock_quests)
        self.assertEqual(world.group_copies.get("EX Ability (Hasty Recovery)"), 1)
        self.assertIn("EX A Royal Gift for Mipha", world.emptied_quests)
        self.assertIn("Weapon: Serene Champion's Spear", world.forced_items)
        data = world.fill_slot_data()
        self.assertEqual(len(data["lab_ids"]), 35)


class TestNoLabWithoutDLC(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"include_dlc": False, "lab_checks": True}

    def test_no_lab_checks(self) -> None:
        self.assertFalse([loc for loc in self.multiworld.get_locations(self.player) if loc.name.startswith("Lab: ")])


class TestLabConditionsInLogic(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"include_dlc": True, "lab_checks": True, "sheikah_runes": "shuffled", "final_mission_goal": False}

    def test_nodes_wait_for_what_their_condition_needs(self) -> None:
        from ..regions import cleared_event
        from ..rules import lab_needs
        world = self.multiworld.worlds[self.player]
        self.assertEqual(lab_needs(world, "Power Play: Nice and Icy")[0], ["Rune: Cryonis"])
        self.assertEqual(lab_needs(world, "Power Play: Bombs Away"), ([], []))
        needs = lab_needs(world, "Ride On")
        self.assertIn("Character: Zelda", needs[0])
        self.assertIn("Weapon: Master Cycle", needs[1])
        self.assertTrue(world.create_item("Weapon: Master Cycle").advancement)
        self.assertEqual(lab_needs(world, "The Ultimate Relic")[0], [cleared_event("The Future of Hyrule")])


class TestLabValues(unittest.TestCase):
    def test_values_follow_items(self) -> None:
        from ..data_lab import RELIC_BYTE, lab_capacity, lab_values
        self.assertEqual(lab_capacity({}), 0)
        got = lab_values({"Weapon Capacity +20 (The Many Sources of Strength)": 1, "Progressive Relic Trial": 2,
                          "Buy Apples (An Abundance of Apples)": 1})
        self.assertEqual(lab_capacity({"Weapon Capacity +20 (The Many Sources of Strength)": 1}), 20)
        self.assertEqual(got[RELIC_BYTE], 2)
        self.assertEqual(got[(0x5A0, 0x1A0B)], 1)
        self.assertEqual(got[(0x5A0, 0x1A0A)], 0)

    def test_research_item_is_delivered_once(self) -> None:
        import tempfile
        from pathlib import Path
        from unittest import mock
        from ..client import delivery as D

        class Live:
            def __init__(self): self.calls = []
            def give_weapon(self, name, wielder): return name
            def give_research(self, material, amount, outfit): self.calls.append((material, amount, outfit)); return "ok"
        with tempfile.TemporaryDirectory() as d, mock.patch.object(D, "STATE_DIR", Path(d)):
            ledger = D.Delivery("seed", "slot")
            live = Live()
            ledger.apply(["Research Rewards (Cold Desert Nights)"], set(), live)
            ledger.apply(["Research Rewards (Cold Desert Nights)"], set(), live)
            self.assertEqual(live.calls, [(50, 3, 20)])


class TestBoughtQuestKeepsNoReward(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"

    def test_individual_item_holds_a_bought_quest(self) -> None:
        from ..data_rewards import PROFILE, RECIPE_BASE, RECIPES
        session = Session(json.loads(json.dumps(self.multiworld.worlds[self.player].fill_slot_data())))
        session.game_done = {"Best-Ever Batter"}
        key = (PROFILE, RECIPE_BASE + RECIPES["Best-Ever Batter"])
        self.assertEqual(session.reward_writes()[key], 0)
        session.apply_received_item_names(["Recipe (Best-Ever Batter)"])
        self.assertEqual(session.reward_writes()[key], 1)
