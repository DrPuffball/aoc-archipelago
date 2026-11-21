"""0.9.90 progress checks (user, 2026-11-19): hero levels, weapon levels, enemies defeated, materials gathered."""
from .test_basic import AoCTestBase
from .. import data_progress as P


def _reaches_all(test: AoCTestBase) -> list[str]:
    """Locations progression items alone can't reach (what a real generation's accessibility check sees)."""
    from BaseClasses import CollectionState
    state = CollectionState(test.multiworld)
    for item in test.multiworld.itempool + list(test.multiworld.precollected_items[test.player]):
        if item.advancement:
            state.collect(item, True)
    state.sweep_for_advancements()
    return [loc.name for loc in test.multiworld.get_locations(test.player) if not loc.can_reach(state)]


class TestOffByDefault(AoCTestBase):
    def test_no_progress_checks(self) -> None:
        names = self.location_names()
        self.assertFalse([n for n in names if n.startswith(("Hero Level: ", "Weapon Level: ", "Gathered: ", "Defeated: "))])


class TestHeroLevels(AoCTestBase):
    options = {"hero_level_checks": True, "hero_level_check_max": 50, "hero_level_check_interval": 10,
               "include_dlc": False}

    def test_steps_and_logic(self) -> None:
        names = {n for n in self.location_names() if n.startswith("Hero Level: ")}
        self.assertEqual(len(names), len(self.world.characters) * 5)  # 10, 20, 30, 40, 50
        self.assertIn("Hero Level: Link Lv 50", names)
        self.assertNotIn("Hero Level: Link Lv 60", names)
        self.assertEqual(P.level_steps(1, 5), [2, 3, 4, 5])  # never level 1
        self.assertEqual(_reaches_all(self), [])
        self.assertFalse(self.can_reach_location("Hero Level: Link Lv 50"))  # needs the whole story

    def test_slot_data(self) -> None:
        self.assertEqual(len(self.world.fill_slot_data()["hero_level_ids"]), len(self.world.characters) * 5)


class TestWeaponLevels(AoCTestBase):
    options = {"weapon_level_checks": True, "weapon_level_check_max": 30, "weapon_level_check_interval": 5,
               "quest_checks": True, "include_dlc": False, "weapon_fusion": True}

    def test_caps_follow_the_quests(self) -> None:
        names = {n for n in self.location_names() if n.startswith("Weapon Level: Link")}
        top = 20 + (5 if "A Monumental Undertaking" in self.world.active_quests else 0) \
            + (5 if {"A Monumental Undertaking", "The Legendary Blacksmith"} <= set(self.world.active_quests) else 0)
        self.assertEqual(max(int(n.rsplit(" ", 1)[1]) for n in names), top)
        self.assertEqual(_reaches_all(self), [])


class TestWeaponLevelsStoryOnly(AoCTestBase):
    options = {"game_mode": "story_only", "weapon_level_checks": True, "weapon_level_check_max": 30,
               "weapon_level_check_interval": 10, "include_dlc": False}

    def test_capped_at_20_without_the_quests(self) -> None:
        names = {n for n in self.location_names() if n.startswith("Weapon Level: Link")}
        self.assertEqual(names, {"Weapon Level: Link Lv 10", "Weapon Level: Link Lv 20"})
        self.assertEqual(_reaches_all(self), [])


class TestGathering(AoCTestBase):
    options = {"material_checks": True, "enemy_defeat_checks": True, "gathering_check_tiers": 3,
               "material_scale": 50, "enemy_defeat_scale": 200, "include_dlc": False}

    def test_counts_and_logic(self) -> None:
        data = self.world.fill_slot_data()
        counts = data["gather_counts"]
        self.assertEqual(counts["Gathered: Hyrule Herb (1)"], 10)  # common 20 at 50 %
        self.assertEqual(counts["Defeated: Bokoblin (3)"], 10000)  # 5000 at 200 %
        self.assertTrue(set(data["gathered_ids"]) <= set(counts) and set(data["defeated_ids"]) <= set(counts))
        names = self.location_names()
        self.assertIn("Defeated: Guardian (3)", names)
        self.assertIn("Defeated: Keese (1)", names)
        self.assertFalse([n for n in names if n.startswith(("Defeated: Hinox", "Defeated: Stone Talus", "Gathered: Diamond"))])
        self.assertEqual(_reaches_all(self), [])


