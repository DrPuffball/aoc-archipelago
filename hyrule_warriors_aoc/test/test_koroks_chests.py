import unittest

from .test_basic import AoCTestBase
from ..client import savefile
from ..client.savewatch import message_for
from ..data import MISSIONS
from ..data_chests import CHEST_BLOCK, CHEST_FLAGS_SAVE, CHESTS_IN_MISSIONS, DLC_CHESTS
from ..data_koroks import (CHALLENGE_KOROK_BLOCK, KOROK_BLOCK, KOROK_FLAGS_SAVE, KOROK_SLOTS, KOROKS_IN_CHALLENGES,
                           KOROKS_IN_MISSIONS)
from ..data_save import SAVE_SIZE


class TestKorokAndChestChecks(AoCTestBase):
    options = {"korok_checks": True, "chest_checks": True, "challenge_checks": False, "quest_checks": False,
               "lab_checks": False, "include_dlc": False}

    def test_counts(self) -> None:
        names = self.location_names()
        self.assertEqual(sum(n.startswith("Korok Seed: ") for n in names), 122 + 12)  # challenge seeds too
        self.assertEqual(sum(n.startswith("Treasure Chest: ") for n in names), sum(CHESTS_IN_MISSIONS.values()))
        clears = sum(self.world.clear_checked(m.name) for m in MISSIONS)  # (no clear check on a goal Future of Hyrule)
        self.assertEqual(len(names), clears + 134 + 153)
        self.assertEqual(self.world.options.side_content.value, {"Korok Seeds", "Chests"})

    def test_need_their_mission(self) -> None:
        self.assertFalse(self.can_reach_location("Treasure Chest: The Future of Hyrule #1"))
        self.assertFalse(self.can_reach_location("Korok Seed: The Future of Hyrule #1"))
        self.assertFalse(self.can_reach_location("Korok Seed: Defend Hyrule Castle #1"))

    def test_runes_are_progression(self) -> None:  # no rune challenges here: the Koroks and chests alone need them
        runes = {i.name: i.advancement for i in self.multiworld.itempool if i.name.startswith("Rune: ")}
        self.assertTrue(all(runes[f"Rune: {r}"] for r in ("Remote Bombs", "Magnesis", "Stasis")))

    def test_slot_data(self) -> None:
        data = self.world.fill_slot_data()
        self.assertEqual(len(data["korok_ids"]), 134)
        self.assertEqual(len(data["chest_ids"]), 153)


class TestRuneLogic(AoCTestBase):
    """Koroks and chests that need a rune never hold it (shuffled runes)."""
    options = {"korok_checks": True, "chest_checks": True, "sheikah_runes": "shuffled", "include_dlc": False}

    def test_korok_needs_stasis(self) -> None:
        self.collect_all_but(["Rune: Stasis"])
        self.assertFalse(self.can_reach_location("Korok Seed: Revali, the Rito Warrior #1"))
        self.assertTrue(self.can_reach_location("Korok Seed: Mipha, the Zora Princess #1"))
        self.collect_by_name("Rune: Stasis")
        self.assertTrue(self.can_reach_location("Korok Seed: Revali, the Rito Warrior #1"))

    def test_chest_needs_magnesis(self) -> None:
        self.collect_all_but(["Rune: Magnesis"])
        self.assertFalse(self.can_reach_location("Treasure Chest: Mipha, the Zora Princess #1"))
        self.assertTrue(self.can_reach_location("Korok Seed: Mipha, the Zora Princess #1"))
        self.collect_by_name("Rune: Magnesis")
        self.assertTrue(self.can_reach_location("Treasure Chest: Mipha, the Zora Princess #1"))

    def test_chest_needs_bombs(self) -> None:
        self.collect_all_but(["Rune: Remote Bombs"])
        self.assertFalse(self.can_reach_location("Treasure Chest: Calamity Strikes #1"))
        self.assertTrue(self.can_reach_location("Treasure Chest: Mipha, the Zora Princess #1"))


class TestProgressionReachesAll(AoCTestBase):
    """The accessibility check of a real generation: progression items alone reach every Korok and chest (0.9.90 seed
    12874845118034458530 had its runes as useful items: no challenges, so 'no rune needed')."""
    options = {"game_mode": "story_only", "korok_checks": True, "chest_checks": True, "include_dlc": True,
               "sheikah_runes": "shuffled"}

    def test_progression_reaches_everything(self) -> None:
        from BaseClasses import CollectionState
        state = CollectionState(self.multiworld)
        for item in self.multiworld.itempool + list(self.multiworld.precollected_items[self.player]):
            if item.advancement:
                state.collect(item, True)
        state.sweep_for_advancements()
        missing = [loc.name for loc in self.multiworld.get_locations(self.player) if not loc.can_reach(state)]
        self.assertEqual(missing, [])


