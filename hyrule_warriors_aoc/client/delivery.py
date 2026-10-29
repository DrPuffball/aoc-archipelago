"""
Give received items to the game exactly once, either live (live_hook.LiveGame) or by editing the save file
while Ryujinx is not running (SaveFileTarget).

What is applied:
  Rupee Pouch          +RUPEE_POUCH rupees
  Material Bundle      +5 each of 3 base-game materials (fixed per item, so a re-run gives the same)
  Character XP Gift    +1 level to your lowest-level unlocked hero
  Weapon XP Gift       live only: +1 level to the equipped weapon of your lowest such hero (up to the game's cap)
  Hearty Meal          cooking ingredients (Hearty Durian x5, Hyrule Herb x5)
  Extra Weapon         live only: one random base-game weapon for a hero you have (fixed per item); counted like
                       received weapons, so it never sends a weapon check
  Heroes               live only: locked/unlocked to match the seed (see hero_targets)

Consumables are counted in a small per-seed ledger (one JSON file per seed and slot), so each one is applied
exactly once even across restarts, reconnects and switching between live and save-file delivery.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from pathlib import Path
from typing import Protocol

from ..data import WEAPON_BY_NAME, WEAPONS
from ..data_save import WEAPON_KINDS
from ..items import WEAPON_PREFIX
from .savefile import SavePatch

RUPEE_POUCH = 1000
CONSUMABLES = ("Rupee Pouch", "Material Bundle", "Character XP Gift", "Extra Weapon", "Weapon XP Gift", "Hearty Meal")
STATE_DIR = Path.home() / "AoC_Archipelago"
BACKUPS_KEPT = 20


class Target(Protocol):
    def add_rupees(self, amount: int) -> str: ...
    def material_bundle(self, seed: int) -> str: ...
    def level_up(self, characters: list[str]) -> str: ...
    def hearty_meal(self) -> str: ...


class SaveFileTarget:
    """Edits the save file (all of Ryujinx's copies) in one go; only use while the game is not running."""

    def __init__(self, path: str, copies: list[str]) -> None:
        self.path = path
        self.copies = copies
        with open(path, "rb") as f:
            self.original = f.read()
        self.patch = SavePatch(self.original)

    def add_rupees(self, amount: int) -> str:
        return self.patch.add_rupees(amount)

    def material_bundle(self, seed: int) -> str:
        return self.patch.material_bundle(seed=seed)

    def level_up(self, characters: list[str]) -> str:
        return self.patch.level_up(characters)

    def hearty_meal(self) -> str:
        return self.patch.hearty_meal()

    def unlock_hero(self, character: str) -> str | None:
        return self.patch.unlock_hero(character)

    def commit(self) -> None:
        if bytes(self.patch.data) == self.original:
            return
        folder = STATE_DIR / "backups"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"svdt_{time.strftime('%Y%m%d_%H%M%S')}").write_bytes(self.original)
        for p in sorted(folder.glob("svdt_*"))[:-BACKUPS_KEPT]:
            p.unlink(missing_ok=True)
        for path in self.copies:
            tmp = path + ".aptmp"
            with open(tmp, "wb") as f:
                f.write(self.patch.data)
            os.replace(tmp, path)


