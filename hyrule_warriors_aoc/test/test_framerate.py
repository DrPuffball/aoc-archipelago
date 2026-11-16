"""Frame rate with constant game speed (client/framerate.py, user 2026-11-15)."""
import time
import unittest

from ..client.framerate import MODES, Pacer, steps_for


class FakeGame:
    """Simulated game: draws `fps` frames a second, each advancing `steps` ticks of 1/60 s."""

    def __init__(self, fps: float) -> None:
        self.fps, self.steps, self.clock, self.pacing = fps, 2, 0.0, None
        self.t = time.perf_counter()
        self.frames = 0.0
        self.playing = True
        self.cutscene = False

    def _advance(self) -> None:
        now = time.perf_counter()
        n_frames = (now - self.t) * self.fps
        whole = int(self.frames + n_frames) - int(self.frames)
        if not self.cutscene:
            self.clock += whole * self.steps
        self.frames += n_frames
        self.t = now

    def battle_clock(self):
        self._advance()
        return int(self.clock) if self.playing else None

    def frame_count(self):
        self._advance()
        return int(self.frames)

    def set_frame_cap(self, fps):
        self.cap_now = fps

    def set_present(self, present):
        self.present = present

    def in_mission(self):
        return self.playing

    def set_frame_step(self, ticks):
        self.step_float = ticks

    def set_pacing(self, cap, present=1):
        self.pacing = cap
        self.steps = 2 if cap is None else 1

    def set_steps(self, steps):
        self._advance()
        self.steps = steps


class FrameRateTests(unittest.TestCase):
    def test_steps(self) -> None:
        self.assertEqual(steps_for(0.0, 60), 1)
        self.assertEqual(steps_for(1.0, 60), 2)
        self.assertEqual(steps_for(0.0, 60, 1.33), 1)
        self.assertEqual(steps_for(0.6, 60, 1.33), 2)
        self.assertEqual(steps_for(-1.0, 60), 1)  # 60 cap: never 0 steps
        self.assertEqual(steps_for(-1.0, 120), 0)
        self.assertEqual(steps_for(10.0, 60), 4)

    def test_game_speed_stays_real_time_at_45_fps(self) -> None:
        game = FakeGame(45)
        pacer = Pacer(lambda: game, "60")
        pacer.start()
        time.sleep(0.5)
        c0, t0 = game.battle_clock(), time.perf_counter()
        time.sleep(2.0)
        speed = (game.battle_clock() - c0) / (time.perf_counter() - t0) / 60
        pacer.stop(); time.sleep(0.1)
        self.assertAlmostEqual(speed, 1.0, delta=0.06)
        self.assertIsNone(game.pacing)  # stopped: the game's own 30 FPS back

    def test_cutscenes_get_the_games_own_30_and_the_map_is_paced(self) -> None:
        game = FakeGame(60)
        pacer = Pacer(lambda: game, "120")
        pacer.pace_map = True
        pacer.start()
        time.sleep(0.3)
        self.assertEqual(game.pacing, 120.0)
        game.cutscene = True  # game time stops in a mission: a cutscene
        time.sleep(0.6)
        self.assertIsNone(game.pacing)
        game.cutscene, game.playing = False, False  # the world map: paced by the ledger
        time.sleep(0.3)
        self.assertEqual(game.pacing, 120.0)
        pacer.stop()

    def test_modes(self) -> None:
        self.assertEqual(MODES, ("60", "30", "off", "120", "unlimited"))  # = the frame_rate option's values
        self.assertEqual(Pacer(lambda: None, "auto").mode, "60")  # an older client's setting
