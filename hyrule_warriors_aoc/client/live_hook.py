"""
The live game hook: reads clears from, and writes items and hero locks into, the running game (Ryujinx).

Live layout (guest addresses, found by following the game's own pointers; see tools/RESEARCH.md session 4):
  P        = [module + 0x2780A48]                 save/profile manager
  missions = [P + 0x598] + 0xE08 + id * 0xF4      same stats as the save's mission records, minus the first u32
  heroes   = [P + 0x580] + 0x224 + slot * 0x20    the game's current table (four copies 0x560 apart; copy 3 at +0x1244
             is the last-saved state, refreshed from copy 0 after missions). +0x0E level-1, +0x16..+0x18 flags
             that put the hero in the System > Characters gallery. They do NOT make a hero selectable for
             missions (confirmed in game); what does is not known yet.
  profile  = [P + 0x588]                          copy 0 (copy 3 is +3*0xC30): +0x1E8 rupees (u32), +0x3E4 materials
Everything here is checked before use; if anything looks wrong the hook detaches and touches nothing.
"""

from __future__ import annotations

import collections
import random
import re
import struct
import sys
import time

from .. import data_save as S
from ..data_chests import CHEST_BLOCK, CHEST_BLOCKS, CHEST_FLAGS_LIVE, chest_flags
from ..data_koroks import CHALLENGE_KOROK_BLOCK, KOROK_BLOCK, KOROK_FLAGS_LIVE, korok_flags
from .ryujinx import MODULE_BASE, FastmemGuest, Guest, Process, emulator_processes

MANAGER = MODULE_BASE + 0x2780A48
PARAMS = (MODULE_BASE + 0x2780A38, 0x698, 0x60)  # [[global]+0x698]+0x60 = mission parameter table (400 rows)
UNLOCKS = (MODULE_BASE + 0x2780A38, 0x308, 0x60)  # mission unlock table (which cleared missions open a mission)
# Quest unlock table (LinkData2 0086e814) in the same param holder: 1000 rows of 36 bytes after a 16-byte header,
# row = quest state id: +4 five u16 mission/challenge records, +14 five u16 quests it needs [read live 2026-10-28]
QUEST_UNLOCKS = (MODULE_BASE + 0x2780A38, 0x300, 0x60)
QUEST_ROW, QUEST_ROW_TYPE = 80, 0x1E  # quest table: rows of 80 bytes from +0x10, reward type at +0x1E
QUEST_TABLE_DISTANCE = 213168  # quest table - unlock table, seen on Eden 2026-11-04 (searched for when it doesn't fit)
LAB_STATES = (0x550, 0x4AE2)  # Royal Ancient Lab: node states
LAB_VISIBLE_FLAG = 0x1A0F  # [0x5A0]: the lab is on the map
WARDROBE_BLOCK, WARDROBE_COUNT, WARDROBE_LIST, WARDROBE_LIST_START = 0x570, 0x120, 0x1678, 5  # outfit list
WARDROBE_OUTFIT_FLAGS, WARDROBE_FIRST_OUTFIT, WARDROBE_SAVED_COPY = 0x32BA, 19, 0xA890
QUEST_UNLOCK_ROWS, QUEST_UNLOCK_SIZE = 1000, 36
# In-battle player state (found by the client's research probe, 2026-10-27): battle object B = [[module + 0x2B63708]
# + 0x30] (1.3.0 cheats used 0x2B5F708); [B + 0x8] = the character you control; its HP is a float at +0x28 and the
# maximum at +0x2C (400 per heart). B + 0x5C/+0x58 = shared rune cooldown remaining/max, B + 0x60 = rune in use.
BATTLE = MODULE_BASE + 0x2B63708
BATTLE_PLAYER, BATTLE_CHARACTER, CHAR_HP, CHAR_HP_MAX = 0x30, 0x8, 0x28, 0x2C
# That HP is a display copy the game refreshes. The real HP sits in the unit table the damage code reads (text 0x100c4):
# [[module + 0x2780A80] + 0x8] + 0x176E70 + unit * 0x6C, HP float at +0x44, max at +0x4C (+0x48 is another HP value
# that can differ, maybe the damage trail); the character's own
# +0x0 / +0x4 (unit index / kind) match the record's. Writing 0 there leaves you at 0 HP and the next hit KOs
# [confirmed in game 2026-10-27]. [module + 0x277DE3C] = number of unit records (140).
UNITS, UNITS_TABLE, UNIT_COUNT = MODULE_BASE + 0x2780A80, 0x8, MODULE_BASE + 0x277DE3C
# Elemental rods (data.RODS): uses left in this mission, u32 per rod at [B + 0x3C8] + 0x910 (Fire, Ice, Lightning). 0 =
# greyed out in the item palette, can't be used [confirmed on Eden 2026-11-19]. The start count per rod is in the story
# flag object's table B (save 0x140..), [P + 0x550] + 0x254 + rod.
ROD_POUCH, ROD_USES, ROD_START = 0x3C8, 0x910, 0x254
PALETTE_USES = (0x0, 0x4, 0x8, 0x1C)  # from ROD_USES: Fire, Ice, Lightning Rod, apples (data.PALETTE_ITEMS)
# Rod "obtained" flags (save 0x52F..0x531): [P+0x550] + 0x121 + rod (Fire, Ice, Lightning), saved copy + 0x1500. A rod
# whose flag is 0 when a mission loads has no slot in the item palette at all; the palette is built at mission load, so
# a change shows in the next mission [confirmed on Eden 2026-11-19: flags 1,1,0 -> Y and X only]. Found with a write-watch
# on the save image the game rebuilds at mission start (serializer text 0x9edbd0: object +0 .. +3 = save 0x52E ..).
ROD_FLAGS, ROD_FLAG_COPIES = 0x121, (0, 0x1500)
# Apples, same structure (S = [P+0x550]+0x120, saved copy S+0x1500; the save writer text 0x9edb44.. stores S+0..6, then
# +0x522, +0x524..+0x52A, +0x631 at save 0x52E..0x53D): S+0x631 = apples obtained (save 0x53D), S+0x522 = apples
# carried into a mission (save 0x535), S+0x524..+0x52A = per kind (save 0x536..0x53C; plain apples +0x526). The item
# palette's own check (text 0xd868bc) shows it only with a rod flag (S+1..3) or S+0x631 set; mission start (0x6e375c)
# loads the apple count from S+0x522. [read from the code 2026-11-19; the flag NOT yet confirmed in game]
APPLE_FLAG, APPLE_TOTAL, APPLE_PLAIN = 0x751, 0x642, 0x646
PALETTE_FLAGS = (ROD_FLAGS, ROD_FLAGS + 1, ROD_FLAGS + 2, APPLE_FLAG)  # data.PALETTE_ITEMS order
UNIT_RECORDS, UNIT_SIZE, UNIT_HP = 0x176E70, 0x6C, 0x44
# HP 0 alone never KOs (the game checks it only when a hit lands). The mission flow state is a u32 at
# [module + 0x2780A80] + 0xB0 (low byte: 0 = playing, 0x60 = pause menu [seen on Eden], 4 = defeated, 12 = defeat menu).
FLOW_STATE, FLOW_REQUEST = 0xB0, 0xB8
OPTIONS, DIFFICULTY_SETTING, OPTIONS_COPY = 0x5B0, 0x123, 0xE0  # game options block: difficulty (1 Easy .. 4 Very Hard)
FLOW_PLAYING = 0
FLOW_OVER = (4, 12)
FLOW_CLOCK = 0x128  # counts up during an attempt (60 per real second at full game speed); starts over on a restart [seen on Eden]
# Frame-rate block (main module, the address the common 60 FPS cheat writes): u32 fps, u32 swap interval, u32 fps,
# float fps. 30/2/30/30.0 default, 60/1/60/60.0 = 60 FPS. Read live: at 60 FPS on a machine that can't hold it the
# mission clock ran ~50 ticks/s (the game slows down); back at 30 it ran 60 [confirmed on Eden 2026-11-15].
FRAME_RATE_BLOCK = 0x26A2280
FRAME_COUNTER = 0x277DBA8  # u32, +1 per drawn frame
# World-map scene (2026-11-19, Eden; see REVERSE_ENGINEERING.md "World-map refresh"): [[[main+0x2780AA8]+0x48]+0x80],
# vtable at module offset 0x26CAF00. +0x134 current state, +0x138 requested state (a change runs the new state's entry
# code next frame). 0 = the pause menu is open, 1 = rebuild (what closing the menu does), 14 = idle on the map.
MAP_SCENE_ROOT, MAP_SCENE_PATH, MAP_SCENE_VTABLE = 0x2780AA8, (0x48, 0x80), 0x26CAF00
MAP_SCENE_STATE, MAP_IDLE, MAP_MENU, MAP_REBUILD = 0x134, 14, 0, 1
MAP_SCENE_TAB, MAP_TAB_MAP = 0x19C, 4  # open tab: 3 Services, 4 Map, 5 Chapters, 7 Quests
FRAME_STEP = 0x26A2290  # float, read by the game mod's frame-timing patch (96 sites)
UI_FRAME_DIVISOR = 0x26A2294  # float, the game mod's UI animation timing (text 0x18cd7c0): 1 / (30 * frame step)
RENDER_COUNTER = 0x27843F0  # u32, the "AllRender" profiling counter: +1 per drawn frame, also in the pause menu
# The display's present interval (1.4.1): the graphics object's u32 at +0x2AA4 (2 = every second refresh = 30 FPS on
# screen), passed to nvnWindowSetPresentInterval each frame (text 0x17D13E8 -> 0x9260). The block alone only changes
# how often the game updates, which is why the old 60 FPS cheats stopped working; block 60/1 + present interval 1 =
# real 60 FPS [confirmed on Eden 2026-11-15: Eden showed 60 FPS / 16.66 ms, frame counters 59/s]. Paths from module
# globals to the graphics object (two, checked against each other):
GFX_PATHS = ((0x276FD98, 0x1898), (0x2784100, 0x2F0))
GFX_PRESENT_INTERVAL = 0x2AA4
# (Party heroes: character objects 0x6D0 apart, +0x0 = party index. A benched hero's display HP is restored by the game
# every frame, so a received death reaches each hero when they are switched in [Eden, 2026-11-03].)
REWARD_SEARCH = 64 << 20  # how far from the parameter table the reward table may sit
LOCK_RECORD = 28  # The Future of Hyrule: a locked mission is made to require it, which nothing clears in time
# Per-mission states the map draws from (one byte per mission record): profile +0x876 (saved copy +3*0xC30) and
# [P+0x5A8] +0x14C / +0x81C (found by matching the user's cleared/open/locked missions; RESEARCH session 8).
MISSION_STATES_PROFILE = (0x876, 0x876 + 3 * 0xC30)
MISSION_STATES_BLOCK, MISSION_STATES_MAP = 0x5A8, (0x14C, 0x81C)
MAP_SELECTION = 0x148  # in the map-state block: the world-map cursor's u16 id + kind byte (map_selection)
MISSIONS = (0x598, 0xE08, 0xF4)
DIFFICULTY_TIMES = -0x10  # per-difficulty clear times (6 u32, slot 0 = Easy) sit just before each live record [confirmed]
HEROES = (0x580, 0x224, 0x20)
HERO_SAVED_COPY = 3 * 0x560  # kept in step so the game's own copy-back never undoes a write
HERO_LEVEL, HERO_FLAGS = 0x0E, 0x16
HERO_XP = 0x04  # u32 cumulative XP (S.HERO_XP_TABLE gives each level's threshold)
HERO_STATS = 0x08  # u16 hearts, ATK, DEF (hearts follow S.HERO_HEARTS_TABLE, ATK/DEF +3 per level)
WRITE_JOURNAL: collections.deque = collections.deque(maxlen=5000)  # (time, address, bytes, client function) for the probe
# Effects the probe verifies later (20 s, 5 min, after the next mission): (time, what, check, detail); check() returns
# (still applied? True / False / None = can't tell, what the game shows now)
EXPECTATIONS: collections.deque = collections.deque(maxlen=500)
PLACEHOLDER_STATS = b"\x01\x00\x01\x00\x01\x00"  # a hero the game never let join: 1 heart, 1 ATK, 1 DEF
HERO_EQUIPPED, HERO_WEAPON, HERO_PLAYABLE = 0x10, 0x12, 0x15  # equipped weapon type; 1 = in the selectable roster (game sets it on join)
HERO_WEAPON_COUNT = -4  # u32 just before each hero row: weapons owned besides the first (the game's next order number)
PROFILE = 0x588
RUPEES, MATERIALS = 0x1E8, 0x3E4
MATERIALS_SEEN = 0x7A9  # u8 per material: 1 = discovered, else the menu hides it [found in game 2026-10-28; save 0x2C2DD]
PROFILE_SAVED_COPY = 3 * 0xC30
QUESTS = 0x560  # quest state bytes at +S.QUEST_STATE_LIVE
QUEST_SAVED_COPY = 0x2550  # saved copy of the quest states, kept in step
# The world map's own copy of each quest's state (its icon): [P+0x5A8] + 0x2DC + quest id, saved copy +0x6D0; 3 = done
# (grey). A hand-in sets both copies; the client set only the quest block until 0.9.74, so quests it completed showed
# orange and "available" on the map although done (user, 2026-11-02; 110 such quests read live; offsets from the
# Marita / Akkala hand-ins).
QUEST_MAP_STATES, QUEST_MAP_SAVED_COPY = 0x2DC, 0x6D0
# Story flag table (save 0x14..0x8F, one byte each) at [P+0x550]+0x18C; four copies 0x700 apart: 0 current (read live,
# even mid-mission), 3 saved, 1/2 a mission's working copies. Rune flags confirmed in game by setting/clearing them.
STORY_FLAGS, STORY_FLAGS_OFFSET, STORY_FLAGS_COPIES = 0x550, 0x18C, (0, 3 * 0x700)
RUNE_FLAGS = {"Remote Bombs": 0x19 - 0x14, "Cryonis": 0x1A - 0x14, "Magnesis": 0x1B - 0x14, "Stasis": 0x1C - 0x14}
# (Remote Bombs = the Slate: off hides the whole rune menu; confirmed in game, RESEARCH session 18)
# Owned weapons: [P + 0x568] holds the pool objects; [[pool + 0x30]] is the current copy, [[pool + 0x48]] the
# saved one. 2139 records of 0x90 bytes, 71 per hero (hero slot * 71). Record: +0x00 order (u32), +0x10 weapon
# kind (u16, each hero has its own range), +0x0C XP (u32), +0x14 attack bonus (u16: shown damage = the weapon's
# base + this), +0x78 level - 1, +0x87 rusted (1 = hidden until restored). Confirmed in game 2026-11-02: the shown
# level follows +0x78 and the damage +0x14, and fusing recomputed both from XP (a written level does not last: the
# Weapon XP Gift was dropped for weapon bundles in 0.9.74). +0x79 (what the gift wrote until then) is not shown;
# game-made records hold 0..16 there (meaning unknown). The save stores the same pool as 81-byte records.
WEAPON_POOL, WEAPON_COPIES = 0x568, (0x30, 0x48)
WEAPON_RECORD, WEAPONS_PER_HERO, WEAPON_RECORDS = 0x90, 71, 2139
WEAPON_XP, WEAPON_KIND, WEAPON_LEVEL, WEAPON_ATTACK, WEAPON_RUSTED = 0x0C, 0x10, 0x78, 0x14, 0x87
WEAPON_OLD_BYTE = 0x79  # kept as the game's own weapon rewards have it (1) in weapons the client gives


