"""Live world-map redraw (live_hook.refresh_map, user 2026-11-19: no more pausing to see what opened)."""
import struct
import unittest

from .test_save import FakeGuest


class SceneGuest(FakeGuest):
    """FakeGuest whose map scene takes a requested state on the next read, like the game's next frame."""

    def __init__(self) -> None:
        super().__init__()
        H = self.H
        self.scene = self.base + 0x60000
        holder, mid = self.base + 0x61000, self.base + 0x62000
        self.put(H.MODULE_BASE + H.MAP_SCENE_ROOT, struct.pack("<Q", holder))
        self.put(holder + H.MAP_SCENE_PATH[0], struct.pack("<Q", mid))
        self.put(mid + H.MAP_SCENE_PATH[1], struct.pack("<Q", self.scene))
        self.put(self.scene, struct.pack("<Q", H.MODULE_BASE + H.MAP_SCENE_VTABLE))
        self.put(self.scene + H.MAP_SCENE_TAB, struct.pack("<i", H.MAP_TAB_MAP))
        self.requests: list[int] = []
        self.takes = True

    def set_state(self, state: int) -> None:
        self.put(self.scene + self.H.MAP_SCENE_STATE, struct.pack("<ii", state, state))

    def write(self, va: int, data: bytes) -> bool:
        if va == self.scene + self.H.MAP_SCENE_STATE + 4:
            self.requests.append(struct.unpack("<i", data)[0])
        self.put(va, data)
        return True

    def read(self, va: int, n: int) -> bytes:
        if self.takes and va == self.scene + self.H.MAP_SCENE_STATE:
            req = struct.unpack("<i", super().read(va + 4, 4))[0]
            self.put(va, struct.pack("<i", req))
        return super().read(va, n)


class MapRefreshTests(unittest.TestCase):
    def setUp(self) -> None:
        from ..client.live_hook import LiveGame
        self.fake = SceneGuest()
        self.game = LiveGame(self.fake)

    def test_idle_map_runs_the_menu_close_sequence(self) -> None:
        self.fake.set_state(14)
        self.assertTrue(self.game.refresh_map())
        self.assertEqual(self.fake.requests, [0, 1])  # the menu state, then the rebuild (as closing the menu does)

    def test_only_when_idle(self) -> None:
        for state in (0, 10, 13):  # pause menu, a reveal, settling after a rebuild
            self.fake.set_state(state)
            self.assertFalse(self.game.refresh_map())
        self.assertEqual(self.fake.requests, [])

    def test_only_on_the_map_tab(self) -> None:
        self.fake.set_state(14)
        for tab in (3, 5, 7):  # Services, Chapters (a redraw there closes the list), Quests
            self.fake.put(self.fake.scene + self.fake.H.MAP_SCENE_TAB, struct.pack("<i", tab))
            self.assertEqual(self.game.map_tab(), tab)
            self.assertFalse(self.game.refresh_map())
        self.assertEqual(self.fake.requests, [])

    def test_wrong_object_left_alone(self) -> None:
        self.fake.set_state(14)
        self.fake.put(self.fake.scene, struct.pack("<Q", 0x1234))  # not the map scene's vtable
        self.assertFalse(self.game.refresh_map())
        self.assertEqual(self.fake.requests, [])

    def test_request_not_taken_puts_idle_back(self) -> None:
        self.fake.set_state(14)
        self.fake.takes = False  # (the game didn't take the menu state: leave the map as it was)
        self.assertFalse(self.game.refresh_map())
        self.assertEqual(self.fake.requests, [0, 14])


if __name__ == "__main__":
    unittest.main()
