"""Frame rate with constant game speed (user, 2026-11-15): 30, 60, 120 or unlimited FPS in gameplay, the game's own
30 in cutscenes, menus and on the world map, and the game always at real-time speed.

How the game times itself [measured on Eden 2026-11-15, tools/selftest/framecount.py, fpsprobe.py, pace.py]:
- frame-rate block main+0x26A2280: u32 fps, u32 steps, u32 fps, float cap. Each drawn frame advances the game by
  `steps` ticks of 1/60 s (30 FPS = 2 steps, 60 FPS = 1); the float caps frames drawn per second.
- the display's present interval: the graphics object's u32 at +0x2AA4 (2 = every second refresh; live_hook._gfx).
- so a fixed `steps` makes the game speed follow the frame rate (slow motion when the PC can't keep up).
The pacer fixes that from outside: a fast loop (every ~2 ms) compares the mission clock (60 ticks per real second)
with real time and sets `steps` for the next frame: 2 (or more) while the game is behind, 1 when on time, 0 when
ahead (frames above 60). Measured: 44-46 frames/s drawn at speed 1.000 where fixed 60 ran at 0.77.

Modes ("frame_rate" YAML option, client /fps): "60", "120", "unlimited", "off" (the game's own 30: the client leaves
everything alone, also for another frame-rate mod - which fights this one). 0.9.90 (user): "30" merged into "off";
an older seed's or setting's "30" means "off"."""
from __future__ import annotations

import threading
import time

MODES = ("60", "30", "off", "120", "unlimited")  # (option values: index; "30" only from older seeds = "off")


def normal_mode(mode: str | None) -> str:
    """A frame rate mode as the pacer uses it: "30" (older seeds and settings) is "off", unknown ones "60"."""
    return "off" if mode == "30" else mode if mode in MODES else "60"
CAPS = {"60": (60.0, 1), "120": (120.0, 1), "unlimited": (1000.0, 0)}  # float cap, present interval
VANILLA = (30, 2, 30, 30.0)
MENU_CAP = (60.0, 1)  # the pause menu (pace_cutscenes): one 1/60 s step per update
FROZEN_SECONDS = 0.3  # no game time for this long = cutscene, pause or loading
MAX_BEHIND = 30.0  # ticks (0.5 s): a longer stall (loading) is dropped instead of fast-forwarded


def fps_cheats(emulator: str | None = None) -> list[str]:
    """Installed cheat files (Eden load/<title>/<mod>/cheats, Ryujinx mods/contents/<title>/<mod>/cheats) that write
    the frame-rate block (cheat address 026A2280): they fight the client's frame rate control."""
    import glob
    import os
    from .savewatch import AOC_TITLE, eden_data_roots, ryujinx_data_roots
    pats = [os.path.join(r, "load", AOC_TITLE, "*", "cheats", "*.txt") for r in eden_data_roots()]         if emulator in (None, "Eden") else []
    if emulator in (None, "Ryujinx"):
        pats += [os.path.join(r, "mods", "contents", AOC_TITLE.lower(), "*", "cheats", "*.txt") for r in ryujinx_data_roots()]
    out = []
    for path in (p for pat in pats for p in glob.glob(pat)):
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                if "026A2280" in f.read().upper():
                    out.append(path)
        except OSError:
            continue
    return out


def steps_for(behind: float, cap: float, frame_ticks: float = 1.0) -> int:
    """Game steps for the next frame: what brings game time level with real time when that frame ends (`behind` =
    ticks owed now, `frame_ticks` = a frame's length in 1/60 s ticks). Never 0 at a 60 cap (that would only
    repeat a frame), at most 4 (one frame jumping further would look like a skip)."""
    want = int(behind + frame_ticks + 0.5)
    return max(0 if cap > 60 else 1, min(4, want))


