"""
Passive research probe (read-only): learns where the game keeps the in-battle player state while you play normally,
so features that need it (Remote Bombs / Cryonis locks, DeathLink) can be built without a dedicated test session.

Older game builds keep a battle player object B = [[module global] + 0x30] with the rune charge at B+0x64, the active
character at [B+0x8] and rod/apple counts under [B+0x3C8] (public cheat codes for 1.2.0 / 1.3.0; RESEARCH session
13). The 1.4.1 global is unknown, so the probe looks for objects of that shape among the pointers in the module's
data, then logs how their small integer fields and the active character's float fields (HP) change while you play,
plus a whole snapshot of each candidate per minute with the Magnesis/Stasis state, so per-rune availability bits can be
matched (all four runes share one cooldown, so a cooldown can't lock a single rune). It never writes game memory. The log goes to %USERPROFILE%/AoC_Archipelago/probe/ and is capped in size.

Since the battle global (live_hook.BATTLE) and the real HP were found, the probe watches that object directly instead
of scanning the module's data for look-alikes, and adds two watchers for the client's own behaviour:
- mission flow state ([module + 0x2780A80] + 0xB0) transitions, logged as events (playing / defeated / retry / map),
  so soft-locks and research findings line up with what the game was doing;
- the client's own writes (live_hook.WRITE_JOURNAL): an address the client keeps rewriting means the game keeps
  changing it back ("fight", e.g. the world-map icon reveal that froze while the client re-locked something), and a
  one-off write the game has undone 20 s later is "reverted" (did a Weapon XP Gift or level write stick?).

Randomizer audit (0.9.53): every effect the client applies (live_hook.EXPECTATIONS: hero levels and stats, Weapon XP
Gift, rupees, materials, weapons given, heroes joining, side content opened) is re-checked 20 s later, 5 min later and
1 min after the next mission clear: findings "effect" (ok true / false / null = can't tell). The client also records
"check" (a location sent, with what in game sent it), "no_check" (done in game, no check in this seed), "received"
(an item and what the client did with it), "goal" and "deathlink". Failures are announced in the client log.

0.9.73 (user: improve the probe to learn how the game works):
- more of the save is watched (story flags, dyes and other blocks earlier surveys saw rewards in; optional, sized
  down until readable), for quest hand-ins and everything below;
- "state_change": save bytes that change on the map with no quest handed in (menu choices such as the difficulty,
  map reveals, unlock flags; size-capped so a save load doesn't count);
- "mission_start" / "mission_end": what changed between the map and the start of a battle (the difficulty and party
  chosen) and over the battle, with the map cursor's mission;
- "game_lost": the client's last writes and the mission state when the game went away (crash forensics).
"""

from __future__ import annotations

import collections
import json
import struct
import time
from pathlib import Path

from .ryujinx import MODULE_BASE

FIGHT_WINDOW, FIGHT_COUNT = 60.0, 5  # the client rewriting one address this often means the game undoes it
VERIFY_AFTER = 20.0  # seconds before a one-off client write is checked for having been undone
ONE_SHOT_WRITERS = {"kill_player", "_request_flow"}
# Gifts the player is free to use up (fuse or sell a weapon, spend rupees or materials): a later change is play, not
# the game undoing the client (user: a fused Extra Weapon was reported as undone).
PLAYER_USES = {"give_weapon", "add_rupees", "material_bundle", "hearty_meal", "_expect_material"}
EFFECT_STAGES = (("20s", 20.0), ("5min", 300.0))  # plus "after_mission": 60 s after the next mission clear
EFFECT_GIVE_UP = 3600.0  # an effect with no mission clear within an hour is dropped after its 5 min check

DATA_START, DATA_END = MODULE_BASE + 0x263E000, MODULE_BASE + 0x2D00000  # module .data/.bss
HEAP_LO, HEAP_HI = 0x10_0000_0000, 0x24_0000_0000
INTS = (0x40, 0x140)  # B fields watched as u32 (rune charge was B+0x64)
MAX_CANDIDATES = 40
SNAPSHOT = 0x400  # bytes of each candidate logged whole per discovery cycle
LOG_LIMIT = 20 << 20
REDISCOVER = 60.0


def _ptr(v: int) -> bool:
    return HEAP_LO <= v < HEAP_HI


