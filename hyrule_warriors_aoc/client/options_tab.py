"""The client's "Options" tab: buttons and toggles for the typed / commands (user, 2026-11-18: "an Options tab
instead of typing /fps").

Every control sends the same text a player would type ("/fps 60", "/goal_banner off", ...) through the window's
command processor, so the tab never has its own copy of a command's logic; the command's answer lands in the log as
if typed. The tab reads its state (option_state) from the client every half second, so a command typed in the text
box shows up here too. Everything above build_options_tab works without a window (unit tests)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("Client")

FPS_CHOICES = (("seed", "YAML"), ("off", "Game's 30"), ("60", "60"), ("120", "120"),
               ("unlimited", "Unlimited"))
BANNER_CHOICES = (("seed", "YAML"), ("on", "On"), ("off", "Off"))
DEATHLINK_CHOICES = (("seed", "YAML"), ("on", "On"), ("off", "Off"))
RESEARCH_CHOICES = (("on", "On"), ("off", "Off"))
CUTSCENE_CHOICES = (("off", "Game's 30"), ("on", "Match gameplay"))
MAP_CHOICES = (("off", "Game's 30"), ("on", "Match gameplay (experimental)"))

# The tab, grouped by what things are for (user, 2026-11-20: the old "Asks first" row grouped by behaviour, which
# wasn't intuitive). Sections in order; in each, its buttons (rows of 4), then its choice rows.
SECTIONS = ("Frame rate", "Display", "Multiworld", "Your progress", "Saves", "Troubleshooting")
# (section, command name, row title, choices, option_state key)
CHOICE_ROWS = (
    ("Frame rate", "fps", "Gameplay", FPS_CHOICES, "fps"),
    ("Frame rate", "fps_cutscenes", "Pause menu", CUTSCENE_CHOICES, "fps_cutscenes"),
    ("Display", "goal_banner", "Goal banner", BANNER_CHOICES, "banner"),
    ("Multiworld", "deathlink", "DeathLink", DEATHLINK_CHOICES, "deathlink"),
    ("Troubleshooting", "research", "Game research", RESEARCH_CHOICES, "research"),
)
# (section, label, command, confirm text or None, needs, warn). A confirm text asks first (label ends in "…");
# needs: None, "slot" (connected to the server) or "held" (clears held back) - greyed out otherwise; warn = can't be
# undone (warning-coloured).
BUTTONS = (
    ("Your progress", "Goal / to do", "/todo", None, "slot", False),
    ("Your progress", "Inventory", "/inventory", None, "slot", False),
    ("Your progress", "Deliveries", "/deliver", None, "slot", False),
    ("Your progress", "Gathered", "/gathered", None, "slot", False),
    ("Saves", "Saves list", "/saves", None, None, False),
    ("Saves", "Sync saves", "/sync_saves", None, "slot", False),
    ("Saves", "Sync saves anyway…", "/sync_saves force",
     "Copy this seed's newest save to the other emulator even if it has fewer story clears (after a New Game)? "
     "The other emulator's save is backed up first.", "slot", False),
    ("Saves", "Install starter save…", "/starter_save",
     "Put this seed's save in place now, even over a save with progress the client doesn't know? That save is kept in "
     "AoC_Archipelago/saves as unclaimed. Close the game first.", "slot", False),
    ("Saves", "Show save folders", "/emulator_folder", None, None, False),  # (then the folder picker, same line)
    ("Troubleshooting", "Check game connection", "/check_hook", None, None, False),
    ("Troubleshooting", "Connection details", "/game", None, None, False),
    ("Troubleshooting", "Accept held clears…", "/accept_save",
     "Send the clears the client held back? Only if this really is this seed's save: they can't be taken back.",
     "held", True),
    ("Troubleshooting", "No Expansion Pass…", "/no_dlc",
     "Your game has no Expansion Pass: take it out of this seed's goal and send its checks? This can't be undone.",
     "slot", True),
)
# (older names, kept for the tests and anything importing them)
ACTIONS = tuple((label, command, None) for _, label, command, ask, _, _ in BUTTONS if not ask)
DANGER = tuple((label, command, ask) for _, label, command, ask, _, _ in BUTTONS if ask)
NEEDS_HELP = {"slot": "Connect to your slot first.", "held": "Nothing is held back right now."}
WARN_COLOUR = (1, 0.55, 0.45, 1)

# What each control does, shown in the help line while the mouse is over it (user, 2026-11-18).
HELP_DEFAULT = "Point at a button to see what it does. Buttons ending in … ask before doing anything."
CHOICE_HELP = {
    "fps": {"seed": "Frame rate: whatever your YAML's frame_rate says.",
            "60": "Frame rate: up to 60 FPS in gameplay; the game still runs at real-time speed.",
            "120": "Frame rate: up to 120 FPS in gameplay; the game still runs at real-time speed.",
            "unlimited": "Frame rate: as fast as your PC allows in gameplay; the game still runs at real-time speed.",
            "off": "Frame rate: the game's own 30 FPS; the client leaves it alone (also for another frame-rate mod)."},
    "fps_cutscenes": {"off": "The pause menu: the game's own 30 FPS. (Cutscenes, special attacks and a mission's last "
                             "seconds always run at the game's own 30.)",
                      "on": "Experimental: the pause menu at the gameplay frame rate too (at most 60 there). Story and "
                            "video cutscenes stay at the game's own 30."},
    "fps_map": {"off": "World map: the game's own 30 FPS (the safe default).",
                "on": "Experimental: the world map at the gameplay frame rate too (scrolling, zoom and the pings "
                      "keep their speed; other map animations are not all checked yet)."},
    "goal_banner": {"seed": "Goal banner: whatever your YAML's goal_banner says.",
                    "on": "Goal banner: show your goal progress at the top of the emulator window on the world map.",
                    "off": "Goal banner: hide it."},
    "deathlink": {"seed": "DeathLink: whatever your YAML's death_link says.",
                  "on": "DeathLink on: when a linked player dies you die too (instantly, the normal defeat menu), and "
                        "they do when you fall in a mission. Takes effect at once.",
                  "off": "DeathLink off: deaths are neither received nor sent. Takes effect at once."},
    "research": {"on": "Game research: record what the game does with each randomizer change (for testers; nothing "
                       "leaves your PC). Starts when the game is next found.",
                 "off": "Game research: stop recording."},
}
ACTION_HELP = {
    "/check_hook": "Check that the client is hooked into the game and in step with this seed.",
    "/game": "Show the game hook's connection and this seed's state.",
    "/todo": "What your goal needs, how far you are, what you can play now and which heroes you may use.",
    "/inventory": "Everything the multiworld has given you so far.",
    "/deliver": "What the client has put in your game, and what is still waiting for the game to run.",
    "/saves": "Which seed each save belongs to, and the saves kept for seeds you're not playing now.",
    "/gathered": "Material and enemy checks: your totals gathered / defeated so far and the next count each needs.",
    "/sync_saves": "Copy this seed's newest save to the other emulator (Ryujinx <-> Eden) now. The other emulator's "
                   "save is backed up first.",
    "/emulator_folder": "Show where the client looks for your Ryujinx and Eden saves, and the saves it found.",
    "pick_folder": "Choose your Ryujinx or Eden folder (the one the emulator's File menu opens) when the client can't find "
                   "your save by itself.",
    "/sync_saves force": "ASKS FIRST. Copy this seed's save to the other emulator even if it has fewer story clears "
                         "(after a New Game). The other save is backed up first.",
    "/no_dlc": "ASKS FIRST. Only if your game has no Expansion Pass: takes it out of the goal and sends its checks. "
               "Can't be undone.",
    "/starter_save": "ASKS FIRST. Put this seed's save in place now, even over a save with progress the client "
                     "doesn't know (that save is kept as unclaimed). Close the game first.",
    "/accept_save": "ASKS FIRST. Send the clears the client held back because the save looked like another seed's. "
                    "Can't be taken back.",
}


def help_for(command: str) -> str:
    """The help line for a control (its command, or "name value" for a choice)."""
    name, _, value = command.lstrip("/").partition(" ")
    if name in CHOICE_HELP and value in CHOICE_HELP[name]:
        return CHOICE_HELP[name][value]
    return ACTION_HELP.get(command, HELP_DEFAULT)


def choice_command(name: str, value: str) -> str:
    """The typed command a choice row sends ("fps", "60" -> "/fps 60")."""
    return f"/{name} {value}"


def folder_command(folder: str) -> str:
    """/emulator_folder with a picked folder (the command takes the rest of the line, spaces included)."""
    return f"/emulator_folder {folder}"


def all_commands() -> list[str]:
    """Every command name the tab can send (tests check each one exists in the command processor)."""
    names = {name for _, name, _, _, _ in CHOICE_ROWS}
    names.update(cmd.split()[0][1:] for _, _, cmd, _, _, _ in BUTTONS)
    return sorted(names)


def available(needs: str | None, state: dict[str, Any]) -> bool:
    """Whether a button can do anything now (greyed out otherwise; its help line says why)."""
    return needs is None or (needs == "slot" and state["slot"]) or (needs == "held" and state["held"] > 0)


def option_state(ctx: Any) -> dict[str, Any]:
    """What the tab shows, read from the client and its settings (the same values the commands report)."""
    from .settings import load_settings
    settings = load_settings()
    fps_pref = getattr(ctx, "fps_pref", None)
    banner_pref = getattr(ctx, "banner_pref", None)
    pacer = getattr(ctx, "pacer", None)
    session = getattr(ctx, "session", None)
    try:
        banner_active = bool(ctx.banner_on())
    except Exception:
        banner_active = False
    return {
        "fps": fps_pref or "seed",
        "fps_active": getattr(pacer, "mode", None),
        "fps_cutscenes": "on" if settings.get("fps_cutscenes") else "off",
        "fps_map": "on" if settings.get("fps_map") else "off",
        "banner": "seed" if banner_pref is None else ("on" if banner_pref else "off"),
        "banner_active": banner_active,
        "deathlink": "seed" if getattr(ctx, "deathlink_pref", None) is None else ("on" if ctx.deathlink_pref else "off"),
        "deathlink_active": _deathlink_active(ctx),
        "research": "on" if settings.get("research_probe") else "off",
        "research_running": bool(getattr(getattr(ctx, "probe", None), "enabled", False)),
        "slot": bool(session and getattr(ctx, "delivery", None)),
        "game": bool(getattr(ctx, "live", None)),
        "held": len(getattr(ctx, "_held", None) or ()),
        "ryujinx_folder": settings.get("ryujinx_folder") or "",
        "eden_folder": settings.get("eden_folder") or "",
    }


def _deathlink_active(ctx: Any) -> bool:
    try:
        return bool(ctx.deathlink_on())
    except Exception:
        return False


def status_text(state: dict[str, Any]) -> str:
    """The tab's one-line status."""
    fps = {"60": "up to 60", "120": "up to 120", "unlimited": "unlimited", "off": "the game's own 30"}.get(state["fps_active"] or "", "?")
    parts = [f"Slot: {'connected' if state['slot'] else 'not connected'}",
             f"Game: {'connected' if state['game'] else 'not found'}",
             f"Frame rate now: {fps}",
             f"Goal banner now: {'on' if state['banner_active'] else 'off'}",
             f"DeathLink now: {'on' if state['deathlink_active'] else 'off'}"]
    if state["held"]:
        parts.append(f"Held clears: {state['held']}")
    return "   |   ".join(parts)


