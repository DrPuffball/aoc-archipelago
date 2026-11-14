"""
Read and write the memory of Age of Calamity running in Ryujinx (Windows), with no extra packages.

Ryujinx in its default "SoftwarePageTable" memory mode keeps a page table in its own memory: one u64 per
4 KiB guest page, holding the host address of that page. We find the table by asking which allocation's
entry for the game's save-writer function points at memory that holds that function's code, then
translate every guest address through it. All addresses below were read from the running game and
checked against the save file (tools/RESEARCH.md, session 4).
"""

from __future__ import annotations

import ctypes
import struct
import sys

MODULE_BASE = 0x8504000          # guest address of the game's main module in Ryujinx
WRITER = 0x9ACF60                 # module offset of the save writer (used to recognise the code)
WRITER_SIG = bytes.fromhex(
    "ff0301d1f50b00f9f44f02a9fd7b03a9fdc3009148ef00f008814439f30300aa"
    "e804003621aa009021641191e0630091e2031f32979e469408544092f40300aa")

if sys.platform == "win32":
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.POINTER(ctypes.c_size_t)]
    _k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.POINTER(ctypes.c_size_t)]
    _k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]

    class _MBI(ctypes.Structure):
        _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                    ("AllocationProtect", wintypes.DWORD), ("PartitionId", wintypes.WORD),
                    ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD), ("Protect", wintypes.DWORD),
                    ("Type", wintypes.DWORD)]

    class _PE32(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    _k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PE32)]
    _k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PE32)]


EMULATOR_EXES = {"ryujinx.exe": "Ryujinx", "eden.exe": "Eden"}  # supported emulators (auto-detected)


def emulator_processes() -> list[tuple[int, str]]:
    """(pid, emulator name) of every running supported emulator."""
    if sys.platform != "win32":
        return []
    snap = _k32.CreateToolhelp32Snapshot(0x2, 0)
    found = []
    entry = _PE32()
    entry.dwSize = ctypes.sizeof(_PE32)
    ok = _k32.Process32FirstW(snap, ctypes.byref(entry))
    while ok:
        name = EMULATOR_EXES.get(entry.szExeFile.lower())
        if name:
            found.append((entry.th32ProcessID, name))
        ok = _k32.Process32NextW(snap, ctypes.byref(entry))
    _k32.CloseHandle(snap)
    return found


def ryujinx_pids() -> list[int]:
    """Pids of every supported emulator (Ryujinx and, since 0.9.73, Eden; the name predates Eden)."""
    return [pid for pid, _ in emulator_processes()]


GAME_TITLE_MARKS = ("Age of Calamity", "01002B00111A2000")  # in Ryujinx's window title while the game runs


def ryujinx_window_titles() -> list[str]:
    """Titles of Ryujinx's visible windows (they name the running game, whatever the memory manager mode)."""
    if sys.platform != "win32":
        return []
    pids = set(ryujinx_pids())
    if not pids:
        return []
    user32 = ctypes.windll.user32
    titles: list[str] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(512)
            if user32.GetWindowTextW(hwnd, buf, 512):
                titles.append(buf.value)
        return True

    user32.EnumWindows(visit, 0)
    return titles


GUEST_MEMORY_MIN = 2 << 30  # Ryujinx reserves the guest's memory (3 GiB for AoC) only while a game runs


def game_in_window() -> bool:
    """Some game is running in Ryujinx, whatever the memory manager mode: its window title names it, or Ryujinx holds
    a guest-memory sized block (Ryujinx 1.3.3's title shows no game name [seen 2026-10-28], so the block decides;
    3.14 GiB while AoC ran)."""
    if any(mark in t for t in ryujinx_window_titles() for mark in GAME_TITLE_MARKS):
        return True
    for pid in ryujinx_pids():
        try:
            proc = Process(pid)
        except OSError:
            continue
        try:
            if any(size >= GUEST_MEMORY_MIN for _, size in proc.allocations(GUEST_MEMORY_MIN)):
                return True
        finally:
            proc.close()
    return False


def ryujinx_exe_dirs() -> list[str]:
    """Folders of the running Ryujinx programs (a portable install keeps its data in <folder>/portable)."""
    if sys.platform != "win32":
        return []
    out = []
    for pid in ryujinx_pids():
        h = _k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            continue
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                import os
                out.append(os.path.dirname(buf.value))
        finally:
            _k32.CloseHandle(h)
    return out