class Probe:
    def __init__(self, guest, folder: Path) -> None:
        self.g = guest
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / time.strftime("probe_%Y%m%d_%H%M%S.jsonl")
        self.candidates: list[tuple[int, int]] = []  # (global address, B)
        self.last: dict[tuple[str, int], bytes] = {}
        self._next_discovery = 0.0
        self.enabled = True
        # Automatic watchers (findings.jsonl next to the log; announcements are printed by the client)
        self.findings = folder / "findings.jsonl"
        self.announcements: list[str] = []
        self._before: tuple[float, list[int] | None, bytes | None, bytes | None] | None = None
        self._after_due: tuple[float, dict] | None = None
        self._last_runes: list[int] | None = None
        self._last_hp: float | None = None
        self._records: bytes | None = None
        self._next_records = 0.0
        self._save_blocks: dict[str, bytes] | None = None  # quest states, profile, flag blocks, hero rows
        self._save_at = 0.0
        self._flow: int | None = None
        self._writes: dict[int, list[float]] = {}  # address -> recent client write times
        self._fought: dict[int, float] = {}  # address -> when last reported
        self._verify: list[tuple[float, int, bytes, str]] = []  # (due, address, written bytes, client function)
        self._effects: list[dict] = []  # pending effect checks (live_hook.EXPECTATIONS)
        self._recent_writes: collections.deque = collections.deque(maxlen=30)  # for game_lost
        self._in_battle = False
        self._map_blocks: dict[str, bytes] | None = None  # save blocks last seen on the map
        self._battle_blocks: dict[str, bytes] | None = None  # at the start of the current battle
        self._last_tick = 0.0

    def _log(self, record: dict) -> None:
        if self.path.exists() and self.path.stat().st_size > LOG_LIMIT:
            self.enabled = False
            return
        record["t"] = round(time.time(), 2)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")

    def _finding(self, record: dict, message: str) -> None:
        record["t"] = round(time.time(), 2)
        with open(self.findings, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
        self.announcements.append(message)

    def record(self, record: dict) -> None:
        """A finding the client reports (checks, items, goal, DeathLink); not announced."""
        record["t"] = round(time.time(), 2)
        with open(self.findings, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":"), default=str) + "\n")

    def watch_effects(self, mission_cleared: bool = False) -> None:
        """Re-check the client's effects at 20 s, 5 min and 1 min after the next mission clear."""
        from .live_hook import EXPECTATIONS
        now = time.time()
        while EXPECTATIONS:
            at, what, check, detail = EXPECTATIONS.popleft()
            self._effects.append({"at": at, "what": what, "check": check, "detail": detail, "done": set(),
                                  "mission_due": None})
        if mission_cleared:
            for e in self._effects:
                if e["mission_due"] is None:
                    e["mission_due"] = now + 60
        keep = []
        for e in self._effects:
            stages = [(name, e["at"] + delay) for name, delay in EFFECT_STAGES]
            if e["mission_due"] is not None:
                stages.append(("after_mission", e["mission_due"]))
            for name, due in stages:
                if name in e["done"] or now < due:
                    continue
                e["done"].add(name)
                try:
                    ok, shown = e["check"]()
                except Exception as ex:  # the game may be between screens
                    ok, shown = None, f"unreadable ({ex})"
                self.record({"finding": "effect", "what": e["what"], "stage": name, "ok": ok, "now": shown,
                             **e["detail"]})
                label = ", ".join(f"{k} {v}" for k, v in e["detail"].items() if k in ("hero", "weapon", "material"))
                if ok is False:
                    self.announcements.append(f"Audit: {e['what']} ({label}) was undone by the game ({name}): {shown}")
                elif name != "20s":
                    self.announcements.append(f"Audit: {e['what']} ({label}) still applied ({name}): {shown}")
            finished = "after_mission" in e["done"] or ("5min" in e["done"] and now - e["at"] > EFFECT_GIVE_UP)
            if not finished:
                keep.append(e)
        self._effects = keep[-500:]

    def _battle(self) -> tuple[int, int] | None:
        """(B, controlled character) via the battle global found on 2026-10-27 (live_hook.BATTLE)."""
        from .live_hook import BATTLE, BATTLE_CHARACTER, BATTLE_PLAYER
        def ptr(va: int) -> int:
            raw = self.g.read(va, 8)
            v = struct.unpack("<Q", raw)[0] if raw else 0
            return v if _ptr(v) else 0
        holder = ptr(BATTLE)
        B = ptr(holder + BATTLE_PLAYER) if holder else 0
        char = ptr(B + BATTLE_CHARACTER) if B else 0
        raw = self.g.read(char + 0x28, 8) if char else None  # HP, max HP: a stale object stays on the map (seen on
        if not raw:                                           # Eden 2026-11-02), as live_hook._battle_character checks
            return None
        hp, top = struct.unpack("<ff", raw)
        return (B, char) if 400 <= top <= 60000 and -1 <= hp <= top + 1 else None

    @staticmethod
    def _bytes_diff(old: bytes | None, new: bytes | None) -> list:
        if not old or not new:
            return []
        return [[hex(i), old[i], new[i]] for i in range(min(len(old), len(new))) if old[i] != new[i]][:200]

    def watch(self) -> None:
        """Rune switches (diff around a Magnesis/Stasis change), knock-outs (HP 0) and difficulty slots of clears."""
        now = time.time()
        runes = self.runes()
        battle = self._battle()
        if battle:
            B, char = battle
            if runes is not None and self._last_runes is not None and runes != self._last_runes and self._before:
                _, was, before_b, before_c = self._before
                after_b, after_c = self.g.read(B, SNAPSHOT), self.g.read(char, 0x800)
                record = {"finding": "runes", "from": was, "to": runes, "B": self._bytes_diff(before_b, after_b),
                          "char": self._bytes_diff(before_c, after_c)}
                self._finding(record, f"Research: rune state {was} -> {runes}, battle/character bytes recorded")
                self._after_due = (now + 5, {"from": was, "to": runes, "b": before_b, "c": before_c})
            if self._after_due and now >= self._after_due[0]:
                info = self._after_due[1]
                self._finding({"finding": "runes_later", "from": info["from"], "to": info["to"],
                               "B": self._bytes_diff(info["b"], self.g.read(B, SNAPSHOT)),
                               "char": self._bytes_diff(info["c"], self.g.read(char, 0x800))},
                              "Research: rune follow-up recorded")
                self._after_due = None
            if not self._before or now - self._before[0] > 5:
                self._before = (now, runes, self.g.read(B, SNAPSHOT), self.g.read(char, 0x800))
            raw = self.g.read(char + 0x28, 8)
            if raw:
                hp, top = struct.unpack("<ff", raw)
                if hp <= 0 < (self._last_hp or 0) and top >= 400:
                    self._finding({"finding": "ko", "max_hp": top}, "Research: knock-out seen (HP reached 0)")
                self._last_hp = hp
        else:
            self._before = None
            self._last_hp = None
        self._last_runes = runes
        if now >= self._next_records:
            self._next_records = now + 10
            self.watch_effects(self._watch_records())
        else:
            self.watch_effects()
        if now >= self._save_at:
            self._save_at = now + 2
            self._watch_save()

    def _watch_records(self) -> bool:
        """Which difficulty slot a new clear lands in (6 u32 times per mission record). Returns True on a new clear."""
        from .. import data_save as S
        from .live_hook import DIFFICULTY_TIMES, MANAGER, MISSIONS
        raw = self.g.read(MANAGER, 8)
        P = struct.unpack("<Q", raw)[0] if raw else 0
        raw = self.g.read(P + MISSIONS[0], 8) if _ptr(P) else None
        table = struct.unpack("<Q", raw)[0] if raw else 0
        blob = self.g.read(table + MISSIONS[1], S.MISSION_RECORD_COUNT * MISSIONS[2]) if _ptr(table) else None
        if not blob:
            return False
        old, self._records = self._records, blob
        if old is None or len(old) != len(blob):
            return False
        cleared = False
        names = {r: n for n, ids in S.MISSION_RECORD_IDS.items() for r in ids}
        for r in range(1, S.MISSION_RECORD_COUNT):
            a = struct.unpack_from("<6I", old, r * MISSIONS[2] + DIFFICULTY_TIMES)
            b = struct.unpack_from("<6I", blob, r * MISSIONS[2] + DIFFICULTY_TIMES)
            for slot in range(6):
                if b[slot] and not a[slot]:
                    cleared = True
                    self._finding({"finding": "clear_slot", "record": r, "mission": names.get(r), "slot": slot,
                                   "time": b[slot]}, f"Research: {names.get(r, r)} cleared in difficulty slot {slot}")
        return cleared

    # (field off the save manager, offset, length) of the save-backed blocks quest rewards and heroes live in
    SAVE_BLOCKS = {"quests": (0x560, 0x809, 1101), "profile": (0x588, 0, 4 * 0xC30), "flags": (0x5A0, 0, 0x33E0),
                   "research": (0x578, 0, 0xFA0), "heroes": (0x580, 0x224, 21 * 0x20)}
    # optional (0.9.73): blocks earlier surveys saw quest rewards in; read at the largest size that works
    EXTRA_BLOCKS = {"story": (0x550, 0, 0x1800), "dyes": (0x570, 0, 0x3000), "states": (0x5A8, 0, 0x800),
                    "p5d8": (0x5D8, 0, 0x400)}
    # rupees and materials (spent and found all the time), in each of the profile's four copies (stride 0xC30)
    NOISE = {"profile": tuple(r for k in range(4) for r in ((0x1E8 + k * 0xC30, 0x1EC + k * 0xC30),
                                                          (0x3E4 + k * 0xC30, 0x3E4 + 2 * 200 + k * 0xC30)))}

    def _read_save_blocks(self) -> dict[str, bytes] | None:
        from .live_hook import MANAGER
        raw = self.g.read(MANAGER, 8)
        P = struct.unpack("<Q", raw)[0] if raw else 0
        if not _ptr(P):
            return None
        blocks = {}
        for name, (field, off, n) in self.SAVE_BLOCKS.items():
            raw = self.g.read(P + field, 8)
            base = struct.unpack("<Q", raw)[0] if raw else 0
            data = self.g.read(base + off, n) if _ptr(base) else None
            if not data:
                return None
            blocks[name] = data
        for name, (field, off, n) in self.EXTRA_BLOCKS.items():
            raw = self.g.read(P + field, 8)
            base = struct.unpack("<Q", raw)[0] if raw else 0
            while _ptr(base) and n >= 0x100:
                data = self.g.read(base + off, n)
                if data:
                    blocks[name] = data
                    break
                n //= 2
        return blocks

    def _diff_blocks(self, old: dict[str, bytes], new: dict[str, bytes], skip_noise: bool = False) -> dict[str, list]:
        """Changed bytes per block (all blocks but quest states and hero rows, which have their own findings)."""
        out = {}
        for name, data in new.items():
            if name in ("quests", "heroes") or name not in old:
                continue
            diff = self._bytes_diff(old[name], data)
            if skip_noise:
                ranges = self.NOISE.get(name, ())
                diff = [d for d in diff if not any(a <= int(d[0], 16) < b for a, b in ranges)]
            if diff:
                out[name] = diff
        return out

    def _map_cursor(self) -> list[int] | None:
        """The world-map cursor's (id, kind) as last highlighted ([P+0x5A8]+0x148 u16 id, +0x14A kind)."""
        from .live_hook import MANAGER
        raw = self.g.read(MANAGER, 8)
        P = struct.unpack("<Q", raw)[0] if raw else 0
        raw = self.g.read(P + 0x5A8, 8) if _ptr(P) else None
        block = struct.unpack("<Q", raw)[0] if raw else 0
        raw = self.g.read(block + 0x148, 4) if _ptr(block) else None
        return [struct.unpack_from("<H", raw)[0], raw[2]] if raw else None

    def game_lost(self, reason: str) -> None:
        """The connection to the game dropped: what the client last wrote and what the game was doing (crashes)."""
        self.record({"finding": "game_lost", "reason": reason, "flow": self._flow, "in_battle": self._in_battle,
                     "since_tick": round(time.time() - self._last_tick, 1) if self._last_tick else None,
                     "last_writes": list(self._recent_writes)})

    def _watch_save(self) -> None:
        """Quest hand-ins: which save bytes changed with each quest that turned done (reward addresses for every quest
        type, from normal play). Hero level-ups: the hero row before and after (stat growth per level)."""
        from .. import data_save as S
        new = self._read_save_blocks()
        old, self._save_blocks = self._save_blocks, new
        if not new or not old:
            return
        names = {i: n for n, i in S.QUEST_STATE_IDS.items()}
        done = [i for i in range(len(new["quests"])) if new["quests"][i] == 3 and old["quests"][i] != 3]
        if done and len(done) <= 3:  # a hand-in (not a save load)
            diffs = self._diff_blocks(old, new)
            for k in ("profile", "flags", "research"):
                diffs.setdefault(k, [])
            self._finding({"finding": "quest_done", "quests": [[i, names.get(i)] for i in done], **diffs},
                          f"Research: quest hand-in recorded ({', '.join(str(names.get(i, i)) for i in done)})")
        elif not done and not self._in_battle:
            changes = self._diff_blocks(old, new, skip_noise=True)
            count = sum(len(v) for v in changes.values())
            if 0 < count <= 60:  # (a save load or New Game changes far more)
                self.record({"finding": "state_change", "cursor": self._map_cursor(), "flow": self._flow, **changes})
        in_battle = self._battle() is not None
        if in_battle and not self._in_battle:  # a mission starts: what changed since the map (difficulty, party)
            self._battle_blocks = new
            changes = self._diff_blocks(self._map_blocks or old, new)
            self.record({"finding": "mission_start", "cursor": self._map_cursor(), "flow": self._flow, **changes})
        elif self._in_battle and not in_battle and self._battle_blocks:  # back on the map / results
            changes = self._diff_blocks(self._battle_blocks, new)
            self.record({"finding": "mission_end", "cursor": self._map_cursor(), "flow": self._flow,
                         **{k: v[:120] for k, v in changes.items()}})
        if not in_battle:
            self._map_blocks = new
        self._in_battle = in_battle
        for slot in range(21):
            a = old["heroes"][slot * 0x20:(slot + 1) * 0x20]
            b = new["heroes"][slot * 0x20:(slot + 1) * 0x20]
            if a[0x0E] != b[0x0E] and b[0x16]:
                self._finding({"finding": "level_up", "slot": slot, "before": a.hex(), "after": b.hex()},
                              f"Research: hero slot {slot} level {a[0x0E] + 1} -> {b[0x0E] + 1} recorded")

    def note(self, event: str) -> None:
        """Client events (clears, received items) for lining the log up with play."""
        if self.enabled:
            self._log({"event": event})

    def discover(self) -> None:
        """The battle object through its known global; candidates keep the old (global, B) shape for the log."""
        from .live_hook import BATTLE
        battle = self._battle()
        found = [(BATTLE, battle[0])] if battle else []
        if [c[1] for c in found] != [c[1] for c in self.candidates]:
            self.candidates = found
            self.last.clear()
            self._log({"candidates": [[hex(G), hex(B)] for G, B in found]})

    def discover_scan(self) -> None:
        """Old shape search over the module's data (kept for a future build whose global moved)."""
        found = []
        seen: set[int] = set()
        chunk = 1 << 20
        for start in range(DATA_START, DATA_END, chunk):
            data = self.g.read(start, chunk)
            if not data:
                continue
            for i in range(0, len(data) - 7, 8):
                v = struct.unpack_from("<Q", data, i)[0]
                if not _ptr(v) or v in seen:
                    continue
                seen.add(v)
                b = self.g.read(v + 0x30, 8)
                if not b:
                    continue
                B = struct.unpack("<Q", b)[0]
                if not _ptr(B):
                    continue
                head = self.g.read(B, 0x3D0)
                if not head:
                    continue
                if _ptr(struct.unpack_from("<Q", head, 0x8)[0]) and _ptr(struct.unpack_from("<Q", head, 0x3C8)[0]) \
                        and struct.unpack_from("<I", head, 0x64)[0] < 100000:
                    found.append((start + i, B))
                    if len(found) >= MAX_CANDIDATES:
                        break
            if len(found) >= MAX_CANDIDATES:
                break
        if [c[1] for c in found] != [c[1] for c in self.candidates]:
            self.candidates = found
            self.last.clear()
            self._log({"candidates": [[hex(G), hex(B)] for G, B in found]})

    def tick(self) -> None:
        if not self.enabled:
            return
        self._last_tick = time.time()
        self.watch()
        now = time.time()
        self.discover()  # three pointer reads: the battle object comes and goes with missions
        if now >= self._next_discovery:
            self._next_discovery = now + REDISCOVER
            self.snapshot()
        self.watch_flow()
        self.watch_writes()
        for G, B in self.candidates:
            ints = self.g.read(B + INTS[0], INTS[1] - INTS[0])
            self._diff("B", B, INTS[0], ints, "<I")

    def watch_flow(self) -> None:
        """Mission flow state transitions (low byte 0 playing, 4 defeated, 12 retry; other bytes: phase/menus)."""
        from .live_hook import FLOW_STATE, UNITS
        raw = self.g.read(UNITS, 8)
        flow = struct.unpack("<Q", raw)[0] if raw else 0
        raw = self.g.read(flow + FLOW_STATE, 4) if _ptr(flow) else None
        state = struct.unpack("<I", raw)[0] if raw else None
        if state != self._flow and state is not None:
            self._log({"flow": f"{state:08x}", "was": f"{self._flow:08x}" if self._flow is not None else None})
        self._flow = state

    def watch_writes(self) -> None:
        """Client writes the game keeps undoing ("fight") and one-off writes it undid ("reverted")."""
        from .live_hook import WRITE_JOURNAL
        now = time.time()
        while WRITE_JOURNAL:
            at, va, data, caller = WRITE_JOURNAL.popleft()
            self._recent_writes.append([round(at, 2), hex(va), data.hex(), caller])
            if caller in ONE_SHOT_WRITERS:
                continue  # DeathLink: the game is meant to change these right after
            times = [t for t in self._writes.get(va, []) if now - t < FIGHT_WINDOW] + [at]
            self._writes[va] = times
            if len(times) >= FIGHT_COUNT and now - self._fought.get(va, 0) > 600:
                self._fought[va] = now
                flow = f"{self._flow:08x}" if self._flow is not None else None
                self._finding({"finding": "fight", "address": hex(va), "writes": len(times), "value": data.hex(),
                               "by": caller, "flow": flow},
                              f"Research: the game keeps undoing a client write ({caller} at {va:#x}), recorded")
            elif len(times) == 1:
                self._verify.append((at + VERIFY_AFTER, va, data, caller))
        due = [v for v in self._verify if v[0] <= now]
        self._verify = [v for v in self._verify if v[0] > now][-500:]
        for _, va, data, caller in due:
            if len(self._writes.get(va, [])) > 1:
                continue  # written again since: a forced value, not a one-off
            now_bytes = self.g.read(va, len(data))
            if now_bytes is not None and now_bytes != data and caller in PLAYER_USES:
                self._log({"finding": "used", "address": hex(va), "wrote": data.hex(), "now": now_bytes.hex(), "by": caller})
            elif now_bytes is not None and now_bytes != data:
                self._finding({"finding": "reverted", "address": hex(va), "wrote": data.hex(), "now": now_bytes.hex(),
                               "by": caller}, f"Research: the game undid a client write ({caller} at {va:#x})")

    def runes(self) -> list[int] | None:
        """Magnesis and Stasis as the game has them now (story flags the client controls), for lining snapshots up
        with rune availability: the bits that follow these across missions are the per-rune switches, and Remote
        Bombs / Cryonis should sit next to them (all four runes share one cooldown, so that can't lock one rune)."""
        from .live_hook import MANAGER, RUNE_FLAGS, STORY_FLAGS, STORY_FLAGS_OFFSET
        raw = self.g.read(MANAGER, 8)
        P = struct.unpack("<Q", raw)[0] if raw else 0
        raw = self.g.read(P + STORY_FLAGS, 8) if _ptr(P) else None
        obj = struct.unpack("<Q", raw)[0] if raw else 0
        flags = self.g.read(obj + STORY_FLAGS_OFFSET, 0x10) if _ptr(obj) else None
        return [flags[RUNE_FLAGS["Magnesis"]], flags[RUNE_FLAGS["Stasis"]]] if flags else None

    def snapshot(self) -> None:
        """Whole battle-object candidates once per discovery cycle when they changed, with the rune state."""
        runes = self.runes()
        for G, B in self.candidates:
            data = self.g.read(B, SNAPSHOT)
            if data and self.last.get(("S", B)) != data:
                self.last[("S", B)] = data
                self._log({"snap": hex(B), "runes": runes, "data": data.hex()})
            raw = self.g.read(B + 0x8, 8)
            char = struct.unpack("<Q", raw)[0] if raw else 0
            cdata = self.g.read(char, 0x800) if _ptr(char) else None
            if cdata and self.last.get(("SC", char)) != cdata:
                self.last[("SC", char)] = cdata
                self._log({"snapc": hex(char), "runes": runes, "data": cdata.hex()})

    def _diff(self, kind: str, base: int, offset: int, data: bytes | None, fmt: str) -> None:
        if not data:
            return
        key = (kind, base)
        old = self.last.get(key)
        self.last[key] = data
        if old is None or old == data:
            return
        changes = []
        for i in range(0, len(data) - 3, 4):
            if data[i:i + 4] != old[i:i + 4]:
                a, b = struct.unpack_from(fmt, old, i)[0], struct.unpack_from(fmt, data, i)[0]
                if fmt == "<f" and not (0.5 < abs(b) < 1e6 or 0.5 < abs(a) < 1e6):
                    continue  # skip tiny/huge floats (positions, angles noise stays out of plausible HP range)
                changes.append([hex(offset + i), round(a, 3) if fmt == "<f" else a, round(b, 3) if fmt == "<f" else b])
        if changes and len(changes) <= 64:
            self._log({kind: hex(base), "ch": changes})
