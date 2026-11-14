"""
Give received items to the game exactly once, either live (live_hook.LiveGame) or by editing the save file
while Ryujinx is not running (SaveFileTarget).

What is applied:
  Rupee Pouch          +RUPEE_POUCH rupees
  Material Bundles     Small 10 each of 3, Material Bundle 15 each of 5, Large 25 each of 8 base-game materials
                       (data.MATERIAL_BUNDLES; fixed per item, so a re-run gives the same)
  Character XP Gift    +1 level to your lowest-level unlocked hero
  Hearty Meal          cooking ingredients (Hearty Durian x5, Hyrule Herb x5)
  Extra Weapon         live only: random base-game weapons for heroes you have (fixed per item), counted like
  Weapon Bundles       received weapons so they never send a weapon check: Extra Weapon 1, Weapon Bundle 3, Large
                       Weapon Bundle 5, each for a different hero where possible (data.WEAPON_BUNDLES). Weapon XP Gift
                       (older seeds) gives 1 too: a written weapon level doesn't last (the game recomputes it from XP)
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

from ..data import MATERIAL_BUNDLES, WEAPON_BUNDLES, WEAPON_BY_NAME, WEAPONS
from ..data_rewards import MASTER_CHEF_ITEM, MASTER_CHEF_RUPEES, RESEARCH_AMOUNT, RESEARCH_BY_ITEM, RESEARCH_REWARDS
from ..data_save import WEAPON_KINDS
from ..items import WEAPON_PREFIX
from .savefile import SavePatch

RUPEE_POUCH = 1000
CONSUMABLES = ("Rupee Pouch", "Material Bundle", "Character XP Gift", "Extra Weapon", "Weapon XP Gift", "Hearty Meal",
               "Small Material Bundle", "Large Material Bundle", "Weapon Bundle", "Large Weapon Bundle")
STATE_DIR = Path.home() / "AoC_Archipelago"
BACKUPS_KEPT = 20


class Target(Protocol):
    def add_rupees(self, amount: int) -> str: ...
    def material_bundle(self, seed: int, kinds: int, amount: int) -> str: ...
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

    def material_bundle(self, seed: int, kinds: int = 5, amount: int = 15) -> str:
        return self.patch.material_bundle(seed=seed, kinds=kinds, amount=amount)

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
        self.skip_dlc = False  # DLC failsafe (the game has no Expansion Pass): DLC heroes' weapons are not written
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
        return [n for n in items[self.state["applied"]:] if n in CONSUMABLES or n in RESEARCH_BY_ITEM or n == MASTER_CHEF_ITEM]

    def apply(self, items: list[str], heroes: set[str], target: Target) -> list[str]:
        """Apply every consumable received since last time. Returns what was done."""
        new = items[self.state["applied"]:]
        done: list[str] = []
        end = len(items)
        for k, name in enumerate(new, start=self.state["applied"]):
            if (name.startswith(WEAPON_PREFIX) or name in WEAPON_BUNDLES or name in RESEARCH_BY_ITEM) \
                    and not hasattr(target, "give_weapon"):
                end = k  # weapons go in only through the live hook: wait here until the game is running
                break
            if name in RESEARCH_BY_ITEM:
                material, outfit = RESEARCH_REWARDS[RESEARCH_BY_ITEM[name]]
                done.append(f"{name}: {target.give_research(material, RESEARCH_AMOUNT, outfit)}")
            elif name == MASTER_CHEF_ITEM:  # 0.9.87: The Master Chef's 1000 rupees (its trade pays nothing)
                done.append(f"{name}: {target.add_rupees(MASTER_CHEF_RUPEES)}")
            elif name == "Rupee Pouch":
                done.append(f"Rupee Pouch: {target.add_rupees(RUPEE_POUCH)}")
            elif name in MATERIAL_BUNDLES:
                kinds, amount = MATERIAL_BUNDLES[name]
                done.append(f"{name}: {target.material_bundle(seed=k, kinds=kinds, amount=amount)}")
            elif name == "Character XP Gift":
                done.append(f"Character XP Gift: {target.level_up(sorted(heroes))}")
            elif name == "Hearty Meal":
                done.append(target.hearty_meal())  # (says "Hearty Meal: ..." itself)
            elif name.startswith(WEAPON_PREFIX) or name in WEAPON_BUNDLES:
                weapons = [name[len(WEAPON_PREFIX):]] if name not in WEAPON_BUNDLES else extra_weapons(heroes, k, WEAPON_BUNDLES[name])
                if not weapons:
                    done.append(f"{name}: no hero to give it to")
                    continue
                results = []
                if self.skip_dlc:
                    from ..data import DLC_CHARACTERS
                    if any(WEAPON_BY_NAME[w].character in DLC_CHARACTERS or WEAPON_BY_NAME[w].dlc for w in weapons):
                        done.append(f"{name}: skipped (no Expansion Pass in the game)")
                        weapons = [w for w in weapons
                                   if WEAPON_BY_NAME[w].character not in DLC_CHARACTERS and not WEAPON_BY_NAME[w].dlc]
                for weapon in weapons:
                    results.append(target.give_weapon(weapon, WEAPON_BY_NAME[weapon].character))
                    given = self.state.setdefault("weapons_given", {})
                    given[weapon] = given.get(weapon, 0) + 1
                if results:
                    done.append(f"{name}: {', '.join(results)}" if name in WEAPON_BUNDLES else results[0])
        if end > self.state["applied"]:
            self.state["applied"] = end
            self.note(done)
            self.save_state()
        return done


def extra_weapon(heroes: set[str], seed: int) -> str | None:
    """The weapon an Extra Weapon item gives: a base-game weapon of one of your heroes, the same for the same item."""
    choices = sorted(w.name for w in WEAPONS if not w.dlc and w.character in heroes and w.name in WEAPON_KINDS)
    return random.Random(seed).choice(choices) if choices else None


def extra_weapons(heroes: set[str], seed: int, count: int) -> list[str]:
    """A weapon filler's weapons: the first is extra_weapon's (so an Extra Weapon item gives what it always gave), the
    rest each for a hero not yet in the bundle while there is one."""
    first = extra_weapon(heroes, seed)
    if first is None:
        return []
    out = [first]
    rng = random.Random(seed * 31 + count)
    for _ in range(count - 1):
        used = {WEAPON_BY_NAME[w].character for w in out}
        fresh = {h for h in heroes if h not in used}
        out.append(extra_weapon(fresh, rng.randrange(1 << 30)) or extra_weapon(heroes, rng.randrange(1 << 30)))
    return out


def hero_targets(received: set[str], available_missions: list[str], forced: dict[str, tuple[str, ...]],
                 all_heroes: list[str]) -> dict[str, bool]:
    """Which heroes should be unlocked in game: those received, plus any a playable story mission forces."""
    allowed = set(received)
    for mission in available_missions:
        allowed.update(forced.get(mission, ()))
    return {h: h in allowed for h in all_heroes}
