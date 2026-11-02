"""Game modes (user, 2026-11-02): Story Only and Challenges Only."""

import json

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
        self.assertEqual(w.options.goal_challenges.value, 50)
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
        self.assertTrue(w.group_copies.get("Progressive Recipe"))  # recipes are items on level clears
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
