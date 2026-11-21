"""The client's Options tab (client/options_tab.py): every control sends a command that exists, and the tab's state
follows the commands whether they come from the tab or are typed."""

import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


class OptionsTabTests(unittest.TestCase):
    def setUp(self) -> None:
        from ..client import settings
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(settings, "SETTINGS_FILE", Path(self.tmp.name) / "settings.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def make(self):
        from ..client.ap_client import AoCCommandProcessor, AoCContext

        class Pacer:
            mode = "60"
            def set_mode(self, mode):
                from ..client.framerate import normal_mode
                self.mode = normal_mode(mode)

        banners = []
        ctx = SimpleNamespace(fps_pref=None, banner_pref=None, deathlink_pref=None, pacer=Pacer(), probe=None,
                              live=None, delivery=None, server=None, _pending_kill=None,
                              _held=[], session=SimpleNamespace(frame_rate="30", goal_banner=True, death_link=False),
                              overlay=SimpleNamespace(set_banner=banners.append))
        ctx.apply_frame_rate_mode = types.MethodType(AoCContext.apply_frame_rate_mode, ctx)
        ctx.banner_on = types.MethodType(AoCContext.banner_on, ctx)
        ctx.deathlink_on = types.MethodType(AoCContext.deathlink_on, ctx)
        out = []
        proc = AoCCommandProcessor(ctx)
        proc.output = out.append
        return ctx, proc, out, banners

    def test_every_command_exists(self) -> None:
        from ..client.ap_client import AoCCommandProcessor
        from ..client.options_tab import all_commands
        commands = AoCCommandProcessor.commands if hasattr(AoCCommandProcessor, "commands") else None
        names = commands or {n[5:] for n in dir(AoCCommandProcessor) if n.startswith("_cmd_")}
        for name in all_commands():
            self.assertIn(name, names, name)

    def test_destructive_commands_ask_first(self) -> None:
        from ..client.options_tab import ACTIONS, DANGER
        plain = {c for _, c, _ in ACTIONS}
        for command in ("/starter_save", "/accept_save", "/no_dlc", "/sync_saves force"):
            self.assertNotIn(command, plain)
            self.assertTrue(any(c == command and warning for _, c, warning in DANGER), command)

    def test_grouped_by_purpose(self) -> None:  # (user, 2026-11-20: sections by what things are for, no "Asks first")
        from ..client.options_tab import BUTTONS, CHOICE_ROWS, SECTIONS
        for section, *_ in BUTTONS + CHOICE_ROWS:
            self.assertIn(section, SECTIONS)
        self.assertNotIn("Asks first", SECTIONS)
        for _, text, _, ask, _, _ in BUTTONS:  # a button that asks first says so with "…"
            self.assertEqual(text.endswith("…"), bool(ask), text)
        texts = [b[1] for b in BUTTONS]
        self.assertEqual(len(texts), len(set(texts)))
        self.assertTrue(all(b[5] for b in BUTTONS if b[2] in ("/accept_save", "/no_dlc")))  # can't be undone: coloured

    def test_buttons_greyed_when_they_cant_apply(self) -> None:
        from ..client.options_tab import BUTTONS, available, option_state
        ctx, _, _, _ = self.make()
        needs = {b[2]: b[4] for b in BUTTONS}
        state = option_state(ctx)
        self.assertFalse(available(needs["/todo"], state))  # not connected
        self.assertTrue(available(needs["/check_hook"], state))
        self.assertFalse(available(needs["/accept_save"], state))
        ctx._held = [1]
        self.assertTrue(available(needs["/accept_save"], option_state(ctx)))

    def test_every_control_explains_itself(self) -> None:  # (user: hovering tells what a button does)
        from ..client.options_tab import (ACTIONS, BANNER_CHOICES, DANGER, FPS_CHOICES, HELP_DEFAULT, RESEARCH_CHOICES,
                                          choice_command, help_for)
        commands = [c for _, c, _ in ACTIONS + DANGER] + ["pick_folder"]
        from ..client.options_tab import CUTSCENE_CHOICES, MAP_CHOICES
        for name, choices in (("fps", FPS_CHOICES), ("fps_cutscenes", CUTSCENE_CHOICES), ("fps_map", MAP_CHOICES),
                              ("goal_banner", BANNER_CHOICES),
                              ("research", RESEARCH_CHOICES)):
            commands += [choice_command(name, v) for v, _ in choices]
        for command in commands:
            self.assertNotEqual(help_for(command), HELP_DEFAULT, command)
        for _, command, _ in DANGER:
            self.assertTrue(help_for(command).startswith("ASKS FIRST"), command)

    def test_fps_choice_and_typed_command_stay_in_sync(self) -> None:
        from ..client.options_tab import FPS_CHOICES, choice_command, option_state
        ctx, proc, out, _ = self.make()
        self.assertEqual(option_state(ctx)["fps"], "seed")
        for value, _ in FPS_CHOICES:  # the tab's buttons
            proc(choice_command("fps", value))
            state = option_state(ctx)
            self.assertEqual(state["fps"], value)
            self.assertEqual(state["fps_active"], "off" if value == "seed" else value)  # seed: an older YAML's 30 = off
        proc("/fps 120")  # typed
        self.assertEqual(option_state(ctx)["fps"], "120")
        self.assertIn("Frame rate: up to 120 FPS", out[-1])

    def test_goal_banner_and_research(self) -> None:
        from ..client.options_tab import option_state
        ctx, proc, _, banners = self.make()
        self.assertEqual((option_state(ctx)["banner"], option_state(ctx)["banner_active"]), ("seed", True))
        proc("/goal_banner off")
        self.assertEqual((option_state(ctx)["banner"], option_state(ctx)["banner_active"]), ("off", False))
        self.assertEqual(banners, [None])
        proc("/goal_banner seed")
        self.assertEqual(option_state(ctx)["banner"], "seed")
        self.assertEqual(option_state(ctx)["research"], "off")
        proc("/research on")
        self.assertEqual(option_state(ctx)["research"], "on")
        proc("/probe off")
        self.assertEqual(option_state(ctx)["research"], "off")

    def test_deathlink_toggle(self) -> None:  # (user, 2026-11-21: on/off from the client, not only the YAML)
        from ..client.options_tab import option_state, status_text
        ctx, proc, out, _ = self.make()
        self.assertEqual((option_state(ctx)["deathlink"], option_state(ctx)["deathlink_active"]), ("seed", False))
        proc("/deathlink on")
        self.assertEqual((option_state(ctx)["deathlink"], option_state(ctx)["deathlink_active"]), ("on", True))
        self.assertIn("DeathLink: on (set with /deathlink)", out[-1])
        self.assertIn("DeathLink now: on", status_text(option_state(ctx)))
        ctx._pending_kill = "Friend"
        proc("/deathlink off")
        self.assertFalse(ctx.deathlink_on())
        self.assertIsNone(ctx._pending_kill)  # (a death received just before is dropped)
        ctx.session.death_link = True
        proc("/deathlink seed")
        self.assertEqual((option_state(ctx)["deathlink"], option_state(ctx)["deathlink_active"]), ("seed", True))

    def test_folder_command_keeps_windows_path(self) -> None:
        from ..client.options_tab import folder_command, option_state
        ctx, proc, out, _ = self.make()
        ctx.save_path = "x"
        ctx._find_save_path = lambda: None
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "My Ryujinx"
            (folder / "bis" / "user" / "save").mkdir(parents=True)
            with mock.patch("worlds.hyrule_warriors_aoc.client.savewatch.find_save_files", return_value=[]):
                proc(folder_command(str(folder)))  # backslashes and a space, as typed or picked
            self.assertEqual(option_state(ctx)["ryujinx_folder"], str(folder))
            self.assertIsNone(ctx.save_path)

    def test_folder_command_takes_eden_too(self) -> None:  # (user: the folder picker works for both emulators)
        from ..client.options_tab import folder_command, option_state
        ctx, proc, out, _ = self.make()
        ctx._find_save_path = lambda: None
        with tempfile.TemporaryDirectory() as d:
            eden, ryu, other = Path(d) / "Eden user", Path(d) / "Ryu", Path(d) / "Nothing"
            (eden / "nand").mkdir(parents=True)
            (ryu / "bis" / "user" / "save").mkdir(parents=True)
            other.mkdir()
            with mock.patch("worlds.hyrule_warriors_aoc.client.savewatch.find_save_files", return_value=[]):
                proc(folder_command(str(eden)))
                proc("/ryujinx_folder " + str(ryu))  # the older name still works
                proc(folder_command(str(other)))  # neither: nothing changes
            state = option_state(ctx)
            self.assertEqual((state["eden_folder"], state["ryujinx_folder"]), (str(eden), str(ryu)))

    def test_status_text(self) -> None:
        from ..client.options_tab import option_state, status_text
        ctx, _, _, _ = self.make()
        ctx._held = [1, 2]
        text = status_text(option_state(ctx))
        self.assertIn("Slot: not connected", text)
        self.assertIn("Frame rate now: up to 60", text)
        self.assertIn("Held clears: 2", text)


if __name__ == "__main__":
    unittest.main()
