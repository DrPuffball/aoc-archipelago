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


class GoalHopeTests(WorldTestBase):
    """goal_hope_of_all_hyrule (0.9.87): the goal also waits for The Hope of All Hyrule, in logic and the client."""
    game = "Hyrule Warriors Age of Calamity"
    options = {"goal_hope_of_all_hyrule": True, "goal_story_missions": 2, "goal_challenges": 0,
               "final_mission_goal": False, "challenge_checks": True, "quest_checks": True}

    def test_goal_waits_for_the_hope(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertTrue(session.goal_hope)
        self.assertIn("100% map to do", session.goal_banner_text())
        session.cleared_missions |= set(session.story_names)
        self.assertFalse(session.goal_complete)
        session.game_done.add("The Hope of All Hyrule")
        self.assertTrue(session.goal_complete)

    def test_logic_needs_every_hero(self) -> None:
        from BaseClasses import CollectionState
        items = self.multiworld.itempool + [loc.item for loc in self.multiworld.get_locations() if loc.item]
        heroes = [i for i in items if i.player == self.player and i.name.startswith("Character: ")]
        state = CollectionState(self.multiworld)
        for item in items:
            if item.player == self.player and item not in heroes and item.advancement and item.code is not None:
                state.collect(item, True)
        state.sweep_for_advancements()
        self.assertFalse(self.multiworld.can_beat_game(state))
        for item in heroes:
            state.collect(item, True)
        state.sweep_for_advancements()
        self.assertTrue(self.multiworld.can_beat_game(state))


class GoalHopeFinalMissionTests(WorldTestBase):
    """Hope with final_mission_goal: some of the 100% map opens only after The Future of Hyrule, so the final mission
    opens without it and the goal is both (fuzz 2026-11-14: the other way round was unbeatable)."""
    game = "Hyrule Warriors Age of Calamity"
    options = {"goal_hope_of_all_hyrule": True, "final_mission_goal": True, "goal_story_missions": 20, "goal_challenges": 0,
               "challenge_checks": True, "quest_checks": True, "post_story_unlock": 20}

    def test_final_mission_first_then_hope(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertTrue(session.final_goal and session.goal_hope)
        others = [m for m in session.story_names if m != session.final_mission]
        session.cleared_missions |= set(others)
        self.assertTrue(session._goal_counts_met(exclude_final=True))  # The Future of Hyrule may open
        session.cleared_missions.add(session.final_mission)
        self.assertFalse(session.goal_complete)
        session.game_done.add("The Hope of All Hyrule")
        self.assertTrue(session.goal_complete)


class GoalHopeChallengesOnlyTests(WorldTestBase):
    """Challenges Only keeps every map quest closed: the Hope goal is turned off there."""
    game = "Hyrule Warriors Age of Calamity"
    options = {"goal_hope_of_all_hyrule": True, "game_mode": "challenges_only"}

    def test_turned_off(self) -> None:
        self.assertFalse(self.world.options.goal_hope_of_all_hyrule)
        self.assertFalse(self.world.fill_slot_data()["goal_hope_of_all_hyrule"])


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

    def test_state_nodes_follow_their_items(self) -> None:
        from ..data_lab import LAB_ITEMS, LAB_STATE_NODES
        self.assertEqual(LAB_ITEMS[-3:], list(LAB_STATE_NODES))  # appended: older lab item ids unchanged
        session = Session(json.loads(json.dumps(self.multiworld.worlds[self.player].fill_slot_data())))
        self.assertEqual(session.lab_held(), {24: False, 25: False, 30: False})
        session.apply_received_item_names(["Collect Research Papers (Roll Out the Research)"])
        self.assertEqual(session.lab_held()[24], True)

    def test_state_node_targets(self) -> None:
        from ..data_lab import lab_state_target
        held = {24: False, 25: True, 30: False}
        self.assertEqual(lab_state_target(24, 2, held, set()), 2)  # not bought: open
        self.assertEqual(lab_state_target(24, 3, held, set()), 1)  # just bought, no item: locked (check sent)
        self.assertEqual(lab_state_target(30, 2, held, {"Sensor of the Heart"}), 1)  # bought earlier: stays locked
        self.assertEqual(lab_state_target(25, 2, held, set()), 3)  # item in: done
        self.assertEqual(lab_state_target(5, 1, held, set()), 2)  # other nodes: opened
        self.assertEqual(lab_state_target(5, 3, held, set()), 3)

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
        from ..data_rewards import MASTER_CHEF_ITEM  # its trade pays nothing exactly when its item is in the seed
        self.assertEqual(bool(world.group_copies.get(MASTER_CHEF_ITEM)), "The Master Chef" in world.emptied_quests)
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
        self.assertEqual(lab_needs(world, "Power Play: Nice and Icy"), ([], []))  # runes are given from the start
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

    def test_master_chef_item_gives_its_rupees_once(self) -> None:
        import tempfile
        from pathlib import Path
        from unittest import mock
        from ..client import delivery as D
        from ..data_rewards import ALL_GROUPS, MASTER_CHEF_ITEM, SPLIT_INTO

        self.assertEqual(ALL_GROUPS[MASTER_CHEF_ITEM].known, ("The Master Chef",))  # now counted, so it is in the pool
        self.assertIn(MASTER_CHEF_ITEM, SPLIT_INTO["Progressive Cooking Lesson"])

        class Live:
            def __init__(self): self.rupees = []
            def add_rupees(self, amount): self.rupees.append(amount); return "ok"
        with tempfile.TemporaryDirectory() as d, mock.patch.object(D, "STATE_DIR", Path(d)):
            ledger = D.Delivery("seed", "slot")
            live = Live()
            self.assertEqual(ledger.pending([MASTER_CHEF_ITEM]), [MASTER_CHEF_ITEM])
            ledger.apply([MASTER_CHEF_ITEM], set(), live)
            ledger.apply([MASTER_CHEF_ITEM], set(), live)
            self.assertEqual(live.rupees, [1000])


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


class BorrowedPartyTests(WorldTestBase):
    """story_party borrowed (0.9.87, user): forced heroes you lack are lent for that mission only."""
    game = "Hyrule Warriors Age of Calamity"
    options = {"story_party": "borrowed", "challenge_checks": True}

    def test_lends_only_the_selected_missions_missing_heroes(self) -> None:
        from ..data_save import MISSION_FORCED_HEROES
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertTrue(session.story_party_borrowed and session.heroes_optional)
        self.assertFalse(session.story_party_free)  # parties are not replaced
        mission = "Road to the Ancient Lab"
        lent = session.lent_heroes(mission)
        self.assertEqual(lent, set(MISSION_FORCED_HEROES[mission]) - set(session.unlocked_characters))
        self.assertEqual(session.lent_heroes(None), set())
        self.assertEqual(session.waiting_for_heroes(), {})  # nothing waits for a hero: they are lent

    def test_challenges_need_no_hero_items_in_logic(self) -> None:
        from ..rules import challenge_requirements
        for name in self.world.active_challenges:
            needs = challenge_requirements(self.world, name)
            self.assertFalse([r for r in needs if isinstance(r, str) and r.startswith("Character: ")], name)


class ChallengeUnlockItemTests(WorldTestBase):
    """challenge_unlock_order items (0.9.87, user: default off): each challenge opens with its own unlock item."""
    game = "Hyrule Warriors Age of Calamity"
    options = {"challenge_unlock_order": "items", "challenge_checks": True}

    def test_items_logic_and_client(self) -> None:
        from ..items import unlock_item
        from ..data_save import MISSION_RECORD_IDS
        world = self.world
        self.assertTrue(world.challenge_item_unlocks)
        pool = {i.name for i in self.multiworld.get_items() if i.player == self.player}
        self.assertTrue({unlock_item(c) for c in world.challenge_item_unlocks} <= pool)
        name = next(c for c in world.challenge_item_unlocks if c in MISSION_RECORD_IDS and c.startswith("Mipha"))
        session = Session(json.loads(json.dumps(world.fill_slot_data())))
        record = MISSION_RECORD_IDS[name][0]
        self.assertEqual(session.challenge_unlocks()[record], (record,))  # closed
        session.apply_received_item_names([unlock_item(name)])
        self.assertEqual(session.challenge_unlocks()[record], ())  # opened by its item
        self.assertFalse({n for n in world.options.start_hints.value if n[len("Unlock: "):] in world.challenge_item_unlocks})

    def test_default_is_off(self) -> None:
        from ..options import ChallengeUnlockOrder
        self.assertNotEqual(ChallengeUnlockOrder.default, ChallengeUnlockOrder.option_items)


class ChallengeUnlockItemsNeedChecksTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"challenge_unlock_order": "items", "challenge_checks": False}

    def test_falls_back_without_challenge_checks(self) -> None:
        self.assertEqual(self.world.challenge_item_unlocks, [])