class Process:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.h = _k32.OpenProcess(0x0400 | 0x0010 | 0x0020 | 0x0008, False, pid)
        if not self.h:
            raise OSError(f"cannot open Ryujinx (pid {pid}), error {ctypes.get_last_error()}")

    def close(self) -> None:
        if self.h:
            _k32.CloseHandle(self.h)
            self.h = None

    def read(self, addr: int, n: int) -> bytes | None:
        buf = (ctypes.c_char * n)()
        got = ctypes.c_size_t(0)
        if not _k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)) or got.value != n:
            return None
        return buf.raw

    def write(self, addr: int, data: bytes) -> bool:
        got = ctypes.c_size_t(0)
        return bool(_k32.WriteProcessMemory(self.h, ctypes.c_void_p(addr), data, len(data), ctypes.byref(got))) \
            and got.value == len(data)

    def age_seconds(self) -> float | None:
        """How long ago the process started (GetProcessTimes), or None if unknown."""
        times = [ctypes.c_ulonglong() for _ in range(4)]
        if not _k32.GetProcessTimes(self.h, *(ctypes.byref(t) for t in times)):
            return None
        now = ctypes.c_ulonglong()
        _k32.GetSystemTimeAsFileTime(ctypes.byref(now))
        return (now.value - times[0].value) / 1e7

    def regions(self):
        """(base, size, state) of every region of the address space (state 0x10000 free, 0x2000 reserved, 0x1000
        committed)."""
        mbi = _MBI()
        addr = 0
        while addr < 0x7FFFFFFFFFFF:
            if not _k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
                break
            base, size = mbi.BaseAddress or 0, mbi.RegionSize
            yield base, size, mbi.State
            addr = base + size

    def allocations(self, min_size: int):
        """(allocation base, region size) of committed regions at least min_size long."""
        mbi = _MBI()
        addr, seen = 0, set()
        while addr < 0x7FFFFFFFFFFF:
            if not _k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
                break
            base, size = mbi.BaseAddress or 0, mbi.RegionSize
            if mbi.State == 0x1000 and size >= min_size and mbi.AllocationBase not in seen:
                seen.add(mbi.AllocationBase)
                yield mbi.AllocationBase, size
            addr = base + size


class Guest:
    """Guest-address access through Ryujinx's software page table."""

    def __init__(self, proc: Process, page_table: int) -> None:
        self.p = proc
        self.pt = page_table
        self._cache: dict[int, int] = {}

    @classmethod
    def attach(cls, proc: Process) -> "Guest | None":
        idx = ((MODULE_BASE + WRITER) >> 12) * 8
        for alloc, _size in proc.allocations(0x1000000):
            raw = proc.read(alloc + idx, 8)
            if not raw:
                continue
            host = struct.unpack("<Q", raw)[0]
            if host and proc.read(host + (WRITER & 0xFFF), len(WRITER_SIG)) == WRITER_SIG:
                return cls(proc, alloc)
        return None

    def host(self, va: int) -> int | None:
        page = va >> 12
        raw = self.p.read(self.pt + page * 8, 8)
        if not raw:
            return None
        e = struct.unpack("<Q", raw)[0]
        return e + (va & 0xFFF) if e else None

    def read(self, va: int, n: int) -> bytes | None:
        out = []
        while n > 0:
            h = self.host(va)
            k = min(n, 0x1000 - (va & 0xFFF))
            chunk = self.p.read(h, k) if h else None
            if chunk is None:
                return None
            out.append(chunk)
            va += k
            n -= k
        return b"".join(out)

    def write(self, va: int, data: bytes) -> bool:
        while data:
            h = self.host(va)
            k = min(len(data), 0x1000 - (va & 0xFFF))
            if not h or not self.p.write(h, data[:k]):
                return False
            va += k
            data = data[k:]
        return True

    def u64(self, va: int) -> int | None:
        raw = self.read(va, 8)
        return struct.unpack("<Q", raw)[0] if raw else None

    def code_ok(self) -> bool:
        return self.read(MODULE_BASE + WRITER, len(WRITER_SIG)) == WRITER_SIG


