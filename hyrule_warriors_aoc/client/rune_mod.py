"""The Age of Calamity Archipelago game mod "AoC Archipelago" (0.9.89+): one ExeFS patch (IPS32) for the game's v1.4.1
main module, installed by the client into Eden and Ryujinx. It holds every game patch the randomizer needs (so far the
rune patch below); the frame rate (client/framerate.py) is set live by the client and needs no patch.

Rune patch:

The game gives a rune when its story flag is set OR the mission it comes from is cleared (Remote Bombs and Cryonis:
The Battle of Hyrule Field; Magnesis and Stasis: Road to the Ancient Lab), so clears handed runes out whatever the
randomizer said. The patch points every constant rune check at unused story flags only the client sets (ids 96-99,
save 0x73-0x76, no linked mission) and the two Remote Bombs checks that gate the whole rune menu at id 111 (save 0x82,
"the Sheikah Slate"). Story scripts read the real flags through a register, so they still work (Hyrule Field's
moblins). Found with Eden's GDB stub 2026-11-14 (REVERSE_ENGINEERING.md "The story flag check and the rune mod").

With the patch in place, rune availability = what the client writes, for every seed: so the client always writes those
flags while the patch is active (vanilla runes follow the clears, start-with-all gives all four).

install() copies the patch into Eden's and Ryujinx's mod folders (load/<title>/AoC Archipelago/exefs and
mods/contents/<title>/AoC Archipelago/exefs), only while no emulator runs (it is read at boot), and removes copies under
an earlier name ("AoC Archipelago Runes", 0.9.89 test builds)."""
from __future__ import annotations

import os
import pkgutil

from .savewatch import AOC_TITLE, eden_data_roots, ryujinx_data_roots

BUILD_ID = "E5F275B5D0889899E55DE1A164EEF060D547B0A8"  # v1.4.1 main NSO
MOD_NAME = "AoC Archipelago"
OLD_MOD_NAMES = ("AoC Archipelago Runes",)
PATCH_FILE = "rune_mod.ips"
# A patched instruction to recognise the patch in memory: text 0xF83D8 "mov w0, #111" (vanilla "mov w0, #6").
CHECK_OFFSET, CHECK_PATCHED, CHECK_VANILLA = 0xF83D8, bytes.fromhex("e00d8052"), bytes.fromhex("c0008052")
# Story flag table offsets (from save 0x14, as live_hook.RUNE_FLAGS) of the flags the patched game reads.
MOD_RUNE_FLAGS = {"Remote Bombs": 0x73 - 0x14, "Cryonis": 0x74 - 0x14, "Magnesis": 0x75 - 0x14, "Stasis": 0x76 - 0x14,
                  "Sheikah Slate": 0x82 - 0x14}


def patch_bytes() -> bytes:
    data = pkgutil.get_data(__package__, PATCH_FILE)
    if not data or not data.startswith(b"IPS32"):
        raise OSError("rune mod patch missing from the apworld")
    return data


def mod_folders(name: str = MOD_NAME) -> list[str]:
    """exefs folders the patch goes into: every Eden user folder and every Ryujinx data folder found."""
    out = [os.path.join(root, "load", AOC_TITLE, name, "exefs") for root in eden_data_roots()]
    out += [os.path.join(root, "mods", "contents", AOC_TITLE.lower(), name, "exefs") for root in ryujinx_data_roots()]
    return out


def remove_old() -> list[str]:
    """Remove the mod's copies under earlier names (two copies of the same patch would both apply)."""
    import shutil
    removed = []
    for name in OLD_MOD_NAMES:
        for exefs in mod_folders(name):
            folder = os.path.dirname(exefs)
            files = set(os.listdir(exefs)) if os.path.isdir(exefs) else set()
            if os.path.isdir(folder) and set(os.listdir(folder)) <= {"exefs"} and files <= {BUILD_ID + ".ips"}:
                shutil.rmtree(folder, ignore_errors=True)
                removed.append(folder)
    return removed


def install(folders: list[str] | None = None) -> list[str]:
    """Write the patch where it is missing or outdated. Returns the files written. Call only with no emulator running."""
    data = patch_bytes()
    written = []
    for folder in mod_folders() if folders is None else folders:
        path = os.path.join(folder, BUILD_ID + ".ips")
        try:
            with open(path, "rb") as f:
                if f.read() == data:
                    continue
        except OSError:
            pass
        os.makedirs(folder, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        written.append(path)
    return written
