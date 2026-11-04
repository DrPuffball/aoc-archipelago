"""Everything the world can hold or hand out has something in the client that handles it (2026-11-04)."""
import unittest

from ..client.delivery import CONSUMABLES
from ..client.session import LOCATION_KINDS, UPGRADE_NAMES, _reward_items
from ..data import ALL_CHARACTERS, FILLER_ITEMS, MISSIONS, WEAPONS
from ..data_challenges import CHALLENGES
from ..data_lab import LAB_ITEMS, LAB_NODES, LAB_WEAPON_ITEMS
from ..data_quests import QUESTS, UNUSED_QUESTS
from ..data_rewards import ALL_GROUPS, RESEARCH_BY_ITEM, RESEARCH_REWARDS, ROYAL_GIFTS
from ..data_save import HERO_SLOTS, MISSION_RECORD_IDS, QUEST_STATE_IDS, WEAPON_KINDS
from ..items import ITEM_NAME_TO_ID
from ..locations import LOCATION_NAME_TO_ID


class CoverageTests(unittest.TestCase):
    def test_every_story_mission_and_challenge_has_a_record(self) -> None:
        self.assertEqual([m.name for m in MISSIONS if m.name not in MISSION_RECORD_IDS], [])
        self.assertEqual([c.name for c in CHALLENGES if c.name not in MISSION_RECORD_IDS], [])

    def test_every_quest_has_a_state_byte(self) -> None:
        self.assertEqual([q.name for q in QUESTS if q.name not in QUEST_STATE_IDS and q.name not in UNUSED_QUESTS], [])

    def test_every_reward_group_quest_exists(self) -> None:
        for group in ALL_GROUPS.values():
            self.assertEqual([q for q in group.quests if q not in QUEST_STATE_IDS], [], group.item)
            if group.kind == "store":
                self.assertEqual(len(group.writes), len(group.quests), group.item)

    def test_every_weapon_and_hero_can_be_given(self) -> None:
        self.assertEqual([w.name for w in WEAPONS if w.name not in WEAPON_KINDS], [])
        self.assertEqual([c for c in ALL_CHARACTERS if c not in HERO_SLOTS], [])
        for item in [*LAB_WEAPON_ITEMS, *(f"Weapon: {w}" for w in ROYAL_GIFTS.values())]:
            self.assertIn(item, ITEM_NAME_TO_ID)

    def test_every_item_has_a_handler(self) -> None:
        rewards = _reward_items()
        prefixes = ("Character: ", "Weapon: ", "Rune: ", "Unlock: ", "Feature: ")
        unknown = [n for n in ITEM_NAME_TO_ID if not n.startswith(prefixes) and n not in FILLER_ITEMS and n not in rewards
                   and n not in UPGRADE_NAMES and n.partition(": ")[0] not in UPGRADE_NAMES]
        self.assertEqual(unknown, [])
        self.assertEqual([n for n in FILLER_ITEMS if n not in CONSUMABLES], [])
        self.assertTrue(set(LAB_ITEMS) <= rewards)
        self.assertTrue(set(RESEARCH_BY_ITEM) <= rewards)
        self.assertEqual(set(RESEARCH_BY_ITEM.values()), set(RESEARCH_REWARDS))

    def test_every_location_kind_reaches_the_client(self) -> None:
        self.assertIn("lab", LOCATION_KINDS)
        for n in LAB_NODES:
            self.assertIn(f"Lab: {n.name}", LOCATION_NAME_TO_ID)
        for q in QUESTS:
            self.assertIn(f"Quest: {q.name}", LOCATION_NAME_TO_ID)
        for c in CHALLENGES:
            self.assertIn(f"Challenge: {c.name}", LOCATION_NAME_TO_ID)