# --- Eden (yuzu family) ---------------------------------------------------------------------------------------------
# Eden maps the guest's address space into one host reservation ("fastmem", on by default): guest address g lives at
# arena + g. Seen live (Eden 0.2.1, 2026-11-02): the game's module starts exactly at a committed region (one read per
# region finds it by the save writer's code), but at another guest address than in Ryujinx (0x29B33000, not 0x8504000),
# and the arena start is not a region boundary. So: find the module, then its guest address M (arena = module host - M).
# M comes from a slot at the start of the module's data that holds its own guest address (M + 0x263E000 seen live:
# M = 0x8071A000); if that ever fails, every page-aligned M is tried once (~15 s) until a pointer the module holds
# (the game state manager) leads to a loaded save. Confirmed live 2026-11-02: clears and rupees read from Eden match
# the save file.
MODULE_SPAN = 0x3000000                   # module code + data the client uses (offsets up to 0x2D00000)
SELF_POINTER = 0x263E000                  # module offset of a slot holding its own guest address
MODULE_GUEST_MAX = 1 << 32                # module guest addresses tried by the fallback search (page steps)
_EDEN_CACHE: dict[tuple[int, int], tuple[int, int]] = {}  # (pid, module host) -> (arena, module guest address)
_EDEN_SEARCHED: set[tuple[int, int, int]] = set()  # (pid, module host, manager pointer) the slow search failed for


class FastmemGuest:
    """Guest-address access through Eden's fastmem arena."""

    def __init__(self, proc: Process, arena: int, module_base: int) -> None:
        self.p = proc
        self.arena = arena
        self.shift = module_base - MODULE_BASE

    @staticmethod
    def modules(proc: Process) -> list[int]:
        """Host addresses where the game's module starts (committed regions holding the save writer's code)."""
        return [base for base, size, state in proc.regions()
                if state == 0x1000 and size > WRITER + len(WRITER_SIG)
                and proc.read(base + WRITER, len(WRITER_SIG)) == WRITER_SIG]

    @classmethod
    def attach(cls, proc: Process, anchor: int, ok) -> "FastmemGuest | None":
        """anchor: module offset of a pointer into game memory (the state manager); ok(guest): the save reads
        right. None until the game runs with a save loaded."""
        for module in cls.modules(proc):
            cached = _EDEN_CACHE.get((proc.pid, module))
            if cached:
                guest = cls(proc, *cached)
                if ok(guest):
                    return guest
            raw = proc.read(module + SELF_POINTER, 8)
            guess = struct.unpack("<Q", raw)[0] - SELF_POINTER if raw else -1
            if guess >= 0 and not guess & 0xFFF and guess < 1 << 39:
                guest = cls(proc, module - guess, guess)
                if ok(guest):
                    _EDEN_CACHE[(proc.pid, module)] = (module - guess, guess)
                    return guest
            raw = proc.read(module + anchor, 8)
            pointer = struct.unpack("<Q", raw)[0] if raw else 0
            if not 0x1000 < pointer < 1 << 39:
                continue  # title screen: the manager is not set up yet
            if (proc.pid, module, pointer) in _EDEN_SEARCHED:
                continue  # searched for this state already: wait for the save to change it
            _EDEN_SEARCHED.add((proc.pid, module, pointer))
            for guest_base in range(0, MODULE_GUEST_MAX, 0x1000):
                arena = module - guest_base
                if proc.read(arena + pointer, 8) is None:
                    continue
                guest = cls(proc, arena, guest_base)
                if ok(guest):
                    _EDEN_CACHE[(proc.pid, module)] = (arena, guest_base)
                    return guest
        return None

    def host(self, va: int) -> int | None:
        if MODULE_BASE <= va < MODULE_BASE + MODULE_SPAN:
            va += self.shift
        return self.arena + va if 0 <= va < 1 << 39 else None

    def read(self, va: int, n: int) -> bytes | None:
        h = self.host(va)
        return self.p.read(h, n) if h is not None else None

    def write(self, va: int, data: bytes) -> bool:
        h = self.host(va)
        return h is not None and self.p.write(h, data)

    def u64(self, va: int) -> int | None:
        raw = self.read(va, 8)
        return struct.unpack("<Q", raw)[0] if raw else None

    def code_ok(self) -> bool:
        return self.read(MODULE_BASE + WRITER, len(WRITER_SIG)) == WRITER_SIG
