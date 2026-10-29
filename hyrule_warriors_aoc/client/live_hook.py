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
import struct
import sys
import time

from .. import data_save as S
from .ryujinx import MODULE_BASE, Guest, Process, ryujinx_pids

MANAGER = MODULE_BASE + 0x2780A48
PARAMS = (MODULE_BASE + 0x2780A38, 0x698, 0x60)  # [[global]+0x698]+0x60 = mission parameter table (400 rows)
UNLOCKS = (MODULE_BASE + 0x2780A38, 0x308, 0x60)  # mission unlock table (which cleared missions open a mission)
# Quest unlock table (LinkData2 0086e814) in the same param holder: 1000 rows of 36 bytes after a 16-byte header,
# row = quest state id: +4 five u16 mission/challenge records, +14 five u16 quests it needs [read live 2026-10-28]
QUEST_UNLOCKS = (MODULE_BASE + 0x2780A38, 0x300, 0x60)
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
UNIT_RECORDS, UNIT_SIZE, UNIT_HP = 0x176E70, 0x6C, 0x44
# HP 0 alone never KOs (the game checks it only when a hit lands). The mission flow state is a u32 at
# [module + 0x2780A80] + 0xB0 (low byte: 0 = playing, 4 = defeated, 12 = retry); a request posted at +0xB8 (with flag
# byte 2 at +0xB3, as the game does) is taken on the next frame. Posting 4 then 12 restarts the mission like a defeat
# + Retry; 4 alone soft-locks (no death animation, so no defeat screen) [both confirmed in game 2026-10-27].
FLOW_STATE, FLOW_FLAGS, FLOW_REQUEST = 0xB0, 0xB3, 0xB8
FLOW_PLAYING, FLOW_DEFEATED, FLOW_RETRY = 0, 4, 12
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
# Story flag table (save 0x14..0x8F, one byte each) at [P+0x550]+0x18C; four copies 0x700 apart: 0 current (read live,
# even mid-mission), 3 saved, 1/2 a mission's working copies. Rune flags confirmed in game by setting/clearing them.
STORY_FLAGS, STORY_FLAGS_OFFSET, STORY_FLAGS_COPIES = 0x550, 0x18C, (0, 3 * 0x700)
RUNE_FLAGS = {"Remote Bombs": 0x19 - 0x14, "Cryonis": 0x1A - 0x14, "Magnesis": 0x1B - 0x14, "Stasis": 0x1C - 0x14}
# (Remote Bombs = the Slate: off hides the whole rune menu; confirmed in game, RESEARCH session 18)
# Owned weapons: [P + 0x568] holds the pool objects; [[pool + 0x30]] is the current copy, [[pool + 0x48]] the
# saved one. 2139 records of 0x90 bytes, 71 per hero (hero slot * 71). Record: +0x00 order (u32), +0x10 weapon
# kind (u16, each hero has its own range), +0x79 level. The save stores the same pool as 81-byte records.
WEAPON_POOL, WEAPON_COPIES = 0x568, (0x30, 0x48)
WEAPON_RECORD, WEAPONS_PER_HERO, WEAPON_RECORDS = 0x90, 71, 2139
WEAPON_KIND, WEAPON_LEVEL = 0x10, 0x79


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

    # --- attaching ------------------------------------------------------------------------

    @classmethod
    def find(cls) -> "LiveGame | None":
        """Attach to the first Ryujinx process that is running Age of Calamity with a save loaded."""
        for pid in ryujinx_pids():
            try:
                proc = Process(pid)
            except OSError:
                continue
            guest = Guest.attach(proc)
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

    # --- reading --------------------------------------------------------------------------

    def cleared_records(self) -> set[int]:
        field, offset, stride = MISSIONS
        base = self._ptr(field) + offset
        blob = self.g.read(base, S.MISSION_RECORD_COUNT * stride)
        if blob is None:
            raise HookError("mission table unreadable")
        return {i for i in range(S.MISSION_RECORD_COUNT) if any(struct.unpack_from("<6I", blob, i * stride))}

    def cleared_missions_at(self, min_slot: int) -> set[str]:
        """Missions with a clear time on difficulty slot min_slot or any higher one (a harder clear counts for every
        easier difficulty)."""
        field, offset, stride = MISSIONS
        base = self._ptr(field) + offset
        blob = self.g.read(base, S.MISSION_RECORD_COUNT * stride)
        if blob is None:
            raise HookError("mission table unreadable")
        done = {i for i in range(1, S.MISSION_RECORD_COUNT)
                if any(struct.unpack_from("<6I", blob, i * stride + DIFFICULTY_TIMES)[min_slot:S.DIFFICULTY_SLOTS])}
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

    def material_bundle(self, seed: int, kinds: int = 3, amount: int = 5) -> str:
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

    def weapon_level_up(self, characters: list[str]) -> str:
        """Weapon XP Gift: +1 level to the equipped weapon of the hero whose equipped weapon is lowest, never above
        the game's current cap (20, or 25 once A Monumental Undertaking's flag is set)."""
        flags = self._ptr(0x5A0)
        monument = self.g.read(flags + 0x63F, 1)
        cap = S.WEAPON_LEVEL_CAP_MONUMENT if monument and monument[0] else S.WEAPON_LEVEL_CAP
        pools = self._weapon_pools()
        best = None
        for hero in characters:
            if hero not in S.HERO_SLOTS or not self.hero_unlocked(hero):
                continue
            row = self._hero_row(hero)
            slot = row[HERO_EQUIPPED] if row else 0
            if slot >= WEAPONS_PER_HERO:
                continue
            offset = (S.HERO_SLOTS[hero] * WEAPONS_PER_HERO + slot) * WEAPON_RECORD
            record = self.g.read(pools[0] + offset, WEAPON_RECORD)
            if not record or not struct.unpack_from("<H", record, WEAPON_KIND)[0] or record[WEAPON_LEVEL] >= cap:
                continue
            if best is None or record[WEAPON_LEVEL] < best[2]:
                best = (hero, offset, record[WEAPON_LEVEL])
        if best is None:
            return "Weapon XP Gift: every equipped weapon is at the level cap"
        hero, offset, level = best
        for base in pools:
            self._write(base + offset + WEAPON_LEVEL, bytes([level + 1]))
        kind = struct.unpack_from("<H", self.g.read(pools[0] + offset, WEAPON_RECORD), WEAPON_KIND)[0]

        def check():  # the same weapon still in that slot at the new level (or higher, from fusing)
            record = self.g.read(self._weapon_pools()[0] + offset, WEAPON_RECORD)
            if not record:
                return False, "unreadable"
            now_kind, now_level = struct.unpack_from("<H", record, WEAPON_KIND)[0], record[WEAPON_LEVEL]
            if now_kind != kind:
                return None, f"slot now holds another weapon (kind {now_kind}; fused, sold or moved?)"
            return now_level >= level + 1, f"weapon level {now_level}"
        self.expect("Weapon XP Gift", check, hero=hero, before=level, wrote=level + 1)
        names = [n for n, kinds in S.WEAPON_KINDS.items() if kind in kinds]
        return f"{hero}'s {names[0] if names else 'weapon'} -> level {level + 1}"

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
        record[WEAPON_LEVEL] = 1
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
        record[WEAPON_LEVEL] = 1
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
        if current is None or max(current) > 5:
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
            current = self.g.read(prof + offset, 1)
            if current is None or current[0] > 10:
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

    def set_quest_states(self, states: dict[str, int]) -> list[str]:
        """Keep quests at a state (current and saved copy): 3 done, 1 not available, 2 at least available (a quest the
        game already shows or has done is left as it is), -1 not available unless already done. Services that follow the quest state open only by items,
        and a held-back quest can't be handed in. Returns the quests changed."""
        base = self._ptr(QUESTS) + S.QUEST_STATE_LIVE
        blob = self.g.read(base, S.QUEST_STATE_COUNT)
        if blob is None or max(blob) > S.QUEST_DONE:
            raise HookError("quest states not recognised")
        changed = []
        for name, want in sorted(states.items()):
            i = S.QUEST_STATE_IDS[name]
            if (want == 2 and blob[i] >= 2) or (want == -1 and blob[i] != 2):
                continue  # already open / never undo a quest the player has handed in
            want = abs(want)
            if blob[i] != want:
                for copy in (0, QUEST_SAVED_COPY):
                    self._write(base + copy + i, bytes([want]))
                changed.append(name)
        return changed

    def complete_quest(self, name: str) -> bool:
        """Mark a quest done (current and saved copy); the Smithy opens this way. Returns True if it changed."""
        base = self._ptr(QUESTS) + S.QUEST_STATE_LIVE
        blob = self.g.read(base, S.QUEST_STATE_COUNT)
        if blob is None or max(blob) > S.QUEST_DONE:
            raise HookError("quest states not recognised")
        i = S.QUEST_STATE_IDS[name]
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
        if not raw or struct.unpack_from("<II", raw) != (unit, kind):
            return None
        hp, _, top = struct.unpack_from("<fff", raw, UNIT_HP)
        return record + UNIT_HP if 400 <= top <= 60000 and -1 <= hp <= top + 1 else None

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

    def _request_flow(self, flow: int, state: int) -> None:
        self._write(flow + FLOW_FLAGS, b"\x02")
        self._write(flow + FLOW_REQUEST, struct.pack("<I", state))

    def kill_player(self) -> bool:
        """DeathLink: real HP (and the display copy) to 0 and the mission flow to "defeated"; restart_mission must
        follow a few seconds later. Returns False outside play (no character, real HP not found, or not playing)."""
        char = self._battle_character()
        real = self._unit_hp(char) if char else None
        flow = self._flow()
        if not real or not flow or flow[1:] != (FLOW_PLAYING, 0):
            return False
        self._write(real, struct.pack("<f", 0.0))
        self._write(char + CHAR_HP, struct.pack("<f", 0.0))
        self._request_flow(flow[0], FLOW_DEFEATED)
        return True

    def restart_mission(self) -> bool:
        """After kill_player: request Retry (the mission restarts). True once requested, or if no longer defeated."""
        flow = self._flow()
        if not flow or flow[2]:
            return False  # unreadable, or a request (ours) not taken yet
        if flow[1] != FLOW_DEFEATED:
            return True
        self._request_flow(flow[0], FLOW_RETRY)
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

    def set_story_parties(self, heroes: list[str] | None) -> list[str]:
        """Give every story mission this party in place of its forced heroes (hero slots only; Divine Beast
        segments and empty slots stay; a mission's support heroes are skipped). heroes=None puts the vanilla parties
        back. Returns the records changed."""
        table = self._params()
        changed = []
        for record, vanilla_hex in S.VANILLA_STORY_PARTY.items():
            vanilla = bytes.fromhex(vanilla_hex)
            want = bytearray(vanilla)
            if heroes is not None:
                # a forced slot keeps its vanilla hero when that hero is yours (the story's own pilots, e.g. Sidon in
                # Water and Fire); the others get your strongest remaining heroes (user: the client forced Calamity
                # Ganon over Sidon)
                support = S.STORY_SUPPORT.get(record, ())
                yours = {S.HERO_SLOTS[h] + 1 for h in heroes if h in S.HERO_SLOTS}
                kept = {b for b in vanilla if 0 < b < 40 and b in yours}
                pick = iter(S.HERO_SLOTS[h] + 1 for h in heroes
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