class TestFinalMissionFiller(AoCTestBase):
    """final_mission_goal: The Future of Hyrule's clear wins, so its Koroks and chests only come after the goal and
    hold filler only (user, 2026-11-18; pacing.exclude_post_goal)."""
    options = {"korok_checks": True, "chest_checks": True, "final_mission_goal": True, "goal_story_missions": 3,
               "include_dlc": False}

    def test_future_of_hyrule_checks_are_excluded(self) -> None:
        from BaseClasses import LocationProgressType
        names = [n for n in self.location_names()
                 if n.startswith(("Korok Seed: The Future of Hyrule", "Treasure Chest: The Future of Hyrule"))]
        self.assertEqual(len(names), 3 + 8)
        for name in names:
            self.assertEqual(self.world.get_location(name).progress_type, LocationProgressType.EXCLUDED, name)

    def test_goal_mission_clear_holds_no_check(self) -> None:  # (user: its clear is the win)
        names = self.location_names()
        self.assertNotIn("Clear: The Future of Hyrule", names)
        self.assertFalse([n for n in names if n.startswith("Clear: The Future of Hyrule")])
        self.assertIn("Clear: Akkala Tower", names)


class TestVanillaRuneLogic(AoCTestBase):
    options = {"chest_checks": True, "sheikah_runes": "vanilla", "include_dlc": False, "mission_unlocks": "items",
               "first_mission": "vanilla"}

    def test_chest_needs_rune_mission(self) -> None:
        from ..rules import rune_needs  # vanilla runes come from Hyrule Field (Bombs, Cryonis) and the Road (Magnesis, Stasis)
        self.assertEqual(rune_needs(self.world, ["Magnesis", "Remote Bombs"]),
                         ["Cleared: Road to the Ancient Lab", "Cleared: The Battle of Hyrule Field"])


class TestDlcChests(AoCTestBase):
    options = {"chest_checks": True, "include_dlc": True}

    def test_dlc_chests(self) -> None:
        names = {n for n in self.location_names() if n.startswith("Treasure Chest: EX ")}
        self.assertEqual(len(names), sum(len(s) for _, s in DLC_CHESTS.values()))
        self.assertIn("Treasure Chest: EX To Zelda's Side #6", names)
        self.assertNotIn("Treasure Chest: EX To Zelda's Side #7", names)


class TestOnByDefault(AoCTestBase):  # (0.9.90, user: on by default)
    def test_korok_and_chest_checks(self) -> None:
        names = self.location_names()
        self.assertTrue(any(n.startswith("Korok Seed: ") for n in names))
        self.assertTrue(any(n.startswith("Treasure Chest: ") for n in names))


class TestTurnedOff(AoCTestBase):
    options = {"korok_checks": False, "chest_checks": False}

    def test_no_korok_or_chest_checks(self) -> None:
        self.assertFalse({n for n in self.location_names() if n.startswith(("Korok Seed: ", "Treasure Chest: "))})


class SaveReaderTests(unittest.TestCase):
    def test_hyrule_field_pickups(self) -> None:
        # what the 2026-11-18 Hyrule Field run left in the save: Koroks in slots 0, 4, 6; chests 1, 2, 4
        data = bytearray(SAVE_SIZE)
        for slot in (0, 4, 6):
            data[KOROK_FLAGS_SAVE + slot] = 1
        for slot in (1, 2, 4):
            data[CHEST_FLAGS_SAVE + slot] = 1
        data[KOROK_FLAGS_SAVE + KOROK_BLOCK + 4] = 1  # Road to the Ancient Lab: slot 4 holds no seed
        hf = "The Battle of Hyrule Field"
        self.assertEqual(savefile.found_koroks(bytes(data)), {f"Korok Seed: {hf} #1", f"Korok Seed: {hf} #5", f"Korok Seed: {hf} #7"})
        self.assertEqual(savefile.opened_chests(bytes(data)), {f"Treasure Chest: {hf} #2", f"Treasure Chest: {hf} #3", f"Treasure Chest: {hf} #5"})
        data[CHEST_FLAGS_SAVE + 19 * CHEST_BLOCK + 7] = 1
        self.assertIn("Treasure Chest: The Future of Hyrule #8", savefile.opened_chests(bytes(data)))
        # challenge seeds (block 20, found 2026-11-18): slot 5 = Elemental Uproar's second, 11 = Defend Hyrule Castle
        data[KOROK_FLAGS_SAVE + CHALLENGE_KOROK_BLOCK * KOROK_BLOCK + 5] = 1
        data[KOROK_FLAGS_SAVE + CHALLENGE_KOROK_BLOCK * KOROK_BLOCK + 11] = 1
        self.assertTrue({"Korok Seed: Elemental Uproar #2", "Korok Seed: Defend Hyrule Castle #1"} <= savefile.found_koroks(bytes(data)))
        # Expansion Pass chests: block 20 slot 6 is EX To Zelda's Side's sixth chest (slot 4 holds none)
        data[CHEST_FLAGS_SAVE + 20 * CHEST_BLOCK + 6] = 1
        data[CHEST_FLAGS_SAVE + 20 * CHEST_BLOCK + 4] = 1
        opened = savefile.opened_chests(bytes(data))
        self.assertIn("Treasure Chest: EX To Zelda's Side #6", opened)
        self.assertNotIn("Treasure Chest: EX To Zelda's Side #5", opened)

    def test_messages(self) -> None:
        self.assertEqual(message_for("Korok Seed: Akkala Tower #2")["type"], "korok_found")
        self.assertEqual(message_for("Treasure Chest: Akkala Tower #2")["type"], "chest_opened")

    def test_slots_fit_blocks(self) -> None:
        self.assertTrue(all(max(s) < KOROK_BLOCK for s in KOROK_SLOTS.values()))
        self.assertTrue(all(n <= CHEST_BLOCK for n in CHESTS_IN_MISSIONS.values()))


