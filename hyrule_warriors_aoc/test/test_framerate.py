"""Frame rate with constant game speed (client/framerate.py, user 2026-11-15)."""
import time
import unittest

from ..client.framerate import MODES, Pacer, steps_for


class FakeGame:
    """Simulated game: draws `fps` frames a second, each advancing `steps` ticks of 1/60 s."""

    def __init__(self, fps: float) -> None:
        self.fps, self.steps, self.clock, self.pacing = fps, 2, 0.0, None
        self.t = time.perf_counter()
        self.frames, self.gameplay_frames = 0.0, 0
        self.playing = True
        self.cutscene = False
        self.paused = False  # the pause menu: in the mission, but no clock
        self.story = False  # an in-engine story cutscene: clock stopped, gameplay frame counter stopped too

    def _advance(self) -> None:
        now = time.perf_counter()
        n_frames = (now - self.t) * self.fps
        whole = int(self.frames + n_frames) - int(self.frames)
        if not self.cutscene and not self.story:
            self.clock += whole * self.steps
        if not self.story:
            self.gameplay_frames += whole
        self.frames += n_frames
        self.t = now

    def battle_clock(self):
        self._advance()
        return int(self.clock) if self.playing and not self.paused else None

    def frame_count(self):
        self._advance()
        return None if self.paused else self.gameplay_frames  # (stops in the pause menu / story scenes)

    def render_count(self):
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

    def test_stop_with_wait_restores_the_game_before_returning(self) -> None:  # (client close: user 2026-11-21)
        game = FakeGame(45)
        pacer = Pacer(lambda: game, "unlimited")
        pacer.start()
        time.sleep(0.5)
        self.assertIsNotNone(game.pacing)
        pacer.stop(wait=2.0)  # no sleep after: the game must be back at its own 30 already
        self.assertIsNone(game.pacing)
        self.assertFalse(pacer._thread.is_alive())

    def test_frozen_clock_with_frames_stays_paced_and_the_map_is_paced(self) -> None:
        game = FakeGame(60)
        pacer = Pacer(lambda: game, "120")
        pacer.pace_map = True
        pacer.start()
        time.sleep(0.3)
        self.assertEqual(game.pacing, 120.0)
        game.cutscene = True  # game time stops, frames still counted: the game's own 30 (in-engine cutscenes ran
        time.sleep(0.6)       # at double speed paced, user 2026-11-21)
        self.assertIsNone(game.pacing)
        game.story = True  # a story cutscene (frame counter stops too): the game's own 30
        time.sleep(0.6)
        self.assertIsNone(game.pacing)
        game.story = False
        game.cutscene, game.playing = False, False  # the world map: paced by the ledger
        time.sleep(0.3)
        self.assertEqual(game.pacing, 120.0)
        pacer.stop()

    def test_cutscenes_paced_when_asked(self) -> None:  # /fps_cutscenes on (experimental, user 2026-11-18)
        game = FakeGame(60)
        pacer = Pacer(lambda: game, "120")
        pacer.pace_cutscenes = True
        pacer.start()
        time.sleep(0.3)
        game.cutscene = True
        time.sleep(0.6)
        self.assertIsNone(game.pacing)  # clock stopped, frames counted: the game's own 30 (in-engine cutscenes, 2026-11-21)
        game.cutscene = False
        time.sleep(0.3)
        self.assertEqual(game.pacing, 120.0)
        pacer.stop()

    def test_story_cutscenes_get_30_even_with_cutscene_pacing(self) -> None:
        # (2026-11-19: story cutscenes advance per drawn frame - ~2x speed at 60; the gameplay frame counter stops there)
        game = FakeGame(60)
        pacer = Pacer(lambda: game, "60")
        pacer.pace_cutscenes = True
        pacer.start()
        time.sleep(0.3)
        game.story = True
        time.sleep(0.6)
        self.assertIsNone(game.pacing)  # the game's own 30
        game.story = False  # back in play
        time.sleep(0.3)
        self.assertEqual(game.pacing, 60.0)
        game.cutscene = True  # clock stopped, frames still counted: the game's own 30 too (2026-11-21)
        time.sleep(0.6)
        self.assertIsNone(game.pacing)
        pacer.stop()

    def test_pause_menu_capped_at_60_above_it(self) -> None:  # (unlimited: the menu loop spun ~6x fast)
        game = FakeGame(60)
        pacer = Pacer(lambda: game, "unlimited")
        pacer.pace_cutscenes = True
        pacer.start()
        time.sleep(0.3)
        game.paused = True
        time.sleep(0.5)
        self.assertEqual(game.pacing, 60.0)
        pacer.stop()

    def test_pause_menu_paced_with_cutscenes(self) -> None:  # (user: the pause menu dropped to 30)
        game = FakeGame(60)
        pacer = Pacer(lambda: game, "60")
        pacer.pace_cutscenes = True
        pacer.start()
        time.sleep(0.3)
        game.paused = True  # no clock at all, still in the mission
        time.sleep(0.5)
        self.assertEqual(game.pacing, 60.0)
        self.assertAlmostEqual(game.step_float, 1.0, delta=0.15)  # 60 frames drawn: one 1/60 s tick each (UI timing)
        game.paused, game.playing = False, False  # the world map, pace_map off: the game's own 30
        time.sleep(0.6)
        self.assertIsNone(game.pacing)
        pacer.stop()

    def test_reattach_finds_the_game_again(self) -> None:  # (a reload left a stale handle: stuck at 30)
        games = [FakeGame(60), FakeGame(60)]
        found = []
        pacer = Pacer(lambda: found.append(1) or games[min(len(found), 2) - 1], "60")
        pacer.start()
        time.sleep(0.3)
        pacer.reattach()
        time.sleep(0.3)
        pacer.stop(); time.sleep(0.1)
        self.assertEqual(len(found), 2)
        self.assertEqual(games[1].pacing, None)  # (stopped: the game's own 30 back on the new handle)

    def test_modes(self) -> None:
        self.assertEqual(MODES, ("60", "30", "off", "120", "unlimited"))  # = the frame_rate option's values
        self.assertEqual(Pacer(lambda: None, "auto").mode, "60")  # an older client's setting
        self.assertEqual(Pacer(lambda: None, "30").mode, "off")  # 0.9.90: 30 merged into off (older seeds/settings)