def level_stats(stats: bytes, old: int, new: int) -> bytes:
    """Hero stats (u16 hearts, ATK, DEF) moved from level old to level new the way the game's level-ups move them."""
    hearts, attack, defence = struct.unpack("<3H", stats)
    hearts += S.HERO_HEARTS_TABLE[new - 1] - S.HERO_HEARTS_TABLE[old - 1]
    step = S.HERO_STAT_PER_LEVEL * (new - old)
    return struct.pack("<3H", *(max(1, min(0xFFFF, v)) for v in (hearts, attack + step, defence + step)))


class HookError(RuntimeError):
    pass


class LiveGame:
    def __init__(self, guest: Guest) -> None:
        self.g = guest
        self._rods_held: dict[int, int] = {}  # rod slot -> uses to give back when its item arrives mid-mission
        self._rod_pouch = 0
        self.material_writes = 0  # materials the client wrote (progress checks count only what the player gathers)

    # --- attaching ------------------------------------------------------------------------

    @classmethod
    def find(cls) -> "LiveGame | None":
        """Attach to the first emulator (Ryujinx or Eden) that is running Age of Calamity with a save loaded."""
        for pid, emulator in emulator_processes():
            try:
                proc = Process(pid)
            except OSError:
                continue
            guest = Guest.attach(proc) if emulator == "Ryujinx" else \
                FastmemGuest.attach(proc, MANAGER - MODULE_BASE, lambda g: cls(g).save_ok())
            if guest:
                game = cls(guest)
                if game.loaded():
                    return game
            proc.close()
        return None

    def close(self) -> None:
        self.g.p.close()

    def _ptr(self, field: int) -> int:
        manager = self.g.u64(MANAGER)
        if not manager or not 0x1000 < manager < 1 << 40:
            raise HookError("game state manager not set up (title screen?)")
        value = self.g.u64(manager + field)
        if not value or not 0x1000 < value < 1 << 40:
            raise HookError("save data not loaded")
        return value

    def loaded(self) -> bool:
        """True when the code is the version we know and a save is loaded (Link's hero row is sane)."""
        try:
            if not self.g.code_ok():
                return False
            row = self._hero_row("Link")
            return row is not None and row[HERO_LEVEL] < S.HERO_LEVEL_MAX and set(row[HERO_FLAGS:HERO_FLAGS + 3]) <= {0, 1}
        except HookError:
            return False

    def save_ok(self) -> bool:
        """Stricter than loaded() (used to find Eden's memory layout, where empty memory passes loaded()): every save
        block points somewhere different, the quest states look like a game's, and so do the mission states (one
        mission open or cleared). 0.9.90: no longer "a mission is cleared": a 0.9.90 starter save has
        none, and the client never attached to it on Eden."""
        try:
            if not self.loaded():
                return False
            if len({self._ptr(f) for f in (STORY_FLAGS, QUESTS, HEROES[0], PROFILE, 0x5A0)}) < 5:
                return False
            blob = self.g.read(self._ptr(QUESTS) + S.QUEST_STATE_LIVE, S.QUEST_STATE_COUNT)
            # blob[0] == 1: the same test completed_quests() makes (on Eden it fails for a few seconds while the save
            # loads, which dropped the fresh connection three times)
            if blob is None or blob[0] != 1 or max(blob) > S.QUEST_DONE or len(set(blob)) <= 1:
                return False
            _, states = self._state_lists()  # (raises unless every list holds 0-3 only)
            return any(s in (2, 3) for s in states[0][1:])
        except HookError:
            return False

    # --- reading --------------------------------------------------------------------------

    def cleared_records(self) -> set[int]:
        field, offset, stride = MISSIONS
        base = self._ptr(field) + offset
        blob = self.g.read(base, S.MISSION_RECORD_COUNT * stride)
        if blob is None:
            raise HookError("mission table unreadable")
        # (0.9.90: the per-difficulty clear times, like the save reader and cleared_missions_at; before, the six u32 at
        # the record start - clear times 4-5 and scores 0-3 - which a clear also fills. Record 0 is never a mission.)
        return {i for i in range(1, S.MISSION_RECORD_COUNT)
                if any(S.clear_slots(i, struct.unpack_from("<6I", blob, i * stride + DIFFICULTY_TIMES)))}

    def cleared_missions_at(self, min_slot: int) -> set[str]:
        """Missions with a clear time on difficulty slot min_slot or any higher one (a harder clear counts for every
        easier difficulty)."""
        field, offset, stride = MISSIONS
        base = self._ptr(field) + offset
        blob = self.g.read(base, S.MISSION_RECORD_COUNT * stride)
        if blob is None:
            raise HookError("mission table unreadable")
        done = {i for i in range(1, S.MISSION_RECORD_COUNT)
                if any(S.clear_slots(i, struct.unpack_from("<6I", blob, i * stride + DIFFICULTY_TIMES))[min_slot:S.DIFFICULTY_SLOTS])}
        return {name for name, ids in S.MISSION_RECORD_IDS.items() if all(i in done for i in ids)}

    def cleared_missions(self) -> set[str]:
        records = self.cleared_records()
        return {name for name, ids in S.MISSION_RECORD_IDS.items() if all(i in records for i in ids)}

    def completed_quests(self) -> set[str]:
        """Quests (requests: upgrades, services, shops) the game marks done."""
        blob = self.g.read(self._ptr(QUESTS) + S.QUEST_STATE_LIVE, S.QUEST_STATE_COUNT)
        if blob is None or blob[0] != 1 or max(blob) > S.QUEST_DONE:
            raise HookError("quest states not recognised")
        return {name for name, i in S.QUEST_STATE_IDS.items() if blob[i] == S.QUEST_DONE}

    def found_koroks(self) -> set[str]:
        """Korok seeds found in story missions and challenges ("Korok Seed: <mission> #n"; data_koroks)."""
        blob = self.g.read(self._ptr(QUESTS) + KOROK_FLAGS_LIVE, KOROK_BLOCK * (CHALLENGE_KOROK_BLOCK + 1))
        if blob is None or max(blob) > 1:
            raise HookError("Korok flags not recognised")
        return {name for name, block, slot in korok_flags() if blob[block * KOROK_BLOCK + slot]}

    def opened_chests(self) -> set[str]:
        """Treasure chests opened ("Treasure Chest: <mission> #n"; data_chests); set the moment one opens."""
        blob = self.g.read(self._ptr(PROFILE) + CHEST_FLAGS_LIVE, CHEST_BLOCK * CHEST_BLOCKS)
        if blob is None or max(blob) > 1:
            raise HookError("chest flags not recognised")
        return {name for name, block, slot in chest_flags() if blob[block * CHEST_BLOCK + slot]}

    def _hero_addr(self, character: str) -> int:
        field, offset, stride = HEROES
        return self._ptr(field) + offset + S.HERO_SLOTS[character] * stride

    def _hero_row(self, character: str) -> bytes | None:
        return self.g.read(self._hero_addr(character), stride_of(HEROES))

    def hero_unlocked(self, character: str) -> bool:
        row = self._hero_row(character)
        return bool(row and row[HERO_FLAGS])

    def hero_level(self, character: str) -> int:
        row = self._hero_row(character)
        return row[HERO_LEVEL] + 1 if row else 0

    def material_counts(self) -> list[int]:
        """Every material count (u16 per material index, profile +MATERIALS)."""
        n = 176
        raw = self.g.read(self._ptr(PROFILE) + MATERIALS, n * 2)
        if raw is None or len(raw) < n * 2:
            raise HookError("materials unreadable")
        return list(struct.unpack(f"<{n}H", raw))

    def best_weapon_levels(self, characters) -> dict[str, int]:
        """Each hero's highest weapon level among the weapons they own (progress checks)."""
        pools = self._weapon_pools()
        if not pools:
            return {}
        out = {}
        for c in characters:
            slot = S.HERO_SLOTS.get(c)
            if slot is None:
                continue
            raw = self.g.read(pools[0] + slot * WEAPONS_PER_HERO * WEAPON_RECORD, WEAPONS_PER_HERO * WEAPON_RECORD)
            if not raw:
                continue
            best = 0
            for i in range(WEAPONS_PER_HERO):
                rec = raw[i * WEAPON_RECORD:(i + 1) * WEAPON_RECORD]
                if struct.unpack_from("<H", rec, WEAPON_KIND)[0]:
                    best = max(best, rec[WEAPON_LEVEL] + 1)
            out[c] = best
        return out

    def rupees(self) -> int:
        raw = self.g.read(self._ptr(PROFILE) + RUPEES, 4)
        if raw is None:
            raise HookError("rupees unreadable")
        return struct.unpack("<I", raw)[0]

    # --- writing (each returns a one-line description) -------------------------------------

    def _write(self, va: int, data: bytes) -> None:
        if not self.g.write(va, data):
            raise HookError("write failed")
        WRITE_JOURNAL.append((time.time(), va, bytes(data), sys._getframe(1).f_code.co_name))

    def expect(self, what: str, check, **detail) -> None:
        """Register an effect for the probe to verify later (check() -> (still applied?, what the game shows))."""
        EXPECTATIONS.append((time.time(), what, check, detail))

    def map_selection(self) -> tuple[int, int] | None:
        """What the world-map cursor is on: (id, kind) - kind 2 = a story mission record, 3 = a challenge record, 4 = a quest
        (id = quest state id) [read live 2026-10-28: [P+0x5A8]+0x148 u16 id, +0x14A kind]."""
        raw = self.g.read(self._ptr(MISSION_STATES_BLOCK) + MAP_SELECTION, 4)
        return (struct.unpack_from("<H", raw)[0], raw[2]) if raw else None

    def quest_state(self, name: str) -> int | None:
        raw = self.g.read(self._ptr(QUESTS) + S.QUEST_STATE_LIVE + S.QUEST_STATE_IDS[name], 1)
        return raw[0] if raw else None

    def mission_states(self, record: int) -> list[int]:
        """The four per-mission state list values of a record (profile lists: 1 locked; map block: 0 locked)."""
        _, blobs = self._state_lists()
        return [b[record] for b in blobs]

    def add_rupees(self, amount: int) -> str:
        old = self.rupees()
        new = min(S.RUPEES_MAX, old + amount)
        self._write(self._ptr(PROFILE) + RUPEES, struct.pack("<I", new))

        def check():  # spending afterwards is fine; back to the old amount is not
            now = self.rupees()
            return now != old or old == new, f"rupees {now}"
        self.expect("Rupee Pouch", check, before=old, wrote=new)
        return f"+{amount} rupees (now {new})"

    def material_bundle(self, seed: int, kinds: int = 5, amount: int = 15) -> str:
        base = self._ptr(PROFILE) + MATERIALS
        picks = random.Random(seed).sample(S.BUNDLE_MATERIALS, kinds)
        for index in picks:
            raw = self.g.read(base + index * 2, 2)
            if raw is None:
                raise HookError("materials unreadable")
            new = min(S.MATERIAL_MAX, struct.unpack("<H", raw)[0] + amount)
            self._write(base + index * 2, struct.pack("<H", new))
            self._expect_material("Material Bundle", base + index * 2, struct.unpack("<H", raw)[0], new, index)
        from ..data_materials import MATERIAL_NAMES
        return f"+{amount} each: {', '.join(MATERIAL_NAMES.get(i, f'material {i}') for i in picks)}"

    def _expect_material(self, what: str, addr: int, old: int, new: int, index: int) -> None:
        self.material_writes += 1
        self._write(self._ptr(PROFILE) + MATERIALS_SEEN + index, bytes([1]))  # shown in the materials menu

        def check():
            raw = self.g.read(addr, 2)
            now = struct.unpack("<H", raw)[0] if raw else None
            return now is not None and (now != old or old == new), f"material {index}: {now}"
        self.expect(what, check, material=index, before=old, wrote=new)

    def hearty_meal(self) -> str:
        base = self._ptr(PROFILE) + MATERIALS
        for index, amount in S.HEARTY_MEAL.items():
            raw = self.g.read(base + index * 2, 2)
            if raw is None:
                raise HookError("materials unreadable")
            old = struct.unpack("<H", raw)[0]
            self._write(base + index * 2, struct.pack("<H", min(S.MATERIAL_MAX, old + amount)))
            self._expect_material("Hearty Meal", base + index * 2, old, min(S.MATERIAL_MAX, old + amount), index)
        return "Hearty Meal: cooking ingredients"

    def level_up(self, characters: list[str]) -> str:
        known = [c for c in characters if c in S.HERO_SLOTS and self.hero_unlocked(c)]
        known = [c for c in known if self.hero_level(c) < S.HERO_LEVEL_MAX]
        if not known:
            return "no hero to level up"
        hero = min(known, key=lambda c: (self.hero_level(c), c))
        self.set_level(hero, self.hero_level(hero) + 1)
        return f"{hero} -> level {self.hero_level(hero)}"

    def set_level(self, character: str, level: int) -> bool:
        """Raise a hero to `level` with the XP that level needs (current and saved copy; never lowers), so the
        game does not drop the level again when XP is next counted. Returns True if it changed."""
        level = min(level, S.HERO_LEVEL_MAX)
        old = self.hero_level(character) if character in S.HERO_SLOTS else 0
        if not old or old >= level:
            return False
        addr = self._hero_addr(character)
        xp = struct.unpack("<I", self.g.read(addr + HERO_XP, 4) or b"\0\0\0\0")[0]
        xp = max(xp, S.HERO_XP_TABLE[level - 1])
        stats = self.g.read(addr + HERO_STATS, 6)
        for copy in (0, HERO_SAVED_COPY):
            self._write(addr + copy + HERO_XP, struct.pack("<I", xp))
            self._write(addr + copy + HERO_LEVEL, bytes([level - 1]))
            if stats and stats != PLACEHOLDER_STATS:  # the game adds stats only on its own level-ups
                self._write(addr + copy + HERO_STATS, level_stats(stats, old, level))
        want = level_stats(stats, old, level) if stats and stats != PLACEHOLDER_STATS else None

        def check():  # level kept, and hearts/ATK/DEF at least what the write gave
            now_level = self.hero_level(character)
            now = self.g.read(self._hero_addr(character) + HERO_STATS, 6)
            ok = now_level >= level and (want is None or (now is not None and all(
                a >= b for a, b in zip(struct.unpack("<3H", now), struct.unpack("<3H", want)))))
            stats_now = list(struct.unpack("<3H", now)) if now else None
            return ok, f"level {now_level}, hearts/ATK/DEF {stats_now}"
        self.expect("Hero level", check, hero=character, before=old, wrote=level,
                    stats=list(struct.unpack("<3H", want)) if want else None)
        return True

    def cap_level(self, character: str, cap: int) -> bool:
        """hero_level_cap: a hero above `cap` goes back to `cap` with that level's XP (current and saved copy);
        hearts/ATK/DEF are kept, so the level-up the game just gave still counted. Returns True if it changed."""
        level = self.hero_level(character) if character in S.HERO_SLOTS else 0
        if level <= cap:
            return False
        addr = self._hero_addr(character)
        for copy in (0, HERO_SAVED_COPY):
            self._write(addr + copy + HERO_XP, struct.pack("<I", S.HERO_XP_TABLE[cap - 1]))
            self._write(addr + copy + HERO_LEVEL, bytes([cap - 1]))
        self.expect("Hero level cap", lambda: (self.hero_level(character) <= cap, f"level {self.hero_level(character)}"),
                    hero=character, before=level, wrote=cap)
        return True

    def raise_levels(self, characters: list[str], level: int) -> list[str]:
        """minimum_character_level: every listed hero below `level` is raised to it. Returns the heroes raised."""
        return [c for c in characters if self.set_level(c, level)]

    def grant_hero(self, character: str) -> bool:
        """Make a hero playable the way the game does: playable flag (+0x15), gallery flags, a starting weapon of
        the hero's own weapon type (+0x12) and real stats instead of the locked placeholder values (copied from your
        lowest-level playable hero; the game raises them on level-up). Returns True if anything changed."""
        if character not in S.HERO_SLOTS:
            return False
        addr = self._hero_addr(character)
        row = bytearray(self.g.read(addr, 0x20) or b"")
        if len(row) != 0x20:
            raise HookError("hero row unreadable")
        before = bytes(row)
        if row[HERO_STATS:HERO_STATS + 6] == PLACEHOLDER_STATS:  # (a starter save unlocks heroes with these too)
            template = self._stat_template(exclude=character)
            if template:
                stats, level = template  # moved to this hero's own level, so later level writes add on top
                row[HERO_STATS:HERO_STATS + 6] = level_stats(stats, level, row[HERO_LEVEL] + 1)
        given = self.give_starter_weapon(character)
        if given:
            row[HERO_WEAPON] = S.HERO_STARTER_WEAPON[character]
            row[0x10] = 0  # equip the weapon just given
        elif row[HERO_WEAPON] == 0:
            row[HERO_WEAPON] = S.HERO_STARTER_WEAPON[character]
        row[HERO_PLAYABLE] = 1
        row[HERO_FLAGS:HERO_FLAGS + 3] = b"\x01\x01\x01"
        if bytes(row) == before:
            return given
        for copy in (0, HERO_SAVED_COPY):
            self._write(addr + copy, bytes(row))

        def check():  # playable, with real stats and a weapon
            now = self._hero_row(character)
            ok = bool(now and now[HERO_PLAYABLE] and now[HERO_FLAGS] and now[HERO_STATS:HERO_STATS + 6] != PLACEHOLDER_STATS
                      and any(self.hero_weapons(character)))
            return ok, f"row {now.hex() if now else None}"
        self.expect("Hero joined", check, hero=character)
        return True

    def prime_hero(self, character: str) -> bool:
        """Starter save: give a hero (locked or not) a starter weapon and real level-1 stats without making it
        playable, so a hero forced into a party never plays with the 1-heart, no-damage placeholder. Returns True if
        anything changed."""
        if character not in S.HERO_SLOTS:
            return False
        addr = self._hero_addr(character)
        row = bytearray(self.g.read(addr, 0x20) or b"")
        if len(row) != 0x20:
            raise HookError("hero row unreadable")
        before = bytes(row)
        if row[HERO_STATS:HERO_STATS + 6] == PLACEHOLDER_STATS:
            template = self._stat_template(exclude=character)
            if template:
                stats, level = template
                row[HERO_STATS:HERO_STATS + 6] = level_stats(stats, level, row[HERO_LEVEL] + 1)
        given = self.give_starter_weapon(character)
        if given:
            row[HERO_WEAPON] = S.HERO_STARTER_WEAPON[character]
            row[HERO_EQUIPPED] = 0
        elif row[HERO_WEAPON] == 0:
            row[HERO_WEAPON] = S.HERO_STARTER_WEAPON[character]
        if bytes(row) != before:
            for copy in (0, HERO_SAVED_COPY):
                self._write(addr + copy, bytes(row))
        return given or bytes(row) != before

    def _weapon_pools(self) -> list[int]:
        pool = self._ptr(WEAPON_POOL)
        bases = []
        for field in WEAPON_COPIES:
            obj = self.g.u64(pool + field)
            records = self.g.u64(obj + 0x00) if obj else None
            count = self.g.u64(obj + 0x08) if obj else None
            # The current copy reports 2139, the others 2059 (meaning unknown); both cover every hero range we use.
            if not records or not WEAPONS_PER_HERO * len(S.HERO_SLOTS) < (count or 0) <= WEAPON_RECORDS:
                raise HookError("weapon pool not recognised")
            bases.append(records)
        return bases

    def hero_weapons(self, character: str) -> list[int]:
        """Weapon kinds in the hero's pool range (0 = empty slot)."""
        base = self._weapon_pools()[0] + S.HERO_SLOTS[character] * WEAPONS_PER_HERO * WEAPON_RECORD
        blob = self.g.read(base, WEAPONS_PER_HERO * WEAPON_RECORD)
        if blob is None:
            raise HookError("weapon pool unreadable")
        return [struct.unpack_from("<H", blob, i * WEAPON_RECORD + WEAPON_KIND)[0] for i in range(WEAPONS_PER_HERO)]

    def weapon_counts(self) -> dict[str, int]:
        """How many copies of each named weapon the player owns (current pool, every hero range)."""
        base = self._weapon_pools()[0]
        blob = self.g.read(base, (max(S.HERO_SLOTS.values()) + 1) * WEAPONS_PER_HERO * WEAPON_RECORD)
        if blob is None:
            raise HookError("weapon pool unreadable")
        owned: dict[int, int] = {}
        for i in range(len(blob) // WEAPON_RECORD):
            kind = struct.unpack_from("<H", blob, i * WEAPON_RECORD + WEAPON_KIND)[0]
            if kind:
                owned[kind] = owned.get(kind, 0) + 1
        counts = {name: sum(owned.get(k, 0) for k in kinds) for name, kinds in S.WEAPON_KINDS.items()}
        return {name: n for name, n in counts.items() if n}

    def give_weapon(self, name: str, wielder: str) -> str:
        """Add a weapon to its wielder's weapons (next free slot, next order number, level 1)."""
        hero = wielder if wielder in S.HERO_SLOTS else "Link"
        kinds = self.hero_weapons(hero)
        if 0 not in kinds:
            return f"{name}: {hero}'s weapon storage is full"
        slot = kinds.index(0)
        count_addr = self._hero_addr(hero) + HERO_WEAPON_COUNT
        count = struct.unpack("<I", self.g.read(count_addr, 4) or b"\0\0\0\0")[0]
        record = bytearray(WEAPON_RECORD)
        struct.pack_into("<I", record, 0, count)
        struct.pack_into("<H", record, WEAPON_KIND, S.WEAPON_KINDS[name][0])
        record[WEAPON_OLD_BYTE] = 1  # level 1 (+0x78 = 0); shown in game this way (2026-11-02)
        offset = (S.HERO_SLOTS[hero] * WEAPONS_PER_HERO + slot) * WEAPON_RECORD
        for base in self._weapon_pools():
            self._write(base + offset, bytes(record))
        for copy in (0, HERO_SAVED_COPY):
            self._write(count_addr + copy, struct.pack("<I", count + 1))

        def check():  # None: not owned any more, which fusing or selling also does
            kinds_now = self.hero_weapons(hero)
            return (True if S.WEAPON_KINDS[name][0] in kinds_now else None), f"{hero}'s slot {slot} holds kind {kinds_now[slot]}"
        self.expect("Weapon given", check, weapon=name, hero=hero, slot=slot)
        return f"{name} for {hero}"

    def give_starter_weapon(self, character: str) -> bool:
        """Give a hero who owns no weapon their basic one, laid out the way the game stores a weapon reward
        (that is how Sidon got his harpoon in the first test): first slot of the hero's range, order 0, level 1,
        and the hero's owned count set to 1. Returns True if a weapon was given."""
        kind = S.HERO_STARTER_KIND.get(character)
        if kind is None or any(self.hero_weapons(character)):
            return False
        record = bytearray(WEAPON_RECORD)
        struct.pack_into("<H", record, WEAPON_KIND, kind)
        record[WEAPON_OLD_BYTE] = 1
        offset = S.HERO_SLOTS[character] * WEAPONS_PER_HERO * WEAPON_RECORD
        for base in self._weapon_pools():
            self._write(base + offset, bytes(record))
        for copy in (0, HERO_SAVED_COPY):
            self._write(self._hero_addr(character) + copy + HERO_WEAPON_COUNT, struct.pack("<I", 1))
        return True

    def revoke_hero(self, character: str) -> bool:
        """Take a hero out of the selectable roster (playable and gallery flags off; weapon and stats are kept)."""
        if character not in S.HERO_SLOTS:
            return False
        addr = self._hero_addr(character)
        if self.g.read(addr + HERO_PLAYABLE, 4) == b"\x00\x00\x00\x00":
            return False
        for copy in (0, HERO_SAVED_COPY):
            self._write(addr + copy + HERO_PLAYABLE, b"\x00\x00\x00\x00")
        return True

    def _stat_template(self, exclude: str) -> tuple[bytes, int] | None:
        """Stats (hearts, ATK, DEF) and level of the lowest-level playable hero; with none (a starter save whose
        starting heroes all have placeholder stats), of the lowest-level hero with real stats, playable or not."""
        for playable_only in (True, False):
            best = None
            for hero in S.HERO_SLOTS:
                if hero == exclude:
                    continue
                row = self._hero_row(hero)
                if row and (row[HERO_PLAYABLE] or not playable_only) and row[0x08] > 1 \
                        and (best is None or row[HERO_LEVEL] < best[HERO_LEVEL]):
                    best = row
            if best:
                return bytes(best[HERO_STATS:HERO_STATS + 6]), best[HERO_LEVEL] + 1
        return None

    def set_upgrade_levels(self, levels: dict[int, int]) -> list[int]:
        """Force combo-upgrade levels (category -> level) in the current and saved profile, so moves come only from
        received items even after the world-map quest is done. Returns the categories changed."""
        base = self._ptr(PROFILE) + S.UPGRADE_LEVELS
        current = self.g.read(base, S.UPGRADE_CATEGORIES)
        # Expansion Pass quests go past 5 (EX Safe Roads, Safe Rides / EX Burning Desire took category 24 from 5 to 6,
        # 2026-11-02); until 0.9.74 a 6 here stopped the client enforcing every upgrade.
        if current is None or max(current) > 9:
            raise HookError("upgrade levels not recognised")
        changed = []
        for category, level in sorted(levels.items()):
            if current[category] != level:
                for copy in (0, PROFILE_SAVED_COPY):
                    self._write(base + copy + category, bytes([level]))
                changed.append(category)
        return changed

    def set_hero_bonus(self, family: str, values: dict[int, int]) -> list[int]:
        """Force a per-hero quest reward (bonus hearts or special gauges; hero slot -> count) in the current and saved
        profile, so it comes only from received items. Returns the hero slots changed."""
        base = self._ptr(PROFILE) + S.HERO_BONUS[family]
        current = self.g.read(base, S.HERO_BONUS_COUNT)
        if current is None or max(current) > 20:
            raise HookError("hero rewards not recognised")
        changed = []
        for slot, value in sorted(values.items()):
            if current[slot] != value:
                for copy in (0, PROFILE_SAVED_COPY):
                    self._write(base + copy + slot, bytes([value]))
                changed.append(slot)
        return changed

    def set_profile_bytes(self, values: dict[int, int]) -> list[int]:
        """Force single-byte profile fields (offset -> value; ability flags, weapon capacity level) in the current and
        saved profile. Returns the offsets changed."""
        prof = self._ptr(PROFILE)
        changed = []
        for offset, value in sorted(values.items()):
            current = self.g.read(prof + offset, 1)  # (weapon capacity holds up to 4 + the lab's 30)
            if current is None or current[0] > (40 if offset == S.WEAPON_CAPACITY_LEVEL else 10):
                raise HookError("profile not recognised")
            if current[0] != value:
                for copy in (0, PROFILE_SAVED_COPY):
                    self._write(prof + copy + offset, bytes([value]))
                changed.append(offset)
        return changed

    def set_runes(self, runes: dict[str, bool]) -> list[str]:
        """Give or take Sheikah Slate runes (current and saved copy of the story flags). Returns the runes changed."""
        base = self._ptr(STORY_FLAGS) + STORY_FLAGS_OFFSET
        flags = self.g.read(base, 0x7C)
        if flags is None or max(flags) > 1:
            raise HookError("story flags not recognised")
        changed = []
        for rune, have in sorted(runes.items()):
            if flags[RUNE_FLAGS[rune]] != have:
                for copy in STORY_FLAGS_COPIES:
                    self._write(base + copy + RUNE_FLAGS[rune], bytes([have]))
                changed.append(rune)
        return changed

    def frame_rate(self) -> int | None:
        """The game's frame-rate target (30 or 60) from its frame-rate block, None when unreadable."""
        raw = self.g.read(MODULE_BASE + FRAME_RATE_BLOCK, 16)
        if not raw:
            return None
        fps, interval, _, _ = struct.unpack("<IIIf", raw)
        return fps if (fps, interval) in ((30, 2), (60, 1)) else None

    def _gfx(self) -> int | None:
        """The graphics object (GFX_PATHS), None unless both paths agree and its present interval looks right."""
        found = []
        for glob, off in GFX_PATHS:
            holder = self.g.u64(MODULE_BASE + glob)
            if not holder or not 0x1000 < holder < 1 << 40:
                return None
            found.append(self.g.u64(holder + off))
        if len(set(found)) != 1 or not found[0] or not 0x1000 < found[0] < 1 << 40:
            return None
        raw = self.g.read(found[0] + GFX_PRESENT_INTERVAL, 4)
        return found[0] if raw and struct.unpack("<I", raw)[0] in (0, 1, 2) else None

    def set_pacing(self, cap: float | None, present: int = 1) -> None:
        """Frame pacing (client/framerate.py): cap = frames per second the game may draw, present = display present
        interval (1 every refresh, 0 unsynced); None puts the game's own 30 FPS back (block 30/2/30/30.0, present 2)."""
        if cap is None:
            self._write(MODULE_BASE + FRAME_RATE_BLOCK, struct.pack("<IIIf", 30, 2, 30, 30.0))
            present = 2
        else:
            self._write(MODULE_BASE + FRAME_RATE_BLOCK, struct.pack("<IIIf", 60, 1, 60, float(cap)))
        self.set_frame_step(2.0 if cap is None else 1.0)
        gfx = self._gfx()
        if gfx is not None:
            self._write(gfx + GFX_PRESENT_INTERVAL, struct.pack("<I", present))

    def set_frame_step(self, ticks: float) -> None:
        """Game mod frame timing: the float frame step (1/60 s ticks the next frame lasts) that the patched movement
        and timer code reads at main+0x26A2290 (client/rune_mod.py). 2.0 = the game's own 30 FPS step.
        The UI divisor next to it stays at the vanilla 1/60: the layout animations are handed dt = frame step / 60
        (stub read-watch at 60 FPS, mission and pause menu, 2026-11-19: 1/60 from 0xa6624c), so they already run at
        real speed; scaling the divisor halved them (the hero-portrait arrow, the world map)."""
        raw = self.g.read(MODULE_BASE + FRAME_STEP, 8)  # (compared with memory, not a cache: the game rewrites)
        divisor = 1.0 / 60.0
        if (not raw or len(raw) < 8 or abs(struct.unpack("<f", raw[:4])[0] - ticks) > 0.005
                or abs(struct.unpack("<f", raw[4:])[0] - divisor) > divisor * 0.002):
            self._write(MODULE_BASE + FRAME_STEP, struct.pack("<ff", ticks, divisor))

    def set_present(self, present: int) -> None:
        """The display's present interval (checked against memory: the game may set it back)."""
        gfx = self._gfx()
        if gfx is not None and struct.unpack("<I", self.g.read(gfx + GFX_PRESENT_INTERVAL, 4))[0] != present:
            self._write(gfx + GFX_PRESENT_INTERVAL, struct.pack("<I", present))

    def _map_scene(self) -> int | None:
        """The world-map scene object, or None (not on the map, or not recognised by its vtable)."""
        p = self.g.u64(MODULE_BASE + MAP_SCENE_ROOT)
        for off in MAP_SCENE_PATH:
            if not p:
                return None
            p = self.g.u64(p + off)
        if not p:
            return None
        guest_base = MODULE_BASE + getattr(self.g, "shift", 0)  # (Eden: the module's real guest address)
        return p if self.g.u64(p) == guest_base + MAP_SCENE_VTABLE else None

    def refresh_map(self) -> bool:
        """Redraw the world map's icons now, as closing the pause menu does, so missions, challenges and quests the
        client opened appear without the player pausing (user, 2026-11-19). Only while the map is idle (state 14):
        requests the menu state, then the rebuild state, the same sequence the game runs [confirmed on Eden
        2026-11-19: states 0, 1, 2, 3 ... 13, 14 like a real menu close; the menu works afterwards]. Requesting the
        rebuild straight from 14 skipped the menu's resets and left the map without input (state 10). Returns True
        when the refresh was started. Only on the Map tab: inside the Chapters list a redraw closes the list and jumps
        to the map (seen 2026-11-20)."""
        scene = self._map_scene()
        if scene is None or self.map_tab(scene) != MAP_TAB_MAP:
            return False
        raw = self.g.read(scene + MAP_SCENE_STATE, 8)
        if not raw or struct.unpack("<ii", raw) != (MAP_IDLE, MAP_IDLE):
            return False
        self._write(scene + MAP_SCENE_STATE + 4, struct.pack("<i", MAP_MENU))
        for _ in range(30):  # (one frame: the game takes the request on its next update)
            time.sleep(0.01)
            raw = self.g.read(scene + MAP_SCENE_STATE, 8)
            if raw and struct.unpack("<i", raw[:4])[0] == MAP_MENU:
                break
        else:
            self._write(scene + MAP_SCENE_STATE + 4, struct.pack("<i", MAP_IDLE))  # (not taken: leave the map as it was)
            return False
        self._write(scene + MAP_SCENE_STATE + 4, struct.pack("<i", MAP_REBUILD))
        return True

    def map_tab(self, scene: int | None = None) -> int | None:
        """The world map's open tab (scene +0x19C): 3 Services, 4 Map, 5 Chapters, 7 Quests [read live on Eden
        2026-11-20, unchanged by the pause menu]. The cursor kind (map_selection) does not tell the tabs apart."""
        scene = scene if scene is not None else self._map_scene()
        raw = self.g.read(scene + MAP_SCENE_TAB, 4) if scene else None
        return struct.unpack("<i", raw)[0] if raw and len(raw) == 4 else None

    def in_mission(self) -> bool:
        """A mission (battle) is loaded: its controlled character exists. False on the world map and in menus."""
        return self._battle_character() is not None

    def set_frame_cap(self, fps: float) -> None:
        """The frame-rate float (block+0xC): the game's frame limiter, and what ~28 effect/UI timers take as the frame
        length (1/fps). The pacer keeps it just above the frame rate reached, so both stay close to real."""
        raw = self.g.read(MODULE_BASE + FRAME_RATE_BLOCK + 12, 4)
        if not raw or abs(struct.unpack("<f", raw)[0] - fps) > 0.5:
            self._write(MODULE_BASE + FRAME_RATE_BLOCK + 12, struct.pack("<f", fps))

    def render_count(self) -> int | None:
        """Frames drawn, counted also in the pause menu (where frame_count stops): the AllRender profiling counter."""
        raw = self.g.read(MODULE_BASE + RENDER_COUNTER, 4)
        return struct.unpack("<I", raw)[0] if raw else None

    def frame_count(self) -> int | None:
        """A counter the game raises once per drawn frame (main+0x277DBA8, found 2026-11-15)."""
        raw = self.g.read(MODULE_BASE + FRAME_COUNTER, 4)
        return struct.unpack("<I", raw)[0] if raw else None

    def set_steps(self, steps: int) -> None:
        """Game steps (1/60 s ticks) the next drawn frame advances (the frame-rate block's second field)."""
        # Compared with memory each time (2026-11-15: the game rewrites the block itself - after /fps 30 the client's
        # cached values said 60 was set while the game sat at 30); the fps fields go back to 60 too.
        raw = self.g.read(MODULE_BASE + FRAME_RATE_BLOCK, 12)
        if not raw or struct.unpack("<III", raw) != (60, steps, 60):
            self._write(MODULE_BASE + FRAME_RATE_BLOCK, struct.pack("<III", 60, steps, 60))

    def battle_clock(self) -> int | None:
        """The mission clock (flow + FLOW_CLOCK): 60 ticks per real second at full game speed, whatever the frame rate;
        fewer when the game can't keep its frame-rate target (the game slows down)."""
        flow = self._flow()
        if not flow or flow[1] != FLOW_PLAYING:
            return None
        return struct.unpack("<I", self.g.read(flow[0] + FLOW_CLOCK, 4))[0]

    def rune_mod_active(self) -> bool | None:
        """The rune mod (client/rune_mod.py) is in the running game: True / False, None when the code can't be read."""
        from .rune_mod import CHECK_OFFSET, CHECK_PATCHED, CHECK_VANILLA
        code = self.g.read(MODULE_BASE + CHECK_OFFSET, 4)
        if code == CHECK_PATCHED:
            return True
        return False if code == CHECK_VANILLA else None

    def set_mod_runes(self, runes: dict[str, bool]) -> list[str]:
        """Rune mod: give or take runes (and the Sheikah Slate) through the flags the patched game reads (current and
        saved copy). The real story flags are left to the game's scripts. Returns the entries changed."""
        from .rune_mod import MOD_RUNE_FLAGS
        base = self._ptr(STORY_FLAGS) + STORY_FLAGS_OFFSET
        flags = self.g.read(base, 0x7C)
        if flags is None or max(flags) > 1:
            raise HookError("story flags not recognised")
        changed = []
        for rune, have in sorted(runes.items()):
            if flags[MOD_RUNE_FLAGS[rune]] != have:
                for copy in STORY_FLAGS_COPIES:
                    self._write(base + copy + MOD_RUNE_FLAGS[rune], bytes([have]))
                changed.append(rune)
        return changed

    def set_reward_bytes(self, values: dict[tuple[int, int], int]) -> list[tuple[int, int]]:
        """Force stored quest rewards ((block field, offset) -> value; data_rewards) in the current and saved copy of
        each block, so they come only from received items. Returns the (block, offset) pairs changed."""
        from ..data_rewards import BLOCK_SAVED_COPY
        changed = []
        for (block, offset), value in sorted(values.items()):
            base = self._ptr(block)
            current = self.g.read(base + offset, 1)
            if current is None or current[0] > 10:
                raise HookError("quest rewards not recognised")
            if current[0] != value:
                for copy in (0, BLOCK_SAVED_COPY[block]):
                    self._write(base + copy + offset, bytes([value]))
                changed.append((block, offset))
        return changed

    def give_research(self, material: int, amount: int, outfit: int | None) -> str:
        """A research quest's reward: materials, and an outfit when it has one (hand-ins 2026-11-03: the wardrobe count
        at +0x120 rises, the new list entry at +0x1678 holds the old count, the outfit's flag is +0x32BA + id - 19)."""
        from ..data_materials import MATERIAL_NAMES
        base = self._ptr(PROFILE) + MATERIALS + material * 2
        raw = self.g.read(base, 2)
        if raw is None:
            raise HookError("materials unreadable")
        old = struct.unpack("<H", raw)[0]
        new = min(S.MATERIAL_MAX, old + amount)
        self._write(base, struct.pack("<H", new))
        self._expect_material("Research reward", base, old, new, material)
        text = f"+{amount} {MATERIAL_NAMES.get(material, f'material {material}')}"
        if outfit is None:
            return text
        wardrobe = self._ptr(WARDROBE_BLOCK)
        flag = wardrobe + WARDROBE_OUTFIT_FLAGS + outfit - WARDROBE_FIRST_OUTFIT
        if self.g.read(flag, 1) != b"\0":
            return text + ", outfit already owned"
        count = struct.unpack("<I", self.g.read(wardrobe + WARDROBE_COUNT, 4) or bytes(4))[0]
        entry = WARDROBE_LIST + 8 * max(0, count - WARDROBE_LIST_START)
        for copy in (0, WARDROBE_SAVED_COPY):
            self._write(wardrobe + copy + WARDROBE_COUNT, struct.pack("<I", count + 1))
            self._write(wardrobe + copy + entry, struct.pack("<Q", count))
            self._write(flag + copy, b"\1")
        return text + f", outfit {outfit}"

    # --- Royal Ancient Lab (data_lab) -------------------------------------------------------------------------------

    def _lab_row0(self) -> int | None:
        """Address of the lab's anchor row (found by its costs; the scan's distance from the unlock table is kept)."""
        holder = self.g.u64(QUEST_UNLOCKS[0])
        table = self.g.u64(holder + QUEST_UNLOCKS[1]) if holder else None
        if not table:
            return None
        marker = struct.pack("<HHH", 2, 5, 10)
        known = getattr(self, "_lab_distance", None)
        if known is not None and self.g.read(table + known + 0x23, 6) == marker:
            return table + known
        for off in range(-(16 << 20), 16 << 20, 1 << 20):
            data = self.g.read(table + off, (1 << 20) + 32) or b""
            at = data.find(marker)
            while at >= 0:
                if at >= 0x23 and data[at - 0x23] == 0xA9:
                    self._lab_distance = off + at - 0x23
                    return table + self._lab_distance
                at = data.find(marker, at + 1)
        return None

    def sync_lab(self, values: dict[tuple[int, int], int], check_nodes: set[str],
                 held: dict[int, bool] | None = None, bought: set[str] = frozenset()) -> list[str]:
        """Keep the lab as the seed wants it: every node open, table rewards the items give removed,
        stored rewards following the items. held (0.9.87): node index -> item received, for nodes whose reward is the
        node being done (bought = check nodes already sent). Returns the check nodes the game shows done."""
        from ..data_lab import (ATTACK_PER_NODE, LAB_ATTACK, LAB_ATTACK_FIELD, WEAPON_LAB_ATTACK, LAB_CAPACITY_FIELD, LAB_MIRROR, LAB_NODE_COUNT, LAB_NODES, LAB_ROW_ANCHOR,
                                LAB_ROW_SIZE, LAB_WEAPON_FIELD, lab_state_target)
        from ..data_rewards import BLOCK_SAVED_COPY, FLAGS, PROFILE
        # The lab shows on the map only with this flag, set by Road to the Ancient Lab's clear [confirmed live 2026-11-04].
        flags = self._ptr(FLAGS)
        if self.g.read(flags + LAB_VISIBLE_FLAG, 1) != b"":
            for copy in (0, BLOCK_SAVED_COPY[FLAGS]):
                self._write(flags + copy + LAB_VISIBLE_FLAG, b"")
        states_at = self._ptr(LAB_STATES[0]) + LAB_STATES[1]
        mirror_at = self._ptr(LAB_MIRROR[0]) + LAB_MIRROR[1]
        states = self.g.read(states_at, LAB_NODE_COUNT)
        if states is None or not all(1 <= s <= 3 for s in states):
            raise HookError("lab states not recognised")
        held = held or {}
        done_now = [n.name for n in LAB_NODES if states[n.index] == 3 and n.name in check_nodes]
        for i, state in enumerate(states):
            want = lab_state_target(i, state, held, bought)
            if want != state:
                self._write(states_at + i, bytes([want]))
                self._write(mirror_at + i, bytes([want]))
        row0 = self._lab_row0()
        if row0 is None:
            raise HookError("lab table not found")
        for node in LAB_NODES:
            row = row0 + (node.index - LAB_ROW_ANCHOR) * LAB_ROW_SIZE
            fields = []
            if node.kind == "weapon":
                fields += [(LAB_WEAPON_FIELD, 2), (LAB_ATTACK_FIELD, 2)]
            if node.kind == "attack":
                fields += [(LAB_ATTACK_FIELD, 2), (0x3D, 2)]
            if node.kind == "hero":
                fields.append((0x3C, 1))
            if node.kind == "count" and node.index in (13, 14):
                fields.append((LAB_CAPACITY_FIELD, 2))
            for field, size in fields:
                if self.g.read(row + field, size) != bytes(size):
                    self._write(row + field, bytes(size))
        for (block, offset), value in values.items():
            base = self._ptr(block)
            if self.g.read(base + offset, 1) != bytes([value]):
                self._write(base + offset, bytes([value]))
                if block in (FLAGS, PROFILE):
                    self._write(base + BLOCK_SAVED_COPY[block] + offset, bytes([value]))
        for item, (byte, hero, weapons) in LAB_ATTACK.items():
            kinds = {S.WEAPON_KINDS[w][0] for w in weapons}
            bonus = values.get(byte, 0) * ATTACK_PER_NODE
            for slot, kind in enumerate(self.hero_weapons(hero)):
                if kind in kinds:
                    offset = (S.HERO_SLOTS[hero] * WEAPONS_PER_HERO + slot) * WEAPON_RECORD + WEAPON_LAB_ATTACK
                    for base in self._weapon_pools():
                        if self.g.read(base + offset, 2) != struct.pack("<H", bonus):
                            self._write(base + offset, struct.pack("<H", bonus))
        return done_now

    # The lab's selected node [found live 2026-11-04]: the panel keeps a pointer to its title, UTF-16 at pointer + 6, in a heap object
    # that moves each boot. A scan lists every pointer to a node title; the one whose title changes to another node's is the panel's.

    def _lab_title(self, holder: int) -> str | None:
        from ..data_lab import LAB_BY_NAME
        raw = self.g.read(holder, 8)
        target = struct.unpack("<Q", raw)[0] if raw else 0
        text = self.g.read(target + 6, 100) if target else None
        if not text:
            return None
        title = text.decode("utf-16-le", "replace").split("\0")[0]
        return title if title in LAB_BY_NAME else None

    def lab_scan(self) -> None:
        """Slow (about 2 s, run it off the client's main loop): list the pointers to node titles."""
        from ..data_lab import LAB_NODES
        holder = self.g.u64(QUEST_UNLOCKS[0])
        table = self.g.u64(holder + QUEST_UNLOCKS[1]) if holder else None
        if not table:
            return
        names = re.compile(b"|".join(re.escape(n.name.encode("utf-16-le") + b"\0\0") for n in LAB_NODES))
        regions = [(a, self.g.read(a, 1 << 20)) for a in range(table - (1 << 30), table + (1 << 30), 1 << 20)]
        regions = [(a, d) for a, d in regions if d]
        heads = {a + m.start() - 6 for a, d in regions for m in names.finditer(d)}
        if not heads:
            return
        pointers = re.compile(b"|".join(re.escape(struct.pack("<Q", h)) for h in heads))
        found = {a + m.start() for a, d in regions for m in pointers.finditer(d) if (a + m.start()) % 8 == 0}
        self._lab_candidates = {h: self._lab_title(h) for h in found}

    def lab_needs_scan(self) -> bool:
        return getattr(self, "_lab_holder", None) is None and not getattr(self, "_lab_candidates", None)

    def lab_selected_node(self) -> str | None:
        """The node the lab panel shows; None until the player has moved the cursor once (nothing to tell the pointers apart)."""
        holder = getattr(self, "_lab_holder", None)
        if holder is not None:
            title = self._lab_title(holder)
            if title:
                return title
            self._lab_holder = None
        kept = {}
        for address, old in getattr(self, "_lab_candidates", {}).items():
            title = self._lab_title(address)
            if title and old and title != old:
                self._lab_holder, self._lab_candidates = address, {}
                return title
            if title:
                kept[address] = title
        self._lab_candidates = kept
        return None

    def _quest_table(self) -> int | None:
        """The quest table in memory, recognised by the type bytes of known quests (research 36, royal gift 51)."""
        holder = self.g.u64(QUEST_UNLOCKS[0])
        table = self.g.u64(holder + QUEST_UNLOCKS[1]) if holder else None
        if not table:
            return None

        def good(base: int) -> bool:
            return (self.g.read(base + 0x10 + 362 * QUEST_ROW + QUEST_ROW_TYPE, 1) == b"\x24"
                    and self.g.read(base + 0x10 + 455 * QUEST_ROW + QUEST_ROW_TYPE, 1) == b"\x33")
        known = getattr(self, "_quest_table_distance", QUEST_TABLE_DISTANCE)
        if good(table + known):
            return table + known
        for off in range(-(64 << 20), 64 << 20, 1 << 20):
            data = self.g.read(table + off, 1 << 20)
            if not data:
                continue
            for at in range(0, len(data), 16):  # (allocations are 16-aligned)
                if data[at:at + 4] == b"\0\0\0\0" and good(table + off + at):
                    self._quest_table_distance = off + at
                    return table + off + at
        return None

    def empty_quest_rows(self, quests: list[str]) -> list[str]:
        """Take the rewards out of these quests' table rows, so buying one only sends its check: the weapon (+0x1C, type
        51), the material and outfit (+0x30..+0x3F, type 36) or The Master Chef's rupees (+0x0C u32, type 42). Rows the
        game put back are emptied again."""
        table = self._quest_table()
        if table is None:
            raise HookError("quest table not found")
        changed = []
        for name in quests:
            row = table + 0x10 + S.QUEST_STATE_IDS[name] * QUEST_ROW
            kind = self.g.read(row + QUEST_ROW_TYPE, 1)
            fields = {b"\x33": ((0x1C, 2), (0x30, 0x10)), b"\x2a": ((0x0C, 4),)}.get(kind, ((0x30, 0x10),))
            for field, size in fields:
                if self.g.read(row + field, size) != bytes(size):
                    self._write(row + field, bytes(size))
                    if name not in changed:
                        changed.append(name)
        return changed

    def set_quest_states(self, states: dict[str, int]) -> list[str]:
        """Keep quests at a state (current and saved copy): 3 done, 1 not available, 2 at least available (a quest the
        game already shows or has done is left as it is), -1 not available unless already done. Services that follow the quest state open only by items,
        and a held-back quest can't be handed in. Returns the quests changed."""
        base = self._ptr(QUESTS) + S.QUEST_STATE_LIVE
        blob = self.g.read(base, S.QUEST_STATE_COUNT)
        if blob is None or max(blob) > S.QUEST_DONE:
            raise HookError("quest states not recognised")
        changed = []
        try:  # the icons are cosmetic: never let them stop the quest states
            map_base = self._ptr(MISSION_STATES_BLOCK) + QUEST_MAP_STATES
            maps = [(copy, self.g.read(map_base + copy, S.QUEST_STATE_COUNT)) for copy in (0, QUEST_MAP_SAVED_COPY)]
        except HookError:
            maps = []
        for name, want in sorted(states.items()):
            i = S.QUEST_STATE_IDS[name]
            if want == S.QUEST_DONE:
                for copy, icons in maps:
                    if icons is not None and icons[i] != S.QUEST_DONE:
                        self._write(map_base + copy + i, bytes([S.QUEST_DONE]))
            if want == -1:  # hidden: the map icon goes too (it kept showing a quest the game had reopened)
                for copy, icons in maps:
                    if icons is not None and icons[i] == 2:
                        self._write(map_base + copy + i, bytes([1]))
            if (want == 2 and blob[i] >= 2) or (want == -1 and blob[i] != 2):
                continue  # already open / never undo a quest the player has handed in
            want = abs(want)
            if blob[i] != want:
                for copy in (0, QUEST_SAVED_COPY):
                    self._write(base + copy + i, bytes([want]))
                changed.append(name)
        return changed

    def _quest_map_done(self, i: int) -> None:
        """Show quest state id `i` as done on the world map too (both copies; cosmetic, so a missing block is skipped)."""
        try:
            base = self._ptr(MISSION_STATES_BLOCK) + QUEST_MAP_STATES + i
        except HookError:
            return
        for copy in (0, QUEST_MAP_SAVED_COPY):
            raw = self.g.read(base + copy, 1)
            if raw is not None and raw[0] != S.QUEST_DONE:
                self._write(base + copy, bytes([S.QUEST_DONE]))

    def set_quest_effects(self, quests: set[str]) -> list[str]:
        """Set the bytes these done quests would have set in game (data_save.QUEST_EFFECTS). Returns quests changed."""
        changed = []
        for quest in sorted(quests):
            for block, offset, value in S.QUEST_EFFECTS.get(quest, ()):
                addr = self._ptr(block) + offset
                raw = self.g.read(addr, 1)
                if raw is not None and raw[0] != value:
                    self._write(addr, bytes([value]))
                    if quest not in changed:
                        changed.append(quest)
        return changed

    def complete_quest(self, name: str) -> bool:
        """Mark a quest done (current and saved copy); the Smithy opens this way. Returns True if it changed."""
        base = self._ptr(QUESTS) + S.QUEST_STATE_LIVE
        blob = self.g.read(base, S.QUEST_STATE_COUNT)
        if blob is None or max(blob) > S.QUEST_DONE:
            raise HookError("quest states not recognised")
        i = S.QUEST_STATE_IDS[name]
        self._quest_map_done(i)
        if blob[i] == S.QUEST_DONE:
            return False
        for copy in (0, QUEST_SAVED_COPY):
            self._write(base + copy + i, bytes([S.QUEST_DONE]))
        return True

    def set_hero(self, character: str, unlocked: bool) -> bool:
        """Lock or unlock a hero. Returns True if anything changed."""
        if character not in S.HERO_SLOTS:
            return False
        want = b"\x01\x01\x01" if unlocked else b"\x00\x00\x00"
        addr = self._hero_addr(character) + HERO_FLAGS
        if self.g.read(addr, 3) == want:
            return False
        for copy in (0, HERO_SAVED_COPY):
            self._write(addr + copy, want)
        return True


    # --- story parties ---------------------------------------------------------------------

    def _params(self, layout: tuple[int, int, int] = PARAMS) -> int:
        holder = self.g.u64(layout[0])
        if not holder or not 0x1000 < holder < 1 << 40:
            raise HookError("mission data not loaded")
        table = self.g.u64(holder + layout[1])
        if not table or not 0x1000 < table < 1 << 40:
            raise HookError("mission data not loaded")
        table += layout[2]
        if self.g.read(table, 8) != struct.pack("<II", S.MISSION_RECORD_COUNT, 0):
            raise HookError("mission data table not recognised")
        return table

    def _battle_character(self) -> int | None:
        """The character you control in a mission, or None outside missions (or if anything looks wrong)."""
        def ptr(va: int) -> int | None:
            raw = self.g.read(va, 8)
            v = struct.unpack("<Q", raw)[0] if raw else 0
            return v if 0x10_0000_0000 <= v < 0x24_0000_0000 else None
        holder = ptr(BATTLE)
        player = ptr(holder + BATTLE_PLAYER) if holder else None
        char = ptr(player + BATTLE_CHARACTER) if player else None
        if not char:
            return None
        raw = self.g.read(char + CHAR_HP, 8)
        if not raw:
            return None
        hp, top = struct.unpack("<ff", raw)
        return char if 400 <= top <= 60000 and -1 <= hp <= top + 1 else None

    def _unit_hp(self, char: int) -> int | None:
        """Address of the real HP of the character at char (its unit table record), or None if it doesn't match."""
        raw = self.g.read(char, 8)
        count = self.g.read(UNIT_COUNT, 4)
        table = self.g.read(UNITS, 8)
        if not raw or not count or not table:
            return None
        unit, kind = struct.unpack("<II", raw)
        holder = struct.unpack("<Q", table)[0]
        if unit >= struct.unpack("<I", count)[0] or not 0x1000 < holder < 1 << 40:
            return None
        raw = self.g.read(holder + UNITS_TABLE, 8)
        units = struct.unpack("<Q", raw)[0] if raw else 0
        if not 0x1000 < units < 1 << 40:
            return None
        record = units + UNIT_RECORDS + unit * UNIT_SIZE
        raw = self.g.read(record, UNIT_HP + 12)
        if raw and struct.unpack_from("<II", raw) == (unit, kind):
            hp, _, top = struct.unpack_from("<fff", raw, UNIT_HP)
            return record + UNIT_HP if 400 <= top <= 60000 and -1 <= hp <= top + 1 else None
        # char's first field isn't always its record (Eden 2026-11-02: it read 0 while the hero was record 50, same
        # kind): find the record of that kind whose HP matches the display copy
        shown = self.g.read(char + CHAR_HP, 8)
        n = struct.unpack("<I", count)[0]
        table_raw = self.g.read(units + UNIT_RECORDS, n * UNIT_SIZE)
        if not shown or not table_raw:
            return None
        want = struct.unpack("<ff", shown)
        for i in range(n):
            base = i * UNIT_SIZE
            if struct.unpack_from("<II", table_raw, base) != (i, kind):
                continue
            hp, _, top = struct.unpack_from("<fff", table_raw, base + UNIT_HP)
            if (hp, top) == want and 400 <= top <= 60000:
                return units + UNIT_RECORDS + base + UNIT_HP
        return None

    def player_hp(self) -> float | None:
        """HP of the character you control (None outside missions): the real value, else the display copy."""
        char = self._battle_character()
        if not char:
            return None
        real = self._unit_hp(char)
        return struct.unpack("<f", self.g.read(real or char + CHAR_HP, 4))[0]

    def _flow(self) -> tuple[int, int, int] | None:
        """(mission flow object, current state low byte, pending request), or None if unreadable."""
        raw = self.g.read(UNITS, 8)
        flow = struct.unpack("<Q", raw)[0] if raw else 0
        raw = self.g.read(flow + FLOW_STATE, 12) if 0x1000 < flow < 1 << 40 else None
        if not raw:
            return None
        state, _, request = struct.unpack("<III", raw)
        return flow, state & 0xFF, request

    def _rod_uses_address(self) -> int | None:
        """Address of the rods' uses-left counters in the running mission, None outside missions."""
        if not self._battle_character():
            return None
        def ptr(va: int) -> int | None:
            raw = self.g.read(va, 8)
            v = struct.unpack("<Q", raw)[0] if raw else 0
            return v if 0x10_0000_0000 <= v < 0x24_0000_0000 else None
        holder = ptr(BATTLE)
        player = ptr(holder + BATTLE_PLAYER) if holder else None
        pouch = ptr(player + ROD_POUCH) if player else None
        return pouch + ROD_USES if pouch else None

    def hold_rods(self, locked: list[bool]) -> list[str]:
        """Item palette lock (rod_items, apple_items): every locked item (data.PALETTE_ITEMS) is held at 0 (one picked
        up in the mission is taken away again); one whose item arrived mid-mission gets back what it was held from.
        Returns what changed ("Fire Rod held", "Apples given back")."""
        from ..data import PALETTE_ITEMS as RODS
        addr = self._rod_uses_address()
        if addr is None:
            self._rods_held, self._rod_pouch = {}, 0
            return []
        if addr != self._rod_pouch:  # a new mission (or a restart): nothing held yet
            self._rods_held, self._rod_pouch = {}, addr
        raw = self.g.read(addr, PALETTE_USES[-1] + 4)
        if not raw:
            return []
        uses = [struct.unpack_from("<I", raw, o)[0] for o in PALETTE_USES]
        if max(uses) > 50:
            return []  # not the rods (layout not recognised)
        changed = []
        for slot, (rod, lock, have) in enumerate(zip(RODS, locked, uses)):
            if lock and have:
                self._rods_held[slot] = max(have, self._rods_held.get(slot, 0))
                self._write(addr + PALETTE_USES[slot], struct.pack("<I", 0))
                changed.append(f"{rod} held")
            elif not lock and slot in self._rods_held:
                give = self._rods_held.pop(slot)
                if have == 0:
                    if give == 0 and slot < 3:
                        give = self._rod_start(slot)
                    if give:
                        self._write(addr + PALETTE_USES[slot], struct.pack("<I", give))
                        changed.append(f"{rod} given back")
            elif lock:
                self._rods_held.setdefault(slot, 0)
        return changed

    def set_rod_flags(self, have: list[bool | None]) -> list[str]:
        """Item palette unlocks (rod_items, apple_items): each item's obtained flag (current and saved copy), in
        data.PALETTE_ITEMS order (Fire, Ice, Lightning Rod, Apples; None = leave that one alone), so a locked item has no
        palette slot from the next mission on. A rod given gets the base 2 uses if its start count is 0 (a fresh save);
        apples given with none carried get 5 plain apples. Returns what changed ("Fire Rod shown", "Apples hidden")."""
        from ..data import PALETTE_ITEMS
        base = self._ptr(STORY_FLAGS)
        flags = [self.g.read(base + off, 1) for off in PALETTE_FLAGS]
        if any(not f or f[0] > 1 for f in flags):
            raise HookError("item palette flags not recognised")
        changed = []
        for slot, (item, want) in enumerate(zip(PALETTE_ITEMS, have)):
            if want is None:
                continue
            for copy in ROD_FLAG_COPIES:
                cur = self.g.read(base + copy + PALETTE_FLAGS[slot], 1)
                if cur and cur[0] != int(want):
                    self._write(base + copy + PALETTE_FLAGS[slot], bytes([int(want)]))
                    if copy == 0:
                        changed.append(f"{item} {'shown' if want else 'hidden'}")
            if not want:
                continue
            if slot < 3:
                for copy in (0, 3 * 0x700):
                    start = self.g.read(base + copy + ROD_START + slot, 1)
                    if start and start[0] == 0:
                        self._write(base + copy + ROD_START + slot, bytes([2]))
            else:
                for copy in ROD_FLAG_COPIES:
                    total = self.g.read(base + copy + APPLE_TOTAL, 1)
                    kinds = self.g.read(base + copy + APPLE_TOTAL + 2, 7)
                    if total == bytes(1) and kinds == bytes(7):
                        self._write(base + copy + APPLE_TOTAL, bytes([5]))
                        self._write(base + copy + APPLE_PLAIN, bytes([5]))
        return changed

    def _rod_start(self, slot: int) -> int:
        """A rod's start-of-mission uses from the save's table B (0 if unreadable)."""
        try:
            raw = self.g.read(self._ptr(STORY_FLAGS) + ROD_START + slot, 1)
        except HookError:
            return 0
        return raw[0] if raw and 0 < raw[0] <= 20 else 0

    def deathlink_hook_active(self) -> bool:
        """The game mod's DeathLink hook (0.9.91, rune_mod.DEATHLINK_*) is in the running game."""
        from .rune_mod import DEATHLINK_HOOK, DEATHLINK_HOOK_CODE
        return self.g.read(MODULE_BASE + DEATHLINK_HOOK, 4) == DEATHLINK_HOOK_CODE

    def kill_player(self) -> bool:
        """DeathLink: real HP (and the display copy) to 0, then (game mod 0.9.91+) the game's own "unit defeated" for the
        hero through the mod's hook: the KO, the mission script's EndBattle and the normal defeat menu ~2 s later, no
        hit needed [Eden 2026-11-19]. self.instant_kill says whether that happened; without the hook the HP is held at
        0 by hold_death and the next hit is the KO (as before). Forcing the flow states instead froze the game on the
        defeat picture. Returns False outside play (no character, real HP not found, or not playing)."""
        char = self._battle_character()
        real = self._unit_hp(char) if char else None
        flow = self._flow()
        if not real or not flow or flow[1:] != (FLOW_PLAYING, 0):
            return False
        self._write(real, struct.pack("<f", 0.0))
        self._write(char + CHAR_HP, struct.pack("<f", 0.0))
        self.instant_kill = False
        if self.deathlink_hook_active():
            from .rune_mod import DEATHLINK_REQUEST
            unit = struct.unpack("<I", self.g.read(real - UNIT_HP, 4))[0]  # (the unit record starts with its index)
            self._write(MODULE_BASE + DEATHLINK_REQUEST, struct.pack("<I", unit + 1))
            self.instant_kill = True
        self._hold_clock = struct.unpack("<I", self.g.read(flow[0] + FLOW_CLOCK, 4))[0]
        self._hold_reals = {char: real}
        return True

    def death_can_land(self) -> bool:
        """In a mission and not already defeated (a pause menu counts: a received death waits for it to close)."""
        flow = self._flow()
        return self._battle_character() is not None and bool(flow) and flow[1] not in FLOW_OVER

    def hold_death(self) -> bool:
        """After kill_player: keep the party at 0 HP until the hit lands, whoever you switch to (a hero switched in shows
        their health for up to a tick). False once it is over: the game left play (the KO), the mission ended, or the
        attempt's clock went back (a restart from the pause menu)."""
        char = self._battle_character()
        real = self._unit_hp(char) if char else None
        # (On Eden the real HP is found by matching the shown HP: an apple picked up with a full pouch heals both apart, so
        # the match failed and the hold ended, healing the player: user, 2026-11-07. Keep each hero's address once found.)
        reals = getattr(self, "_hold_reals", {})
        real = real or reals.get(char)
        if char and real:
            reals[char] = real
        flow = self._flow()
        if not real or not flow or flow[1] in FLOW_OVER:  # (a pause menu keeps the hold)
            return False
        clock = struct.unpack("<I", self.g.read(flow[0] + FLOW_CLOCK, 4))[0]
        if clock < getattr(self, "_hold_clock", 0):
            return False
        self._hold_clock = clock
        self._write(char + CHAR_HP, struct.pack("<f", 0.0))
        self._write(real, struct.pack("<f", 0.0))
        return True

    def reward_table(self) -> int:
        """Address of the live mission reward table (data_mission_rewards), found once by its vanilla header and first
        rows near the mission parameter table (the game loads its data tables together)."""
        from .. import data_mission_rewards as R
        cached = getattr(self, "_reward_table", None)
        if cached and self.g.read(cached, 8) == R.TABLE[:8]:
            return cached
        params = self._params()
        signature = R.TABLE[:R.HEADER + 3 * R.ROW_SIZE]
        chunk = 1 << 20
        for distance in range(0, REWARD_SEARCH, chunk):
            for start in {params - distance - chunk, params + distance}:
                data = self.g.read(start, chunk + len(signature))
                if not data:
                    continue
                i = data.find(signature)
                if i >= 0:
                    self._reward_table = start + i
                    return self._reward_table
        raise HookError("mission reward table not found")

    def set_mission_rewards(self, rows: dict[int, bytes]) -> list[int]:
        """Write mission reward rows (record -> 64 bytes). Returns the records changed."""
        from .. import data_mission_rewards as R
        table = self.reward_table()
        changed = []
        for record, row in sorted(rows.items()):
            addr = table + R.HEADER + record * R.ROW_SIZE
            if self.g.read(addr, R.ROW_SIZE) != row:
                self._write(addr, row)
                changed.append(record)
        return changed

    def _state_lists(self) -> tuple[list[tuple[int, int]], list[bytes]]:
        """The four per-mission state lists as (address, value meaning locked), with their current bytes."""
        lists = [(self._ptr(PROFILE) + offset, 1) for offset in MISSION_STATES_PROFILE]
        lists += [(self._ptr(MISSION_STATES_BLOCK) + offset, 0) for offset in MISSION_STATES_MAP]
        blobs = [self.g.read(addr, S.MISSION_RECORD_COUNT) for addr, _ in lists]
        if any(b is None or max(b) > 3 for b in blobs):
            raise HookError("mission states not recognised")
        return lists, blobs

    def set_mission_states(self, open_missions: set[str]) -> list[int]:
        """Update the per-mission states the world map draws from, so opened/locked missions show at once instead of
        after the next mission. Profile list: 1 locked, 2 open, 3 cleared (current + saved copy); the map-state block
        uses 0 for locked (two copies). Cleared missions are never touched. Returns the records changed."""
        lists, blobs = self._state_lists()
        changed = []
        for name in S.MISSION_RECORD_IDS:
            record = S.MISSION_RECORD_IDS[name][0]
            if record not in S.VANILLA_STORY_UNLOCK:
                continue
            for (addr, locked), blob in zip(lists, blobs):
                if blob[record] == 3:
                    continue
                want = 2 if name in open_missions else locked
                if blob[record] != want:
                    self._write(addr + record, bytes([want]))
                    if record not in changed:
                        changed.append(record)
        return changed

    def raise_difficulty(self, minimum: int) -> int | None:
        """difficulty_lock (0.9.87): the game's difficulty setting is [P+0x5B0]+0x123, four copies 0xE0 apart, values
        1 Easy, 2 Normal, 3 Hard, 4 Very Hard (5 Apocalyptic, guessed) [confirmed 2026-11-13 on Eden: the Options menu
        shows a written value]. Raises it to `minimum` when lower; returns the old value if it changed, else None."""
        base = self._ptr(OPTIONS) + DIFFICULTY_SETTING
        values = [self.g.read(base + k * OPTIONS_COPY, 1) for k in range(4)]
        if any(v is None or not 1 <= v[0] <= 5 for v in values):
            raise HookError("difficulty setting not recognised")
        old = values[0][0]
        if all(v[0] >= minimum for v in values):
            return None
        for k in range(4):
            self._write(base + k * OPTIONS_COPY, bytes([max(values[k][0], minimum)]))
        return old

    def hold_rune_mission(self, hold: bool) -> bool:
        """Rune lock (0.9.87): at mission load the game gives Magnesis and Stasis when their story flag is set OR Road to
        the Ancient Lab's PROFILE mission state is 3 [confirmed 2026-11-09, Eden: profile lists only at 2 removed them;
        clear times and map lists don't matter]. hold=True keeps a cleared Road's profile state (current and saved copy)
        at 2 so the flags decide; hold=False puts 3 back once Road has a clear time. Clear times, the map lists and the
        missions Road unlocks are untouched (the game's unlock checks and the client both read clears). Side effects
        while held [seen]: Road shows no COMPLETE in the Chapters list and the load-screen clear count is one lower.
        Returns True when something was written."""
        lists, blobs = self._state_lists()
        record = S.MISSION_RECORD_IDS["Road to the Ancient Lab"][0]
        if hold:
            want, only = 2, 3
        elif record in self.cleared_records():
            want, only = 3, 2
        else:
            return False
        wrote = False
        for (addr, _), blob in zip(lists[:len(MISSION_STATES_PROFILE)], blobs):
            if blob[record] == only:
                self._write(addr + record, bytes([want]))
                wrote = True
        return wrote

    def set_mission_locks(self, open_missions: set[str] | None) -> list[int]:
        """Make the game's own unlock rules follow the multiworld: every story mission in open_missions has no
        prerequisites, every other one requires the final mission. None puts the vanilla rules back.
        Returns the records changed."""
        table = self._params(UNLOCKS)
        if self.g.read(table + 16 + 9 * S.UNLOCK_ROW_SIZE, 2) != b"\x00\x00":
            raise HookError("mission unlock table not recognised")
        changed = []
        for name in S.MISSION_RECORD_IDS:
            record = S.MISSION_RECORD_IDS[name][0]
            if record not in S.VANILLA_STORY_UNLOCK:
                continue
            if open_missions is None:
                want = bytes.fromhex(S.VANILLA_STORY_UNLOCK[record])
            elif name in open_missions:
                want = bytes(10)
            else:
                want = struct.pack("<H", LOCK_RECORD) + bytes(8)
            addr = table + 16 + record * S.UNLOCK_ROW_SIZE + S.UNLOCK_OFFSET
            if self.g.read(addr, len(want)) != want:
                self._write(addr, want)
                changed.append(record)
        return changed

    def set_quest_locks(self, rows: dict[str, tuple[tuple[int, ...], tuple[int, ...]]]) -> list[str]:
        """Rewrite quest rows of the quest unlock table: quest -> (records, quests) it needs (up to five each).
        Returns the quests whose row changed."""
        holder = self.g.u64(QUEST_UNLOCKS[0])
        table = self.g.u64(holder + QUEST_UNLOCKS[1]) if holder else None
        if not table:
            raise HookError("quest unlock table not loaded")
        table += QUEST_UNLOCKS[2]
        if self.g.read(table, 8) != struct.pack("<II", QUEST_UNLOCK_ROWS, 0):
            raise HookError("quest unlock table not recognised")
        changed = []
        for name, (records, quests) in sorted(rows.items()):
            i = S.QUEST_STATE_IDS[name]
            if i >= QUEST_UNLOCK_ROWS:
                continue
            addr = table + 16 + i * QUEST_UNLOCK_SIZE + 4
            want = struct.pack("<5H5H", *(list(records[:5]) + [0] * (5 - len(records[:5]))),
                               *(list(quests[:5]) + [0] * (5 - len(quests[:5]))))
            if self.g.read(addr, len(want)) != want:
                self._write(addr, want)
                changed.append(name)
        return changed

    def set_challenge_locks(self, unlocks: dict[int, tuple[int, ...]] | None) -> list[int]:
        """Rewrite challenge rows of the unlock table: each record in unlocks requires exactly those records (up to
        five) and no quests; None puts the vanilla rows back. With unlocks, the map states of uncleared challenges
        follow too (open once every required record is cleared). Returns the records whose row changed."""
        table = self._params(UNLOCKS)
        if self.g.read(table + 16 + 9 * S.UNLOCK_ROW_SIZE, 2) != b"\x00\x00":
            raise HookError("mission unlock table not recognised")
        changed = []
        for record, vanilla_hex in S.VANILLA_CHALLENGE_UNLOCK.items():
            if unlocks is None:
                want = bytes.fromhex(vanilla_hex)
            elif record in unlocks:
                want = struct.pack("<5H", *unlocks[record][:5], *[0] * (5 - len(unlocks[record][:5])))
                want += bytes(S.CHALLENGE_UNLOCK_SIZE - len(want))
            else:
                continue
            addr = table + 16 + record * S.UNLOCK_ROW_SIZE + S.UNLOCK_OFFSET
            if self.g.read(addr, len(want)) != want:
                self._write(addr, want)
                changed.append(record)
        if unlocks:
            cleared = self.cleared_records()
            lists, blobs = self._state_lists()
            for record, needs in unlocks.items():
                for (addr, locked), blob in zip(lists, blobs):
                    want = 2 if all(r in cleared for r in needs) else locked
                    if blob[record] != 3 and blob[record] != want:
                        self._write(addr + record, bytes([want]))
        return changed

    def set_story_parties(self, heroes: list[str] | None, challenges: bool = False,
                          skip: frozenset[int] = frozenset()) -> list[str]:
        """Give every story mission (with challenges=True every challenge too, the Expansion Pass story included) this
        party in place of its forced heroes (hero slots only; Divine Beast segments and empty slots stay; a mission's
        support heroes are skipped). heroes=None puts the vanilla parties back. Returns the records changed."""
        table = self._params()
        changed = []
        rows = {**S.VANILLA_STORY_PARTY, **(S.VANILLA_CHALLENGE_PARTY if challenges or heroes is None else {})}
        for record, vanilla_hex in rows.items():
            if record in skip and heroes is not None:  # (records left vanilla, e.g. the DLC without include_dlc)
                continue
            vanilla = bytes.fromhex(vanilla_hex)
            want = bytearray(vanilla)
            if heroes is not None:
                # a forced slot keeps its vanilla hero when that hero is yours (the story's own pilots, e.g. Sidon in
                # Water and Fire); the others get your strongest remaining heroes (user: the client forced Calamity
                # Ganon over Sidon)
                # The free slots stay the player's choice, so a forced slot whose hero you don't have takes your
                # lowest-level heroes, never one the mission needs from the start (forced slots can join late:
                # Mipha put in Daruk's slot 4 of Relentless as a Waterfall softlocked it - user, 2026-11-01).
                support = (set(S.STORY_SUPPORT.get(record, ())) | set(S.STORY_NEEDED_EARLY.get(record, ()))
                           | set(S.CHALLENGE_SUPPORT.get(record, ())))
                yours = {S.HERO_SLOTS[h] + 1 for h in heroes if h in S.HERO_SLOTS}
                kept = {b for b in vanilla if 0 < b < 40 and b in yours}
                order = reversed(heroes) if 0 in vanilla else heroes  # all slots forced: your strongest
                pick = iter(S.HERO_SLOTS[h] + 1 for h in order
                            if h in S.HERO_SLOTS and h not in support and S.HERO_SLOTS[h] + 1 not in kept)
                for i, b in enumerate(vanilla):
                    if 0 < b < 40:
                        want[i] = b if b in kept else next(pick, 0)
            addr = table + 16 + record * S.PARTY_ROW_SIZE + S.PARTY_OFFSET
            if self.g.read(addr, 4) != bytes(want):
                self._write(addr, bytes(want))
                changed.append(record)
        return changed

    def best_heroes(self, characters: set[str]) -> list[str]:
        """The given heroes, highest level first (ties in roster order)."""
        known = [c for c in characters if c in S.HERO_SLOTS]
        return sorted(known, key=lambda c: (-self.hero_level(c), S.HERO_SLOTS[c]))


def stride_of(layout: tuple[int, int, int]) -> int:
    return layout[2]
