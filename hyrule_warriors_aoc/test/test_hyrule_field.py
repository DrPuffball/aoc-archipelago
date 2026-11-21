"""Hyrule Field shuffled (0.9.90, user 2026-11-19; no option): The Battle of Hyrule Field as a normal mission. The game mod stops the
forced opening; the starter save leaves it uncleared with a clear time only in slot 5 (no difficulty uses it), which
keeps the game from loading the New Game opening (and hanging) while the client still sees it uncleared."""
import json
import struct
import unittest

from .test_basic import AoCTestBase
from .. import data_save as L
from ..client import starter_save as ST
from ..client.savefile import cleared_missions

HF = "The Battle of Hyrule Field"


def _times(data: bytes, record: int) -> tuple[int, ...]:
    return struct.unpack_from("<6I", data, L.MISSION_RECORDS + record * L.MISSION_RECORD_SIZE + 4)


class StarterSaveTests(unittest.TestCase):
    def test_uncleared_field_with_its_marker(self) -> None:
        data = ST.prepare(["Link"], ["Road to the Ancient Lab"], hf_playable=True)
        self.assertEqual(_times(data, L.HF_RECORD), (0, 0, 0, 0, 0, L.HF_MARKER_TIME))
        self.assertNotIn(HF, cleared_missions(data))  # the client ignores the marker slot
        for offset, locked in ST.STATE_LISTS:  # not opened: locked like any closed mission
            self.assertEqual(data[offset + L.HF_RECORD], locked)
        self.assertTrue(ST.is_fresh(data))

    def test_opened_when_it_is_a_starting_mission(self) -> None:
        data = ST.prepare(["Link"], [HF], hf_playable=True)
        for offset, _ in ST.STATE_LISTS:
            self.assertEqual(data[offset + L.HF_RECORD], 2)

    def test_older_seeds_keep_it_cleared(self) -> None:
        data = ST.prepare(["Link"], ["Road to the Ancient Lab"])
        self.assertIn(HF, cleared_missions(data))
        self.assertEqual(data[ST.STATE_LISTS[0][0] + L.HF_RECORD], 3)

    def test_a_real_clear_counts(self) -> None:
        data = bytearray(ST.prepare(["Link"], [HF], hf_playable=True))
        struct.pack_into("<I", data, L.MISSION_RECORDS + L.HF_RECORD * L.MISSION_RECORD_SIZE + 4, 400)  # Easy
        self.assertIn(HF, cleared_missions(bytes(data)))

    def test_marker_only_for_hyrule_field(self) -> None:
        self.assertEqual(L.clear_slots(L.HF_RECORD, (0, 0, 0, 0, 0, 9)), [0] * 6)
        self.assertEqual(L.clear_slots(2, (0, 0, 0, 0, 0, 9)), [0, 0, 0, 0, 0, 9])


class TestSlotDataAndClient(AoCTestBase):
    options = {"mission_unlocks": "items"}

    def test_client_opens_it_by_its_item(self) -> None:
        from ..client.session import Session
        from ..items import unlock_item
        s = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertTrue(s.hf_shuffled)
        if HF != self.world.mission_order[0] and HF not in self.world.starting_unlocks:
            self.assertNotIn(HF, s.available_missions())
            s.mission_unlocks.add(HF)
            s.unlocked_characters |= set(self.world.characters)
            self.assertIn(HF, s.available_missions())
        self.assertIsNotNone(unlock_item(HF))


class TestChallengesOnlyKeepsItPrecleared(AoCTestBase):
    options = {"game_mode": "challenges_only"}

    def test_not_shuffled(self) -> None:
        self.assertFalse(self.world.hf_shuffled)