class Pacer:
    """Runs the frame-rate loop on its own thread with its own game handle (live_hook.LiveGame)."""

    def __init__(self, game_factory, mode: str = "60") -> None:
        self._factory = game_factory
        self.mode = normal_mode(mode)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.fps_drawn: float | None = None
        self.frame_step = True  # the game mod's float frame step (set False for a game without the mod)
        # World map above 30: off - parts of the map animate once per drawn frame, so it ran fast (user, 2026-11-15)
        self.pace_map = False
        # Cutscenes (and the pause menu) above 30, experimental (user, 2026-11-18): the mission clock is frozen there, so
        # the ledger of handed-out steps stands in for it, as on the world map. Off = the game's own 30 there.
        self.pace_cutscenes = False
        self.floor_steps, self.floor_float = 0, 0.25  # lowest whole / decimal step a frame gets above 60 FPS
        self.in_gameplay = False
        self._reattach = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="AoC frame pacer", daemon=True)
        self._thread.start()

    def stop(self, wait: float = 0.0) -> None:
        """Stop pacing; the thread puts the game's own 30 FPS back on its way out. wait: seconds to let it finish
        (the client's shutdown waits, so closing the client always leaves the game at its own frame rate - the thread
        is a daemon, and the process used to exit before it got there: user 2026-11-21, fast pause-menu pings with the
        client closed)."""
        self._stop.set()
        thread = self._thread
        if wait and thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(wait)

    def reattach(self) -> None:
        """Drop the pacer's game handle and find the game again (called when the client's own hook reconnects). After
        a reload ("game state manager not set up") the old handle still reads, but frozen values: the pacer took the
        game for paused and stayed at 30 (seen 2026-11-18 on Eden, starting a mission)."""
        self._reattach = True

    def set_mode(self, mode: str) -> None:
        self.mode = normal_mode(mode)

    def _run(self) -> None:
        game = None
        state = None  # what the block holds: "vanilla" / "paced"
        while not self._stop.is_set():
            try:
                if self._reattach:
                    self._reattach, game = False, None
                    self.in_gameplay = False
                if game is None:
                    game = self._factory()
                    if game is None:
                        time.sleep(1)
                        continue
                    state, base, last_tick, last_move = None, None, 0, 0.0
                    ledger, on_map, cur_steps = 0, False, 1
                    mission_at, mission_now, menu_at = 0.0, True, 0.0
                    fc_last, fc_moved = None, 0.0
                    menu_rc, menu_t, menu_dt = None, 0.0, 1 / 45
                mode = self.mode
                if mode == "off":
                    if state == "paced":
                        game.set_pacing(None)
                        state = "vanilla"
                    time.sleep(0.25)
                    continue
                now = time.perf_counter()
                # Always checked (2026-11-19): the world map has a running battle clock of its own, so with
                # pace_map off the map used to be paced anyway (seen on Eden: block 60/1 on the map, default settings).
                if mode in CAPS:
                    if now - mission_at > 0.25:  # (a few reads: checked four times a second, not every frame)
                        mission_at, mission_now = now, game.in_mission()
                    in_mission = mission_now
                else:
                    in_mission = True
                clock = game.battle_clock() if mode in CAPS and in_mission else None
                if self.pace_cutscenes and mode in CAPS and in_mission and clock is None:
                    # The pause menu (user, 2026-11-18): a mission with no clock and no frame count at all, so there
                    # is nothing to pace by; the game is stopped anyway: keep the gameplay frame rate on screen.
                    self.in_gameplay = False
                    if state != "paced" or now - menu_at > 0.1:  # (the game rewrites the block in menus)
                        # At most 60 here: the menu is cheap to draw, so above that its loop spun far faster than
                        # frames were shown (2026-11-19, unlimited: ~363 updates/s, 60 shown) and everything that
                        # moves by whole steps per update - the minimap ping on the pause map - ran ~6x fast.
                        cap, present = MENU_CAP if CAPS[mode][0] > MENU_CAP[0] else CAPS[mode]
                        game.set_pacing(cap, present)
                        state, menu_at = "paced", now
                    # The menu layouts' dt follows the frame step: measure the real frame length with the render
                    # counter (the gameplay frame counter stops in the pause menu) so menu animations run at speed.
                    rc = game.render_count()
                    if rc is not None and rc != menu_rc:
                        if menu_rc is not None:
                            frames = max(1, min(8, rc - menu_rc))
                            menu_dt += 0.2 * (min(0.1, (now - menu_t) / frames) - menu_dt)
                        menu_rc, menu_t = rc, now
                    game.set_frame_step(max(0.25, min(4.0, menu_dt * 60)))
                    base = None
                    time.sleep(0.004)
                    continue
                if mode in CAPS and not in_mission and self.pace_map:
                    # World map (no mission running): no game clock to compare with, so keep a ledger of the
                    # steps handed out (each drawn frame advances the current step count) as the clock.
                    clock = ledger
                    last_move = now
                elif clock is not None and clock != last_tick:
                    if clock < last_tick:
                        base = None  # a restart reset the clock
                    last_tick, last_move = clock, now
                # Story cutscenes (in-engine, 2026-11-19): the clock stays readable (stopped) and the gameplay frame
                # counter stops too, while frames are still drawn. They advance a fixed amount per drawn frame (timed
                # at forced 60/1 vs 30/2: ~2x further at 60), so they get the game's own 30 even with pace_cutscenes.
                # Divine Beast attacks and a mission's opening scene keep the frame counter running and follow game
                # time (opening scene: 9.4 s at both 30 and 60): those stay paced.
                fc = game.frame_count() if mode in CAPS and in_mission and clock is not None else None
                if fc != fc_last:
                    fc_last, fc_moved = fc, now
                story = fc is not None and now - fc_moved >= FROZEN_SECONDS
                # Clock stopped but gameplay frames still counted: Divine Beast and special attacks and a mission's last
                # ~10 s follow game time, but in-engine story cutscenes look the same here and advance once per drawn
                # frame: paced, they ran at double speed (user 2026-11-21, 0.9.92 test run). So this state gets the
                # game's own 30 again (as in 0.9.89; pacing it by default lasted 2026-11-19..21). The frame-counter
                # check (`story`) did not catch those cutscenes.
                cutscene = False
                use_ledger = (mode in CAPS and not in_mission and self.pace_map) or cutscene
                if use_ledger != on_map:
                    on_map, base = use_ledger, None  # switched between ledger and mission clock: new reference
                playing = clock is not None and not story and (cutscene or now - last_move < FROZEN_SECONDS)
                if not playing:
                    self.in_gameplay = False
                    if state != "vanilla":
                        game.set_pacing(None)
                        state = "vanilla"
                    base = None
                    time.sleep(0.02)
                    continue
                cap, present = CAPS[mode]
                if state != "paced":
                    game.set_pacing(cap, present)
                    state = "paced"
                    frame_dt, last_frame, last_count = 1 / 45, now, None
                    fbase, fsum, fstep, fcount = None, 0.0, 1.0, None
                    last_present = now
                self.in_gameplay = True
                if base is None:
                    base = (now, clock)
                count = game.frame_count()
                if count is not None and count == last_count:
                    time.sleep(0.001)
                    continue  # still the same frame: its steps are set already
                if count is not None:  # a new frame started: measure frame length, set the steps of the next one
                    if last_count is not None:
                        ledger += cur_steps * max(0, min(8, count - last_count))
                        frame_dt += 0.2 * (min(0.1, (now - last_frame) / max(1, count - last_count)) - frame_dt)
                    last_frame, last_count = now, count
                if on_map:
                    clock = ledger
                behind = (now - base[0]) * 60 - (clock - base[1])
                if behind > MAX_BEHIND or behind < -MAX_BEHIND:  # a long stall: start counting from here
                    base, behind = (now, clock), 0.0
                if now - last_present > 0.5:  # the game may set the display back to every second refresh
                    game.set_present(present)
                    last_present = now
                cur_steps = max(self.floor_steps, steps_for(behind, cap, frame_dt * 60))
                game.set_steps(cur_steps)
                if self.frame_step:  # game mod: movement and timers scale by the real frame length, kept level
                    # with real time: a ledger of the frame steps handed out (each drawn frame used the last one)
                    if fbase is None or count is None:
                        fbase, fsum = now, 0.0
                    elif fcount is not None and count != fcount:
                        fsum += fstep * max(0, min(8, count - fcount))
                    fcount = count
                    fowed = (now - fbase) * 60 - fsum
                    if abs(fowed) > MAX_BEHIND:
                        fbase, fsum, fowed = now, 0.0, 0.0
                    fstep = max(self.floor_float if cap > 60 else 1.0, min(4.0, frame_dt * 60 + 0.5 * fowed))
                    game.set_frame_step(fstep)
                    # frame-rate float = just above the rate reached (the limiter stays out of the way, and the
                    # effect/UI timers that take 1/fps as a frame's length stay within a few percent of real)
                    game.set_frame_cap(min(cap, max(30.0, 1.0 / max(frame_dt, 1e-3) * 1.06 + 2)))
                time.sleep(0.001)
            except Exception:  # noqa: BLE001 - game closed or memory moved: reattach
                game = None
                time.sleep(1)
        if game is not None and state == "paced":
            try:
                game.set_pacing(None)
            except Exception:  # noqa: BLE001
                pass