class Delivery:
    def __init__(self, seed: str, slot: str) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w.-]+", "_", f"{seed}_{slot}")
        self.state_file = STATE_DIR / f"{safe}.json"
        self.state = {"applied": 0, "baseline": None, "log": []}
        if self.state_file.is_file():
            try:
                self.state.update(json.loads(self.state_file.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass

    def save_state(self) -> None:
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1), encoding="utf-8")
        os.replace(tmp, self.state_file)

    def note(self, lines: list[str]) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.state["log"] = (self.state["log"] + [f"{stamp} {d}" for d in lines])[-200:]

    # --- baseline: clears that were in the game before this seed started ---------------------

    def baseline(self, cleared: set[str]) -> set[str]:
        if self.state["baseline"] is None:
            self.state["baseline"] = sorted(cleared)
            self.save_state()
        return set(self.state["baseline"])

    def set_baseline(self, names: set[str]) -> None:
        self.state["baseline"] = sorted(names)
        self.save_state()

    def add_progress(self, names: set[str]) -> None:
        """Remember what the game showed cleared under this seed, so a later New Game can be recognised."""
        progress = set(self.state.get("progress", ())) | names
        if progress != set(self.state.get("progress", ())):
            self.state["progress"] = sorted(progress)
            self.save_state()

    def new_game(self, cleared: set[str]) -> None:
        """The game was reset: keep only what is still cleared, and give every received item again."""
        self.state["baseline"] = sorted(set(self.state["baseline"] or ()) & cleared)
        self.state["progress"] = sorted(set(self.state.get("progress", ())) & cleared)
        self.state["applied"] = 0
        self.state["weapons_given"] = {}
        self.state["caught_up"] = []
        self.note(["New Game: received items will be given again"])
        self.save_state()

    # --- consumables ------------------------------------------------------------------------

    def pending(self, items: list[str]) -> list[str]:
        return [n for n in items[self.state["applied"]:] if n in CONSUMABLES]

    def apply(self, items: list[str], heroes: set[str], target: Target) -> list[str]:
        """Apply every consumable received since last time. Returns what was done."""
        new = items[self.state["applied"]:]
        done: list[str] = []
        end = len(items)
        for k, name in enumerate(new, start=self.state["applied"]):
            if (name.startswith(WEAPON_PREFIX) or name in ("Extra Weapon", "Weapon XP Gift")) and not hasattr(target, "give_weapon"):
                end = k  # weapons go in only through the live hook: wait here until the game is running
                break
            if name == "Rupee Pouch":
                done.append(f"Rupee Pouch: {target.add_rupees(RUPEE_POUCH)}")
            elif name == "Material Bundle":
                done.append(f"Material Bundle: {target.material_bundle(seed=k)}")
            elif name == "Character XP Gift":
                done.append(f"Character XP Gift: {target.level_up(sorted(heroes))}")
            elif name == "Weapon XP Gift":
                done.append(f"Weapon XP Gift: {target.weapon_level_up(sorted(heroes))}")
            elif name == "Hearty Meal":
                done.append(target.hearty_meal())  # (says "Hearty Meal: ..." itself)
            elif name.startswith(WEAPON_PREFIX) or name == "Extra Weapon":
                weapon = name[len(WEAPON_PREFIX):] if name != "Extra Weapon" else extra_weapon(heroes, k)
                if weapon is None:
                    done.append("Extra Weapon: no hero to give it to")
                    continue
                given = target.give_weapon(weapon, WEAPON_BY_NAME[weapon].character)
                done.append(f"Extra Weapon: {given}" if name == "Extra Weapon" else given)
                given = self.state.setdefault("weapons_given", {})
                given[weapon] = given.get(weapon, 0) + 1
        if end > self.state["applied"]:
            self.state["applied"] = end
            self.note(done)
            self.save_state()
        return done


def extra_weapon(heroes: set[str], seed: int) -> str | None:
    """The weapon an Extra Weapon item gives: a base-game weapon of one of your heroes, the same for the same item."""
    choices = sorted(w.name for w in WEAPONS if not w.dlc and w.character in heroes and w.name in WEAPON_KINDS)
    return random.Random(seed).choice(choices) if choices else None


def hero_targets(received: set[str], available_missions: list[str], forced: dict[str, tuple[str, ...]],
                 all_heroes: list[str]) -> dict[str, bool]:
    """Which heroes should be unlocked in game: those received, plus any a playable story mission forces."""
    allowed = set(received)
    for mission in available_missions:
        allowed.update(forced.get(mission, ()))
    return {h: h in allowed for h in all_heroes}
