import os
import struct
import time
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .. import data_save as L
from ..client import delivery
from ..client.savefile import SaveFormatError, SavePatch, cleared_missions, hero_level, hero_unlocked, material, rupees
from ..client.savewatch import SaveWatcher, message_for
from ..data import MISSION_NAMES
from ..data_challenges import CHALLENGES, GAME_LEVEL, STORY_LEVEL


def blank_save() -> bytearray:
    data = bytearray(L.SAVE_SIZE)
    data[0] = L.SAVE_FORMAT
    for hero in ("Link", "Zelda", "Impa"):
        data[L.HEROES + L.HERO_SLOTS[hero] * L.HERO_SIZE + L.HERO_UNLOCKED] = 1
    return data


def clear(data: bytearray, name: str) -> None:
    for i in L.MISSION_RECORD_IDS[name]:
        struct.pack_into("<I", data, L.MISSION_RECORDS + i * L.MISSION_RECORD_SIZE + 4, 600)


class SaveLayoutTests(unittest.TestCase):
    def test_every_location_has_a_record(self) -> None:
        names = set(L.MISSION_RECORD_IDS)
        self.assertLessEqual(set(MISSION_NAMES), names)
        self.assertLessEqual({c.name for c in CHALLENGES}, names)

    def test_records_are_unique_and_in_range(self) -> None:
        ids = [i for v in L.MISSION_RECORD_IDS.values() for i in v]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(0 < i < L.MISSION_RECORD_COUNT for i in ids))

    def test_two_part_mission_needs_both_records(self) -> None:
        data = blank_save()
        name = "Mipha, the Zora Princess"
        first = L.MISSION_RECORD_IDS[name][0]
        struct.pack_into("<I", data, L.MISSION_RECORDS + first * L.MISSION_RECORD_SIZE + 4, 1)
        self.assertNotIn(name, cleared_missions(data))
        clear(data, name)
        self.assertIn(name, cleared_missions(data))

    def test_any_difficulty_slot_counts(self) -> None:
        data = blank_save()
        i = L.MISSION_RECORD_IDS["Mastering Cryonis"][0]
        struct.pack_into("<I", data, L.MISSION_RECORDS + i * L.MISSION_RECORD_SIZE + 4 + 4 * 5, 7)
        self.assertEqual(cleared_missions(data), {"Mastering Cryonis"})

    def test_messages(self) -> None:
        self.assertEqual(message_for("Akkala Tower"), {"type": "mission_cleared", "mission": "Akkala Tower"})
        self.assertEqual(message_for("Mastering Cryonis"), {"type": "challenge_cleared", "challenge": "Mastering Cryonis"})

    def test_rejects_other_formats(self) -> None:
        with self.assertRaises(SaveFormatError):
            SavePatch(bytes(L.SAVE_SIZE))
        with self.assertRaises(SaveFormatError):
            SavePatch(bytes([L.SAVE_FORMAT]) + bytes(10))


class PatchTests(unittest.TestCase):
    def test_rupees_capped(self) -> None:
        patch = SavePatch(blank_save())
        patch.add_rupees(1000)
        self.assertEqual(rupees(patch.data), 1000)
        patch.add_rupees(L.RUPEES_MAX)
        self.assertEqual(rupees(patch.data), L.RUPEES_MAX)

    def test_material_bundle_is_repeatable(self) -> None:
        a, b = SavePatch(blank_save()), SavePatch(blank_save())
        a.material_bundle(seed=4)
        b.material_bundle(seed=4)
        self.assertEqual(a.data, b.data)
        given = [i for i in L.BUNDLE_MATERIALS if material(a.data, i)]
        self.assertEqual(len(given), 3)
        self.assertTrue(all(a.data[L.MATERIAL_SEEN + i] == 1 for i in given))

    def test_level_up_lowest_unlocked(self) -> None:
        data = blank_save()
        data[L.HEROES + L.HERO_SLOTS["Link"] * L.HERO_SIZE] = 9
        patch = SavePatch(data)
        patch.level_up(["Link", "Zelda", "Mipha"])  # Mipha is not unlocked in the save
        self.assertEqual(hero_level(patch.data, "Zelda"), 2)
        self.assertEqual(hero_level(patch.data, "Link"), 10)
        self.assertEqual(hero_level(patch.data, "Mipha"), 1)

    def test_unlock_hero(self) -> None:
        patch = SavePatch(blank_save())
        self.assertIsNotNone(patch.unlock_hero("Mipha"))
        self.assertTrue(hero_unlocked(patch.data, "Mipha"))
        self.assertIsNone(patch.unlock_hero("Mipha"))


class WatchAndDeliverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "0").mkdir()
        (root / "1").mkdir()
        self.path = str(root / "0" / "svdt")
        self.copies = [self.path, str(root / "1" / "svdt")]
        self.data = blank_save()
        clear(self.data, "The Battle of Hyrule Field")
        self.write(self.data)
        patcher = mock.patch.object(delivery, "STATE_DIR", root / "state")
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, data: bytes) -> None:
        # A strictly rising mtime: Windows file times tick about every 15 ms, so "now + 1" can repeat between writes.
        self._mtime = getattr(self, "_mtime", 1_000_000) + 10
        for p in self.copies:
            Path(p).write_bytes(data)
            os.utime(p, (0, self._mtime))  # make sure the watcher sees a change

    def test_watch_ignores_baseline_and_reports_new_clears(self) -> None:
        d = delivery.Delivery("seed", "me")
        watcher = SaveWatcher(self.path, ignore=d.baseline(cleared_missions(self.data)))
        self.assertEqual(watcher.poll(), [])
        clear(self.data, "Mastering Cryonis")
        self.write(self.data)
        self.assertEqual(watcher.poll(), [{"type": "challenge_cleared", "challenge": "Mastering Cryonis"}])
        self.assertEqual(watcher.poll(), [])
        # the baseline is remembered per seed, even if the game changes later
        self.assertEqual(delivery.Delivery("seed", "me").baseline(set()), {"The Battle of Hyrule Field"})

    def test_new_game_releases_baseline(self) -> None:
        d = delivery.Delivery("seed", "me")
        watcher = SaveWatcher(self.path, ignore=d.baseline(cleared_missions(self.data)), on_ignore_change=d.set_baseline)
        self.assertEqual(watcher.poll(), [])
        self.write(blank_save())  # New Game
        self.assertEqual(watcher.poll(), [])
        self.assertEqual(delivery.Delivery("seed", "me").state["baseline"], [])
        fresh = blank_save()
        clear(fresh, "The Battle of Hyrule Field")
        self.write(fresh)
        self.assertEqual(watcher.poll(), [{"type": "mission_cleared", "mission": "The Battle of Hyrule Field"}])

    def test_consumables_applied_once_to_save_file(self) -> None:
        d = delivery.Delivery("seed", "me")
        items = ["Rupee Pouch", "Character: Mipha", "Hearty Meal", "Rupee Pouch"]
        target = delivery.SaveFileTarget(self.path, self.copies)
        self.assertEqual(len(d.apply(items, {"Link"}, target)), 3)
        target.commit()
        for p in self.copies:
            self.assertEqual(rupees(Path(p).read_bytes()), 2 * delivery.RUPEE_POUCH)
        target = delivery.SaveFileTarget(self.path, self.copies)
        self.assertEqual(d.apply(items, {"Link"}, target), [])
        # a fresh client (restart) must not apply them again
        again = delivery.Delivery("seed", "me")
        target = delivery.SaveFileTarget(self.path, self.copies)
        done = again.apply(items + ["Material Bundle"], {"Link"}, target)
        target.commit()
        self.assertEqual(len(done), 1)
        self.assertEqual(rupees(Path(self.path).read_bytes()), 2 * delivery.RUPEE_POUCH)
        self.assertTrue(list((Path(self.tmp.name) / "state" / "backups").glob("svdt_*")))

    def test_live_and_file_share_the_ledger(self) -> None:
        class FakeLive:
            def __init__(self): self.calls = []
            def add_rupees(self, n): self.calls.append(("rupees", n)); return "r"
            def material_bundle(self, seed): self.calls.append(("bundle", seed)); return "m"
            def level_up(self, heroes): self.calls.append(("level", tuple(heroes))); return "l"
        d = delivery.Delivery("seed", "me")
        live = FakeLive()
        d.apply(["Rupee Pouch", "Material Bundle"], {"Link"}, live)
        d.apply(["Rupee Pouch", "Material Bundle", "Character XP Gift"], {"Link"}, live)
        self.assertEqual(live.calls, [("rupees", delivery.RUPEE_POUCH), ("bundle", 1), ("level", ("Link",))])
        target = delivery.SaveFileTarget(self.path, self.copies)
        self.assertEqual(d.apply(["Rupee Pouch", "Material Bundle", "Character XP Gift"], {"Link"}, target), [])

    def test_extra_weapon_live_only_and_never_a_check(self) -> None:
        from ..data import WEAPON_BY_NAME

        class FakeLive:
            def __init__(self): self.given = []
            def give_weapon(self, name, wielder): self.given.append((name, wielder)); return name
        d = delivery.Delivery("seed", "me")
        target = delivery.SaveFileTarget(self.path, self.copies)
        self.assertEqual(d.apply(["Extra Weapon"], {"Mipha"}, target), [])  # waits for the live game
        live = FakeLive()
        d.apply(["Extra Weapon", "Extra Weapon"], {"Mipha"}, live)
        self.assertEqual(len(live.given), 2)
        for name, wielder in live.given:
            self.assertEqual(wielder, "Mipha")
            self.assertFalse(WEAPON_BY_NAME[name].dlc)
        self.assertEqual(sum(d.state["weapons_given"].values()), 2)  # owned copies match: no weapon check is sent
        self.assertEqual(delivery.extra_weapon({"Mipha"}, 7), delivery.extra_weapon({"Mipha"}, 7))  # fixed per item
        self.assertIsNone(delivery.extra_weapon(set(), 0))


class HeroTargetTests(unittest.TestCase):
    def test_forced_heroes_of_playable_missions_stay_unlocked(self) -> None:
        targets = delivery.hero_targets({"Mipha"}, ["The Battle of Hyrule Field"], L.MISSION_FORCED_HEROES,
                                        list(L.HERO_SLOTS))
        self.assertTrue(targets["Mipha"] and targets["Link"] and targets["Impa"])
        self.assertFalse(targets["Zelda"] or targets["Daruk"])

    def test_forced_data_uses_known_heroes(self) -> None:
        for mission, heroes in L.MISSION_FORCED_HEROES.items():
            self.assertIn(mission, L.MISSION_RECORD_IDS)
            self.assertTrue(set(heroes) <= set(L.HERO_SLOTS), mission)


