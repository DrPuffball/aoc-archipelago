"""Archipelago client for Hyrule Warriors: Age of Calamity."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from CommonClient import (
    ClientCommandProcessor,
    CommonContext,
    get_base_parser,
    gui_enabled,
    handle_url_arg,
    logger,
    server_loop,
)
from NetUtils import ClientStatus

from ..data import GAME_NAME
from ..world import WORLD_VERSION
from .bridge import PROTOCOL_VERSION, GameBridge
from .overlay import Overlay
from .session import Session, make_notice, title_info

PROBE_LOGGER = "AoCProbe"  # research probe lines (its own client tab when the probe is on)
probe_logger = logging.getLogger(PROBE_LOGGER)
LEVEL_CAP, LEVEL_CAP_DELAY = 99, 5.0  # hero_level_cap: back to 99 this many seconds after reaching 100
DEATH_STALE = 8.0  # seconds a received DeathLink waits for a mission in progress before it is dropped

NEW_GAME_CONFIRM = 30.0  # seconds a smaller game state must last before it counts as a New Game


FIRST_MISSION = "The Battle of Hyrule Field"
FIRST_MISSION_NOTE = ("Note: a new game always starts with The Battle of Hyrule Field played as Link and Impa (the game "
                      "forces it before the world map exists). Your starting heroes and the seed's mission order take "
                      "over from the world map; clearing it is still a check.")
BEAST = {"Regulating the Reservoir": " (Vah Ruta)", "Surveying the Volcano": " (Vah Rudania)",
         "Revitalize Those in the Skies": " (Vah Medoh)", "Patrolling the Desert": " (Vah Naboris)"}  # [guess by name]
LAB_SERVICE = 425  # map cursor id of the Royal Ancient Lab (kind 5)
SELECTION_PAGE, SELECTION_SECONDS = 6, 4.0  # cursor panel: checks per page, seconds per page
STARTER_NOTE = ("This seed skips the forced first mission, but the starter save isn't installed on this save. If this "
                "is a New Game, close Age of Calamity in the emulator: the client installs the starter save (backup kept) "
                "and you then pick Continue. Type /starter_save to force it.")

EMULATOR_BOOT_SECONDS = 90  # an emulator younger than this may be booting the game: never switch saves
REFRESH_HINT_SECONDS = 20  # how long the "pause and go back to the map" banner stays after a new seed's setup
FLOW_PAUSED = 0x60  # mission flow state of the pause menu
DEATH_HOLD_SECONDS = 0.1  # how often a received death re-zeroes the party's health
TIP_SECONDS = 30  # how long a banner tip (what to do next) stays on the map
TITLE_HINT_SECONDS = 120  # the game is up but unreadable this long: from "pick Continue" to "see the client window"


class AoCCommandProcessor(ClientCommandProcessor):
    ctx: AoCContext

    def _cmd_check_hook(self) -> None:
        """Quick health check: is the game hook connected, and is it in sync with this seed?"""
        ctx = self.ctx
        if ctx.live:
            self.output(f"Connected to the game in {'Eden' if type(ctx.live.g).__name__ == 'FastmemGuest' else 'Ryujinx'} (live)." + ("" if ctx.session else " Connect to your slot next."))
            if ctx.session:
                try:
                    self.output(f"Rupees in game: {ctx.live.rupees()}; clears seen: {len(ctx._live_seen or ())}")
                except Exception as e:  # mid-load: the hook reconnects on its own
                    self.output(f"Game is loading or changed ({e}); the client reconnects by itself.")
        elif not ctx.bridge.connected:
            self.output("Game NOT connected. Start Age of Calamity in Ryujinx or Eden (only one open) and load your "
                        "save; the client attaches by itself within a few seconds (Windows; Ryujinx: memory mode "
                        "'Software'; Eden: CPU accuracy Auto).")
        elif not ctx.session:
            self.output("Hook connected, but you are not connected to a multiworld slot yet.")
        else:
            self.output("Hook connected and seed loaded. Sending a state refresh to the game...")
            asyncio.create_task(ctx._push_state())

    def _cmd_game(self) -> None:
        """Show whether the game-side hook is connected and the current seed state."""
        ctx = self.ctx
        self.output(f"Game hook connected: {ctx.bridge.connected}")
        if ctx.session:
            s = ctx.session
            self.output(f"Missions cleared: {len(s.cleared_missions)}/{len(s.mission_ids)}")
            self.output(f"Available: {', '.join(s.available_missions()) or 'none'}")


    def _cmd_ryujinx_folder(self, folder: str = "") -> None:
        """Tell the client where Ryujinx keeps its data, when it can't find your save by itself (in Ryujinx:
        File > Open Ryujinx Folder; the folder that contains "bis"). Without a folder: show where it looks."""
        import os
        from .savewatch import find_save_files, ryujinx_data_roots
        from .settings import save_setting
        ctx = self.ctx
        if folder:
            folder = folder.strip().strip('"')
            if not os.path.isdir(os.path.join(folder, "bis", "user", "save")):
                self.output(f"{folder} has no bis/user/save folder: pick the folder Ryujinx opens with "
                            "File > Open Ryujinx Folder.")
                return
            save_setting("ryujinx_folder", folder)
            ctx.save_path = None
            ctx._find_save_path()
        self.output("Looking for Ryujinx data in: " + (", ".join(ryujinx_data_roots()) or "nothing found"))
        found = find_save_files()
        self.output("Age of Calamity saves: " + (", ".join(found) or "none"))

    def _cmd_sync_saves(self, mode: str = "") -> None:
        """Copy this seed's newest save to the other emulator (Ryujinx <-> Eden) now; the client also does it by itself
        whenever no game is running. The first time, the other emulator's Age of Calamity save becomes this seed's
        (it is backed up first). "/sync_saves force" also copies a save with fewer story clears (after a New Game)."""
        ctx = self.ctx
        if not ctx.delivery:
            self.output("Connect to your slot first.")
            return
        if ctx._game_running():
            self.output("Close Age of Calamity first (saves are only copied while no game runs).")
            return
        lines = ctx.sync_saves(force=mode.lower() == "force", claim=True)
        self.output("\n".join(lines) if lines else
                    "Nothing to copy: " + (", ".join(ctx.own_saves()) or "no save of this seed found") + ".")

    def _cmd_no_dlc(self) -> None:
        """Your game has no Expansion Pass: takes it out of this seed's goal and sends its checks. This can't be undone."""
        self.ctx.confirm_no_dlc()

    def _cmd_research(self, state: str = "") -> None:
        """Game research for testers (off by default): records what the game did with each randomizer change in
        AoC_Archipelago/research, to help improve the randomizer. It only reads the game, and nothing leaves your PC.
        "/research on" or "/research off"; it starts or stops when the game is next found."""
        from .settings import load_settings, save_setting
        if state.lower() in ("on", "off"):
            save_setting("research_probe", state.lower() == "on")
            if state.lower() == "off" and self.ctx.probe:
                self.ctx.probe.enabled = False
        self.output("Game research: " + ("on" if load_settings().get("research_probe") else "off"))

    def _cmd_probe(self, state: str = "") -> None:
        """Old name of /research."""
        self._cmd_research(state)

    def _cmd_goal_banner(self, state: str = "") -> None:
        """The goal progress banner at the top of the emulator window while you're on the world map. "/goal_banner on"
        or "/goal_banner off" (remembered on this PC); "/goal_banner seed" follows your YAML's goal_banner again."""
        from .settings import load_settings, save_setting
        state = state.lower()
        if state in ("on", "off", "seed"):
            save_setting("goal_banner", None if state == "seed" else state == "on")
            self.ctx.banner_pref = load_settings().get("goal_banner")
            if not self.ctx.banner_on():
                self.ctx.overlay.set_banner(None)
        self.output("Goal banner: " + ("on" if self.ctx.banner_on() else "off")
                    + (" (your YAML's setting)" if self.ctx.banner_pref is None else " (set with /goal_banner)"))

    def _cmd_saves(self) -> None:
        """Which seed each save belongs to, and the saves kept for the seeds you're not playing right now."""
        ctx = self.ctx
        shelf = ctx._shelf()
        for path, seed in shelf.owners().items():
            self.output(f"{path}: {seed}")
        kept = sorted(p.name for p in shelf.folder.glob("*.svdt")) if shelf.folder.is_dir() else []
        self.output("Kept saves: " + (", ".join(kept) or "none"))
        self.output("Switch seeds by connecting to the other seed with Age of Calamity closed.")

    def _cmd_starter_save(self) -> None:
        """Set this seed's save in place now even over a save with progress the client doesn't know (that one is kept
        in AoC_Archipelago/saves as unclaimed). Close the game in Ryujinx first."""
        ctx = self.ctx
        if not ctx.session or not ctx.delivery:
            self.output("Connect to your slot first.")
            return
        ctx.maybe_install_starter(force=True)

    def _cmd_deliver(self) -> None:
        """What the client has given you in game, and what is still waiting for the game to run."""
        ctx = self.ctx
        if not ctx.delivery:
            self.output("Connect to your slot first.")
            return
        pending = ctx.delivery.pending(ctx.received_names())
        self.output(f"Game: {'connected live' if ctx.live else 'not running (items wait for it, or go into the save file while the emulator is closed)'}")
        self.output(f"Waiting to be given: {', '.join(pending) or 'nothing'}")
        for line in ctx.delivery.state["log"][-5:]:
            self.output("  " + line)

    def _cmd_todo(self) -> None:
        """What the goal needs and how far you are, what you can play right now, and which heroes you may use."""
        ctx = self.ctx
        if not ctx.session:
            self.output("Connect to your multiworld slot first.")
            return
        s = ctx.session
        for line in s.goal_progress():
            self.output(line)
        self.output("Story missions you can play now: " + (", ".join(s.available_missions()) or "none"))
        self.output("Heroes you may use: " + ", ".join(sorted(s.unlocked_characters)))
        if s.features:
            self.output("Unlocked features: " + ", ".join(sorted(s.features)))
        else:
            self.output("(No features are locked unless your YAML locked some.)")

    def _cmd_inventory(self) -> None:
        """Everything the multiworld has given you so far (the client applies all of it in game by itself)."""
        ctx = self.ctx
        if not ctx.session:
            self.output("Connect to your multiworld slot first.")
            return
        s = ctx.session
        self.output("Heroes: " + ", ".join(sorted(s.unlocked_characters)))
        if s.upgrades:
            self.output("Upgrades: " + ", ".join(f"{k} x{v}" for k, v in sorted(s.upgrades.items())))
        if s.unlocked_weapons:
            self.output("Weapons received: " + ", ".join(sorted(s.unlocked_weapons)))
        counts: dict[str, int] = {}
        for item in ctx.items_received:
            name = ctx.item_names.lookup_in_game(item.item)
            if name in ("Character XP Gift", "Weapon XP Gift", "Extra Weapon", "Weapon Bundle", "Large Weapon Bundle"):
                counts[name] = counts.get(name, 0) + 1
        if counts:
            self.output("Gifts: " + ", ".join(f"{k} x{v}" for k, v in counts.items()))


