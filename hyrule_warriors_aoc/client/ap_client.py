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

DEATH_RESTART_DELAY = 3.0  # seconds between the forced defeat (HP 0, controls off) and Retry

NEW_GAME_CONFIRM = 30.0  # seconds a smaller game state must last before it counts as a New Game


FIRST_MISSION = "The Battle of Hyrule Field"
FIRST_MISSION_NOTE = ("Note: a new game always starts with The Battle of Hyrule Field played as Link and Impa (the game "
                      "forces it before the world map exists). Your starting heroes and the seed's mission order take "
                      "over from the world map; clearing it is still a check.")
BEAST = {"Regulating the Reservoir": " (Vah Ruta)", "Surveying the Volcano": " (Vah Rudania)",
         "Revitalize Those in the Skies": " (Vah Medoh)", "Patrolling the Desert": " (Vah Naboris)"}  # [guess by name]
SELECTION_PAGE, SELECTION_SECONDS = 6, 4.0  # cursor panel: checks per page, seconds per page
STARTER_NOTE = ("This seed skips the forced first mission, but the starter save isn't installed on this save. If this "
                "is a New Game, close Age of Calamity in Ryujinx: the client installs the starter save (backup kept) "
                "and you then pick Continue. Type /starter_save to force it.")

class AoCCommandProcessor(ClientCommandProcessor):
    ctx: AoCContext

    def _cmd_check_hook(self) -> None:
        """Quick health check: is the game hook connected, and is it in sync with this seed?"""
        ctx = self.ctx
        if ctx.live:
            self.output("Connected to the game in Ryujinx (live)." + ("" if ctx.session else " Connect to your slot next."))
            if ctx.session:
                try:
                    self.output(f"Rupees in game: {ctx.live.rupees()}; clears seen: {len(ctx._live_seen or ())}")
                except Exception as e:  # mid-load: the hook reconnects on its own
                    self.output(f"Game is loading or changed ({e}); the client reconnects by itself.")
        elif not ctx.bridge.connected:
            self.output("Game NOT connected. Start Age of Calamity in Ryujinx and load your save; the client attaches "
                        "by itself within a few seconds (Windows, Ryujinx memory mode 'Software' only).")
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
        self.output(f"Game: {'connected live' if ctx.live else 'not running (items wait for it, or go into the save file while Ryujinx is closed)'}")
        self.output(f"Waiting to be given: {', '.join(pending) or 'nothing'}")
        for line in ctx.delivery.state["log"][-5:]:
            self.output("  " + line)

    def _cmd_todo(self) -> None:
        """What you can play right now, and which heroes you are allowed to use."""
        ctx = self.ctx
        if not ctx.session:
            self.output("Connect to your multiworld slot first.")
            return
        s = ctx.session
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
            if name in ("Character XP Gift", "Weapon XP Gift", "Extra Weapon"):
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
        self._last_hp: float | None = None
        self._restart_at: float | None = None  # DeathLink: when to request Retry after the forced defeat
        self.probe = None
        self._probe_task: asyncio.Task | None = None
        self._open_logged: set[str] = set()
        self._challenges_logged = False
        self._first_mission_noted = False
        self._quest_rows_ok = True
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
            self.set_save_path(max(mine or free or found, key=lambda p: os.path.getmtime(p)))
        else:
            logger.debug("No Age of Calamity save found yet; checking again shortly (live play works without it).")
            now = time.time()
            if self._no_save_since is None:
                self._no_save_since = now
            elif now - self._no_save_since > 60 and self._no_save_since > 0:
                self._no_save_since = -1.0  # said once
                from .savewatch import ryujinx_data_roots
                logger.warning("No Age of Calamity save found (looked in: %s). Start the game once on your Ryujinx "
                               "profile. If Ryujinx keeps its data somewhere else, type /ryujinx_folder <folder> (in "
                               "Ryujinx: File > Open Ryujinx Folder shows it).",
                               ", ".join(ryujinx_data_roots()) or "no Ryujinx folder")

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
        if ignore:
            logger.warning("%d clears were already in this save before the seed started; they will NOT count as checks. "
                           "For a full run, start a New Game (back up your save first).", len(ignore))

    # --- the live game hook ---------------------------------------------------------------

    async def _live_tick(self) -> None:
        from .live_hook import HookError, LiveGame
        from .savewatch import message_for

        now = time.time()
        if (other := self.save_belongs_elsewhere()) and self._game_running():  # another seed's save: hands off
            if self._elsewhere_noted != other:
                self._elsewhere_noted = other
                logger.info("The save on this Ryujinx profile belongs to seed %s, so the client leaves the game alone. "
                            "To play this seed, close Age of Calamity: the client switches the save (seed %s's save "
                            "is kept and comes back when you connect it again).", other, other)
                self.overlay.show("This save belongs to another seed: close the game to switch")
            if self.live is not None:
                self.live.close()
                self.live = None
            return
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
                self._warn_unreadable(now)
                return
            self._unreadable_since = None
            self._live_seen = None
            if self.save_path and self.delivery and self._shelf().owner(self.save_path) is None:
                self._shelf().set_owner(self.save_path, self.delivery.state_file.stem)  # the save this seed plays on
            self._start_probe()
            logger.info("Connected to Age of Calamity in Ryujinx: story and challenge clears are sent the moment "
                        "they happen; Rupee Pouch, Material Bundle and Character XP Gift arrive in game.")
        try:
            cleared = self.live.cleared_missions() | self.live.completed_quests()
            self.session.game_done = set(cleared)  # random side unlocks open by this count
            if not self._first_mission_noted and FIRST_MISSION not in cleared and not self.session.cleared_missions:
                self._first_mission_noted = True
                if not self.session.starter_save:  # seeds before 0.9.54
                    logger.info(FIRST_MISSION_NOTE)
                    self.overlay.show("First mission: Hyrule Field with Link and Impa (vanilla)")
                elif not (self.delivery and self.delivery.state.get("starter")):
                    logger.info(STARTER_NOTE)
                    self.overlay.show("Close the game: the client sets up your starter save")
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
                logger.info("Cleared in game: %s", name)
                if self.probe:
                    self.probe.note(f"cleared {name}")
                await self._on_game_message(message_for(name))
            done = self.delivery.apply(self.received_names(), set(self.session.unlocked_characters), self.live)
            if done:
                logger.info("Given in game: %s", "; ".join(done))
                for line in done:  # who or what got each gift (user request)
                    self.overlay.show(line)
                self._audit({"finding": "delivered", "done": done})
            self._sync_heroes()
            if self.delivery.state.get("primed") is False:  # a fresh starter save: every hero gets a weapon and stats
                self._prime_heroes()
            if self.session.story_party_free:
                party = self.live.best_heroes(set(self.session.unlocked_characters))
                if self.live.set_story_parties(party) and party != self._party_logged:
                    self._party_logged = party
                    logger.info("Story missions now start with your heroes: %s", ", ".join(party))
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
                        logger.info("Mission rewards set by the seed (%s).",
                                    "shuffled" if self.session.mission_rewards.get("mode") == 1 else "none")
                except HookError as e:  # never let this one feature drop the game connection
                    self._rewards_ok = False
                    logger.warning("Mission rewards stay vanilla: %s", e)
            if self.live.set_reward_bytes(self.session.reward_writes()):
                logger.info("Quest rewards set from received items.")
            if quests := self.live.set_quest_states(self.session.quest_states()):
                logger.info("Services (quest states) set from received items: %s", ", ".join(quests))
            self._show_selection()
            if self._quest_rows_ok and (rows := self.session.quest_rows()):
                try:
                    if self.live.set_quest_locks(rows) and not self._quest_rows_logged:
                        self._quest_rows_logged = True
                        logger.info("Quests now open by the seed's rules (random, by completions), not the game's order.")
                except HookError as e:  # never let this one feature drop the game connection
                    self._quest_rows_ok = False
                    logger.warning("Quest unlock rules stay vanilla: %s", e)
            if self.session.goal_challenges:
                any_done = self.live.cleared_missions()
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
                                len(done & set(self.session.mission_ids)), self.session.goal_story_missions,
                                len(done & self.session.goal_challenge_pool), self.session.goal_challenges)
                    await self._maybe_finish()
            if self.session.death_link:
                await self._death_link_tick()
            runes = self.session.rune_flags()
            if runes and (changed := self.live.set_runes(runes)):
                logger.info("Sheikah Slate: %s", ", ".join(f"{r} {'given' if runes[r] else 'held back'}" for r in changed))
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
            if self.live.set_challenge_locks(self.session.challenge_unlocks()) and not self._challenges_logged:
                self._challenges_logged = True
                logger.info("Challenges now open by the seed's rules (%s), not the vanilla order.",
                            "random, by completions" if self.session.side_random else "challenge_logic")
        except (HookError, OSError) as e:
            logger.info("Lost the connection to the game (%s); reconnecting when it is back.", e)
            self.live.close()
            self.live = None

    async def _death_link_tick(self) -> None:
        """Your HP reaching 0 in a mission sends a death; a death from someone else drops your HP to 0."""
        if self._restart_at is not None:
            now = time.monotonic()
            if now >= self._restart_at and (self.live.restart_mission() or now > self._restart_at + 30):
                self._restart_at = None
            self._last_hp = 0.0  # our own death from a received link is not sent back
            return
        hp = self.live.player_hp()
        if self._pending_kill and hp is not None and hp > 0:
            if self.live.kill_player():
                logger.info("DeathLink: %s died, so did you; the mission restarts.", self._pending_kill)
                self.overlay.show(f"DeathLink: {self._pending_kill} died")
                self._audit({"finding": "deathlink", "direction": "applied", "source": self._pending_kill, "hp_was": hp})
                self._pending_kill = None
                self._restart_at = time.monotonic() + DEATH_RESTART_DELAY
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

        if self._probe_task and not self._probe_task.done():
            return
        self.probe = Probe(self.live.g, STATE_DIR / "probe")

        async def loop() -> None:
            while self.live is not None and self.probe and self.probe.enabled:
                try:
                    await asyncio.to_thread(self.probe.tick)
                    while self.probe.announcements:
                        logger.info(self.probe.announcements.pop(0))
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

    def _sync_heroes(self) -> None:
        """Received heroes are made playable (flag, starting weapon, stats) and every other hero is taken out of the
        selectable roster; in vanilla story-party mode heroes an open story mission forces stay."""
        from ..data_save import HERO_SLOTS, MISSION_FORCED_HEROES
        from .delivery import hero_targets

        received = set(self.session.unlocked_characters)
        if self.session.story_party_free:
            targets = {h: h in received for h in HERO_SLOTS}
        else:
            targets = hero_targets(received, self.session.available_missions(), MISSION_FORCED_HEROES, list(HERO_SLOTS))
        changed = []
        if not self.session.include_dlc:  # the Expansion Pass plays vanilla: its heroes are left alone
            from ..data import DLC_CHARACTERS
            targets = {h: w for h, w in targets.items() if h not in DLC_CHARACTERS}
        for hero, want in targets.items():
            if want and self.live.grant_hero(hero):
                changed.append(f"gave {hero}")
            elif not want and self.live.revoke_hero(hero):
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
            if self._rescue_task is None or self._rescue_task.done():
                self._rescue_task = asyncio.create_task(self._rescue_loop(), name="stuck rescue")
            self._items_applied = 0
            self.session.apply_checked_location_ids(set(args.get("checked_locations", [])))
            asyncio.create_task(self._push_state(), name="push state after connect")
            # This slot's own ledger and save (another seed may have been connected before in this client run).
            self.delivery = None
            self.save_path = None
            self.save_watcher = None
            self._live_seen = None
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
            self._pending_kill = data.get("source", "someone")  # applied by the live hook in the next mission tick
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
        for name in names:
            before = self.session.unlocked_by(name)
            self.session.apply_received_item_names([name])
            opened = [q for q in self.session.unlocked_by(name) if q not in before]
            shown.append(name + " -> " + ", ".join(q + BEAST.get(q, "") for q in opened) if opened else name)
            if opened:
                logger.info("%s unlocks %s (complete it in game for its reward)", name, ", ".join(opened))
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
        elif kind == "quest_completed":
            location_id = self.session.on_quest_completed(str(message.get("quest")))
        elif kind == "korok_found":
            location_id = self.session.on_korok_found(str(message.get("korok")))
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

        source = next((str(message.get(k)) for k in ("mission", "weapon", "challenge", "quest", "korok") if k in message), "")
        if location_id is None:
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
                    if self.live is None:
                        logger.info("Save shows cleared: %s", m.get("mission") or m.get("challenge"))
                    await self._on_game_message(m)
            if self.live is None and time.time() >= self._starter_check_at:
                self._starter_check_at = time.time() + 10
                self.maybe_install_starter()
            if self.live is None:
                self._deliver_to_save_file()

    def _game_running(self) -> bool:
        """Age of Calamity is booted in some Ryujinx: its window title names the game (works whatever the memory
        mode), or its memory is mapped. Saves are only ever switched when this is False."""
        if sys.platform != "win32":
            return False
        from .ryujinx import Guest, Process, game_in_window, ryujinx_pids
        if game_in_window():
            return True
        for pid in ryujinx_pids():
            try:
                proc = Process(pid)
            except OSError:
                continue
            try:
                if Guest.attach(proc):
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
                logger.info("Close Age of Calamity in Ryujinx first; the client switches the save while it is closed.")
            return
        path = self.save_path
        if not path:
            if force or self._starter_reason != "no save":
                self._starter_reason = "no save"
                logger.info("No Age of Calamity save on this Ryujinx profile yet: start the game once (New Game until "
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
        else:
            data = starter_save.prepare(sorted(self.session.unlocked_characters), self.session.available_missions())
            starter_save.install(path, save_copies(path), data, STATE_DIR / "backups")
            self.delivery.new_game(set())  # a fresh save: every received item is given again
            from .savefile import owned_weapons
            self.delivery.set_baseline(owned_weapons(data))  # weapons it starts with are no finds; Hyrule Field counts
            self.delivery.state["primed"] = False  # heroes get weapons and stats on the first live tick
            logger.info("Starter save installed (%s). Start Age of Calamity and pick Continue: the forced first mission "
                        "is skipped; play %s with your starting heroes.", why,
                        " or ".join(m for m in self.session.available_missions() if m != FIRST_MISSION)
                        or "your first mission")
        self.delivery.state.setdefault("starter", {})[path] = time.time()
        self.delivery.save_state()
        shelf.set_owner(path, me)
        self._starter_reason = None
        self.set_save_path(path)  # watch the new save from scratch

    def _show_selection(self) -> None:
        """The cursor panel: while the world-map cursor is on a mission, challenge or quest, the overlay's bottom-right
        panel lists what its checks hold, one per line (from a free scout of this slot's locations at connect; no hint
        points), cycling SELECTION_PAGE at a time when there are more. It goes away when the cursor leaves it or a
        mission is running."""
        sel = None if self.live._battle_character() else self.live.map_selection()
        now = time.monotonic()
        if sel == self._selection:
            if len(self._selection_pages) > 1 and now >= self._selection_turn:  # next page of a long list
                self._selection_page = (self._selection_page + 1) % len(self._selection_pages)
                self._selection_turn = now + SELECTION_SECONDS
                self.overlay.set_status(self._selection_pages[self._selection_page])
            return
        self._selection = sel
        self._selection_pages, self._selection_page, self._selection_turn = [], 0, now + SELECTION_SECONDS
        found = self.session.selection_checks(*sel) if sel else None
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
                lines.append(item if info.player == self.slot else f"{self.player_names.get(info.player, '?')}'s {item}")
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
        elif now - self._unreadable_since > 120 and not self._unreadable_warned:
            self._unreadable_warned = True
            logger.warning("Ryujinx is running Age of Calamity but the client can't read the game. Check: (1) Ryujinx > "
                           "Options > Settings > System > Memory Manager Mode = Software (then restart the game); "
                           "(2) the game is version 1.4.1 (Ryujinx shows it in the window title); (3) a save is "
                           "loaded (pick Continue). Built for Ryujinx 1.3.3 on Windows.")
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

        class AoCManager(ui):
            base_title = "Archipelago Age of Calamity Client"

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
