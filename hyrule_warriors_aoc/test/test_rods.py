"""Elemental rod items (rod_items, 0.9.92): the three rods are items; the client holds a rod at 0 uses until it arrives."""
import json
import struct
import unittest

from . import test_basic as B
from ..data import RODS
from ..locations import lab_location


class TestRodItemsDefault(B.AoCTestBase):
    options = {"lab_checks": True, "include_dlc": True}

    def test_rods_in_pool(self) -> None:
        names = [i.name for i in self.multiworld.itempool if i.player == self.player]
        names += [i.name for i in self.multiworld.precollected_items[self.player]]
        for rod in RODS:
            self.assertEqual(names.count(rod), 1, rod)
        self.assertEqual(self.world.fill_slot_data()["rod_items"], 1)

    def test_client_locks_follow_items(self) -> None:
        from ..client.session import Session
        data = json.loads(json.dumps(self.world.fill_slot_data()))
        session = Session(data)
        self.assertEqual(session.rod_locks(), [True, True, True, False])  # (apples: apple_items is off by default)
        self.assertTrue(session.apply_received_item_names(["Ice Rod"]))
        self.assertEqual(session.rod_locks(), [True, False, True, False])
        data["rod_items"] = 0
        self.assertIsNone(Session(data).rod_locks())  # rods as in the game
        del data["rod_items"]
        self.assertIsNone(Session(data).rod_locks())  # seeds before 0.9.92

    def test_fire_rod_lab_node_needs_the_rod(self) -> None:
        if "An Apple a Day" not in self.world.checked_lab:
            self.skipTest("lab node not checked in this seed")
        from ..rules import lab_needs
        self.assertIn("Fire Rod", lab_needs(self.world, "An Apple a Day")[0])
        rods = [i for i in self.multiworld.itempool if i.player == self.player and i.name == "Fire Rod"]
        self.assertTrue(all(i.advancement for i in rods))
        loc = self.multiworld.get_location(lab_location("An Apple a Day"), self.player)
        if not rods:  # (handed out at the start: nothing to check)
            return
        state = self.multiworld.get_all_state(False)
        self.assertTrue(loc.can_reach(state))
        state.remove(rods[0])
        self.assertFalse(loc.can_reach(state))


class TestAppleItem(B.AoCTestBase):
    options = {"apple_items": True, "rod_items": False}

    def test_apples_in_pool_and_locked(self) -> None:
        from ..client.session import Session
        names = [i.name for i in self.multiworld.itempool if i.player == self.player]
        names += [i.name for i in self.multiworld.precollected_items[self.player]]
        self.assertEqual(names.count("Apples"), 1)
        self.assertFalse(set(names) & set(RODS))
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertEqual(session.rod_locks(), [False, False, False, True])
        session.apply_received_item_names(["Apples"])
        self.assertEqual(session.rod_locks(), [False, False, False, False])


class TestRodItemsOff(B.AoCTestBase):
    options = {"rod_items": False}

    def test_no_rods(self) -> None:
        names = {i.name for i in self.multiworld.itempool if i.player == self.player}
        self.assertFalse(names & set(RODS))
        self.assertEqual(self.world.fill_slot_data()["rod_items"], 0)
        from ..rules import lab_needs
        self.assertNotIn("Fire Rod", lab_needs(self.world, "An Apple a Day")[0])