class TestGatheringStoryOnly(AoCTestBase):
    options = {"game_mode": "story_only", "material_checks": True, "enemy_defeat_checks": True, "include_dlc": False}

    def test_challenge_enemies_left_out(self) -> None:
        names = self.location_names()
        self.assertFalse([n for n in names if n.startswith(("Defeated: Molduga", "Gathered: Molduga"))])
        self.assertIn("Defeated: Lynel (1)", names)  # Lynels are in story missions too: the whole story covers them
        self.assertIn("Defeated: Bokoblin (1)", names)
        self.assertEqual(_reaches_all(self), [])


class ClientProgressTests(AoCTestBase):
    options = {"hero_level_checks": True, "hero_level_check_interval": 10, "weapon_level_checks": True,
               "weapon_level_check_interval": 5, "material_checks": True, "enemy_defeat_checks": True,
               "gathering_check_tiers": 2, "include_dlc": False}

    def test_tally_counts_gains_not_spending_or_deliveries(self) -> None:
        from ..client.progress import GatherTally
        state: dict = {}
        tally = GatherTally(state)
        counts = [0] * 176
        tally.update(counts, 0)  # first look: the baseline
        counts[22] = 30  # +30 Hyrule Herb gathered
        self.assertTrue(tally.update(list(counts), 0))
        counts[22] = 5  # spent 25
        tally.update(list(counts), 0)
        counts[22] = 20  # +15 by a Material Bundle (the client wrote materials)
        tally.update(list(counts), 1)
        counts[22] = 26  # +6 gathered
        tally.update(list(counts), 1)
        self.assertEqual(tally.total(22), 36)
        self.assertIn("gathered", state)  # kept in the seed's ledger

    def test_reached_and_messages(self) -> None:
        import json
        from ..client.progress import GatherTally, reached
        from ..client.savewatch import message_for
        from ..client.session import Session
        s = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertTrue(s.has_progress_checks)
        hero = sorted(s.unlocked_characters)[0]
        tally = GatherTally({})
        tally.update([0] * 176, 0)
        counts = [0] * 176
        counts[158] = 600  # Bokoblin trophies
        tally.update(counts, 0)
        got = reached(s.ids, s.gather_counts, {hero: 25}, {hero: 12}, tally)
        self.assertIn(f"Hero Level: {hero} Lv 20", got)
        self.assertNotIn(f"Hero Level: {hero} Lv 30", got)
        self.assertIn(f"Weapon Level: {hero} Lv 10", got)
        self.assertIn("Defeated: Bokoblin (1)", got)  # 500
        self.assertNotIn("Defeated: Bokoblin (2)", got)  # 2000
        msg = message_for("Defeated: Bokoblin (1)")
        self.assertEqual(msg["type"], "progress_reached")
        self.assertEqual(s.on_progress(msg["kind"], msg["name"]), s.ids["defeated"]["Defeated: Bokoblin (1)"])


class TestChallengesOnlyProgress(AoCTestBase):
    """Challenges Only has no story: the progress checks' story gates become shares of the goal's challenge clears
    (fuzz 2026-11-19: they were all unreachable there), always below the goal itself."""
    options = {"game_mode": "challenges_only", "hero_level_checks": True, "hero_level_check_max": 100,
               "weapon_level_checks": True, "enemy_defeat_checks": True, "material_checks": True,
               "gathering_check_tiers": 3, "goal_challenges": 168, "include_dlc": False}

    def test_reachable_and_no_story_rewards(self) -> None:
        self.assertEqual(_reaches_all(self), [])
        names = self.location_names()
        self.assertFalse([n for n in names if n.startswith("Gathered: ")
                          and P.MATERIALS[n.split(": ", 1)[1].rsplit(" (", 1)[0]][2][0] == "missions"])


class TestFinalGoalChallengesBeforeIt(AoCTestBase):
    """final_mission_goal with every challenge and the vanilla challenge order: the challenges that need The Future of
    Hyrule's clear don't count towards opening it (fuzz 2026-11-19 seed 9017)."""
    options = {"final_mission_goal": True, "goal_challenges": 168, "challenge_unlock_order": "vanilla",
               "challenge_logic": "by_level", "include_dlc": False}

    def test_goal_lowered_and_reachable(self) -> None:
        self.assertLess(self.world.options.goal_challenges.value, len(self.world.goal_challenge_pool) + 1)
        self.assertEqual(_reaches_all(self), [])
