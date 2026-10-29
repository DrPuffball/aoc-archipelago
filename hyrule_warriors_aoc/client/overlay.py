"""
On-screen notices over Ryujinx: a small borderless, always-on-top, click-through box in the top-right corner of the
Ryujinx window ("Received X from Y" and the client's other notices), each shown for a few seconds. It follows the
Ryujinx window and hides while Ryujinx is not the active window, so it never covers other programs.

Runs tkinter in its own thread (every Tk call stays in that thread); the client only queues text. Windows only;
anything going wrong turns the overlay off quietly (it is a convenience, never worth disturbing play).
"""

from __future__ import annotations

import logging
import queue
import sys
import threading
import time

logger = logging.getLogger("AgeOfCalamity")

SHOW_SECONDS = 7.0  # one notice at a time (user: several at once in a large font were cut off)
BUSY_SECONDS = 3.5  # each notice's turn while more are waiting
MARGIN_X, MARGIN_Y = 24, 64  # from the Ryujinx window's top-right corner (clears its menu bar)
STATUS_MARGIN_Y = 48  # the cursor panel: from the bottom-right corner (clears Ryujinx's status bar)
STATUS_BACKGROUND = "#1d2a1f"
BACKGROUND, FOREGROUND = "#141820", "#f2e6c4"
_pids: list = [0.0, set()]  # (when read, Ryujinx process ids)


class Overlay:
    def __init__(self) -> None:
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None
        self.enabled = sys.platform == "win32"
        self.status: str | None = None  # the cursor panel's text (shown while set; None hides it)

    def _start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="AoC overlay", daemon=True)
            self._thread.start()

    def show(self, text: str) -> None:
        """A notice (top-right), shown for a few seconds, one at a time."""
        if not self.enabled or not text:
            return
        self._start()
        self._queue.put(text)

    def set_status(self, text: str | None) -> None:
        """The cursor panel (bottom-right): stays while text is set (what the highlighted map entry holds)."""
        if not self.enabled:
            return
        self.status = text or None
        if text:
            self._start()

    # --- overlay thread ---------------------------------------------------------------------

    def _run(self) -> None:
        try:
            self._loop()
        except Exception as e:  # never let the overlay take the client down
            logger.debug("overlay stopped: %s", e)
            self.enabled = False

    def _loop(self) -> None:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.88)
        root.configure(bg=BACKGROUND)
        label = tk.Label(root, bg=BACKGROUND, fg=FOREGROUND, font=("Segoe UI", 10), justify="left", anchor="w",
                         padx=10, pady=6)
        label.pack()
        root.update_idletasks()
        _click_through(root)
        panel = tk.Toplevel(root)
        panel.withdraw()
        panel.overrideredirect(True)
        panel.attributes("-topmost", True)
        panel.attributes("-alpha", 0.9)
        panel.configure(bg=STATUS_BACKGROUND)
        status_label = tk.Label(panel, bg=STATUS_BACKGROUND, fg=FOREGROUND, font=("Segoe UI", 10), justify="left",
                                anchor="w", padx=10, pady=6)
        status_label.pack()
        panel.update_idletasks()
        _click_through(panel)
        panel_shown = False
        pending: list[str] = []
        current: tuple[float, str] | None = None  # (shown until, text): one notice at a time (user request)
        shown = False
        while self.enabled:
            now = time.monotonic()
            while True:
                try:
                    pending.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if current and current[0] <= now:
                current = None
            if current is None and pending:
                # a shorter turn each while more are waiting, so a burst of items doesn't take minutes
                current = (now + (SHOW_SECONDS if len(pending) == 1 else BUSY_SECONDS), pending.pop(0))
            status = self.status
            rect = _ryujinx_rect() if current or status else None
            if status and rect:
                span = rect[2] - rect[0]
                status_label.configure(text=status, wraplength=max(240, int(span * 0.4)),
                                       font=("Segoe UI", max(9, min(12, span // 140))))
                panel.update_idletasks()
                width, height = panel.winfo_reqwidth(), panel.winfo_reqheight()
                x = max(rect[0] + MARGIN_X, rect[2] - width - MARGIN_X)
                panel.geometry(f"{width}x{height}+{x}+{rect[3] - height - STATUS_MARGIN_Y}")
                if not panel_shown:
                    panel.deiconify()
                    panel.attributes("-topmost", True)
                    _click_through(panel)
                    panel_shown = True
            elif panel_shown:
                panel.withdraw()
                panel_shown = False
            if current and rect:
                span = rect[2] - rect[0]
                text = current[1] + (f"   (+{len(pending)} more)" if pending else "")
                label.configure(text=text, wraplength=max(240, int(span * 0.4)),
                                font=("Segoe UI", max(9, min(12, span // 140))))
                root.update_idletasks()
                width, height = root.winfo_reqwidth(), root.winfo_reqheight()
                x, y = max(rect[0] + MARGIN_X, rect[2] - width - MARGIN_X), rect[1] + MARGIN_Y
                root.geometry(f"{width}x{height}+{x}+{y}")
                if not shown:
                    root.deiconify()
                    root.attributes("-topmost", True)
                    _click_through(root)
                    shown = True
            elif shown:
                root.withdraw()
                shown = False
            root.update()
            time.sleep(0.1)
        root.destroy()


def _click_through(root) -> None:
    """Mouse clicks pass through, no taskbar button, never takes focus from the game."""
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
    GWL_EXSTYLE = -20
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style |= 0x80000 | 0x20 | 0x80 | 0x08000000  # LAYERED | TRANSPARENT | TOOLWINDOW | NOACTIVATE
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


def _ryujinx_rect() -> tuple[int, int, int, int] | None:
    """Screen rectangle (left, top, right, bottom) of the Ryujinx window when it is the active window, else None."""
    import ctypes
    from ctypes import wintypes
    from .ryujinx import ryujinx_pids

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    now = time.monotonic()
    if now - _pids[0] > 5:  # the process list is re-read every few seconds, not every frame
        _pids[:] = [now, set(ryujinx_pids())]
    if pid.value not in _pids[1] or user32.IsIconic(hwnd):
        return None
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)) or rect.right - rect.left < 320:
        return None
    return rect.left, rect.top, rect.right, rect.bottom
