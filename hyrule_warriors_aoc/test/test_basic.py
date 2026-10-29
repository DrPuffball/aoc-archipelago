from test.bases import WorldTestBase

from ..data import ALL_CHARACTERS, BASE_CHARACTERS, MISSIONS, WEAPONS
from ..data_challenges import CHALLENGES
from ..data_quests import QUESTS
from ..data_save import BASIC_WEAPONS
from ..locations import KOROKS


class AoCTestBase(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"

    def sweep(self) -> None:
        self.multiworld.state.sweep_for_advancements()

    def collect_champions(self) -> None:
        """Calamity Strikes needs Mipha, Daruk, Revali and Urbosa (those not among the starters)."""
        names = [f"Character: {c}" for c in ("Mipha", "Daruk", "Revali", "Urbosa")
                 if c not in self.world.starting_characters]
        if names:
            self.collect_by_name(names)

    def location_names(self) -> set[str]:
        """Every check except the bonus checks on story clears (those depend on the item count)."""
        return {loc.name for loc in self.multiworld.get_locations(self.player)
                if loc.address is not None and "(Bonus " not in loc.name}


class TestDefaults(AoCTestBase):
    def test_four_random_starters_precollected(self) -> None:
        names = {i.name for i in self.multiworld.precollected_items[self.player]}
        self.assertEqual(len(names), 4)
        self.assertEqual(names, {f"Character: {c}" for c in self.world.starting_characters})
        self.assertTrue(set(self.world.starting_characters) <= set(BASE_CHARACTERS))

    def test_story_needs_only_the_champions(self) -> None:
        # Any heroes can play the story missions; Calamity Strikes alone needs the four Champions.
        self.assertTrue(self.can_reach_location(f"Clear: {self.world.mission_order[0]}"))  # first_mission's pick
        self.assertFalse(self.can_reach_location(f"Clear: {self.world.mission_order[-1]}"))
        self.collect_champions()
        self.sweep()
        self.assertTrue(self.can_reach_location("Clear: The Future of Hyrule"))

    def test_default_locations(self) -> None:
        names = self.location_names()
        # weapon checks are off by default; items beyond the checks get bonus checks on story clears
        self.assertFalse(any(n.startswith("Obtain: ") for n in names))
        bonus = sum(getattr(self.world, "bonus_checks", {}).values())
        # (post-story challenges are mixed in by default, post_story_unlock 10; with 20 they'd hold no checks)
        self.assertFalse(self.world.post_goal_side)
        self.assertEqual(len(names), len(MISSIONS) + len([c for c in CHALLENGES if not c.is_ex])
                         + len(self.world.checked_quests) + bonus)
        self.assertIn("Quest: Hyrule Swordfighting Academy", names)

    def test_finishing_requires_every_mission(self) -> None:
        # The main story needs only the four Champions (Calamity Strikes) besides clearing every mission in order.
        self.collect_champions()
        self.assertBeatable(True)


class TestRestrictedChallenge(AoCTestBase):
    options = {"starting_character_pool": ["Link"], "starting_character_count": 1, "story_pacing": 0}

    def test_restricted_challenge_needs_its_character(self) -> None:
        self.sweep()
        self.collect_by_name([f"Character: {c}" for c in ALL_CHARACTERS if c != "Daruk"])
        self.assertFalse(self.can_reach_location("Challenge: Daruk's Training"))
        self.collect_by_name(["Character: Daruk"])
        self.assertTrue(self.can_reach_location("Challenge: Daruk's Training"))


class TestEverything(AoCTestBase):
    options = {
        "side_content": ["Weapons", "Challenges", "Quests"],
        "include_dlc": True,
        "starting_character_count": 6,
    }

    def test_all_locations_exist(self) -> None:
        from ..data_rewards import OPEN_SERVICE_QUESTS
        # no check: quests open from the start (Training Camp; the Smithy only without Weapon Fusion); no Koroks
        no_check = len(set(OPEN_SERVICE_QUESTS) - set(self.world.item_quests))
        from ..data_quests import UNUSED_QUESTS
        expected = (len(MISSIONS) + len([w for w in WEAPONS if w.name not in BASIC_WEAPONS]) - len(self.world.post_goal_weapons)
                    + len(self.world.checked_challenges)  # (post-story ones: after the goal, no checks)
                    + len(self.world.checked_quests))
        self.assertEqual(len(self.location_names()), expected)
        self.assertEqual(len(self.world.starting_characters), 6)

    def test_quest_prereqs_enforced(self) -> None:
        self.collect_all_but([])
        self.assertTrue(self.can_reach_location("Quest: Keeping the Village Peace"))


class TestStoryOnly(AoCTestBase):
    options = {"side_content": []}

    def test_only_missions(self) -> None:
        self.assertEqual(len(self.location_names()), len(MISSIONS))


class TestStoryOnlyToggles(AoCTestBase):
    options = {"challenge_checks": False, "quest_checks": False}

    def test_only_missions(self) -> None:
        self.assertEqual(len(self.location_names()), len(MISSIONS))
        self.assertEqual(self.world.options.side_content.value, set())


class TestWeaponToggle(AoCTestBase):
    options = {"weapon_checks": True, "challenge_checks": False}

    def test_side_content_from_toggles(self) -> None:
        self.assertEqual(self.world.options.side_content.value, {"Weapons", "Quests"})


class TestShuffledOrder(AoCTestBase):
    options = {"mission_order": "shuffle_all"}

    def test_slots_cover_all_missions(self) -> None:
        self.assertEqual(sorted(self.world.slot_to_mission.values()), sorted(m.name for m in MISSIONS))

    def test_first_mission_is_early(self) -> None:  # Hyrule Field, then first_mission random_early (default)
        self.assertEqual(self.world.mission_order[0], "The Battle of Hyrule Field")
        self.assertLessEqual(next(m.chapter for m in MISSIONS if m.name == self.world.mission_order[1]), 2)


class TestVanillaFirstMission(AoCTestBase):
    options = {"mission_order": "shuffle_all", "first_mission": "vanilla"}

    def test_hyrule_field_stays_first(self) -> None:
        self.assertEqual(self.world.mission_order[0], "The Battle of Hyrule Field")


class TestSideGates(AoCTestBase):
    options = {
        "side_content": ["Challenges", "Quests"],
        "challenge_logic": "by_level",
        "side_missions_per_unlock": 3,
        "mission_order": "shuffle_within_chapter",
    }

    def test_gates_present_and_achievable(self) -> None:
        required = self.world.slot_side_required
        self.assertEqual(required["The Battle of Hyrule Field"], 0)
        self.assertGreater(max(required.values()), 0)
        self.assertTrue(self.world.side_counted)
        self.assertLessEqual(next(m.chapter for m in MISSIONS if m.name == self.world.mission_order[0]), 2)
        # The main story needs only the four Champions besides clearing every mission in order.
        self.collect_champions()
        self.assertBeatable(True)


class TestVanillaParty(AoCTestBase):
    options = {"story_party": "vanilla", "starting_character_pool": ["Link"], "starting_character_count": 1,
               "first_mission": "vanilla"}

    def test_champion_mission_needs_champion(self) -> None:
        self.sweep()
        self.assertTrue(self.can_reach_location("Clear: Road to the Ancient Lab"))
        self.assertFalse(self.can_reach_location("Clear: Daruk, the Goron Hero"))
        self.collect_by_name(["Character: Daruk"])
        self.assertTrue(self.can_reach_location("Clear: Daruk, the Goron Hero"))


class TestShuffledVanillaParty(AoCTestBase):
    options = {"story_party": "vanilla", "mission_order": "shuffle_all", "starting_character_count": 1}

    def test_first_slot_playable(self) -> None:
        first = self.world.mission_order[0]
        self.assertTrue(self.can_reach_location(f"Clear: {first}"))


class TestChampionStartersFreeParty(AoCTestBase):
    options = {"starting_character_pool": ["Mipha", "Daruk", "Revali", "Urbosa"], "starting_character_count": 4,
               "side_content": []}

    def test_calamity_strikes_needs_a_hero_it_lets_you_pick(self) -> None:
        self.assertIn("Calamity Strikes", self.world.party_needs)
        self.assertNotIn("Mipha", self.world.party_needs["Calamity Strikes"])
        self.assertTrue(self.world.characters_matter)
        from BaseClasses import CollectionState
        allowed = {f"Character: {c}" for c in self.world.party_needs["Calamity Strikes"]}
        state = CollectionState(self.multiworld)  # the four Champion starters only
        items = self.multiworld.itempool + [loc.item for loc in self.multiworld.get_locations() if loc.item]
        for item in items:
            if item.player == self.player and item.name not in allowed:
                state.collect(item, True)
        start = self.world.get_entrance("Start Calamity Strikes")
        self.assertFalse(start.access_rule(state))
        state.collect(self.world.create_item("Character: Link"), True)
        self.assertTrue(start.access_rule(state))


class TestGoals(AoCTestBase):
    options = {"goal": "story_and_side_missions", "goal_side_missions": 5, "side_content": ["Quests"]}

    def test_goal_needs_side_missions(self) -> None:
        self.assertEqual(self.world.goal_side_required, 5)
        self.assertTrue(self.world.side_counted)
        self.collect_champions()
        self.assertBeatable(True)


class TestAllCharactersGoal(AoCTestBase):
    options = {"goal": "story_and_all_characters", "side_content": []}

    def test_needs_every_character(self) -> None:
        self.assertBeatable(False)
        self.collect_all_but([])
        self.assertBeatable(True)


class TestFeaturesAndLocalFiller(AoCTestBase):
    options = {"locked_features": ["Shops", "Cooking"], "local_filler": True}

    def test_feature_items_in_pool(self) -> None:
        names = {i.name for i in self.multiworld.itempool if i.player == self.player}
        # pre_fill may already have placed it (front-loaded progression)
        names |= {loc.item.name for loc in self.multiworld.get_locations(self.player) if loc.item}
        self.assertIn("Feature: Shops", names)
        self.assertIn("Rupee Pouch", self.multiworld.worlds[self.player].options.local_items.value)

    def test_smithy_always_open(self) -> None:
        from ..data import LOCKABLE_FEATURES, SMITHY_QUEST
        self.assertNotIn("Smithy", LOCKABLE_FEATURES)
        self.assertNotIn(SMITHY_QUEST, self.world.checked_quests)


class TestPace(AoCTestBase):
    options = {"minimum_character_level": 10, "catch_up_levels": True}

    def test_level_settings_reach_the_client(self) -> None:
        pace = self.world.pace()
        self.assertEqual(pace, {"min_level": 10, "catch_up": True})
        self.assertEqual(self.world.fill_slot_data()["pace"], pace)


class TestBossRush(AoCTestBase):
    options = {"goal": "story_and_boss_rush", "side_content": []}

    def test_boss_events_exist_without_side_content(self) -> None:
        self.assertEqual(len(self.world.active_challenges), 18)
        self.assertEqual(len(self.location_names()), len(MISSIONS))
        # Boss challenges need the heroes their party uses, so the goal needs items, not just the starting heroes.
        self.collect_all_but([])
        self.assertBeatable(True)


class TestFeaturedChallenge(AoCTestBase):
    options = {"featured_challenge": True}

    def test_priority_location_set(self) -> None:
        name = self.world.featured_challenge
        self.assertIsNotNone(name)
        self.assertIn(f"Challenge: {name}", self.world.options.priority_locations.value)


class TestSteadyRewards(AoCTestBase):
    options = {"side_content": ["Weapons", "Challenges", "Quests"]}

    def test_no_filler_on_story_clears_and_no_traps(self) -> None:
        from Fill import distribute_items_restrictive

        for seed in range(15):
            self.world_setup(seed)
            distribute_items_restrictive(self.multiworld)
            for name in self.world.mission_order[1:]:  # Hyrule Field: pre-cleared, holds a locked filler of yours
                item = self.multiworld.get_location(f"Clear: {name}", self.player).item
                self.assertFalse(item.player == self.player and item.advancement is False and item.useful is False,
                                 f"seed {seed}: {name} holds filler {item.name}")
            for item in self.multiworld.itempool:
                self.assertFalse(item.trap)


class TestPacing(AoCTestBase):
    options = {"side_unlocks": "game_rules", "side_content": ["Weapons", "Challenges", "Quests"], "story_pacing": 100, "combo_upgrades": 1,
               "quest_reward_items": {}, "weapon_fusion": False, "seal_slot_upgrades": 0, "locked_features": []}
    # (fewer power items than early checks, so the spread is measurable)

    def test_power_items_spread_over_every_story_stage(self) -> None:
        from .. import pacing

        stages = pacing.candidate_locations(self.world)
        per_stage: dict[int, int] = {}
        for loc in self.multiworld.get_locations(self.player):
            if loc.address is not None and loc.item and loc.name in stages and stages[loc.name] <= 20:
                per_stage[stages[loc.name]] = per_stage.get(stages[loc.name], 0) + 1
        # (stage 20 may stay empty: with Calamity Strikes behind the four Champions, the fill keeps power items off it)
        self.assertGreaterEqual(len(per_stage), 19)
        # the last stage only has the final clear before the goal (what it opens comes after winning)
        early = [per_stage[st] for st in range(1, 20)]
        self.assertLessEqual(max(early) - min(early), 10)  # (the Champions must come before Calamity Strikes)


class TestUpgradesComplete(AoCTestBase):
    options = {"combo_upgrades": 5, "side_content": ["Challenges", "Quests"], "include_dlc": True}

    def test_every_hero_gets_every_combo_level(self) -> None:
        from collections import Counter
        placed = [loc.item for loc in self.multiworld.get_locations(self.player) if loc.item]  # incl. story pacing
        pool = Counter(i.name for i in self.multiworld.itempool + placed if i.player == self.player)
        pool.update(i.name for i in self.multiworld.precollected_items[self.player])
        for hero in self.world.characters:
            self.assertEqual(pool[f"Combo Upgrade: {hero}"], 5, hero)
        self.assertEqual(self.world.fill_slot_data()["combo_upgrades"], 5)


class TestUpgradesScaledWhenShort(AoCTestBase):
    options = {"combo_upgrades": 5, "side_content": [], "locked_features": ["Shops"], "starting_character_count": 4}

    def test_tight_pool_keeps_features_and_even_upgrades(self) -> None:
        from collections import Counter
        placed = [loc.item for loc in self.multiworld.get_locations(self.player) if loc.item]  # incl. story pacing
        pool = Counter(i.name for i in self.multiworld.itempool + placed if i.player == self.player)
        pool.update(i.name for i in self.multiworld.precollected_items[self.player])
        self.assertEqual(pool["Feature: Shops"], 1)
        combos = {pool[f"Combo Upgrade: {hero}"] for hero in self.world.characters}
        self.assertEqual(len(combos), 1)  # every hero the same
        self.assertEqual(self.world.fill_slot_data()["combo_upgrades"], combos.pop())


class TestBasicWeaponsUnchecked(AoCTestBase):
    options = {"side_content": ["Weapons"], "include_dlc": True, "weapon_check_logic": "after_character"}

    def test_no_basic_weapon_checks(self) -> None:
        from ..data_save import BASIC_WEAPONS
        from ..locations import weapon_location

        names = set(self.location_names())
        self.assertFalse({weapon_location(w) for w in BASIC_WEAPONS} & names)
        self.assertIn(weapon_location("Master Sword"), names)


class TestPostGoalExcluded(AoCTestBase):
    options = {"side_content": ["Weapons", "Challenges", "Quests"]}

    def test_post_goal_checks_hold_filler(self) -> None:
        from BaseClasses import LocationProgressType
        from worlds.AutoWorld import call_all
        call_all(self.multiworld, "pre_fill")
        state = self.multiworld.get_all_state(False)
        for name in self.world.post_goal_excluded:
            loc = self.multiworld.get_location(name, self.player)
            self.assertEqual(loc.progress_type, LocationProgressType.EXCLUDED)
            self.assertTrue(loc.can_reach(state))


class TestGoalExtrasExcludeNothing(AoCTestBase):
    options = {"side_content": ["Weapons", "Challenges"], "goal_challenges": 1}

    def test_nothing_excluded(self) -> None:
        from worlds.AutoWorld import call_all
        call_all(self.multiworld, "pre_fill")
        self.assertEqual(self.world.post_goal_excluded, [])


class TestPostStoryWeaponsNoChecks(AoCTestBase):
    options = {"side_content": ["Weapons"]}

    def test_no_check_behind_the_goal(self) -> None:
        from ..data import WEAPONS
        from ..locations import weapon_location
        names = set(self.location_names())
        unverified = {w.name for w in WEAPONS if not w.verified}
        self.assertTrue(self.world.post_goal_weapons)
        self.assertFalse({weapon_location(w) for w in unverified} & names)


class TestPostStoryWeaponsWithChallengeGoal(AoCTestBase):
    options = {"side_content": ["Weapons", "Challenges"], "goal_challenges": 1}

    def test_drops_stay_checks(self) -> None:
        self.assertEqual(self.world.post_goal_weapons, [])


class TestBonusChecks(AoCTestBase):
    options = {"side_content": []}

    def test_items_get_bonus_checks_on_story_clears(self) -> None:
        import json
        from ..client.session import Session
        from ..locations import bonus_location
        bonus = self.world.bonus_checks
        self.assertTrue(bonus)
        self.assertLessEqual(max(bonus.values()) - min(bonus.values()), 1)  # spread evenly
        hf = self.world.get_location("Clear: The Battle of Hyrule Field")
        self.assertTrue(hf.locked and hf.item.player == self.player and hf.item.filler)  # a locked filler of yours
        # nothing beyond the starting heroes is handed out: every item has a check
        self.assertEqual(len(self.multiworld.precollected_items[self.player]), len(self.world.starting_characters))
        self.assertNotIn(self.world.mission_order[0], bonus)  # Hyrule Field: pre-cleared, no checks behind it
        mission = self.world.mission_order[1]
        self.collect_all_but([])
        self.assertTrue(self.can_reach_location(bonus_location(mission, 1)))
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertEqual(len(session.bonus_ids(mission)), bonus[mission])


class TestNoBonusWhenChecksSuffice(AoCTestBase):
    options = {"side_content": ["Weapons", "Challenges", "Quests"], "weapon_check_logic": "after_character"}

    def test_no_bonus(self) -> None:
        self.assertEqual(self.world.bonus_checks, {})


class TestShortGoalExcludesLaterSlots(AoCTestBase):
    options = {"side_content": ["Challenges"], "goal_story_missions": 10}

    def test_slots_after_the_goal_hold_filler(self) -> None:
        from BaseClasses import LocationProgressType
        from ..locations import mission_location
        for mission in self.world.mission_order[10:]:  # slots past the goal's ten
            loc = self.multiworld.get_location(mission_location(mission), self.player)
            self.assertEqual(loc.progress_type, LocationProgressType.EXCLUDED, mission)
        first = self.multiworld.get_location(mission_location(self.world.mission_order[0]), self.player)
        self.assertNotEqual(first.progress_type, LocationProgressType.EXCLUDED)


class TestChallengeGoalKeepsPostStoryOpen(AoCTestBase):
    options = {"side_content": ["Challenges"], "goal_challenges": 5, "post_story_unlock": 20}

    def test_story_can_finish_first(self) -> None:
        from BaseClasses import LocationProgressType
        from ..locations import mission_location
        last = self.world.mission_order[-1]
        loc = self.multiworld.get_location(mission_location(last), self.player)
        self.assertNotEqual(loc.progress_type, LocationProgressType.EXCLUDED)
        # any challenge can be one of the goal's five, so no challenge or story check is post-goal
        self.assertFalse([n for n in self.world.post_goal_excluded if n.startswith(("Clear: ", "Challenge: "))])


class TestCalamityRescues(AoCTestBase):
    """Calamity Strikes opens once all four Champions are yours (no unlock item, not shuffled) and opens Water and
    Fire / Air and Lightning itself, so no Champion is ever trapped (unplayable) after it."""
    options = {"mission_unlocks": "items", "side_content": ["Challenges"], "side_unlocks": "game_rules"}

    def test_calamity_strikes_needs_the_champions(self) -> None:
        for name in ("Calamity Strikes", "Water and Fire", "Air and Lightning"):
            self.assertEqual(self.world.slot_to_mission[name], name)
        names = {i.name for i in self.multiworld.itempool} | {i.name for i in self.multiworld.precollected_items[self.player]}
        for name in ("Calamity Strikes", "Water and Fire", "Air and Lightning"):
            self.assertNotIn(f"Unlock: {name}", names)
        missing = [f"Character: {c}" for c in ("Mipha", "Daruk", "Revali", "Urbosa") if c not in self.world.starting_characters]
        if missing:
            self.collect_all_but(missing)
            self.assertFalse(self.can_reach_location("Clear: Calamity Strikes"))
        self.collect_all_but([])
        self.assertTrue(self.can_reach_location("Clear: Calamity Strikes"))

    def test_client_opens_calamity_strikes_with_the_champions(self) -> None:
        import json
        from ..client.session import Session
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        others = [c for c in session.all_characters if c not in ("Mipha", "Daruk", "Revali", "Urbosa")]
        session.unlocked_characters = set(others)
        self.assertNotIn("Calamity Strikes", session.available_missions())
        session.unlocked_characters |= {"Mipha", "Daruk", "Revali", "Urbosa"}
        self.assertIn("Calamity Strikes", session.available_missions())
        self.assertNotIn("Water and Fire", session.available_missions())
        session.cleared_missions.add("Calamity Strikes")
        self.assertIn("Water and Fire", session.available_missions())

    def test_trapped_champion_challenges_close_after_calamity_strikes(self) -> None:
        import json
        from ..client.session import Session
        from ..data_save import MISSION_RECORD_IDS
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        session.unlocked_characters = set(session.all_characters) - {"Mipha"}
        record = MISSION_RECORD_IDS["Escorting the Injured"][0]
        self.assertNotEqual(session.challenge_unlocks()[record], (record,))
        session.cleared_missions.add("Calamity Strikes")
        self.assertEqual(session.challenge_unlocks()[record], (record,))  # Mipha (its AI ally) isn't yours



class TestVanillaPostStory(AoCTestBase):
    """post_story_unlock 20 (vanilla): post-story content opens after a story-only goal, so it holds no checks."""
    options = {"post_story_unlock": 20, "side_content": ["Challenges", "Quests"]}

    def test_no_checks_after_the_goal(self) -> None:
        from ..world import _post_story_challenge
        self.assertTrue(self.world.post_goal_side)
        self.assertFalse(any(_post_story_challenge(c) for c in self.world.checked_challenges))
        self.assertFalse(any(_post_story_challenge(c) for c in self.world.challenge_open_at))
