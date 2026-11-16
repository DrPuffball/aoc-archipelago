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

Modes ("frame_rate" YAML option, client /fps): "30" (the game's own, untouched), "60", "120", "unlimited", "off"
(leave everything alone, e.g. for another frame-rate mod - which fights this one)."""
from __future__ import annotations

import threading
import time

MODES = ("60", "30", "off", "120", "unlimited")  # (option values: index)
CAPS = {"60": (60.0, 1), "120": (120.0, 1), "unlimited": (1000.0, 0)}  # float cap, present interval
VANILLA = (30, 2, 30, 30.0)
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
        self.mode = mode if mode in MODES else "60"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.fps_drawn: float | None = None
        self.frame_step = True  # the game mod's float frame step (set False for a game without the mod)
        # World map above 30: off - parts of the map animate once per drawn frame, so it ran fast (user, 2026-11-15)
        self.pace_map = False
        self.floor_steps, self.floor_float = 0, 0.25  # lowest whole / decimal step a frame gets above 60 FPS
        self.in_gameplay = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="AoC frame pacer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def set_mode(self, mode: str) -> None:
        self.mode = mode if mode in MODES else "60"

    def _run(self) -> None:
        game = None
        state = None  # what the block holds: "vanilla" / "paced"
        while not self._stop.is_set():
            try:
                if game is None:
                    game = self._factory()
                    if game is None:
                        time.sleep(1)
                        continue
                    state, base, last_tick, last_move = None, None, 0, 0.0
                    ledger, on_map, cur_steps = 0, False, 1
                mode = self.mode
                if mode == "off":
                    if state == "paced":
                        game.set_pacing(None)
                        state = "vanilla"
                    time.sleep(0.25)
                    continue
                now = time.perf_counter()
                in_mission = game.in_mission() if mode in CAPS and self.pace_map else True
                clock = game.battle_clock() if mode in CAPS and in_mission else None
                if mode in CAPS and not in_mission:
                    # World map (no mission running): no game clock to compare with, so keep a ledger of the
                    # steps handed out (each drawn frame advances the current step count) as the clock.
                    clock = ledger
                    last_move = now
                elif clock is not None and clock != last_tick:
                    if clock < last_tick:
                        base = None  # a restart reset the clock
                    last_tick, last_move = clock, now
                if (mode in CAPS and not in_mission) != on_map:
                    on_map, base = not on_map, None  # switched between map and mission: new reference
                playing = clock is not None and now - last_move < FROZEN_SECONDS
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
