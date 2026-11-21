"""Progress checks in the client (0.9.90, data_progress): hero levels, weapon levels, and totals gathered.

Totals: the game only keeps what you hold now (spending lowers it), so the client keeps its own running totals per
material in the seed's ledger: every rise of a count adds to the total, drops are ignored, and a rise right after the
client itself wrote materials (Material Bundle and other deliveries: LiveGame.material_writes) is not counted. Totals
start at zero when the seed first connects (what you already held never counts)."""

from __future__ import annotations

import re

from .. import data_progress as P

_LEVEL = re.compile(r"^(?:Hero|Weapon) Level: (.+) Lv (\d+)$")
_TIER = re.compile(r"^(?:Gathered|Defeated): (.+) \((\d)\)$")


class GatherTally:
    """Running totals per material index, kept in a dict that lives in the seed's ledger (delivery.state)."""

    def __init__(self, state: dict) -> None:
        self.state = state.setdefault("gathered", {"totals": {}, "last": None, "writes": None})

    @property
    def totals(self) -> dict[str, int]:
        return self.state["totals"]

    def update(self, counts: list[int], client_writes: int) -> bool:
        """Takes the game's counts now; returns True when a total rose (the ledger should be saved)."""
        last, changed = self.state.get("last"), False
        if last is not None and len(last) == len(counts) and self.state.get("writes") == client_writes:
            for i, (old, new) in enumerate(zip(last, counts)):
                if new > old:
                    self.totals[str(i)] = self.totals.get(str(i), 0) + new - old
                    changed = True
        self.state["last"], self.state["writes"] = list(counts), client_writes  # (a client write: new baseline)
        return changed

    def total(self, index: int) -> int:
        return self.totals.get(str(index), 0)


def material_index(name: str) -> int | None:
    """Material index of a "Gathered: X (n)" / "Defeated: X (n)" location (the enemy's trophy for Defeated)."""
    m = _TIER.match(name)
    if not m:
        return None
    what = m.group(1)
    if name.startswith("Defeated: "):
        return P.ENEMIES[what][0] if what in P.ENEMIES else None
    return P.MATERIALS[what][0] if what in P.MATERIALS else None


def reached(ids: dict[str, dict[str, int]], counts: dict[str, int], hero_levels: dict[str, int],
            weapon_levels: dict[str, int], tally: GatherTally | None) -> set[str]:
    """Progress check names reached now (ids: session.ids; counts: slot_data gather_counts)."""
    out = set()
    for kind, levels in (("hero_level", hero_levels), ("weapon_level", weapon_levels)):
        for name in ids.get(kind, {}):
            m = _LEVEL.match(name)
            if m and levels.get(m.group(1), 0) >= int(m.group(2)):
                out.add(name)
    if tally is not None:
        for kind in ("gathered", "defeated"):
            for name in ids.get(kind, {}):
                index = material_index(name)
                if index is not None and name in counts and tally.total(index) >= counts[name]:
                    out.add(name)
    return out


def summary(ids: dict[str, dict[str, int]], counts: dict[str, int], tally: GatherTally | None) -> list[str]:
    """/gathered: each material or enemy with checks, its total and the next count it needs."""
    nxt: dict[str, tuple[int, int]] = {}
    for kind in ("defeated", "gathered"):
        for name in ids.get(kind, {}):
            index = material_index(name)
            if index is None or name not in counts:
                continue
            total = tally.total(index) if tally else 0
            label = name.split(": ", 1)[1].rsplit(" (", 1)[0]
            if name.startswith("Defeated: "):
                label = f"{label} (defeated)"
            need = counts[name]
            best = nxt.get(label)
            if total < need and (best is None or need < best[1]):
                nxt[label] = (total, need)
            elif best is None:
                nxt.setdefault(label, (total, 0))
    lines = [f"{label}: {total}" + (f" / next check at {need}" if need else " (all checks reached)")
             for label, (total, need) in sorted(nxt.items())]
    return lines or ["No material or enemy checks in this seed."]