class RodHookTests(unittest.TestCase):
    def test_hold_and_give_back(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        from .test_save import FakeGuest
        fake = FakeGuest()
        game = LiveGame(fake)
        self.assertEqual(game.hold_rods([True, True, True, False]), [])  # outside missions: nothing
        holder, player, char, pouch = (fake.base + 0x50000, fake.base + 0x51000, fake.base + 0x52000,
                                       fake.base + 0x54000)
        fake.put(H.BATTLE, struct.pack("<Q", holder))
        fake.put(holder + H.BATTLE_PLAYER, struct.pack("<Q", player))
        fake.put(player + H.BATTLE_CHARACTER, struct.pack("<Q", char))
        fake.put(char + H.CHAR_HP, struct.pack("<ff", 1945.8, 2000.0))
        fake.put(player + H.ROD_POUCH, struct.pack("<Q", pouch))
        apples = lambda: struct.unpack("<I", fake.read(pouch + H.ROD_USES + 0x1C, 4))[0]
        uses = lambda: struct.unpack("<3I", fake.read(pouch + H.ROD_USES, 12))
        fake.put(pouch + H.ROD_USES, struct.pack("<3I", 3, 3, 3))
        fake.put(pouch + H.ROD_USES + 0x1C, struct.pack("<I", 5))
        self.assertEqual(game.hold_rods([True, False, True, True]),
                         ["Fire Rod held", "Lightning Rod held", "Apples held"])
        self.assertEqual((uses(), apples()), ((0, 3, 0), 0))
        self.assertEqual(game.hold_rods([True, False, True, True]), [])  # held: no new writes
        fake.put(pouch + H.ROD_USES, struct.pack("<I", 1))  # a fire rod picked up: taken away again
        self.assertEqual(game.hold_rods([True, False, True, True]), ["Fire Rod held"])
        self.assertEqual(uses(), (0, 3, 0))
        self.assertEqual(game.hold_rods([False, False, True, False]), ["Fire Rod given back", "Apples given back"])
        self.assertEqual((uses(), apples()), ((3, 3, 0), 5))
        fake.put(pouch + H.ROD_USES, struct.pack("<3I", 0, 0, 0))
        self.assertEqual(game.hold_rods([False, False, False, False]), ["Lightning Rod given back"])
        self.assertEqual(uses()[2], 3)  # (from the uses it was held from)
        self.assertEqual(uses()[:2], (0, 0))  # rods used up by play stay used up
        fake.put(pouch + H.ROD_USES, struct.pack("<3I", 99, 99, 99))  # not rod counters: leave alone
        self.assertEqual(game.hold_rods([True, True, True, True]), [])


if __name__ == "__main__":
    unittest.main()


class RodFlagTests(unittest.TestCase):
    def test_flags_follow_items(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        from .test_save import FakeGuest
        fake = FakeGuest()
        game = LiveGame(fake)
        P = fake.base + 0x1000
        story = fake.base + 0x30000
        fake.put(P + H.STORY_FLAGS, struct.pack("<Q", story))
        for copy in (0, 0x1500):
            fake.put(story + copy + H.ROD_FLAGS, bytes([1, 1, 1]))  # all three picked up in game
            fake.put(story + copy + H.APPLE_FLAG, bytes([1]))
        self.assertEqual(game.set_rod_flags([True, False, False, None]), ["Ice Rod hidden", "Lightning Rod hidden"])
        for copy in (0, 0x1500):
            self.assertEqual(fake.read(story + copy + H.ROD_FLAGS, 3), bytes([1, 0, 0]))
            self.assertEqual(fake.read(story + copy + H.APPLE_FLAG, 1), bytes([1]))  # apples left alone (None)
        self.assertEqual(game.set_rod_flags([True, False, False, None]), [])
        self.assertEqual(game.set_rod_flags([True, True, False, False]), ["Ice Rod shown", "Apples hidden"])
        self.assertEqual(fake.read(story + H.ROD_START + 1, 1), bytes([2]))  # a fresh save's 0 uses -> 2
        self.assertEqual(fake.read(story + 0x1500 + H.ROD_START + 1, 1), bytes([2]))
        for copy in (0, 0x1500):
            self.assertEqual(fake.read(story + copy + H.APPLE_FLAG, 1), bytes([0]))
        self.assertEqual(game.set_rod_flags([True, True, False, True]), ["Apples shown"])
        for copy in (0, 0x1500):  # none carried (fresh save): 5 plain apples
            self.assertEqual(fake.read(story + copy + H.APPLE_TOTAL, 1), bytes([5]))
            self.assertEqual(fake.read(story + copy + H.APPLE_PLAIN, 1), bytes([5]))
        fake.put(story + H.ROD_FLAGS, bytes([7, 0, 0]))
        with self.assertRaises(H.HookError):
            game.set_rod_flags([True, True, True, True])
