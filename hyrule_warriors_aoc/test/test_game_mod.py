"""The bundled game mod (client/rune_mod.ips) must work on Ryujinx as well as Eden (2026-11-20: its code caves sat in
the page padding after the text segment, which Ryujinx doesn't load; the first cave run crashed Ryujinx at boot)."""
import struct
import unittest

TEXT_END = 0x1B55930  # v1.4.1 main NSO: the text segment's real length (Ryujinx loads only this much)
RODATA = 0x1B56000  # the next segment


def records(data: bytes):
    """(address, bytes) of each IPS32 record (address = NSO offset - 0x100 header = module offset)."""
    assert data.startswith(b"IPS32") and data.endswith(b"EEOF")
    pos, out = 5, []
    while data[pos:pos + 4] != b"EEOF":
        offset = int.from_bytes(data[pos:pos + 4], "big")
        size = int.from_bytes(data[pos + 4:pos + 6], "big")
        out.append((offset - 0x100, data[pos + 6:pos + 6 + size]))
        pos += 6 + size
    return out


class GameModTests(unittest.TestCase):
    def setUp(self) -> None:
        from ..client.rune_mod import patch_bytes
        self.records = records(patch_bytes())

    def test_nothing_in_the_padding_after_the_text_segment(self) -> None:
        for at, data in self.records:
            self.assertFalse(at < RODATA and at + len(data) > TEXT_END,
                             f"patch at {at:#x} lands in the text page padding (zeros on Ryujinx)")

    def test_every_branch_into_the_mod_stays_in_the_text_segment(self) -> None:
        for at, data in self.records:
            if at >= TEXT_END:
                continue  # (data patches)
            for k in range(0, len(data) - 3, 4):
                word = struct.unpack_from("<I", data, k)[0]
                if word >> 26 in (0b000101, 0b100101):  # b / bl
                    imm = word & 0x3FFFFFF
                    target = at + k + ((imm - (1 << 26) if imm >> 25 else imm) << 2)
                    self.assertLess(target, TEXT_END, f"branch at {at + k:#x} to {target:#x}")

    def test_client_recognises_the_deathlink_hook(self) -> None:
        from ..client.rune_mod import DEATHLINK_HOOK, DEATHLINK_HOOK_CODE
        self.assertIn((DEATHLINK_HOOK, DEATHLINK_HOOK_CODE), [(at, d) for at, d in self.records])


if __name__ == "__main__":
    unittest.main()
