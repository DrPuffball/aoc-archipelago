"""Story missions that can't be finished without Remote Bombs (data.MISSION_RUNES; Discord, 2026-11-23: a player with
mission unlock items started with Urbosa's mission, whose "Defeat the Yiga Clan with Remote Bombs" he couldn't do)."""
from unittest import TestCase
from types import SimpleNamespace

from BaseClasses import CollectionState, ItemClassification
from test.bases import WorldTestBase

from ..data import MISSION_RUNES, MISSIONS
from ..items import rune_item, unlock_item
from ..regions import cleared_event

URBOSA, WCF, HF = "Urbosa, the Gerudo Chief", "When Courage Fails", "The Battle of Hyrule Field"


class Base(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    run_default_tests = False

    def open_with(self, *names, mission=URBOSA) -> bool:
        state = CollectionState(self.multiworld)
        for n in names:
            state.collect(self.world.create_item(n), True)
        return self.world.get_entrance(f"Start {mission}").access_rule(state)


class TestShuffledRunesItems(Base):
    options = {"mission_unlocks": "items", "sheikah_runes": "shuffled"}

    def test_needs_the_bombs(self) -> None:
        for mission in MISSION_RUNES:
            heroes = [f"Character: {c}" for c in self.world.characters]
            self.assertFalse(self.open_with(unlock_item(mission), *heroes, mission=mission))
            self.assertTrue(self.open_with(unlock_item(mission), rune_item("Remote Bombs"), *heroes, mission=mission))

    def test_bombs_are_progression(self) -> None:
        self.assertEqual(self.world.create_item(rune_item("Remote Bombs")).classification, ItemClassification.progression)

    def test_never_behind_itself(self) -> None:
        """The clear and its bonus checks can't hold the bombs: not reachable without them, with everything else."""
        state = CollectionState(self.multiworld)
        for item in self.multiworld.itempool:
            if item.name != rune_item("Remote Bombs"):
                state.collect(item, True)
        state.sweep_for_advancements()
        for loc in self.multiworld.get_locations(1):
            if loc.name.startswith((f"Clear: {URBOSA}", f"Clear: {WCF}")):
                self.assertFalse(loc.can_reach(state), loc.name)


class TestStoryOnlyNoOtherUse(Base):
    """Nothing else in the seed needs the rune: it must still be progression."""
    options = {"game_mode": "story_only", "korok_checks": False, "chest_checks": False, "sheikah_runes": "shuffled"}

    def test_bombs_are_progression(self) -> None:
        self.assertEqual(self.world.create_item(rune_item("Remote Bombs")).classification, ItemClassification.progression)


class TestStartWithAll(Base):
    options = {"mission_unlocks": "items", "sheikah_runes": "start_with_all"}

    def test_open(self) -> None:
        self.assertTrue(self.open_with(unlock_item(URBOSA), *[f"Character: {c}" for c in self.world.characters]))


class TestVanillaRunes(Base):
    options = {"mission_unlocks": "items", "sheikah_runes": "vanilla"}

    def test_needs_hyrule_field(self) -> None:
        heroes = [f"Character: {c}" for c in self.world.characters]
        self.assertFalse(self.open_with(unlock_item(URBOSA), *heroes))
        state = CollectionState(self.multiworld)
        for n in (unlock_item(URBOSA), *heroes):
            state.collect(self.world.create_item(n), True)
        state.prog_items[1][cleared_event(HF)] += 1
        self.assertTrue(self.world.get_entrance(f"Start {URBOSA}").access_rule(state))


class TestFirstMissionPlayable(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    run_default_tests = False

    def test_many_seeds(self) -> None:
        for mode in ("standard", "story_only"):
            for unlocks in ("items", "story_order"):
                for runes in ("shuffled", "vanilla"):
                    for first in ("random_any", "random_early", "vanilla"):
                        for seed in range(6):
                            self.options = {"game_mode": mode, "mission_unlocks": unlocks, "sheikah_runes": runes,
                                            "first_mission": first, "mission_order": "shuffle_all",
                                            "starting_mission_unlocks": 5}
                            with self.subTest(**self.options, seed=seed):
                                self.world_setup(seed)
                                w = self.world
                                order = w.story_chain or w.mission_order
                                self.assertEqual(sorted(w.mission_order), sorted(m.name for m in MISSIONS))
                                self.assertNotIn(order[0], MISSION_RUNES)
                                if w.starting_unlocks:  # others may need the bombs; the first one never does
                                    self.assertNotIn(w.starting_unlocks[0], MISSION_RUNES)
                                if unlocks == "story_order" and runes == "vanilla":
                                    for m in MISSION_RUNES:
                                        self.assertLess(order.index(HF), order.index(m))


class TestClientTodo(TestCase):
    def test_missing_runes(self) -> None:
        from ..client.session import Session
        for have, want in (({"Remote Bombs": False}, ["Remote Bombs"]), ({"Remote Bombs": True}, [])):
            fake = SimpleNamespace(mod_rune_flags=lambda have=have: have)
            self.assertEqual(Session.missing_runes(fake, URBOSA), want)
            self.assertEqual(Session.missing_runes(fake, HF), [])


EX_ITEMS = "EX Battle Research: Items"


class TestExBattleResearchItems(Base):
    """EX Battle Research: Items is played with the runes and fire attacks (data.RUNE_CHALLENGES, ROD_CHALLENGES)."""
    options = {"include_dlc": True, "rod_items": True, "sheikah_runes": "shuffled", "side_content": ["Challenges"],
               "goal": "story"}

    def test_needs_every_rune_and_the_fire_rod(self) -> None:
        from BaseClasses import ItemClassification
        from ..items import classify
        from ..rules import challenge_requirements
        need = challenge_requirements(self.world, EX_ITEMS)
        for item in ("Rune: Remote Bombs", "Rune: Cryonis", "Rune: Magnesis", "Rune: Stasis", "Fire Rod"):
            self.assertIn(item, need)
            self.assertEqual(classify(self.world, item), ItemClassification.progression)
        self.assertNotIn("Ice Rod", need)


class TestExBattleResearchItemsNoRods(Base):
    options = {"include_dlc": True, "rod_items": False, "sheikah_runes": "start_with_all", "goal": "story"}

    def test_nothing_to_find(self) -> None:
        from ..rules import challenge_requirements
        need = challenge_requirements(self.world, EX_ITEMS)
        self.assertFalse([n for n in need if n.startswith("Rune: ") or n == "Fire Rod"])


class TestRuneTables(TestCase):
    """The per-seed and per-chest rune tables (read from the game's data, 2026-11-23)."""

    def test_tables_name_real_checks(self) -> None:
        from ..data import RODS, ROD_CHALLENGES, RUNE_CHALLENGES, RUNES
        from ..data_challenges import CHALLENGE_BY_NAME
        from ..data_chests import CHEST_RUNES, CHESTS_IN_MISSIONS, DLC_CHESTS
        from ..data_koroks import KOROK_RUNES, KOROKS_IN_CHALLENGES, KOROKS_IN_MISSIONS
        seeds = {**KOROKS_IN_MISSIONS, **KOROKS_IN_CHALLENGES}
        chests = {**CHESTS_IN_MISSIONS, **{m: len(slots) for m, (_, slots) in DLC_CHESTS.items()}}
        for table, counts in ((KOROK_RUNES, seeds), (CHEST_RUNES, chests)):
            for (source, n), runes in table.items():
                self.assertTrue(1 <= n <= counts[source], (source, n))
                self.assertTrue(set(runes) <= set(RUNES))
        self.assertTrue(set(RUNE_CHALLENGES) | set(ROD_CHALLENGES) <= set(CHALLENGE_BY_NAME))
        self.assertTrue({r for rods in ROD_CHALLENGES.values() for r in rods} <= set(RODS))
        self.assertEqual((len(KOROK_RUNES), len(CHEST_RUNES)), (14, 14))


class TestBudgetBattle(Base):
    options = {"include_dlc": True, "rod_items": True}

    def test_ice_rod(self) -> None:
        from ..rules import challenge_requirements
        self.assertIn("Ice Rod", challenge_requirements(self.world, "EX The Budget Battle"))
        self.assertNotIn("Rune: Remote Bombs", challenge_requirements(self.world, "Explosive—Handle With Care"))


class TestLabVanillaRunes(Base):
    options = {"include_dlc": True, "sheikah_runes": "vanilla", "lab_checks": True, "mission_order": "shuffle_all"}

    def test_lab_waits_for_the_rune(self) -> None:
        from ..rules import lab_needs
        self.assertIn(cleared_event("Road to the Ancient Lab"), lab_needs(self.world, "Power Play: Magnetic Mayhem")[0])
        self.assertIn(cleared_event(HF), lab_needs(self.world, "Power Play: Bombs Away")[0])