def build_options_tab(manager) -> Any:
    """The tab's widget for the Kivy window (manager: the client's GameManager)."""
    import threading

    from kivy.clock import Clock
    from kivy.metrics import dp
    from kivymd.uix.boxlayout import MDBoxLayout
    from kivymd.uix.button import MDButton, MDButtonText
    from kivymd.uix.label import MDLabel
    from kvui import ButtonsPrompt, ToggleButton, UILog

    ctx = manager.ctx

    # KivyMD's hover check (HoverBehavior.on_mouse_update) compares the window position of the mouse with the parent
    # position of a button that is a RelativeLayout (MDButton is): inside a client tab, whose screen starts above the
    # Command bar, the highlight showed below the button (user, 2026-11-18; clicks were right). These buttons convert
    # the mouse position into their parent's space first.
    def hover_update(self, *args) -> None:
        if self.parent is None or self.get_root_window() is None:
            return
        inside = self.collide_point(*self.parent.to_widget(*args[1]))
        if inside and not self.hovering:
            self.hovering = True
            self.hover_visible = True
            self.dispatch("on_enter")
        elif not inside and self.hovering:
            self.hovering = False
            self.enter_point = None
            if self.hover_visible:
                self.hover_visible = False
                self.dispatch("on_leave")

    class AoCOptionButton(MDButton):  # (a real method: Kivy finds bound handlers by their name)
        def on_mouse_update(self, *args) -> None:
            hover_update(self, *args)

    class AoCOptionToggle(ToggleButton):
        def on_mouse_update(self, *args) -> None:
            hover_update(self, *args)

    def send(command: str) -> None:
        logger.info("(Options) %s", command)  # what to type for the same thing
        manager.commandprocessor(command)

    def confirm(title: str, text: str, command: str) -> None:
        def answer(button: str) -> None:
            prompt.dismiss()
            if button == "Yes":
                send(command)
        prompt = ButtonsPrompt(title, text, answer, "Yes", "Cancel")
        prompt.open()

    def label(text: str, **kw) -> MDLabel:
        return MDLabel(text=text, size_hint_y=None, height=dp(kw.pop("h", 28)), **kw)

    buttons: dict[str, MDButton] = {}

    def button(text: str, on_press, warn: bool = False) -> MDButton:
        caption = (MDButtonText(text=text, theme_text_color="Custom", text_color=WARN_COLOUR) if warn
                   else MDButtonText(text=text))
        b = AoCOptionButton(caption, style="outlined", size_hint_y=None, height=dp(36))
        b.bind(on_release=lambda *_: on_press())
        buttons[text] = b
        return b

    root = MDBoxLayout(orientation="vertical", size_hint_y=None, padding=dp(8), spacing=dp(4))
    root.bind(minimum_height=root.setter("height"))
    status = label("", h=22, theme_text_color="Secondary")
    root.add_widget(status)
    help_line = label(HELP_DEFAULT, h=36, theme_text_color="Custom", text_color=(1, 0.85, 0.4, 1))
    root.add_widget(help_line)
    hover: list[tuple[Any, str, str | None]] = []  # (widget, help text, needs)
    needs_of: dict[str, str | None] = {}  # button label -> what it needs (greyed out without it)
    last_state: dict[str, Any] = {}

    rows: dict[str, dict[str, ToggleButton]] = {}

    def row_title(text: str) -> MDLabel:
        return MDLabel(text=text, size_hint_x=None, width=dp(120), theme_text_color="Custom",
                       text_color=(0.85, 0.88, 0.92, 1))

    def section_title(text: str) -> MDLabel:  # (blue capitals, a little space above: the rows below are plain)
        return label(f"[b]{text.upper()}[/b]", h=32, markup=True, theme_text_color="Custom",
                     text_color=(0.55, 0.8, 1, 1), valign="bottom")

    def line_box() -> MDBoxLayout:
        return MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(4))

    def choice_row(name: str, title: str, choices) -> None:  # (what each choice does: the help line)
        row = line_box()
        row.add_widget(row_title(title))
        rows[name] = {}
        for value, text in choices:
            t = AoCOptionToggle(MDButtonText(text=text), group=f"aoc_{name}", allow_no_selection=False,
                                size_hint_y=None, height=dp(36))
            t.bind(on_release=lambda _b, v=value: send(choice_command(name, v)))
            hover.append((t, help_for(choice_command(name, value)), None))
            rows[name][value] = t
            row.add_widget(t)
        root.add_widget(row)

    folder_label = MDLabel(text="", theme_text_color="Secondary")

    def pick_folder() -> None:
        def run() -> None:  # (the dialog blocks: keep it off the client's loop)
            import Utils
            state = option_state(ctx)
            folder = Utils.open_directory("Ryujinx or Eden folder (the emulator's File menu opens it)",
                                          state["eden_folder"] or state["ryujinx_folder"])
            if folder:
                Clock.schedule_once(lambda _dt: send(folder_command(folder)))
        threading.Thread(target=run, name="AoCFolderPicker", daemon=True).start()

    for section in SECTIONS:
        root.add_widget(section_title(section))
        line = None
        for n, (_, text, command, ask, needs, warn) in enumerate(b for b in BUTTONS if b[0] == section):
            if n % 4 == 0:
                line = line_box()
                root.add_widget(line)
            press = (lambda t=text, c=command, w=ask: confirm(t.rstrip("…"), w, c)) if ask else (lambda c=command: send(c))
            line.add_widget(button(text, press, warn))
            hover.append((buttons[text], help_for(command), needs))
            needs_of[text] = needs
        if section == "Saves":  # the folder picker and where the client looks, after "Show save folders"
            line.add_widget(button("Pick emulator folder…", pick_folder))
            hover.append((buttons["Pick emulator folder…"], help_for("pick_folder"), None))
            line.add_widget(folder_label)
        for row_section, name, title, choices, _ in CHOICE_ROWS:
            if row_section == section:
                choice_row(name, title, choices)

    def refresh(_dt=None) -> None:
        try:
            state = option_state(ctx)
        except Exception as e:  # (never in the way of the client)
            logger.debug("Options tab: %s", e)
            return
        last_state.clear()
        last_state.update(state)
        for _, name, _, _, key in CHOICE_ROWS:
            for value, toggle in rows[name].items():
                want = "down" if value == state[key] else "normal"
                if toggle.state != want:
                    toggle.state = want
        for text, needs in needs_of.items():
            off = not available(needs, state)
            if buttons[text].disabled != off:
                buttons[text].disabled = off
        status.text = status_text(state)
        folder_label.text = (f"Ryujinx: {state['ryujinx_folder'] or 'found by itself'}   |   "
                             f"Eden: {state['eden_folder'] or 'found by itself'}")

    def on_mouse(_window, pos) -> None:
        if help_line.get_root_window() is None:  # another tab is showing
            return
        for widget, text, needs in hover:
            if widget.parent is not None and widget.collide_point(*widget.parent.to_widget(*pos)):
                off = last_state and not available(needs, last_state)
                help_line.text = f"{text} ({NEEDS_HELP[needs]})" if off else text
                return
        help_line.text = HELP_DEFAULT

    from kivy.core.window import Window
    Window.bind(mouse_pos=on_mouse)

    refresh()
    Clock.schedule_interval(refresh, 0.5)
    # (user, 2026-11-18) No scroll view around the controls: KivyMD drew the buttons' hover highlight below the mouse
    # inside one (clicks were right). The controls sit at the top and a small copy of the client log fills the rest,
    # so a command's answer shows without switching tabs.
    tab = MDBoxLayout(orientation="vertical")
    tab.add_widget(root)
    log = UILog(logging.getLogger("Client"))
    log.adaptive_height = False  # (UILog grows to its whole content by default: it would push the controls away)
    log.size_hint_y = 1
    tab.add_widget(log)
    tab.aoc_rows, tab.aoc_buttons, tab.aoc_refresh, tab.aoc_log, tab.aoc_help = rows, buttons, refresh, log, help_line  # (for scripted checks)
    return tab