class StoryPartyDataTests(unittest.TestCase):
    def test_vanilla_parties_cover_story_records(self) -> None:
        story_records = {i for name in MISSION_NAMES for i in L.MISSION_RECORD_IDS[name]}
        self.assertTrue(set(L.VANILLA_STORY_PARTY) <= story_records)
        for record, hexed in L.VANILLA_STORY_PARTY.items():
            self.assertEqual(len(bytes.fromhex(hexed)), 4)
            self.assertTrue(any(0 < b < 40 for b in bytes.fromhex(hexed)), record)

    def test_support_heroes_match_the_logic(self) -> None:
        from ..data import MISSION_SUPPORT
        for record, heroes in L.STORY_SUPPORT.items():
            mission = next(n for n in MISSION_NAMES if record in L.MISSION_RECORD_IDS[n])
            self.assertTrue(set(heroes) <= set(MISSION_SUPPORT[mission]), mission)
            self.assertTrue(set(heroes) <= set(L.HERO_SLOTS), mission)

    def test_party_override_skips_support_heroes(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        fake = FakeGuest()
        holder, table = fake.base + 0x30000, fake.base + 0x40000
        fake.put(H.PARAMS[0], struct.pack("<Q", holder))
        fake.put(holder + H.PARAMS[1], struct.pack("<Q", table))
        rows = table + H.PARAMS[2]
        fake.put(rows, struct.pack("<II", L.MISSION_RECORD_COUNT, 0))
        LiveGame(fake).set_story_parties(["Mipha", "Sidon", "Link", "Daruk"])

        def party(record: int) -> bytes:
            return fake.read(rows + 16 + record * L.PARTY_ROW_SIZE + L.PARTY_OFFSET, 4)
        self.assertEqual(party(1), bytes([1, 4, 0, 0]))  # Hyrule Field: Link kept (his own slot), Impa -> Mipha
        self.assertEqual(party(18), bytes([0, 0, 9, 1]))  # Water and Fire: Sidon kept; Yunobo -> Link (not Mipha/Daruk, its allies)


class GameDataLogicTests(unittest.TestCase):
    def test_level_gates_follow_story_levels(self) -> None:
        from ..rules import level_gate
        self.assertEqual(level_gate("Mastering Remote Bombs"), "The Battle of Hyrule Field")
        for name, level in GAME_LEVEL.items():
            gate = level_gate(name) if level else None
            if gate:
                self.assertGreaterEqual(STORY_LEVEL[gate], level, name)
        self.assertIsNone(level_gate(max(GAME_LEVEL, key=GAME_LEVEL.get)))

    def test_game_parties_are_required(self) -> None:
        from ..data_challenges import CHALLENGE_BY_NAME, GAME_PARTY
        for name, heroes in GAME_PARTY.items():
            self.assertTrue(set(heroes) <= set(CHALLENGE_BY_NAME[name].required_characters), name)


class FakeGuest:
    """Flat guest memory: just enough of the manager, hero table and weapon pool for LiveGame."""

    def __init__(self) -> None:
        from ..client import live_hook as H
        self.H = H
        self.base = 0x10_0000_0000
        self.mem = bytearray(0x100000)
        P, heroes, pool = self.base + 0x1000, self.base + 0x2000, self.base + 0x10000
        self.put(H.MANAGER, struct.pack("<Q", P))
        self.put(P + H.HEROES[0], struct.pack("<Q", heroes))
        self.put(P + H.WEAPON_POOL, struct.pack("<Q", pool))
        for i, field in enumerate(H.WEAPON_COPIES):
            obj = pool + 0x100 + i * 0x60000
            self.put(pool + field, struct.pack("<Q", obj))
            self.put(obj, struct.pack("<QQ", obj + 0x30, H.WEAPON_RECORDS))
        self.heroes, self.pools = heroes, [pool + 0x130, pool + 0x60130]
        # Sidon owns his harpoon already; Revali owns nothing and has placeholder stats.
        self.put(pool + 0x130 + L.HERO_SLOTS["Sidon"] * 71 * 0x90 + 0x10, struct.pack("<H", 251))

    def put(self, va: int, data: bytes) -> None:
        if va < self.base:  # MANAGER is a module address; keep it at the start of the fake memory
            va = self.base + (va & 0xFFF)
        self.mem[va - self.base:va - self.base + len(data)] = data

    def read(self, va: int, n: int) -> bytes:
        if va < 1 << 32:  # module addresses (MANAGER, PARAMS ...) live at the start of the fake memory
            va = self.base + (va & 0xFFF)
        elif va < self.base:
            return bytes(n)  # unmapped heap below the fake region
        return bytes(self.mem[va - self.base:va - self.base + n])

    write = lambda self, va, data: (self.put(va, data), True)[1]
    u64 = lambda self, va: struct.unpack("<Q", self.read(va, 8))[0]


class MissionRewardTableTests(unittest.TestCase):
    def test_vanilla_rows_match_published_rewards(self) -> None:
        from .. import data_mission_rewards as R
        bombs = R.vanilla_row(L.MISSION_RECORD_IDS["Mastering Remote Bombs"][0])
        # Ethereal Stone x1, Ancient Screw x5, Ancient Gear x5 (ids + 1)
        self.assertEqual(bombs[0x24:0x27], bytes([0x97, 0x8D, 0x8F]))
        self.assertEqual(struct.unpack_from("<3H", bombs, 0x04), (1, 5, 5))
        self.assertEqual(R.vanilla_row(L.MISSION_RECORD_IDS["Akkala Tower"][0])[0x25], 0x67)  # Opal

    def test_live_table_found_near_params_and_rows_written(self) -> None:
        from .. import data_mission_rewards as R
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        fake = FakeGuest()
        holder, params, rewards = fake.base + 0x30000, fake.base + 0x40000, fake.base + 0x48010
        fake.put(H.PARAMS[0], struct.pack("<Q", holder))
        fake.put(holder + H.PARAMS[1], struct.pack("<Q", params - H.PARAMS[2]))
        fake.put(params, struct.pack("<II", L.MISSION_RECORD_COUNT, 0))
        fake.put(rewards, R.TABLE)
        game = LiveGame(fake)
        self.assertEqual(game.reward_table(), rewards)
        bombs = L.MISSION_RECORD_IDS["Mastering Remote Bombs"][0]
        new = R.vanilla_row(13)
        self.assertEqual(game.set_mission_rewards({bombs: new, 13: new}), [bombs])
        self.assertEqual(fake.read(rewards + R.HEADER + bombs * R.ROW_SIZE, R.ROW_SIZE), new)


class HeroLevelTests(unittest.TestCase):
    def test_xp_table(self) -> None:
        self.assertEqual(len(L.HERO_XP_TABLE), L.HERO_LEVEL_MAX)
        self.assertTrue(all(a < b for a, b in zip(L.HERO_XP_TABLE, L.HERO_XP_TABLE[1:])))
        self.assertTrue(2024 < L.HERO_XP_TABLE[1] <= 2664 and 5218 < L.HERO_XP_TABLE[2] <= 5545)  # in-game samples
        self.assertEqual(L.HERO_XP_TABLE[-1], 3706825)  # the 100% save

    def test_live_level_and_xp_in_both_copies(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        fake = FakeGuest()
        game = LiveGame(fake)
        mipha = fake.heroes + H.HEROES[1] + L.HERO_SLOTS["Mipha"] * H.HEROES[2]
        fake.put(mipha + H.HERO_XP, struct.pack("<I", 3000))  # level 2 with some XP
        fake.put(mipha + H.HERO_LEVEL, b"\x01")
        self.assertTrue(game.set_level("Mipha", 5))
        for copy in (0, H.HERO_SAVED_COPY):
            self.assertEqual(fake.read(mipha + copy + H.HERO_LEVEL, 1), b"\x04")
            self.assertEqual(struct.unpack("<I", fake.read(mipha + copy + H.HERO_XP, 4))[0], L.HERO_XP_TABLE[4])
        self.assertFalse(game.set_level("Mipha", 3))  # never lowers
        self.assertEqual(game.raise_levels(["Mipha", "Sidon"], 5), ["Sidon"])

    def test_stats_follow_written_levels(self) -> None:
        """ATK/DEF +3 per level and hearts by level (recorded level-ups); a granted hero gets the lowest hero's stats
        moved to its own level, so catch-up adds on top instead of counting twice."""
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        fake = FakeGuest()
        game = LiveGame(fake)
        row = lambda hero: fake.heroes + H.HEROES[1] + L.HERO_SLOTS[hero] * H.HEROES[2]
        stats = lambda hero: struct.unpack("<3H", fake.read(row(hero) + H.HERO_STATS, 6))
        fake.put(row("Link") + H.HERO_XP, struct.pack("<I", L.HERO_XP_TABLE[9]))
        fake.put(row("Link") + H.HERO_STATS, struct.pack("<3H", 7, 300, 290))
        fake.put(row("Link") + H.HERO_LEVEL, b"	")
        fake.put(row("Link") + H.HERO_PLAYABLE, b"\x01")
        fake.put(row("Mipha") + H.HERO_STATS, H.PLACEHOLDER_STATS)
        self.assertTrue(game.grant_hero("Mipha"))
        self.assertEqual(stats("Mipha"), (4, 273, 263))  # Link's level-10 stats moved down to level 1
        self.assertTrue(game.set_level("Mipha", 10))
        self.assertEqual(stats("Mipha"), (7, 300, 290))
        self.assertEqual(struct.unpack("<3H", fake.read(row("Mipha") + H.HERO_SAVED_COPY + H.HERO_STATS, 6)),
                         (7, 300, 290))
        self.assertTrue(game.set_level("Link", 31))
        self.assertEqual(stats("Link"), (11, 363, 353))
        fake.put(row("Sidon") + H.HERO_STATS, H.PLACEHOLDER_STATS)
        self.assertTrue(game.set_level("Sidon", 5))  # a locked hero's placeholder stats stay as they are
        self.assertEqual(stats("Sidon"), (1, 1, 1))

    def test_save_file_level_and_xp(self) -> None:
        from ..client.savefile import hero_level
        patch = SavePatch(bytes(blank_save()))
        self.assertTrue(patch.set_level("Link", 10))
        row = L.HEROES + L.HERO_SLOTS["Link"] * L.HERO_SIZE
        self.assertEqual(hero_level(patch.data, "Link"), 10)
        self.assertEqual(int.from_bytes(patch.data[row + 1:row + 4], "little"), L.HERO_XP_TABLE[9])
        patch.level_up(["Link"])
        self.assertEqual(int.from_bytes(patch.data[row + 1:row + 4], "little"), L.HERO_XP_TABLE[10])


class GiftTests(unittest.TestCase):
    def test_weapon_xp_gift_raises_lowest_equipped_weapon_up_to_the_cap(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        fake = FakeGuest()
        flags = fake.base + 0x90000
        fake.put(fake.base + 0x1000 + 0x5A0, struct.pack("<Q", flags))
        game = LiveGame(fake)
        for hero, level in (("Mipha", 7), ("Sidon", 3)):
            row = fake.heroes + H.HEROES[1] + L.HERO_SLOTS[hero] * H.HEROES[2]
            fake.put(row + H.HERO_FLAGS, bytes([1, 1, 1]))
            for pool in fake.pools:
                rec = pool + L.HERO_SLOTS[hero] * H.WEAPONS_PER_HERO * H.WEAPON_RECORD
                fake.put(rec + H.WEAPON_KIND, struct.pack("<H", 251))
                fake.put(rec + H.WEAPON_LEVEL, bytes([level]))
        self.assertEqual(game.weapon_level_up(["Mipha", "Sidon"]), "Sidon's Fishing Harpoon -> level 4")
        sidon = L.HERO_SLOTS["Sidon"] * H.WEAPONS_PER_HERO * H.WEAPON_RECORD + H.WEAPON_LEVEL
        self.assertEqual([fake.read(p + sidon, 1)[0] for p in fake.pools], [4, 4])
        for pool in fake.pools:
            fake.put(pool + sidon, bytes([L.WEAPON_LEVEL_CAP]))
        self.assertEqual(game.weapon_level_up(["Sidon"]), "Weapon XP Gift: every equipped weapon is at the level cap")

    def test_hearty_meal_adds_ingredients(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        fake = FakeGuest()
        prof = fake.base + 0x80000
        fake.put(fake.base + 0x1000 + H.PROFILE, struct.pack("<Q", prof))
        LiveGame(fake).hearty_meal()
        for index, amount in L.HEARTY_MEAL.items():
            self.assertEqual(struct.unpack("<H", fake.read(prof + H.MATERIALS + index * 2, 2))[0], amount)


class WeaponGrantTests(unittest.TestCase):
    def setUp(self) -> None:
        from ..client.live_hook import LiveGame
        self.fake = FakeGuest()
        self.game = LiveGame(self.fake)

    def test_hero_without_weapons_gets_starter(self) -> None:
        self.assertTrue(self.game.give_starter_weapon("Revali"))
        self.assertEqual([k for k in self.game.hero_weapons("Revali") if k], [L.HERO_STARTER_KIND["Revali"]])
        for pool in self.fake.pools:  # current and saved copy
            record = pool + L.HERO_SLOTS["Revali"] * 71 * 0x90
            self.assertEqual(self.fake.read(record + 0x10, 2), struct.pack("<H", 221))
            self.assertEqual(self.fake.read(record + 0x79, 1), b"\x01")
        count = self.game._hero_addr("Revali") - 4
        self.assertEqual(self.fake.read(count, 4), struct.pack("<I", 1))
        self.assertFalse(self.game.give_starter_weapon("Revali"))

    def test_hero_with_a_weapon_is_left_alone(self) -> None:
        self.assertFalse(self.game.give_starter_weapon("Sidon"))
        self.assertEqual([k for k in self.game.hero_weapons("Sidon") if k], [251])

    def test_starter_kinds_follow_hero_ranges(self) -> None:
        self.assertEqual(set(L.HERO_STARTER_KIND), set(L.HERO_SLOTS))
        for hero, kind in L.HERO_STARTER_KIND.items():
            if hero != "Link" and L.HERO_SLOTS[hero] <= 17:
                self.assertEqual(kind, L.HERO_STARTER_WEAPON[hero] + 130, hero)


class MissionLockTests(unittest.TestCase):
    def setUp(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        self.fake = FakeGuest()
        holder, table = self.fake.base + 0x80000, self.fake.base + 0x90000
        self.fake.put(H.UNLOCKS[0], struct.pack("<Q", holder))
        self.fake.put(holder + H.UNLOCKS[1], struct.pack("<Q", table))
        self.table = table + H.UNLOCKS[2]
        self.fake.put(self.table, struct.pack("<II", L.MISSION_RECORD_COUNT, 0))
        for record, hexed in L.VANILLA_STORY_UNLOCK.items():
            self.fake.put(self.row(record), bytes.fromhex(hexed))
        self.game = LiveGame(self.fake)

    def row(self, record: int) -> int:
        return self.table + 16 + record * L.UNLOCK_ROW_SIZE + L.UNLOCK_OFFSET

    def test_open_missions_lose_prerequisites_and_others_are_locked(self) -> None:
        self.game.set_mission_locks({"The Battle of Hyrule Field", "The Yiga Clan Attacks!"})
        self.assertEqual(self.fake.read(self.row(9), 10), bytes(10))
        self.assertEqual(self.fake.read(self.row(3), 2), struct.pack("<H", 28))
        self.assertEqual(self.fake.read(self.row(1), 10), bytes(10))
        self.assertEqual(self.game.set_mission_locks({"The Battle of Hyrule Field", "The Yiga Clan Attacks!"}), [])

    def test_vanilla_restores_the_game_rules(self) -> None:
        self.game.set_mission_locks(set())
        self.game.set_mission_locks(None)
        for record, hexed in L.VANILLA_STORY_UNLOCK.items():
            self.assertEqual(self.fake.read(self.row(record), 10).hex(), hexed)


    def test_challenge_rows_follow_the_given_rules(self) -> None:
        from ..client import live_hook as H
        for record, hexed in L.VANILLA_CHALLENGE_UNLOCK.items():
            self.fake.put(self.row(record), bytes.fromhex(hexed) + b"\x2a")
        profile, block = self.fake.base + 0xC0000, self.fake.base + 0xD0000
        self.fake.put(self.fake.base + 0x1000 + H.PROFILE, struct.pack("<Q", profile))
        self.fake.put(self.fake.base + 0x1000 + H.MISSION_STATES_BLOCK, struct.pack("<Q", block))
        for offset in H.MISSION_STATES_PROFILE:
            self.fake.put(profile + offset + 158, b"\x01\x03")
        cleared = {1, 2}
        self.game.cleared_records = lambda: cleared
        self.assertEqual(self.game.set_challenge_locks({158: (2,), 186: (14,), 159: (2,)}), [159, 186])  # 158 is already vanilla
        row = self.fake.read(self.row(186), L.CHALLENGE_UNLOCK_SIZE + 1)
        self.assertEqual(row, struct.pack("<H", 14) + bytes(L.CHALLENGE_UNLOCK_SIZE - 2) + b"\x2a")  # quests gone
        self.assertEqual(self.fake.read(self.row(102), 4).hex(), L.VANILLA_CHALLENGE_UNLOCK[102][:8])  # not given
        for offset in H.MISSION_STATES_PROFILE:
            self.assertEqual(self.fake.read(profile + offset + 158, 2), b"\x02\x03")  # open; cleared stays
        self.assertEqual(self.fake.read(block + H.MISSION_STATES_MAP[0] + 186, 1), b"\x00")  # Akkala not cleared
        cleared.add(14)
        self.game.set_challenge_locks({158: (2,), 186: (14,), 159: (2,)})
        self.assertEqual(self.fake.read(block + H.MISSION_STATES_MAP[0] + 186, 1), b"\x02")
        self.assertEqual(self.game.set_challenge_locks({158: (2,), 186: (14,), 159: (2,)}), [])
        self.game.set_challenge_locks(None)
        self.assertEqual(self.fake.read(self.row(186), L.CHALLENGE_UNLOCK_SIZE).hex(), L.VANILLA_CHALLENGE_UNLOCK[186])


class QuestStateTests(unittest.TestCase):
    def test_done_quests_are_read_from_the_save(self) -> None:
        from ..client.savefile import completed_quests
        data = blank_save()
        data[L.QUEST_STATE_SAVE + L.QUEST_STATE_IDS["The Frontiers of Knowledge"]] = L.QUEST_DONE
        data[L.QUEST_STATE_SAVE + L.QUEST_STATE_IDS["Keeping the Village Peace"]] = 2  # available, not done
        self.assertEqual(completed_quests(bytes(data)), {"The Frontiers of Knowledge"})
        self.assertEqual(message_for("The Frontiers of Knowledge"),
                         {"type": "quest_completed", "quest": "The Frontiers of Knowledge"})

    def test_quest_names_are_distinct_from_missions(self) -> None:
        self.assertFalse(set(L.QUEST_STATE_IDS) & set(L.MISSION_RECORD_IDS))
        self.assertEqual(L.QUEST_STATE_IDS["The Frontiers of Knowledge"], 25)

    def test_every_quest_has_a_state_entry(self) -> None:
        from ..data_quests import QUESTS
        self.assertEqual({q.name for q in QUESTS}, set(L.QUEST_STATE_IDS))
        self.assertEqual(len(set(L.QUEST_STATE_IDS.values())), len(L.QUEST_STATE_IDS))
        self.assertLess(max(L.QUEST_STATE_IDS.values()), L.QUEST_STATE_COUNT)


class UpgradeLevelTests(unittest.TestCase):
    def test_levels_written_to_current_and_saved_profile(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        fake = FakeGuest()
        profile = fake.base + 0xC0000
        fake.put(fake.base + 0x1000 + H.PROFILE, struct.pack("<Q", profile))
        game = LiveGame(fake)
        fake.put(profile + L.UPGRADE_LEVELS + 5, b"\x01")  # bought in game, not received
        self.assertEqual(game.set_upgrade_levels({0: 2, 5: 0}), [0, 5])
        for copy in (0, H.PROFILE_SAVED_COPY):
            self.assertEqual(fake.read(profile + copy + L.UPGRADE_LEVELS, 6), b"\x02\x00\x00\x00\x00\x00")
        self.assertEqual(game.set_upgrade_levels({0: 2, 5: 0}), [])


class WeaponItemTests(unittest.TestCase):
    def setUp(self) -> None:
        from ..client.live_hook import LiveGame
        self.fake = FakeGuest()
        self.game = LiveGame(self.fake)

    def test_given_weapon_lands_in_wielders_next_slot(self) -> None:
        self.assertEqual(self.game.give_weapon("Silverscale Spear", "Sidon"), "Silverscale Spear for Sidon")
        kinds = [k for k in self.game.hero_weapons("Sidon") if k]
        self.assertEqual(kinds, [251, L.WEAPON_KINDS["Silverscale Spear"][0]])
        self.assertEqual(self.game.weapon_counts()["Silverscale Spear"], 1)
        count = self.fake.read(self.game._hero_addr("Sidon") - 4, 4)
        self.assertEqual(count, struct.pack("<I", 1))

    def test_unique_weapons_are_mapped(self) -> None:
        for name in ("Master Sword", "Bow of Light", "Serene Champion's Spear", "Steadfast Champion's Greatsword",
                     "Soaring Champion's Bow", "Nimble Champion's Sword", "Master Cycle"):
            self.assertIn(name, L.WEAPON_KINDS)
        from ..data import WEAPONS
        self.assertEqual({w.name for w in WEAPONS}, set(L.WEAPON_KINDS))
        self.assertFalse(set(L.WEAPON_KINDS) & (set(L.MISSION_RECORD_IDS) | set(L.QUEST_STATE_IDS)))

    def test_weapon_items_wait_for_the_live_game(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(delivery, "STATE_DIR", Path(tmp)):
            ledger = delivery.Delivery("seed", 1)

            class SaveOnly:
                def add_rupees(self, n): return f"+{n}"

            done = ledger.apply(["Rupee Pouch", "Weapon: Master Sword", "Rupee Pouch"], set(), SaveOnly())
            self.assertEqual(done, ["Rupee Pouch: +1000"])  # each gift names itself
            self.assertEqual(ledger.state["applied"], 1)
            live = mock.Mock()
            live.give_weapon.return_value = "Master Sword for Link"
            live.add_rupees.return_value = "+1000"
            ledger.apply(["Rupee Pouch", "Weapon: Master Sword", "Rupee Pouch"], set(), live)
            live.give_weapon.assert_called_once_with("Master Sword", "Link")
            self.assertEqual(ledger.state["weapons_given"], {"Master Sword": 1})


class MissionStateTests(unittest.TestCase):
    def test_open_and_locked_missions_written_to_map_states(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        fake = FakeGuest()
        profile, block = fake.base + 0xC0000, fake.base + 0xD0000
        fake.put(fake.base + 0x1000 + H.PROFILE, struct.pack("<Q", profile))
        fake.put(fake.base + 0x1000 + H.MISSION_STATES_BLOCK, struct.pack("<Q", block))
        for offset in H.MISSION_STATES_PROFILE:
            fake.put(profile + offset, bytes([0, 3, 3, 2, 1, 2]))
        game = LiveGame(fake)
        game.set_mission_states({"The Battle of Hyrule Field", "The Yiga Clan Attacks!"})
        for offset in H.MISSION_STATES_PROFILE:
            row = fake.read(profile + offset, 10)
            self.assertEqual(row[1:3], b"\x03\x03")  # cleared stay cleared
            self.assertEqual((row[3], row[9]), (1, 2))  # Mipha locked, Yiga open
        self.assertEqual(fake.read(block + H.MISSION_STATES_MAP[0] + 3, 1), b"\x00")  # map block: 0 = locked


class NewGameWeaponTests(unittest.TestCase):
    def test_fusing_away_a_weapon_is_not_a_new_game(self) -> None:
        from types import SimpleNamespace

        from ..client import ap_client
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(delivery, "STATE_DIR", Path(tmp)):
            d = delivery.Delivery("seed", "me")
            d.baseline(set())
            d.add_progress({"The Battle of Hyrule Field", "Cursed Bone Shard", "Shop-Quick Store"})
            ctx = SimpleNamespace(delivery=d, _shrink_seen=None, _live_seen=None, save_watcher=None)
            for t in (0.0, ap_client.NEW_GAME_CONFIRM + 1):
                ap_client.AoCContext._shrink_baseline(ctx, {"The Battle of Hyrule Field"}, t)  # weapon fused away
            self.assertIsNone(ctx._shrink_seen)
            self.assertEqual(d.state["progress"], ["Cursed Bone Shard", "Shop-Quick Store", "The Battle of Hyrule Field"])


class NewGameDetectionTests(unittest.TestCase):
    """The client must not mistake the blank state right after boot for a New Game (it sent an old save's
    clears as checks that way), but a real New Game gives every received item again."""

    def setUp(self) -> None:
        from types import SimpleNamespace

        from ..client import ap_client

        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(delivery, "STATE_DIR", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        self.ap = ap_client
        self.d = delivery.Delivery("seed", "me")
        self.d.baseline({"The Battle of Hyrule Field", "Boko Club"})
        self.d.state.update(applied=5, weapons_given={"Woodcutter's Axe": 1})
        self.ctx = SimpleNamespace(delivery=self.d, _shrink_seen=None, _live_seen=None, save_watcher=None)

    def tick(self, cleared: set[str], now: float) -> None:
        self.ap.AoCContext._shrink_baseline(self.ctx, cleared, now)

    def test_boot_blank_state_is_not_a_new_game(self) -> None:
        self.tick(set(), 0.0)
        self.tick(set(), 3.0)
        self.assertIsNotNone(self.ctx._shrink_seen)  # waiting: nothing is reported meanwhile
        self.tick({"The Battle of Hyrule Field", "Boko Club"}, 5.0)  # the old save finished loading
        self.assertIsNone(self.ctx._shrink_seen)
        self.assertEqual(self.d.state["applied"], 5)
        self.assertEqual(set(self.d.state["baseline"]), {"The Battle of Hyrule Field", "Boko Club"})

    def test_new_game_regives_items(self) -> None:
        self.tick(set(), 0.0)
        self.tick(set(), self.ap.NEW_GAME_CONFIRM + 1)
        self.assertEqual(self.d.state["baseline"], [])
        self.assertEqual(self.d.state["applied"], 0)
        self.assertEqual(self.d.state["weapons_given"], {})

    def test_progress_under_the_seed_also_detects_new_game(self) -> None:
        self.d.set_baseline(set())
        self.d.add_progress({"Road to the Ancient Lab"})
        self.tick(set(), 0.0)
        self.tick(set(), self.ap.NEW_GAME_CONFIRM + 1)
        self.assertEqual(self.d.state["applied"], 0)
        self.assertEqual(self.d.state["progress"], [])


class SaveWeaponTests(unittest.TestCase):
    def test_owned_weapons(self) -> None:
        from ..client.savefile import owned_weapons

        data = blank_save()
        struct.pack_into("<H", data, L.SAVE_WEAPONS + 3 * L.SAVE_WEAPON_RECORD, 4)
        self.assertEqual(owned_weapons(data), {"Soldier's Broadsword"})


class RuneTests(unittest.TestCase):
    def test_runes_written_to_current_and_saved_copy_only(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        fake = FakeGuest()
        block = fake.base + 0xA0000
        fake.put(fake.base + 0x1000 + H.STORY_FLAGS, struct.pack("<Q", block))
        flags = block + H.STORY_FLAGS_OFFSET
        for copy in range(4):
            fake.put(flags + copy * 0x700, bytes([1, 0, 1, 1, 1, 1, 1, 0, 0, 1]))  # after Hyrule Field: no Magnesis or Stasis
        game = LiveGame(fake)
        self.assertEqual(game.set_runes({"Magnesis": False, "Stasis": True}), ["Stasis"])
        for copy in (0, 3):
            self.assertEqual(fake.read(flags + copy * 0x700 + 7, 2), bytes([0, 1]))  # save 0x1B Magnesis, 0x1C Stasis
        for copy in (1, 2):  # a mission's working copies are left alone
            self.assertEqual(fake.read(flags + copy * 0x700 + 7, 2), bytes([0, 0]))
        self.assertEqual(game.set_runes({"Magnesis": False, "Stasis": True}), [])

    def test_smithy_quest_marked_done_in_both_copies(self) -> None:
        from .. import data_save as S
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        from ..data import SMITHY_QUEST
        fake = FakeGuest()
        block = fake.base + 0xA0000
        fake.put(fake.base + 0x1000 + H.QUESTS, struct.pack("<Q", block))
        states = block + S.QUEST_STATE_LIVE
        for copy in (0, H.QUEST_SAVED_COPY):
            fake.put(states + copy, bytes([1] * S.QUEST_STATE_COUNT))
        game = LiveGame(fake)
        self.assertTrue(game.complete_quest(SMITHY_QUEST))
        i = S.QUEST_STATE_IDS[SMITHY_QUEST]
        for copy in (0, H.QUEST_SAVED_COPY):
            self.assertEqual(fake.read(states + copy + i - 1, 3), bytes([1, S.QUEST_DONE, 1]))
        self.assertFalse(game.complete_quest(SMITHY_QUEST))

    def test_hero_bonus_written_to_current_and_saved_profile(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        fake = FakeGuest()
        prof = fake.base + 0x80000
        fake.put(fake.base + 0x1000 + H.PROFILE, struct.pack("<Q", prof))
        game = LiveGame(fake)
        mipha = L.HERO_SLOTS["Mipha"]
        self.assertEqual(game.set_hero_bonus("Heart Container", {mipha: 1, 0: 0}), [mipha])
        for copy in (0, H.PROFILE_SAVED_COPY):
            self.assertEqual(fake.read(prof + copy + L.HERO_BONUS["Heart Container"] + mipha, 1), bytes([1]))
            self.assertEqual(fake.read(prof + copy + L.HERO_BONUS["Special Gauge Upgrade"] + mipha, 1), bytes([0]))
        self.assertEqual(game.set_hero_bonus("Heart Container", {mipha: 1}), [])

    def test_rune_challenges_exist(self) -> None:
        from ..data import ENFORCED_RUNES, RUNE_CHALLENGES, RUNES
        from ..data_challenges import CHALLENGE_BY_NAME
        self.assertTrue(set(RUNE_CHALLENGES) <= set(CHALLENGE_BY_NAME))
        self.assertTrue(set(RUNE_CHALLENGES.values()) <= set(RUNES) and set(ENFORCED_RUNES) <= set(RUNES))


class QuestRewardHookTests(unittest.TestCase):
    def test_reward_bytes_written_to_both_copies(self) -> None:
        from ..client.live_hook import LiveGame
        from ..data_rewards import BLOCK_SAVED_COPY, FLAGS, PROFILE
        fake = FakeGuest()
        prof, flags = fake.base + 0x80000, fake.base + 0x90000
        fake.put(fake.base + 0x1000 + PROFILE, struct.pack("<Q", prof))
        fake.put(fake.base + 0x1000 + FLAGS, struct.pack("<Q", flags))
        fake.put(flags + 0x5E0, b"\x01")  # the vanilla hand-in gave it
        game = LiveGame(fake)
        values = {(PROFILE, 0x79E): 2, (FLAGS, 0x5E0): 0, (FLAGS, 0x5D9): 0}
        self.assertEqual(game.set_reward_bytes(values), [(PROFILE, 0x79E), (FLAGS, 0x5E0)])
        for block, base, offset, value in ((PROFILE, prof, 0x79E, 2), (FLAGS, flags, 0x5E0, 0)):
            for copy in (0, BLOCK_SAVED_COPY[block]):
                self.assertEqual(fake.read(base + copy + offset, 1), bytes([value]))
        self.assertEqual(game.set_reward_bytes(values), [])

    def test_quest_states_done_or_hidden(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        fake = FakeGuest()
        block = fake.base + 0xA0000
        fake.put(fake.base + 0x1000 + H.QUESTS, struct.pack("<Q", block))
        states = block + L.QUEST_STATE_LIVE
        for copy in (0, H.QUEST_SAVED_COPY):
            fake.put(states + copy, bytes([2] * L.QUEST_STATE_COUNT))
        game = LiveGame(fake)
        want = {"Brawny Blacksmiths": 3, "Gotta Have a Sign": 1}
        self.assertEqual(game.set_quest_states(want), ["Brawny Blacksmiths", "Gotta Have a Sign"])
        for copy in (0, H.QUEST_SAVED_COPY):
            self.assertEqual(fake.read(states + copy + L.QUEST_STATE_IDS["Brawny Blacksmiths"], 1), bytes([L.QUEST_DONE]))
            self.assertEqual(fake.read(states + copy + L.QUEST_STATE_IDS["Gotta Have a Sign"], 1), bytes([L.QUEST_HIDDEN]))
        self.assertEqual(game.set_quest_states(want), [])


class ProbeTests(unittest.TestCase):
    def test_watches_known_battle_object_flow_and_client_writes(self) -> None:
        import json
        from ..client import live_hook as H
        from ..client import probe as P

        class Mem:
            def __init__(self): self.m = {}
            def put(self, va, data): self.m[va] = bytearray(data)
            def read(self, va, n):
                for base, buf in self.m.items():
                    if base <= va and va + n <= base + len(buf):
                        return bytes(buf[va - base:va - base + n])
                if P.DATA_START <= va < P.DATA_END:
                    return bytes(n)
                return None

        mem = Mem()
        holder, B, char, flow = 0x10_0000_1000, 0x10_0000_2000, 0x10_0000_4000, 0x10_0000_8000
        mem.put(H.BATTLE, struct.pack("<Q", holder))
        mem.put(holder, struct.pack("<7Q", 0, 0, 0, 0, 0, 0, B))
        b = bytearray(0x400); struct.pack_into("<Q", b, 0x8, char)
        mem.put(B, b); mem.put(char, bytearray(0x800))
        mem.put(H.UNITS, struct.pack("<Q", flow)); mem.put(flow, struct.pack("<48I", *[0] * 44, 0x5400, 0, 0, 0))
        target = 0x10_0000_9000
        mem.put(target, b"\x02")
        H.WRITE_JOURNAL.clear()
        with tempfile.TemporaryDirectory() as tmp:
            probe = P.Probe(mem, Path(tmp))
            probe.tick()
            self.assertEqual(probe.candidates, [(H.BATTLE, B)])
            struct.pack_into("<I", mem.m[B], 0x64, 300)  # a rune cooldown starts
            struct.pack_into("<I", mem.m[flow], H.FLOW_STATE, 0x02005404)  # defeated
            now = time.time()
            for i in range(P.FIGHT_COUNT):  # the client forces a byte the game keeps changing back
                H.WRITE_JOURNAL.append((now, target, b"\x01", "set_quest_states"))
            H.WRITE_JOURNAL.append((now - 30, target + 1, b"\x05", "set_level"))  # one-off, undone (memory 0)
            mem.put(target, b"\x02\x00")
            probe.tick()
            probe.tick()  # the one-off write is due now
            probe.note("cleared Akkala Tower")
            lines = [json.loads(l) for l in probe.path.read_text().splitlines()]
            findings = [json.loads(l) for l in probe.findings.read_text().splitlines()]
        self.assertIn([hex(0x64), 0, 300], next(l for l in lines if "B" in l)["ch"])
        self.assertEqual([l["flow"] for l in lines if "flow" in l], ["00005400", "02005404"])
        self.assertEqual(lines[-1]["event"], "cleared Akkala Tower")
        snap = next(l for l in lines if "snap" in l)
        self.assertEqual((snap["snap"], len(snap["data"])), (hex(B), 2 * P.SNAPSHOT))
        fight = next(f for f in findings if f["finding"] == "fight")
        self.assertEqual((fight["address"], fight["by"], fight["flow"]), (hex(target), "set_quest_states", "02005404"))
        reverted = next(f for f in findings if f["finding"] == "reverted")
        self.assertEqual((reverted["address"], reverted["by"], reverted["now"]), (hex(target + 1), "set_level", "00"))


class QuestUnlockHookTests(unittest.TestCase):
    def test_hide_unless_done_and_open(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        fake = FakeGuest()
        block = fake.base + 0xA0000
        fake.put(fake.base + 0x1000 + H.QUESTS, struct.pack("<Q", block))
        states = block + L.QUEST_STATE_LIVE
        ids = L.QUEST_STATE_IDS
        for copy in (0, H.QUEST_SAVED_COPY):
            fake.put(states + copy, bytes([1] * L.QUEST_STATE_COUNT))
            fake.put(states + copy + ids["Surveying the Volcano"], b"\x02")      # game opened it: hide
            fake.put(states + copy + ids["Patrolling the Desert"], b"\x03")      # handed in already: keep
        game = LiveGame(fake)
        want = {"Surveying the Volcano": -1, "Patrolling the Desert": -1, "Regulating the Reservoir": 2}
        self.assertEqual(game.set_quest_states(want), ["Regulating the Reservoir", "Surveying the Volcano"])
        for copy in (0, H.QUEST_SAVED_COPY):
            self.assertEqual([fake.read(states + copy + ids[q], 1)[0] for q in want], [1, 3, 2])


class DeathLinkHookTests(unittest.TestCase):
    def test_hp_read_and_kill(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        fake = FakeGuest()
        game = LiveGame(fake)
        self.assertIsNone(game.player_hp())  # outside missions: nothing to read
        holder, player, char = fake.base + 0x50000, fake.base + 0x51000, fake.base + 0x52000
        fake.put(H.BATTLE, struct.pack("<Q", holder))
        fake.put(holder + H.BATTLE_PLAYER, struct.pack("<Q", player))
        fake.put(player + H.BATTLE_CHARACTER, struct.pack("<Q", char))
        fake.put(char + H.CHAR_HP, struct.pack("<ff", 1945.8, 2000.0))
        fake.put(char, struct.pack("<II", 1, 9))  # unit 1, kind 9
        self.assertAlmostEqual(game.player_hp(), 1945.8, places=1)  # no unit table yet: the display copy
        self.assertFalse(game.kill_player())  # writing only the display copy does nothing in game: refuse
        holder, units = fake.base + 0x53000, fake.base + 0x60000 - H.UNIT_RECORDS
        record = fake.base + 0x60000 + H.UNIT_SIZE
        fake.put(H.UNITS, struct.pack("<Q", holder))
        fake.put(holder + H.UNITS_TABLE, struct.pack("<Q", units))
        fake.put(H.UNIT_COUNT, struct.pack("<I", 140))
        fake.put(record, struct.pack("<II", 1, 9))
        fake.put(record + H.UNIT_HP, struct.pack("<fff", 1900.0, 1200.0, 2000.0))  # +0x48 can be lower than HP
        self.assertAlmostEqual(game.player_hp(), 1900.0)  # the real HP wins
        fake.put(holder + H.FLOW_STATE, struct.pack("<I", 0x5400))  # mission flow: playing, nothing requested
        self.assertTrue(game.kill_player())
        self.assertEqual(game.player_hp(), 0.0)
        self.assertEqual(struct.unpack("<f", fake.read(record + H.UNIT_HP, 4))[0], 0.0)
        self.assertEqual(struct.unpack("<f", fake.read(char + H.CHAR_HP, 4))[0], 0.0)
        self.assertEqual(struct.unpack("<I", fake.read(holder + H.FLOW_REQUEST, 4))[0], H.FLOW_DEFEATED)
        self.assertEqual(fake.read(holder + H.FLOW_FLAGS, 1), b"\x02")
        fake.put(record + H.UNIT_HP, struct.pack("<f", 1900.0))
        self.assertFalse(game.kill_player())  # a request is pending: not playing
        self.assertFalse(game.restart_mission())  # not taken yet
        fake.put(holder + H.FLOW_STATE, struct.pack("<III", 0x02005404, 0, 0))  # the game took it: defeated
        self.assertFalse(game.kill_player())
        self.assertTrue(game.restart_mission())
        self.assertEqual(struct.unpack("<I", fake.read(holder + H.FLOW_REQUEST, 4))[0], H.FLOW_RETRY)
        fake.put(holder + H.FLOW_STATE, struct.pack("<III", 0x5400, 0, 0))  # back to playing
        self.assertTrue(game.restart_mission())  # nothing left to do
        fake.put(record + H.UNIT_HP, struct.pack("<f", 0.0))
        fake.put(record + H.UNIT_HP, struct.pack("<f", 1900.0))
        fake.put(record, struct.pack("<II", 1, 18))  # another kind in that slot: not ours
        self.assertEqual(game.player_hp(), 0.0)  # back to the display copy
        self.assertFalse(game.kill_player())
        fake.put(char + H.CHAR_HP, struct.pack("<ff", 5.0, 3.0e9))  # not an HP pair: refuse
        self.assertIsNone(game.player_hp())
        self.assertFalse(game.kill_player())


class DifficultyGoalHookTests(unittest.TestCase):
    def test_harder_clears_count_for_easier_difficulties(self) -> None:
        from ..client import live_hook as H
        from ..client.live_hook import LiveGame
        fake = FakeGuest()
        table = fake.base + 0x60000
        fake.put(fake.base + 0x1000 + H.MISSIONS[0], struct.pack("<Q", table - H.MISSIONS[1]))
        hf, lab = L.MISSION_RECORD_IDS["The Battle of Hyrule Field"][0], L.MISSION_RECORD_IDS["Road to the Ancient Lab"][0]
        fake.put(table + hf * H.MISSIONS[2] + H.DIFFICULTY_TIMES, struct.pack("<6I", 0, 0, 640, 0, 0, 0))  # Hard
        fake.put(table + lab * H.MISSIONS[2] + H.DIFFICULTY_TIMES, struct.pack("<6I", 610, 0, 0, 0, 0, 0))  # Easy
        game = LiveGame(fake)
        self.assertTrue({"The Battle of Hyrule Field", "Road to the Ancient Lab"} <= game.cleared_missions_at(0))
        normal = game.cleared_missions_at(1)
        self.assertIn("The Battle of Hyrule Field", normal)
        self.assertNotIn("Road to the Ancient Lab", normal)
        self.assertNotIn("The Battle of Hyrule Field", game.cleared_missions_at(3))  # not on Very Hard


class ProbeWatcherTests(unittest.TestCase):
    def test_hand_in_rune_change_and_knock_out_are_recorded(self) -> None:
        import json
        from ..client import live_hook as H
        from ..client import probe as P

        class Mem:
            def __init__(self): self.m = {}
            def put(self, va, data): self.m[va] = bytearray(data)
            def read(self, va, n):
                for base, buf in self.m.items():
                    if base <= va and va + n <= base + len(buf):
                        return bytes(buf[va - base:va - base + n])
                return None

        mem = Mem()
        man, flags_obj = 0x10_0000_0000, 0x10_0001_0000
        blocks = {0x560: 0x10_0010_0000, 0x588: 0x10_0020_0000, 0x5A0: 0x10_0030_0000, 0x578: 0x10_0040_0000,
                  0x580: 0x10_0050_0000, H.STORY_FLAGS: flags_obj}
        mgr = bytearray(0x600)
        for field, addr in blocks.items():
            struct.pack_into("<Q", mgr, field, addr)
            mem.put(addr, bytearray(0x4000))
        mem.put(man, mgr)
        mem.put(H.MANAGER, struct.pack("<Q", man))
        holder, B, char = 0x10_0060_0000, 0x10_0061_0000, 0x10_0062_0000
        mem.put(H.BATTLE, struct.pack("<Q", holder))
        mem.put(holder, struct.pack("<7Q", 0, 0, 0, 0, 0, 0, B))
        b = bytearray(0x400); struct.pack_into("<Q", b, 0x8, char); mem.put(B, b)
        c = bytearray(0x800); struct.pack_into("<ff", c, 0x28, 800.0, 1600.0); mem.put(char, c)
        with tempfile.TemporaryDirectory() as tmp:
            probe = P.Probe(mem, Path(tmp))
            probe.watch(); probe._watch_save()
            mem.m[blocks[0x560]][0x809 + L.QUEST_STATE_IDS["Roast and Relaxation"]] = 3  # hand-in
            mem.m[blocks[0x588]][0x79E] = 1
            probe._watch_save()
            mem.m[flags_obj][H.STORY_FLAGS_OFFSET + H.RUNE_FLAGS["Magnesis"]] = 1  # Magnesis arrives
            mem.m[B][0x62] = 1
            struct.pack_into("<f", mem.m[char], 0x28, 0.0)  # knocked out
            probe.watch()
            found = [json.loads(l) for l in probe.findings.read_text().splitlines()]
        kinds = {f["finding"]: f for f in found}
        self.assertEqual(kinds["quest_done"]["quests"], [[L.QUEST_STATE_IDS["Roast and Relaxation"], "Roast and Relaxation"]])
        self.assertIn([hex(0x79E), 0, 1], kinds["quest_done"]["profile"])
        self.assertIn([hex(0x62), 0, 1], kinds["runes"]["B"])
        self.assertEqual(kinds["ko"]["max_hp"], 1600.0)
