"""Goal guard (2026-11-15): another seed's finished save in the save slot must not complete this seed's goal."""
import json
import types

from test.bases import WorldTestBase

from ..client.ap_client import AoCContext
from ..client.savewatch import message_for
from ..client.session import Session
from ..data import MISSIONS


class GoalGuardTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"goal_story_missions": 5, "final_mission_goal": False}

    def _ctx(self):
        ctx = types.SimpleNamespace(session=Session(json.loads(json.dumps(self.world.fill_slot_data()))),
                                    checked_locations=set(), _held=[],
                                    overlay=types.SimpleNamespace(show=lambda *a: None))
        ctx.GUARD_CLEARS = AoCContext.GUARD_CLEARS
        return ctx

    def test_a_finished_save_is_held(self) -> None:
        ctx = self._ctx()
        batch = [message_for(m.name) for m in MISSIONS[:12]]  # a finished save: far past this seed's progress
        self.assertTrue(AoCContext._hold_batch(ctx, batch, "the save file", True))
        self.assertEqual(len(ctx._held), 12)
        self.assertFalse(ctx.session.cleared_missions)  # nothing counted yet
        self.assertTrue(AoCContext._hold_batch(ctx, [message_for(MISSIONS[13].name)], "the game", False))  # still held

    def test_normal_play_is_not_held(self) -> None:
        ctx = self._ctx()
        self.assertFalse(AoCContext._hold_batch(ctx, [message_for(MISSIONS[1].name)], "the game", True))
        self.assertFalse(AoCContext._hold_batch(ctx, [message_for(m.name) for m in MISSIONS[1:9]], "the game", False))