class AoCContext(CommonContext):
    game = GAME_NAME
    items_handling = 0b111  # the server hands us every item; the game never holds them locally
    command_processor = AoCCommandProcessor

    def __init__(self, server_address: str | None, password: str | None) -> None:
        super().__init__(server_address, password)
        self.session: Session | None = None
        self._items_applied = 0
        self._rescue_task: asyncio.Task | None = None
        self.bridge = GameBridge(self._on_game_message)
        self.overlay = Overlay()  # notices shown over the Ryujinx window
        self.save_watcher = None
        self.save_path: str | None = None
        self.room_seed = ""
        self.delivery = None
        self.live = None
        self._live_retry = 0.0
        self._live_seen: set[str] | None = None
        self._several_noted = False  # warned that several emulators are open
        self._too_easy: set[str] | None = None  # clears below the difficulty lock (warned once each)
        self._below_goal: set[str] | None = None  # goal_difficulty: clears below it (announced once each)
        self._hero_waits_told: set[str] = set()  # open missions told to wait for their forced heroes (once each)
        self._refresh_hint = False  # a starter save went in: ask for one map refresh once the game is on the map
        self._refresh_until: float | None = None
        # A short instruction for the banner (user, 2026-11-02: "keep elaborating on it where it could apply"): shown on
        # the map in place of the goal line until it expires, whatever /goal_banner says (it is what to do next).
        self._banner_tip: tuple[str, float] | None = None
        from .settings import load_settings
        self.banner_pref: bool | None = load_settings().get("goal_banner")  # /goal_banner; None = the seed's option
        self._shrink_seen: float | None = None  # when a possible New Game was first seen
        self._party_logged: list[str] | None = None
        self._rewards_logged = False
        self._rewards_ok = True
        self._save_search_at = 0.0
        self._starter_check_at = 0.0
        self._starter_reason: str | None = None
        self._elsewhere_noted: str | None = None
        self._unreadable_since: float | None = None
        self._unreadable_warned = False
        self._no_save_since: float | None = None
        self._pending_kill: str | None = None
        self._pending_kill_at = 0.0
        self._cap_seen: dict[str, float] = {}  # hero -> when they were first seen above the level cap
        self._last_hp: float | None = None
        self._death_hold = False  # DeathLink: a received death holds your HP at 0 until the next hit
        self._dlc_warned = False  # the Expansion Pass question was asked
        self._death_hold_task: asyncio.Task | None = None
        self._death_hold_source: str | None = None
        self._no_check_noted: set[str] = set()
        self.probe = None
        self._probe_task: asyncio.Task | None = None
        self._open_logged: set[str] = set()
        self._challenges_logged = False
        self._first_mission_noted = False
        self._quest_rows_ok = True
        self._lab_ok = self._quest_table_ok = True
        self._lab_scan_at = 0.0
        self._selection: tuple[int, int] | None = None
        self._selection_pages: list[str] = []
        self._selection_page = 0
        self._selection_turn = 0.0
        self._quest_rows_logged = False
        self._side_opened: set[str] | None = None  # random side content already open (first tick: no notice)
        self._save_task: asyncio.Task | None = None
        self.bridge.on_connect = self._on_game_connected

    # --- save file: automatic checks and item delivery ------------------------------------

    def received_names(self) -> list[str]:
        return [self.item_names.lookup_in_game(i.item) for i in self.items_received]

    def set_save_path(self, path: str) -> None:
        self.save_path = path
        logger.info("Using save file %s", path)
        self._start_save_link()

    def _find_save_path(self) -> None:
        from .savewatch import find_save_files

        found = find_save_files()
        if found:  # several Ryujinx profiles: the one this seed is played on, else the newest one no other seed owns
            me = self.delivery.state_file.stem if self.delivery else None
            owners = {p: self._shelf().owner(p) for p in found}
            mine = [p for p in found if owners[p] == me]
            free = [p for p in found if owners[p] is None]
            # a save of the emulator that is open wins (the same seed's save can exist in Ryujinx and Eden), then the newest
            from .ryujinx import emulator_processes
            running = {name for _, name in emulator_processes()}

            def rank(p: str) -> tuple[bool, float]:
                emulator = "Eden" if os.sep + "eden" + os.sep in p.lower() else "Ryujinx"
                return emulator in running, os.path.getmtime(p)
            self.set_save_path(max(mine or free or found, key=rank))
        else:
            logger.debug("No Age of Calamity save found yet; checking again shortly (live play works without it).")
            now = time.time()
            if self._no_save_since is None:
                self._no_save_since = now
            elif now - self._no_save_since > 60 and self._no_save_since > 0:
                self._no_save_since = -1.0  # said once
                from .savewatch import ryujinx_data_roots
                from .savewatch import eden_data_roots
                logger.warning("No Age of Calamity save found (looked in: %s). Start the game once in Ryujinx or Eden. "
                               "If Ryujinx keeps its data somewhere else, type /ryujinx_folder <folder> (in Ryujinx: "
                               "File > Open Ryujinx Folder shows it).",
                               ", ".join(ryujinx_data_roots() + eden_data_roots()) or "no emulator folder")

    def _ensure_delivery(self) -> bool:
        from .delivery import Delivery

        if self.delivery:
            return True
        seed = self.room_seed or str(self.seed_name or "")
        if not (self.session and self.slot and seed):
            return False
        self.delivery = Delivery(seed, self.player_names.get(self.slot, str(self.slot)))
        return True

    def _shrink_baseline(self, cleared: set[str], now: float) -> None:
        """Something cleared earlier under this seed (or before it) that is no longer cleared means a New Game:
        let it count again and give every received item again. Only once the smaller state has lasted
        NEW_GAME_CONFIRM seconds: right after boot the game shows a blank state for a few seconds before
        it loads the save, and that must not count as a New Game."""
        from ..data_save import MISSION_RECORD_IDS

        # Only mission and challenge clears decide: they can't be undone in play. Owned weapons drop when you fuse
        # or sell them, and the client itself closes bought shop quests, so those never mean a New Game.
        known = set(self.delivery.state["baseline"] or ()) | set(self.delivery.state.get("progress", ()))
        known &= set(MISSION_RECORD_IDS)
        if not known - cleared:
            self._shrink_seen = None
            return
        if self._shrink_seen is None:
            self._shrink_seen = now
            return
        if now - self._shrink_seen < NEW_GAME_CONFIRM:
            return
        self._shrink_seen = None
        self.delivery.new_game(cleared)
        self._live_seen = cleared
        if self.save_watcher:
            self.save_watcher.ignore = set(self.delivery.state["baseline"])
        logger.info("New Game detected: everything you received will be given again.")

    def _start_save_link(self) -> None:
        from .savefile import SaveFormatError, check_save, cleared_missions, completed_quests, owned_weapons
        from .savewatch import SaveWatcher

        if not (self.save_path and self._ensure_delivery()):
            return
        try:
            with open(self.save_path, "rb") as f:
                data = f.read()
            check_save(data)
        except (OSError, SaveFormatError) as e:
            logger.warning("Cannot use save file %s: %s", self.save_path, e)
            return
        ignore = self.delivery.baseline(cleared_missions(data) | completed_quests(data) | owned_weapons(data))
        self.save_watcher = SaveWatcher(self.save_path, ignore=ignore, on_ignore_change=self.delivery.set_baseline)
        # (a starter save's clears are expected; another seed's save is about to be swapped for one)
        if ignore and self.save_path not in self.delivery.state.get("starter", {}) and not self.save_belongs_elsewhere():
            logger.warning("%d clears were already in this save before the seed started; they will NOT count as checks. "
                           "For a full run, start a New Game (back up your save first).", len(ignore))

    # --- the live game hook ---------------------------------------------------------------

    async def _live_tick(self) -> None:
        from .live_hook import HookError, LiveGame
        from .savewatch import message_for

        now = time.time()
        if self._several_emulators():
            self.overlay.set_banner("Several emulators are open: close all but one")
            if self.live is not None:
                self.live.close()
                self.live = None
            return
        if (other := self.save_belongs_elsewhere()) and self._game_running():  # another seed's save: hands off
            # (user, 2026-11-02: the note in the client window was easy to miss) stays up until the game is closed
            self.overlay.set_banner("This save belongs to another seed: close the emulator and wait for the client before reopening")
            if self._elsewhere_noted != other:
                self._elsewhere_noted = other
                logger.info("The save in use belongs to seed %s, so the client leaves the game alone. "
                            "To play this seed, close the emulator and wait for this window to say the save was set up (seed %s's save "
                            "is kept and comes back when you connect it again).", other, other)
                self.overlay.show("This save belongs to another seed: close the game to switch")
            if self.live is not None:
                self.live.close()
                self.live = None
            return
        if self._elsewhere_noted is not None:
            self.overlay.set_banner(None)
        self._elsewhere_noted = None
        if self.live is None:
            if now < self._live_retry:
                return
            self._live_retry = now + 5
            try:
                self.live = LiveGame.find()
            except Exception as e:
                logger.debug("hook attach failed: %s", e)
                self.live = None
            if self.live is None:
                self.overlay.set_banner(None)
                self._warn_unreadable(now)
                return
            self._unreadable_since = None
            self._live_seen = None
            self._too_easy = None
            self._below_goal = None
            if self.save_path and self.delivery and self._shelf().owner(self.save_path) is None:
                self._shelf().set_owner(self.save_path, self.delivery.state_file.stem)  # the save this seed plays on
            self._start_probe()
            self._dlc_failsafe()  # (now the emulator in use is known)
            logger.info("Connected to Age of Calamity in %s: story and challenge clears are sent the moment "
                        "they happen; Rupee Pouch, Material Bundle and Character XP Gift arrive in game.",
                        "Eden" if type(self.live.g).__name__ == "FastmemGuest" else "Ryujinx")
        try:
            cleared = self._counted_clears() | self.live.completed_quests()
            self.session.game_done = set(cleared)  # random side unlocks open by this count
            if not self._first_mission_noted and FIRST_MISSION not in cleared and not self.session.cleared_missions:
                self._first_mission_noted = True
                if not self.session.starter_save:  # seeds before 0.9.54
                    logger.info(FIRST_MISSION_NOTE)
                    self.overlay.show("First mission: Hyrule Field with Link and Impa (vanilla)")
                elif not (self.delivery and self.delivery.state.get("starter")):
                    logger.info(STARTER_NOTE)
                    self.overlay.show("Close the game: the client sets up your starter save")
                    self._tip("New game? Close the game: the client then sets up your starter save", 600)
            # Weapons count as found once the player owns more copies than Archipelago handed out.
            given = self.delivery.state.get("weapons_given", {})
            cleared |= {n for n, c in self.live.weapon_counts().items() if c > given.get(n, 0)}
            self.delivery.baseline(cleared)  # first contact with this seed: what was already cleared never counts
            self._shrink_baseline(cleared, now)
            if self._shrink_seen is not None:
                return  # possible New Game: report and give nothing until it is confirmed
            base = set(self.delivery.state["baseline"] or ())
            new = cleared - (self._live_seen or set()) - base
            self._live_seen = cleared
            self.delivery.add_progress(cleared - base)
            for name in sorted(new):
                # (clears that hold no check - services open from the start, weapons you own - are detail, not news)
                (logger if self.session.has_check(name) else probe_logger).info("Cleared in game: %s", name)
                if self.probe:
                    self.probe.note(f"cleared {name}")
                await self._on_game_message(message_for(name))
            self.delivery.skip_dlc = not self.session.include_dlc
            done = self.delivery.apply(self.received_names(), set(self.session.unlocked_characters), self.live)
            if done:
                logger.info("Given in game: %s", "; ".join(done))
                for line in done:  # who or what got each gift (user request)
                    self.overlay.show(line)
                self._audit({"finding": "delivered", "done": done})
            self._sync_heroes()
            self._cap_levels()
            if self.delivery.state.get("primed") is False:  # a fresh starter save: every hero gets a weapon and stats
                self._prime_heroes()
            if self.session.story_party_free:
                party = self.live.best_heroes(set(self.session.unlocked_characters))
                if self.live.set_story_parties(party, challenges=True, skip=self.session.vanilla_records())                         and party != self._party_logged:
                    self._party_logged = party
                    logger.info("Story missions and challenges now start with your heroes in place of forced heroes "
                                "you don't have: %s", ", ".join(party))
            levels = self.session.combo_levels()
            if levels and self.live.set_upgrade_levels(levels):
                logger.info("Combo upgrades set from received items.")
            if self.live.set_profile_bytes(self.session.profile_rewards()):
                logger.info("Enhanced abilities / weapon capacity set from received items.")
            from ..data_save import ALL_HERO_HEART_QUESTS
            everyone = self.session.hearts_for_all()  # +1 heart for all per item share (else the vanilla quests)
            if everyone is None:
                everyone = len(self.live.completed_quests() & set(ALL_HERO_HEART_QUESTS))
            for family in ("Heart Container", "Special Gauge Upgrade"):
                bonus = self.session.hero_bonus(family, everyone if family == "Heart Container" else 0)
                if bonus and self.live.set_hero_bonus(family, bonus):
                    logger.info("%ss set from received items.", family)
            rows = self.session.mission_reward_rows() if self._rewards_ok else {}
            if rows:
                try:
                    if self.live.set_mission_rewards(rows) and not self._rewards_logged:
                        self._rewards_logged = True
                        probe_logger.info("Mission rewards set by the seed (%s).",
                                    "shuffled" if self.session.mission_rewards.get("mode") == 1 else "none")
                except HookError as e:  # never let this one feature drop the game connection
                    self._rewards_ok = False
                    logger.warning("Mission rewards stay vanilla: %s", e)
            if self.live.set_reward_bytes(self.session.reward_writes()):
                probe_logger.info("Quest rewards set from received items.")
            await self._lab_tick()
            if (self.live.map_selection() == (LAB_SERVICE, 5) and self.session.ids["lab"] and self._lab_ok
                    and self.live.lab_needs_scan() and time.monotonic() >= self._lab_scan_at):
                self._lab_scan_at = time.monotonic() + 15
                await asyncio.to_thread(self.live.lab_scan)
            states = self.session.quest_states()
            if quests := self.live.set_quest_states(states):
                probe_logger.info("Services (quest states) set from received items: %s", ", ".join(quests))
            done = {q for q, state in states.items() if state == 3} - self.session.store_quests()
            if quests := self.live.set_quest_effects(done):
                probe_logger.info("Quest effects set in game: %s", ", ".join(quests))
            self._show_selection()
            self._show_goal_banner()
            if self._quest_rows_ok and (rows := self.session.quest_rows()):
                try:
                    if self.live.set_quest_locks(rows) and not self._quest_rows_logged:
                        self._quest_rows_logged = True
                        probe_logger.info("Quests now open by the seed's rules (random, by completions), not the game's order.")
                except HookError as e:  # never let this one feature drop the game connection
                    self._quest_rows_ok = False
                    logger.warning("Quest unlock rules stay vanilla: %s", e)
            if self.session.goal_challenges:
                any_done = self._counted_clears()
                if any_done != self.session.cleared_any:
                    self.session.cleared_any = any_done
                    await self._maybe_finish()
            if self.session.goal_difficulty:
                done = self.live.cleared_missions_at(self.session.goal_difficulty - 1)
                if done != self.session.difficulty_cleared:
                    from ..data_save import DIFFICULTIES
                    self.session.difficulty_cleared = done
                    logger.info("Cleared on %s or harder: %d/%d story missions, %d/%d challenges",
                                DIFFICULTIES[self.session.goal_difficulty - 1],
                                len(done & set(self.session.story_names)), self.session.goal_story_missions,
                                len(done & self.session.goal_challenge_pool), self.session.goal_challenges)
                    await self._maybe_finish()
                self._warn_below_goal(done)
            if self.session.death_link:
                await self._death_link_tick()
            runes = self.session.rune_flags()
            # The Battle of Hyrule Field's script switches the runes on itself before its last wave (the three moblins) and
            # waits for them: forcing them off there soft-locked the mission [confirmed live 2026-11-07: switching them on
            # brought the moblins at once]. So the client leaves the runes alone during that mission.
            # Road to the Ancient Lab (record 2) is where the story hands out Magnesis and Stasis: left alone the same way
            # [guess: its script may wait for them like Hyrule Field's].
            in_battle = bool(self.live._battle_character())
            if runes and in_battle and (self.live.map_selection() or (0, 0))[:2] in ((1, 2), (2, 2)):
                runes = {}
            if runes and (changed := self.live.set_runes(runes)):
                probe_logger.info("Sheikah Slate: %s", ", ".join(f"{r} {'given' if runes[r] else 'held back'}" for r in changed))
            # Rune lock (0.9.87): a cleared Road to the Ancient Lab makes the game give Magnesis and Stasis whatever their
            # flags say, so its profile state is held at "open" until both are received (map only, never mid-mission).
            if self.session.difficulty_lock and not in_battle:  # the game's menu follows the lock (1 Normal = game 2)
                try:
                    if (old := self.live.raise_difficulty(self.session.difficulty_lock + 1)) is not None:
                        logger.info("Difficulty lock: the game's difficulty was raised (it was %s).",
                                    ("Easy", "Normal", "Hard", "Very Hard", "Apocalyptic")[old - 1])
                except HookError as e:
                    logger.debug("difficulty: %s", e)
            if not in_battle and (hold := self.session.hold_rune_mission()) is not None \
                    and self.live.hold_rune_mission(hold):
                probe_logger.info("Rune lock: Road to the Ancient Lab %s", "held open" if hold else "cleared again")
            # The game's own unlock rules follow the multiworld: only missions the seed has opened can be started.
            opened = cleared | self.session.cleared_missions | set(self.session.available_missions())
            self.live.set_mission_states(opened)  # the map shows the change the next time it is opened
            if self.live.set_mission_locks(opened):
                new_open = sorted(set(self.session.available_missions()) - self._open_logged)
                if new_open:
                    logger.info("Open on the world map: %s", ", ".join(new_open))
                self._open_logged |= set(new_open)
            if self.session.side_random:
                side_now = self.session.side_opened()
                if self._side_opened is not None and (new_side := sorted(side_now - self._side_opened)):
                    logger.info("Now open: %s", ", ".join(new_side))
                    shown = ", ".join(new_side[:3]) + (f" +{len(new_side) - 3} more" if len(new_side) > 3 else "")
                    self.overlay.show(make_notice("info", text=f"Now open: {shown}")["text"])
                    self._audit({"finding": "side_open", "opened": new_side, "completions": self.session.completions})
                    self._expect_side_open(new_side)
                self._side_opened = side_now
            waiting = self.session.waiting_for_heroes()
            for name in sorted(set(waiting) - self._hero_waits_told):
                logger.info("%s is open for you, but the game forces %s into it: it appears once %s yours.", name,
                            " and ".join(waiting[name]), "they are" if len(waiting[name]) > 1 else "that hero is")
                self.overlay.show(f"{name}: waits for {', '.join(waiting[name])}")
                self._tip(f"{name} opens once you have {' and '.join(waiting[name])}")
            self._hero_waits_told |= set(waiting)
            if self.live.set_challenge_locks(self.session.challenge_unlocks()) and not self._challenges_logged:
                self._challenges_logged = True
                probe_logger.info("Challenges now open by the seed's rules (%s), not the vanilla order.",
                            "random, by completions" if self.session.side_random else "challenge_logic")
        except (HookError, OSError) as e:
            logger.info("Lost the connection to the game (%s); reconnecting when it is back.", e)
            if self.probe and self.probe.enabled:
                try:
                    self.probe.game_lost(str(e))  # what the client last wrote, for crash reports
                except Exception:  # (research only: never in the way)
                    pass
            self.live.close()
            self.live = None
            self.overlay.set_banner(None)

    async def _lab_tick(self) -> None:
        """Royal Ancient Lab nodes as checks, and quest rows emptied of the rewards their items give (0.9.81)."""
        session, live = self.session, self.live
        if not session.include_dlc:
            return
        try:
            if session.emptied_quests and self._quest_table_ok:
                if quests := live.empty_quest_rows(session.emptied_quests):
                    probe_logger.info("Rewards taken out of %d quest rows (their items give them).", len(quests))
            if session.ids["lab"] and self._lab_ok:
                for node in live.sync_lab(session.lab_values(), set(session.ids["lab"]),
                                          session.lab_held(), set(session.done["lab"])):
                    if node not in session.done["lab"]:
                        await self._on_game_message({"type": "lab_node", "name": node})
        except Exception as e:  # never let this feature drop the game connection (tried again on reconnect)
            self._lab_ok = self._quest_table_ok = False
            logger.warning("Royal Ancient Lab control is off: %s", e)

    async def _hold_death_loop(self) -> None:
        """A received death holds the party at 0 until the KO, or the mission or attempt ends: a healing item or a hero
        switched in is wiped within DEATH_HOLD_SECONDS (user, 2026-11-03: healing just wastes the item)."""
        from .live_hook import HookError
        try:
            while self.live is not None and self.live.hold_death():
                await asyncio.sleep(DEATH_HOLD_SECONDS)
        except (HookError, OSError) as e:
            logger.debug("DeathLink hold ended: %s", e)

    async def _death_link_tick(self) -> None:
        """Your HP reaching 0 in a mission sends a death; a death from someone else drops your HP to 0."""
        if self._death_hold:
            self._last_hp = 0.0  # our own death from a received link is not sent back
            if self._death_hold_task is None or self._death_hold_task.done():
                self._death_hold = False  # the KO landed (defeat menu), or the mission ended
                self._last_hp = None
            return
        hp = self.live.player_hp()
        if (self._pending_kill and time.monotonic() - self._pending_kill_at > DEATH_STALE
                and not self.live.death_can_land()):
            logger.info("DeathLink from %s ignored: you weren't in a mission.", self._pending_kill)
            self._pending_kill = None  # (user rule) a death outside a mission would only kill the next mission's start
        if self._pending_kill and hp is not None and hp > 0:
            if self.live.kill_player():
                logger.info("DeathLink: %s died. Your health is at 0: the next hit defeats you.", self._pending_kill)
                self.overlay.show(f"DeathLink: {self._pending_kill} died")
                self._audit({"finding": "deathlink", "direction": "applied", "source": self._pending_kill, "hp_was": hp})
                self._death_hold_source = self._pending_kill
                self._pending_kill = None
                self._death_hold = True
                self._death_hold_task = asyncio.create_task(self._hold_death_loop(), name="DeathLink hold")
                self._last_hp = 0.0
                return
        if hp is not None and hp <= 0 and (self._last_hp or 0) > 0:
            logger.info("DeathLink: you fell; telling the others.")
            self._audit({"finding": "deathlink", "direction": "sent"})
            await self.send_death(f"{self.player_names.get(self.slot, 'A hero')} fell in Hyrule")
        self._last_hp = hp

    def _audit(self, record: dict) -> None:
        """A randomizer audit finding (probe findings.jsonl); never lets the audit break the client."""
        if self.probe and self.probe.enabled:
            try:
                self.probe.record(record)
            except OSError:
                pass

    def _expect_side_open(self, names: list[str]) -> None:
        """Opened random side content: the probe checks the game shows it (quest available / challenge open)."""
        from ..data_save import MISSION_RECORD_IDS, QUEST_STATE_IDS
        live = self.live
        for name in names:
            if name in QUEST_STATE_IDS and name in self.session.quest_open_at:
                live.expect("Quest opened", lambda n=name: ((live.quest_state(n) or 0) >= 2, f"state {live.quest_state(n)}"),
                            quest=name)
            elif name in MISSION_RECORD_IDS:
                record = MISSION_RECORD_IDS[name][0]
                live.expect("Challenge opened", lambda r=record: (
                    (lambda st: (st[0] >= 2, f"states {st}"))(live.mission_states(r))), challenge=name)

    def _start_probe(self) -> None:
        """Passive, read-only research probe (client/probe.py) in its own thread, so it never slows the live hook."""
        from .delivery import STATE_DIR
        from .probe import Probe
        from .settings import load_settings
        if not load_settings().get("research_probe"):  # testers only: "/research on"
            return

        if self._probe_task and not self._probe_task.done():
            return
        self.probe = Probe(self.live.g, STATE_DIR / "research")

        async def loop() -> None:
            while self.live is not None and self.probe and self.probe.enabled:
                try:
                    await asyncio.to_thread(self.probe.tick)
                    while self.probe.announcements:
                        probe_logger.info(self.probe.announcements.pop(0))
                except Exception as e:  # research only: never disturb play
                    logger.debug("probe stopped: %s", e)
                    self.probe.enabled = False
                await asyncio.sleep(0.5)

        self._probe_task = asyncio.create_task(loop(), name="research probe")

    def _prime_heroes(self) -> None:
        """Once per starter save: every hero (locked or not) gets a starter weapon and real level-1 stats, so none
        plays with the 1-heart, no-damage placeholder when a party forces it in (live_hook.prime_hero)."""
        from ..data import DLC_CHARACTERS
        from ..data_save import HERO_SLOTS
        heroes = [h for h in HERO_SLOTS if self.session.include_dlc or h not in DLC_CHARACTERS]
        primed = [h for h in heroes if self.live.prime_hero(h)]
        self.delivery.state["primed"] = True
        self.delivery.note([f"starter weapon and stats: {', '.join(primed) or 'nothing needed'}"])
        self.delivery.save_state()
        if primed:
            logger.info("Starter save: gave a starter weapon and level-1 stats to %s.", ", ".join(primed))

    def _dlc_failsafe(self) -> None:
        """A seed with the Expansion Pass on a game whose emulator doesn't list it: say so and ask. Sending checks can't be
        undone, and an emulator's list can be wrong or out of date (Discord report, 2026-11-03: a player with the DLC lost
        every DLC check on connecting), so this only reads the emulator actually running, and only /no_dlc acts on it."""
        if not self.session.include_dlc or not self.session.dlc_location_ids:
            return
        if self.delivery and self.delivery.state.get("no_dlc"):  # confirmed before: keep the goal without the DLC
            self.session.drop_dlc()
            return
        from .dlc import missing_waves
        try:
            missing = missing_waves()
        except Exception as e:  # never let this check break connecting
            logger.debug("DLC check failed: %s", e)
            return
        if not missing or self._dlc_warned:
            return  # installed, nothing running to ask, or the emulator can't tell: nothing changes
        self._dlc_warned = True
        logger.warning("Expansion Pass not detected: your emulator doesn't list %s. If you don't have it, type /no_dlc in "
                       "this window: it releases this seed's DLC checks and takes the DLC out of your goal (this can't be "
                       "undone). If you do have it, check it's installed and enabled for the game, and ignore this.",
                       " / ".join(missing))
        self.overlay.show("Expansion Pass not detected: see the client window")
        self._tip("Expansion Pass not detected. Don't have it? Type /no_dlc in the client to release its checks", 90)

    def confirm_no_dlc(self) -> None:
        """/no_dlc: the player says the game has no Expansion Pass: the goal drops it and its checks are sent."""
        if not self.session or not self.session.dlc_location_ids:
            logger.info("This seed has no Expansion Pass content.")
            return
        if self.delivery:
            self.delivery.state["no_dlc"] = True
            self.delivery.save_state()
        ids = self.session.drop_dlc()
        left = [i for i in ids if i not in self.checked_locations]
        logger.warning("The goal no longer needs DLC story missions or EX challenges (goal challenges now %d), and the %d "
                       "DLC checks are sent so nothing is stuck behind them.", self.session.goal_challenges, len(left))
        if left:
            asyncio.create_task(self.check_locations(left), name="send DLC checks")

    def _warn_below_goal(self, counted: set[str]) -> None:
        """goal_difficulty: say so when a story mission or goal challenge is cleared below it (it still sends its
        check, but doesn't count for the goal). Clears already there when the game is found are not announced."""
        from ..data_save import DIFFICULTIES
        s = self.session
        if s.difficulty_lock or s.goal_complete:  # the lock warns by itself
            return
        goal_names = set(s.story_names) | s.goal_challenge_pool
        below = (self.live.cleared_missions() & goal_names) - counted
        if self._below_goal is not None:
            level = DIFFICULTIES[s.goal_difficulty - 1]
            for name in sorted(below - self._below_goal):
                logger.info("%s was cleared below %s: its check is sent, but the goal only counts clears on %s or "
                            "harder.", name, level, level)
                self.overlay.show(f"{name}: below {level} - doesn't count for the goal")
                self._tip(f"{name}: replay it on {level} or harder for it to count for the goal")
        self._below_goal = below

    def _counted_clears(self) -> set[str]:
        """Story missions and challenges the game shows cleared, as this seed counts them: with a difficulty lock only
        clears on that difficulty or harder (The Battle of Hyrule Field, pre-cleared in the starter save, always), plus
        "<name> (<difficulty>)" for each per-difficulty check earned (a harder clear earns the easier ones too)."""
        from .session import DIFFICULTY_LEVEL
        from ..data_save import DIFFICULTIES
        any_clear = self.live.cleared_missions()
        lock = self.session.difficulty_lock
        if not lock:
            cleared = set(any_clear)
        else:
            cleared = self.live.cleared_missions_at(lock) | ({FIRST_MISSION} & any_clear)
            too_easy = any_clear - cleared
            if self._too_easy is not None:
                for name in sorted(too_easy - self._too_easy):
                    logger.info("%s was cleared below %s: it counts for nothing in this seed (difficulty lock). "
                                "Replay it on %s or harder.", name, DIFFICULTIES[lock], DIFFICULTIES[lock])
                    self.overlay.show(f"{name}: too easy - replay on {DIFFICULTIES[lock]}+")
                    self._tip(f"{name} didn't count: replay it on {DIFFICULTIES[lock]} or harder")
            self._too_easy = too_easy
        wanted = self.session.ids["difficulty"]
        for level in range(1, self.session.difficulty_levels + 1):
            label = next(n for n, v in DIFFICULTY_LEVEL.items() if v == level)
            cleared |= {f"{n} ({label})" for n in self.live.cleared_missions_at(level)} & set(wanted)
        return cleared

    def _cap_levels(self) -> None:
        """hero_level_cap: a hero who reaches 100 goes back to 99 a few seconds later (the level-up itself, with its
        heart and gauge refill, still happens in game)."""
        if not self.session.hero_level_cap:
            return
        now = time.monotonic()
        for hero in sorted(self.session.unlocked_characters):
            if self.live.hero_level(hero) < LEVEL_CAP + 1:
                self._cap_seen.pop(hero, None)
                continue
            since = self._cap_seen.setdefault(hero, now)
            if now - since >= LEVEL_CAP_DELAY and self.live.cap_level(hero, LEVEL_CAP):
                self._cap_seen.pop(hero, None)
                logger.info("%s reached level %d and was set back to %d (hero_level_cap).", hero, LEVEL_CAP + 1, LEVEL_CAP)

    def _sync_heroes(self) -> None:
        """Received heroes are made playable (flag, starting weapon, stats) and every other hero is taken out of the
        selectable roster; in vanilla story-party mode heroes an open story mission forces stay."""
        from ..data_save import HERO_SLOTS, MISSION_FORCED_HEROES
        from .delivery import hero_targets

        received = set(self.session.unlocked_characters)
        if getattr(self.session, "story_party_borrowed", False):  # forced heroes you lack, for the mission at hand
            sel = self.live.map_selection() or (0, 0)
            name = self.session.selection_checks(*sel)[0] if sel[1] in (2, 3) and self.session.selection_checks(*sel) else None
            lent = self.session.lent_heroes(name)
            # (A menu closing leaves the cursor on nothing for a moment: keep the last loan 5 s so heroes don't flicker.)
            now = time.time()
            if lent:
                self._lent_last = (lent, now)
            elif getattr(self, "_lent_last", None) and now - self._lent_last[1] < 5:
                lent = self._lent_last[0]
            if lent and lent != getattr(self, "_lent_logged", set()):
                self._lent_logged = lent
                logger.info("Borrowed for %s: %s (locked again afterwards)", name, ", ".join(sorted(lent)))
            targets = {h: h in received or h in lent for h in HERO_SLOTS}
        elif self.session.story_party_free:
            targets = {h: h in received for h in HERO_SLOTS}
        else:
            targets = hero_targets(received, self.session.available_missions(), MISSION_FORCED_HEROES, list(HERO_SLOTS))
        changed = []
        if not self.session.include_dlc:  # the Expansion Pass plays vanilla: its heroes are left alone
            from ..data import DLC_CHARACTERS
            targets = {h: w for h, w in targets.items() if h not in DLC_CHARACTERS}
        # Never lock a hero mid-battle: a mission that brings one in by script (Impa in The Battle of Hyrule Field)
        # can stall when that hero is taken away (user + Discord: the three moblins never came; probe saw the game
        # restore revoked heroes twice). They are locked again once the battle is over.
        in_battle = bool(self.live._battle_character())
        for hero, want in targets.items():
            if want and self.live.grant_hero(hero):
                changed.append(f"gave {hero}")
            elif not want and not in_battle and self.live.revoke_hero(hero):
                changed.append(f"locked {hero}")
        mine = sorted(h for h in received if targets.get(h))
        if self.session.pace.get("catch_up"):
            # A newly received hero joins at the level of your lowest-level hero (once per hero; never lowered). That
            # is also the hero grant_hero copies the stats from.
            caught = self.delivery.state.setdefault("caught_up", [])
            new = [h for h in mine if h not in caught]
            old = [h for h in mine if h in caught or h in self.session.starting_characters]
            if old:
                level = min(self.live.hero_level(h) for h in old)
                for hero in new:
                    if hero not in self.session.starting_characters and self.live.set_level(hero, level):
                        changed.append(f"{hero} caught up to level {level}")
            caught.extend(new)
        if self.session.min_level > 1:
            changed += [f"{h} raised to level {self.session.min_level}"
                        for h in self.live.raise_levels(mine, self.session.min_level)]
        if changed:
            self.delivery.note(changed)
            self.delivery.save_state()
            logger.info("Heroes: %s", ", ".join(changed))

    def _deliver_to_save_file(self) -> None:
        """Only while Ryujinx is not running at all: the game would overwrite the file otherwise."""
        from .delivery import SaveFileTarget
        from .ryujinx import ryujinx_pids
        from .savewatch import save_copies

        if not self.save_path or not self.delivery.pending(self.received_names()):
            return
        if ryujinx_pids():
            return
        try:
            target = SaveFileTarget(self.save_path, save_copies(self.save_path))
            self.delivery.skip_dlc = not self.session.include_dlc
            done = self.delivery.apply(self.received_names(), set(self.session.unlocked_characters), target)
            target.commit()
        except Exception as e:  # never let a bad save crash the client
            logger.warning("Could not write items into the save: %s", e)
            return
        if done:
            logger.info("Written into your save (you will see them when you start the game): %s", "; ".join(done))

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict[str, Any]) -> None:
        if cmd == "RoomInfo":
            self.room_seed = str(args.get("seed_name", ""))
        elif cmd == "Connected":
            self.session = Session(args["slot_data"])
            asyncio.create_task(self.update_death_link(self.session.death_link), name="death link tag")
            self.session.note_activity(time.time())
            if self.session.world_version != WORLD_VERSION:
                logger.warning(
                    "This seed was generated with world version %s but this client is %s. Update the apworld on "
                    "both sides to avoid problems.", self.session.world_version, WORLD_VERSION)
            logger.info(self.session.goal_summary())
            if self._rescue_task is None or self._rescue_task.done():
                self._rescue_task = asyncio.create_task(self._rescue_loop(), name="stuck rescue")
            self._items_applied = 0
            self.session.apply_checked_location_ids(set(args.get("checked_locations", [])))
            self._dlc_failsafe()
            asyncio.create_task(self._push_state(), name="push state after connect")
            # This slot's own ledger and save (another seed may have been connected before in this client run).
            self.delivery = None
            self.save_path = None
            self.save_watcher = None
            self._live_seen = None
            self._too_easy = None
            self._below_goal = None
            self._side_opened = None
            self._starter_reason = None
            self._elsewhere_noted = None
            self._first_mission_noted = False
            self._ensure_delivery()
            self._find_save_path()
            self._selection = None
            missing = sorted(self.missing_locations)  # what each check holds, for the map cursor notice (free scout)
            if missing:
                asyncio.create_task(self.send_msgs([{"cmd": "LocationScouts", "locations": missing, "create_as_hint": 0}]),
                                    name="scout own locations")
        elif cmd == "ReceivedItems" and self.session:
            asyncio.create_task(self._sync_items(), name="sync received items")
        elif cmd == "RoomUpdate" and self.session and "checked_locations" in args:
            if self.session.apply_checked_location_ids(set(args["checked_locations"])):
                asyncio.create_task(self._push_state(), name="push state after room update")

    def on_deathlink(self, data: dict[str, Any]) -> None:
        """A linked player died: tell the game to kill the player."""
        super().on_deathlink(data)
        if self.session and self.session.death_link:
            self._pending_kill = data.get("source", "someone")  # applied in the next ticks if you are in a mission
            self._pending_kill_at = time.monotonic()
            self._audit({"finding": "deathlink", "direction": "received", "source": self._pending_kill})
            asyncio.create_task(
                self.bridge.send({"type": "death_link", "source": data.get("source", ""), "cause": data.get("cause", "")}),
                name="forward death link",
            )

    # --- multiworld -> game --------------------------------------------------------------

    async def _sync_items(self) -> None:
        assert self.session is not None
        start = self._items_applied
        new = self.items_received[start:]
        self._items_applied = len(self.items_received)
        # Items already announced in an earlier connection to this seed get no notice again (a reconnect resends them
        # all); the count is kept in the seed's ledger.
        announced = 0
        if self._ensure_delivery():  # seeds from before this count: the items already delivered
            announced = int(self.delivery.state.get("announced", self.delivery.state.get("applied", 0)))
        names = [self.item_names.lookup_in_game(i.item) for i in new]
        shown = []  # notice text: a quest reward group item names the quest(s) this copy unlocks
        from ..data_rewards import ALL_GROUPS
        for k, name in enumerate(names, start=start):
            before = self.session.unlocked_by(name)
            self.session.apply_received_item_names([name])
            opened = [q for q in self.session.unlocked_by(name) if q not in before]
            shown.append(name + " -> " + ", ".join(q + BEAST.get(q, "") for q in opened) if opened else name)
            if opened and k >= announced:  # (a reconnect resends every item: say it once per seed)
                kind = ALL_GROUPS[name].kind if name in ALL_GROUPS else "unlock"
                how = {"store": "reward given", "hearts": "reward given",
                       "quest": "service opens once you have bought it"}.get(kind, "complete it in game for its reward")
                logger.info("%s: %s (%s)", name, ", ".join(opened), how)
        # Always forward the raw names too: filler (rupees, materials, meals) is applied game-side.
        await self.bridge.send({"type": "items_received", "items": names})
        notices = [
            make_notice("received", item=text, me=self.player_names.get(self.slot, ""),
                        player=self.player_names.get(item.player, "") if item.player != self.slot else "")
            for item, text in zip(new, shown)
        ]
        fresh = [k for k in range(len(new)) if start + k >= announced]
        for k in fresh:
            self._audit({"finding": "received", "item": names[k], "from": self.player_names.get(new[k].player, "")})
        for k in fresh:  # the overlay shows them one at a time
            self.overlay.show(notices[k]["text"])
            await self.bridge.send(notices[k])
        if self.delivery and self._items_applied > announced:
            self.delivery.state["announced"] = self._items_applied
            self.delivery.save_state()
        await self._push_state()

    async def _scout_random_hint(self) -> None:
        import random

        pool = sorted(self.missing_locations - self.locations_checked)
        if pool:
            await self.send_msgs([{"cmd": "LocationScouts", "locations": [random.choice(pool)], "create_as_hint": 2}])

    async def _rescue_loop(self) -> None:
        """Hint one unchecked location after a long quiet spell, so there is always a next target."""
        while self.session:
            await asyncio.sleep(30)
            if self.session and self.session.rescue_due(time.time()):
                logger.info("No new checks for a while - revealing a hint.")
                await self._scout_random_hint()

    async def _grant_free_hints(self) -> None:
        """Every N story missions, scout one random unchecked location as a hint."""
        assert self.session is not None
        import random

        # Hints already given are kept in the seed's ledger: every reconnect reports all clears again, and the
        # in-memory count alone would hand the same hints out once per client start.
        stored = self.delivery.state.get("hints_given", 0) if self.delivery else 0
        self.session.hints_given = max(self.session.hints_given, stored)
        due = self.session.hints_due()
        if self.delivery and self.session.hints_given != stored:
            self.delivery.state["hints_given"] = self.session.hints_given
            self.delivery.save_state()
        for _ in range(due):
            pool = sorted(self.missing_locations - self.locations_checked)
            if not pool:
                return
            await self.send_msgs([{
                "cmd": "LocationScouts", "locations": [random.choice(pool)], "create_as_hint": 2,
            }])

    def _write_tracker(self) -> None:
        if not self.session:
            return
        try:
            Path("aoc_tracker.html").write_text(self.session.tracker_html(), encoding="utf-8")
        except OSError:
            logger.debug("could not write aoc_tracker.html", exc_info=True)

    async def _push_state(self) -> None:
        await self.bridge.send(self._title_info())
        if self.session:
            self._write_tracker()
            await self.bridge.send(self.session.snapshot())
        await self._maybe_finish()

    def _title_info(self) -> dict[str, Any]:
        s = self.session
        if not s or not self.slot:
            return title_info(False)
        return title_info(
            True, slot=self.player_names.get(self.slot, ""), seed=str(self.seed_name or ""),
            server=str(self.server_address or ""), world_version=s.world_version,
            checked=s.checks_done(), total=s.total_checks(), goal_complete=s.goal_complete,
        )

    async def _on_game_connected(self) -> None:
        await self.bridge.send({"type": "hello", "version": PROTOCOL_VERSION, "game": GAME_NAME})
        await self._push_state()

    async def disconnect(self, allow_autoreconnect: bool = False) -> None:
        self.session = None
        await self.bridge.send(title_info(False))
        await super().disconnect(allow_autoreconnect)

    def on_print_json(self, args: dict[str, Any]) -> None:
        """Turn item sends and hints from the server into on-screen notices."""
        super().on_print_json(args)
        kind = args.get("type")
        if kind not in ("ItemSend", "Hint"):
            return
        item, receiver = args.get("item"), args.get("receiving")
        if item is None or receiver is None:
            return
        item_name = self.item_names.lookup_in_game(item.item, self.slot_info[receiver].game)
        if kind == "ItemSend" and item.player == self.slot and receiver != self.slot:
            notice = make_notice("sent", item=item_name, player=self.player_names.get(receiver, ""),
                                 me=self.player_names.get(self.slot, ""))
        elif kind == "Hint" and not args.get("found") and receiver == self.slot:
            location = self.location_names.lookup_in_game(item.location, self.slot_info[item.player].game)
            notice = make_notice("hint", item=item_name, location=location)
        else:
            return
        self.overlay.show(notice["text"])
        asyncio.create_task(self.bridge.send(notice), name="forward notice")

    # --- game -> multiworld --------------------------------------------------------------

    async def _on_game_message(self, message: dict[str, Any]) -> None:
        if not self.session:
            return  # not connected to a slot yet; the hook will be resynced on connect
        kind = message.get("type")
        location_id = None
        if kind == "mission_cleared":
            location_id = self.session.on_mission_cleared(str(message.get("mission")))
        elif kind == "weapon_obtained":
            location_id = self.session.on_weapon_obtained(str(message.get("weapon")))
        elif kind == "challenge_cleared":
            location_id = self.session.on_challenge_cleared(str(message.get("challenge")))
        elif kind == "difficulty_cleared":
            location_id = self.session.on_difficulty_cleared(str(message.get("name")))
        elif kind == "quest_completed":
            location_id = self.session.on_quest_completed(str(message.get("quest")))
        elif kind == "korok_found":
            location_id = self.session.on_korok_found(str(message.get("korok")))
        elif kind == "lab_node":
            location_id = self.session.on_lab_node(str(message.get("name")))
        elif kind == "player_died":
            if self.session.death_link:
                await self.send_death(f"{self.player_names.get(self.slot, 'A hero')} fell in Hyrule")
                self._audit({"finding": "deathlink", "direction": "sent"})
            return
        elif kind == "request_state":
            await self._push_state()
            return
        else:
            logger.debug("Ignoring unknown game message: %r", message)
            return

        source = next((str(message.get(k)) for k in ("mission", "weapon", "challenge", "quest", "korok", "name")
                       if k in message), "")
        if location_id is None and source not in self._no_check_noted:  # (once each: thousands piled up per week)
            self._no_check_noted.add(source)
            self._audit({"finding": "no_check", "kind": kind, "name": source})
        if location_id is not None:
            self.session.note_activity(time.time())
            sent = {location_id}
            if kind in ("mission_cleared", "challenge_cleared"):  # bonus checks go out with their clear
                sent |= self.session.bonus_ids(source)
            self._audit({"finding": "check", "kind": kind, "name": source, "locations": sorted(sent)})
            await self.check_locations(sent)
            if kind == "mission_cleared":
                await self._grant_free_hints()
            await self._push_state()

    async def _maybe_finish(self) -> None:
        if self.session and self.session.goal_complete and not self.finished_game:
            self.finished_game = True
            if self.delivery:  # this seed is over: its save may get a new seed's starter save
                self.delivery.state["finished"] = True
                self.delivery.save_state()
            await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            self._audit({"finding": "goal", "cleared": sorted(self.session.cleared_missions)})

    # --- shutdown / ui -------------------------------------------------------------------

    async def _save_loop(self) -> None:
        while not self.exit_event.is_set():
            await asyncio.sleep(1)
            if not self.session or not self._ensure_delivery():
                continue
            if sys.platform == "win32":
                await self._live_tick()
            if not self.save_path and time.time() >= self._save_search_at:
                self._save_search_at = time.time() + 30  # a save made after connecting is picked up too
                self._find_save_path()
            if self.save_watcher:
                for m in self.save_watcher.poll():
                    if self.session.difficulty_lock and m.get("type") in ("mission_cleared", "challenge_cleared"):
                        continue  # the save reader doesn't see difficulties: the live hook decides (_counted_clears)
                    if self.live is None:
                        logger.info("Save shows cleared: %s", m.get("mission") or m.get("challenge"))
                    await self._on_game_message(m)
            if self.live is None and time.time() >= self._starter_check_at:
                self._starter_check_at = time.time() + (2 if self.save_belongs_elsewhere() else 10)  # (a quick reopen must not miss it)
                self._follow_emulator()
                self.maybe_install_starter()
                self.sync_saves()
            if self.live is None:
                self._deliver_to_save_file()

    def _several_emulators(self) -> bool:
        """More than one emulator is open (Ryujinx and Eden, or two of one): the client refuses to touch the game or
        any save until only one is left, said once."""
        from .ryujinx import emulator_processes
        names = [name for _, name in emulator_processes()]
        if len(names) <= 1:
            self._several_noted = False
            return False
        if not self._several_noted:
            self._several_noted = True
            logger.warning("Several emulators are open (%s). The client leaves the game and your saves alone until "
                           "only one is open.", ", ".join(names))
            self.overlay.show("Several emulators open: close all but one")
        return True

    def _follow_emulator(self) -> None:
        """Use the save of the emulator that is open (the same seed can have a save in Ryujinx and in Eden)."""
        from .ryujinx import emulator_processes
        from .savesync import emulator_of
        running = {name for _, name in emulator_processes()}
        if self.save_path and len(running) == 1 and emulator_of(self.save_path) not in running:
            self.save_path = None
            self._find_save_path()

    def own_saves(self) -> list[str]:
        """This seed's saves, one per emulator."""
        from .savewatch import find_save_files
        me = self.delivery.state_file.stem if self.delivery else None
        return [p for p in find_save_files() if me and self._shelf().owner(p) == me]

    def sync_saves(self, force: bool = False, claim: bool = False) -> list[str]:
        """No game running: copy this seed's newest save over its older copies in the other emulator. claim: also
        make an unowned save in an emulator that has none of this seed's yet this seed's (from /sync_saves)."""
        from .delivery import STATE_DIR
        from .savesync import emulator_of, sync_saves
        from .savewatch import find_save_files
        if not self.delivery or self._game_running():
            return []
        mine = self.own_saves()
        if claim and mine:
            have = {emulator_of(p) for p in mine}
            for path in find_save_files():
                if emulator_of(path) not in have and self._shelf().owner(path) is None:
                    self._shelf().set_owner(path, self.delivery.state_file.stem)
                    have.add(emulator_of(path))
                    mine.append(path)
        try:
            lines = sync_saves(mine, STATE_DIR / "backups" / "save_sync", force)
        except Exception as e:  # never let syncing break the client
            lines = [f"Save sync skipped: {e}"]
        for line in lines:
            logger.info(line)
        return lines

    def _game_running(self) -> bool:
        """Age of Calamity is booted in some Ryujinx: its window title names the game (works whatever the memory
        mode), or its memory is mapped. Saves are only ever switched when this is False."""
        if sys.platform != "win32":
            return False
        if self._several_emulators():
            return True  # never touch a save while it is unclear which emulator plays it
        from .ryujinx import FastmemGuest, Guest, Process, emulator_processes, game_in_window
        if game_in_window():
            return True
        for pid, emulator in emulator_processes():
            try:
                proc = Process(pid)
            except OSError:
                continue
            try:
                # An emulator that just started may be booting the game: Eden reads the save before the window title
                # or the game's code show it (2026-11-13: a starter save went in mid-boot, the game ran the old seed's
                # save and the client counted its quests). Wait until it has run a while.
                age = proc.age_seconds()
                if age is not None and age < EMULATOR_BOOT_SECONDS:
                    return True
                if Guest.attach(proc) if emulator == "Ryujinx" else FastmemGuest.modules(proc):
                    return True
            finally:
                proc.close()
        return False

    def _shelf(self):
        from .delivery import STATE_DIR
        from .starter_save import SaveShelf
        return SaveShelf(STATE_DIR / "saves")

    def maybe_install_starter(self, force: bool = False) -> None:
        """Make the save on disk this seed's (the game must be closed): a new seed gets the starter save (skips the
        forced first mission), a seed played before gets its own save back, and the save it replaces is parked under
        the seed it belongs to, so switching back restores it. A save with progress the client has never seen with
        any seed is only replaced by /starter_save. See starter_save.plan_switch."""
        from . import starter_save
        from .delivery import STATE_DIR
        from .savewatch import save_copies
        if not self.session or not self.delivery:
            return
        if self._game_running():
            if force:
                logger.info("Close Age of Calamity first; the client switches the save while it is closed.")
            return
        path = self.save_path
        if not path:
            if force or self._starter_reason != "no save":
                self._starter_reason = "no save"
                logger.info("No Age of Calamity save yet: start the game once (New Game until "
                            "the first cutscene), close it, and the client sets up this seed's save.")
            return
        try:
            with open(path, "rb") as f:
                current = f.read()
            starter_save.check_save(current)
        except (OSError, starter_save.SaveFormatError) as e:
            logger.warning("Save %s can't be read: %s", path, e)
            return
        shelf, me = self._shelf(), self.delivery.state_file.stem
        owner = shelf.owner(path)
        if (owner == me and self.session.starter_save and starter_save.is_fresh(current)
                and path not in self.delivery.state.get("starter", {})):
            owner = None  # claimed during live play before the starter went in (the game made a New Game save)
        action, park, why = starter_save.plan_switch(me, owner, starter_save.is_fresh(current), shelf.has_parked(me),
                                                     self.session.starter_save, force)
        if action == "none":
            return
        if action == "refuse":
            if force or why != self._starter_reason:
                self._starter_reason = why
                logger.info("Save not changed: %s.", why)
            return
        if action == "claim":
            shelf.set_owner(path, me)
            return
        if park:
            parked = shelf.park(owner or f"unclaimed_{time.strftime('%Y%m%d_%H%M%S')}", current)
            logger.info("Your save for %s is kept in %s.", owner or "the unknown game", parked)
        if action == "restore":
            data = shelf.take(me)
            starter_save.install(path, save_copies(path), data, STATE_DIR / "backups")
            logger.info("Switched to this seed's own save (%s). Start Age of Calamity and pick Continue.", why)
            self._refresh_hint = True
        else:
            try:  # the seed's opening quests and challenges too, so the first map draw is right (0.9.87)
                quests, challenges = self.session.quest_states(), self.session.challenge_unlocks()
                extras_ok = True
            except Exception as e:  # never let this extra stop the install
                logger.debug("starter save extras: %s", e)
                quests, challenges, extras_ok = {}, {}, False
            data = starter_save.prepare(sorted(self.session.unlocked_characters), self.session.available_missions(),
                                        quests, challenges)
            starter_save.install(path, save_copies(path), data, STATE_DIR / "backups")
            self.delivery.new_game(set())  # a fresh save: every received item is given again
            from .savefile import owned_weapons
            self.delivery.set_baseline(owned_weapons(data))  # weapons it starts with are no finds; Hyrule Field counts
            self.delivery.state["primed"] = False  # heroes get weapons and stats on the first live tick
            # 0.9.87: the starter save already holds the seed's opening missions, quests and challenges, so the first map
            # draw is right [confirmed on Eden 2026-11-13 with no client running]; the refresh hint is only a fallback.
            self._refresh_hint = not extras_ok
            logger.info("Starter save installed (%s). Start Age of Calamity and pick Continue: the forced first mission "
                        "is skipped; play %s with your starting heroes.", why,
                        " or ".join(m for m in self.session.available_missions() if m != FIRST_MISSION)
                        or "your first mission")
        self.delivery.state.setdefault("starter", {})[path] = time.time()
        self.delivery.save_state()
        shelf.set_owner(path, me)
        self._starter_reason = None
        self.set_save_path(path)  # watch the new save from scratch

    def banner_on(self) -> bool:
        if self.banner_pref is not None:
            return bool(self.banner_pref)
        return bool(self.session and self.session.goal_banner)

    def _tip(self, text: str, seconds: float = TIP_SECONDS) -> None:
        """Put what to do next in the banner for a while (the newest tip wins)."""
        self._banner_tip = (text, time.monotonic() + seconds)

    def _show_goal_banner(self) -> None:
        """Goal progress at the top of the emulator window while on the world map (not during a mission)."""
        in_battle = self.live._battle_character()
        hold = getattr(self, "_death_hold_source", None) if getattr(self, "_death_hold", False) else None
        flow = self.live._flow() if in_battle else None
        waiting = flow and flow[1] == FLOW_PAUSED and getattr(self, "_pending_kill", None)
        if hold or waiting:  # (what to do next, whatever /goal_banner says)
            self.overlay.set_banner(f"DeathLink from {hold}: your next hit defeats you (healing won't help)" if hold
                                    else f"DeathLink from {self._pending_kill}: it lands when you unpause")
            return
        if self._refresh_hint and not in_battle:  # a new seed's first visit: the map was drawn before the client's setup
            if self._refresh_until is None:
                self._refresh_until = time.monotonic() + REFRESH_HINT_SECONDS
                logger.info("New seed set up: open the pause menu and go back to the map once, so the Smithy, the "
                            "Training Camp and every opened icon show up.")
            if time.monotonic() < self._refresh_until:
                self.overlay.set_banner("New seed: pause and go back to the map once so everything appears (this note clears by itself)")
                return
            self._refresh_hint = False
        if getattr(self, "_banner_tip", None) and not in_battle:
            if time.monotonic() < self._banner_tip[1]:
                self.overlay.set_banner(self._banner_tip[0])
                return
            self._banner_tip = None
        on_map = self.banner_on() and not in_battle
        self.overlay.set_banner(self.session.goal_banner_text() if on_map else None)

    def _show_selection(self) -> None:
        """The cursor panel: while the world-map cursor is on a mission, challenge or quest, the overlay's bottom-right
        panel lists what its checks hold, one per line (from a free scout of this slot's locations at connect; no hint
        points), cycling SELECTION_PAGE at a time when there are more. It goes away when the cursor leaves it or a
        mission is running."""
        sel = None if self.live._battle_character() else self.live.map_selection()
        now = time.monotonic()
        lab_node = None
        if sel == (LAB_SERVICE, 5) and self.session.ids["lab"] and self.session.include_dlc:
            try:
                lab_node = self.live.lab_selected_node()
            except Exception as e:  # (the panel is a convenience: never in the way)
                logger.debug("Lab cursor: %s", e)
            sel = (LAB_SERVICE, 5, lab_node)
        if sel == self._selection:
            if len(self._selection_pages) > 1 and now >= self._selection_turn:  # next page of a long list
                self._selection_page = (self._selection_page + 1) % len(self._selection_pages)
                self._selection_turn = now + SELECTION_SECONDS
                self.overlay.set_status(self._selection_pages[self._selection_page])
            return
        self._selection = sel
        self._selection_pages, self._selection_page, self._selection_turn = [], 0, now + SELECTION_SECONDS
        found = self.session.selection_checks(*sel[:2]) if sel else None
        if lab_node:
            found = (lab_node, [self.session.ids["lab"][lab_node]] if lab_node in self.session.ids["lab"] else [])
        if not found:
            self.overlay.set_status(None)
            return
        name, ids = found
        left = [i for i in ids if i not in self.checked_locations and i not in self.locations_checked]
        if not ids:
            self._selection_pages = [f"{name}\nno check in this seed"]
        elif not left:
            self._selection_pages = [f"{name}\nall checks done"]
        else:
            lines = []
            for i in left:
                info = self.locations_info.get(i)
                if info is None:
                    lines.append("? (not scouted)")
                    continue
                item = self.item_names.lookup_in_slot(info.item, info.player)
                line = item if info.player == self.slot else f"{self.player_names.get(info.player, '?')}'s {item}"
                node = self.session.lab_node_of(i)
                lines.append(f"{node}: {line}" if node and not lab_node else line)
            pages = [lines[k:k + SELECTION_PAGE] for k in range(0, len(lines), SELECTION_PAGE)]
            self._selection_pages = [f"{name}" + (f"  ({n + 1}/{len(pages)})" if len(pages) > 1 else "") + "\n"
                                     + "\n".join(page) for n, page in enumerate(pages)]
        logger.debug("Map cursor: %s", self._selection_pages[0].replace("\n", "; "))
        self.overlay.set_status(self._selection_pages[0])

    def _warn_unreadable(self, now: float) -> None:
        """Ryujinx shows the game running but the client can't read it for a while: tell the player what to check."""
        from .ryujinx import game_in_window
        if not game_in_window():
            self._unreadable_since = None
            return
        if self._unreadable_since is None:
            self._unreadable_since = now
        # (the banner needs no readable game: it sits on the emulator window)
        if now - self._unreadable_since <= TITLE_HINT_SECONDS:
            self.overlay.set_banner("Archipelago connected: pick Continue to load your save")
        else:
            self.overlay.set_banner("The client can't read the game: see the client window")
        if now - self._unreadable_since > 120 and not self._unreadable_warned:
            self._unreadable_warned = True
            logger.warning("An emulator is running Age of Calamity but the client can't read the game. Check: (1) "
                           "Ryujinx: Options > Settings > System > Memory Manager Mode = Software (then restart the "
                           "game); Eden: CPU accuracy Auto; (2) the game is version 1.4.1 (the window title shows "
                           "it); (3) a save is loaded (pick Continue). Tested on Ryujinx 1.3.3 and Eden 0.2.1.")
            self.overlay.show("Client can't read the game: see the client window")

    def save_belongs_elsewhere(self) -> str | None:
        """The seed the save on disk belongs to, when it isn't this one (then live play must not touch the game)."""
        if not (self.save_path and self.delivery):
            return None
        owner = self._shelf().owner(self.save_path)
        return owner if owner and owner != self.delivery.state_file.stem else None

    async def shutdown(self) -> None:
        self.overlay.enabled = False
        await self.bridge.stop()
        await super().shutdown()

    def make_gui(self):
        ui = super().make_gui()

        from .settings import load_settings

        class AoCManager(ui):
            base_title = "Archipelago Age of Calamity Client"
            if load_settings().get("research_probe"):  # its own tab, so research lines don't bury the game's
                logging_pairs = [("Client", "Archipelago"), (PROBE_LOGGER, "Game Research")]

        return AoCManager


def launch(*launch_args: str) -> None:
    import colorama

    async def main(args) -> None:
        ctx = AoCContext(args.connect, args.password)
        ctx.auth = args.name
        await ctx.bridge.start()
        ctx._save_task = asyncio.create_task(ctx._save_loop(), name="SaveWatch")
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="ServerLoop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        await ctx.exit_event.wait()
        await ctx.shutdown()

    parser = get_base_parser(description="Age of Calamity Archipelago client")
    parser.add_argument("--name", default=None, help="Slot name to connect as.")
    parser.add_argument("url", nargs="?", help="Archipelago connection url")
    args = handle_url_arg(parser.parse_args(launch_args), parser=parser)
    logging.getLogger("AgeOfCalamity").setLevel(logging.INFO)
    colorama.just_fix_windows_console()
    asyncio.run(main(args))
    colorama.deinit()