def _unreachable(test: AoCTestBase) -> list[str]:
    """Locations progression items alone can't reach (a real generation's accessibility check)."""
    from BaseClasses import CollectionState
    state = CollectionState(test.multiworld)
    for item in test.multiworld.itempool + list(test.multiworld.precollected_items[test.player]):
        if item.advancement:
            state.collect(item, True)
    state.sweep_for_advancements()
    return [loc.name for loc in test.multiworld.get_locations(test.player) if not loc.can_reach(state)]


class TestStoryOnlyStoryOrder(AoCTestBase):
    """Story Only, each clear opening the next: the story's seeds and chests, no challenge seeds (no challenges)."""
    options = {"game_mode": "story_only", "mission_unlocks": "story_order", "korok_checks": True,
               "chest_checks": True, "include_dlc": True, "sheikah_runes": "vanilla"}

    def test_story_seeds_and_chests_only(self) -> None:
        names = self.location_names()
        koroks = [n for n in names if n.startswith("Korok Seed: ")]
        self.assertEqual(len(koroks), 122)
        self.assertFalse([n for n in koroks if n.rsplit(" #", 1)[0][len("Korok Seed: "):] in KOROKS_IN_CHALLENGES])
        chests = [n for n in names if n.startswith("Treasure Chest: ")]
        self.assertEqual(len(chests), sum(CHESTS_IN_MISSIONS.values()) + sum(len(s) for _, s in DLC_CHESTS.values()))
        self.assertEqual(_unreachable(self), [])


class TestChallengesOnly(AoCTestBase):
    """Challenges Only: the story is closed, so only the challenge seeds (and the Expansion Pass story's chests, which
    are challenges there) hold checks; each needs its challenge (and its unlock), and the runes it needs."""
    options = {"game_mode": "challenges_only", "korok_checks": True, "chest_checks": True, "include_dlc": True,
               "challenge_unlock_order": "items"}

    def test_only_challenge_content(self) -> None:
        names = self.location_names()
        koroks = {n for n in names if n.startswith("Korok Seed: ")}
        self.assertEqual(len(koroks), sum(KOROKS_IN_CHALLENGES.values()))
        self.assertIn("Korok Seed: Elemental Uproar #2", koroks)
        chests = {n for n in names if n.startswith("Treasure Chest: ")}
        self.assertEqual(chests, {n for n in chests if n.startswith("Treasure Chest: EX ")})
        self.assertEqual(len(chests), sum(len(s) for _, s in DLC_CHESTS.values()))
        self.assertEqual(_unreachable(self), [])

    def test_needs_the_challenge_and_rune(self) -> None:
        from BaseClasses import CollectionState
        from ..items import unlock_item
        from ..rules import challenge_event

        def reach(without: str, location: str) -> bool:  # (events are left out: they follow from the items)
            state = CollectionState(self.multiworld)
            self.collect_all_but([without] + [i.name for i in self.multiworld.get_items() if i.code is None], state)
            state.sweep_for_advancements()
            return self.multiworld.get_location(location, self.player).can_reach(state)

        locked = next(c for c in KOROKS_IN_CHALLENGES if c not in self.world.starting_challenge_unlocks)
        self.assertIn(challenge_event(locked), {i.name for i in self.multiworld.get_items()})
        self.assertFalse(reach(unlock_item(locked), f"Korok Seed: {locked} #1"))  # never behind its own unlock
        self.assertTrue(reach("Nothing", f"Korok Seed: {locked} #1"))
        self.assertFalse(reach("Rune: Remote Bombs", "Korok Seed: Defend Hyrule Castle #1"))  # a bomb-able wall


class TestChallengesOnlyNoDlc(AoCTestBase):
    options = {"game_mode": "challenges_only", "korok_checks": True, "chest_checks": True, "include_dlc": False}

    def test_no_chests_without_the_expansion(self) -> None:
        names = self.location_names()
        self.assertFalse([n for n in names if n.startswith("Treasure Chest: ")])
        self.assertEqual(sum(n.startswith("Korok Seed: ") for n in names), 12)
        self.assertEqual(_unreachable(self), [])
