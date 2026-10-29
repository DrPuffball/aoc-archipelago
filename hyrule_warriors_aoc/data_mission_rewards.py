"""
Mission rewards: LinkData2 table 009cba94 (16-byte header + 400 rows of 64 bytes, row = mission record). Decoded in
tools/RESEARCH.md session 13 and matched against published reward lists: first-clear reward counts u16 at +0x04..+0x0E,
material ids + 1 (u8) at +0x24..+0x29; a second list (counts +0x10..+0x1E, ids +0x32..+0x36). Kept here so the client
always knows the vanilla rows, even after it has rewritten the live table.
"""

from __future__ import annotations

import base64
import zlib

ROW_SIZE, ROWS, HEADER = 64, 400, 16
_PACKED = (
    "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"
)
TABLE = zlib.decompress(base64.b64decode("".join(_PACKED)))
assert len(TABLE) == HEADER + ROWS * ROW_SIZE


def vanilla_row(record: int) -> bytes:
    return TABLE[HEADER + record * ROW_SIZE: HEADER + (record + 1) * ROW_SIZE]


def has_rewards(record: int) -> bool:
    """A row that gives something on its first clear (record ids with an empty row are unused or special)."""
    row = vanilla_row(record)
    return any(row[0x24:0x2A]) and any(row[0x04:0x10])
