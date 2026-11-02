from __future__ import annotations

from .data_challenges import DLC_STORY_MISSIONS
from typing import TYPE_CHECKING

from BaseClasses import Location

from .data import GAME_NAME, LOCATION_ID_BASE, MISSIONS, WEAPONS
from .data_challenges import CHALLENGES
from .data_koroks import KOROKS_IN_CHALLENGES, KOROKS_IN_MISSIONS, korok_location
from .data_quests import QUESTS

if TYPE_CHECKING:
    from .world import AgeOfCalamityWorld


class AgeOfCalamityLocation(Location):
    game = GAME_NAME


def mission_location(name: str) -> str:
    return f"Clear: {name}"


BONUS_PER_MISSION = 50  # extra checks a story clear can hold when the items outnumber the checks


def bonus_location(mission: str, index: int) -> str:
    return f"Clear: {mission} (Bonus {index})"


BONUS_PER_CHALLENGE = 5  # 0.9.63: extra checks spread over challenge clears too (user: one clear sent too many)


def challenge_bonus_location(challenge: str, index: int) -> str:
    return f"Challenge: {challenge} (Bonus {index})"


DIFFICULTY_NAMES = ("Normal", "Hard", "Very Hard")  # the game's difficulty slots 1-3 (Easy = the plain check)


def difficulty_location(base: str, level: int) -> str:
    """The check for clearing a mission/challenge (base: its location name) on difficulty `level` (1 Normal .. 3)."""
    return f"{base} ({DIFFICULTY_NAMES[level - 1]})"


def weapon_location(name: str) -> str:
    return f"Obtain: {name}"


def quest_location(name: str) -> str:
    return f"Quest: {name}"


def challenge_location(name: str) -> str:
    return f"Challenge: {name}"


# Korok seeds as (source, kind, index); kind "mission" or "challenge".
KOROKS: list[tuple[str, str, int]] = [
    (src, "mission", i + 1) for src, n in KOROKS_IN_MISSIONS.items() for i in range(n)
] + [(src, "challenge", i + 1) for src, n in KOROKS_IN_CHALLENGES.items() for i in range(n)]

# Reserved, append-only ID ranges (see data.py). Never reorder an existing table.
_RANGES = {
    "mission": (0, [mission_location(m.name) for m in MISSIONS]),
    "quest": (100, [quest_location(q.name) for q in QUESTS]),
    "challenge": (700, [challenge_location(c.name) for c in CHALLENGES]),
    "korok": (1000, [korok_location(s, i) for s, _, i in KOROKS]),
    "weapon": (1200, [weapon_location(w.name) for w in WEAPONS]),
    "bonus": (1400, [bonus_location(m.name, k) for m in MISSIONS for k in range(1, 21)]),
    "bonus2": (1800, [bonus_location(m.name, k) for m in MISSIONS for k in range(21, BONUS_PER_MISSION + 1)]),
    "challenge_bonus": (2400, [challenge_bonus_location(c.name, k) for c in CHALLENGES
                               for k in range(1, BONUS_PER_CHALLENGE + 1)]),
    "difficulty": (3500, [difficulty_location(base, level) for base in [mission_location(m.name) for m in MISSIONS]
                          + [challenge_location(c.name) for c in CHALLENGES] for level in (1, 2, 3)]),
    # 0.9.74: the DLC story missions are story missions, so they hold as many bonus checks as one (6..50)
    "dlc_story_bonus": (5000, [challenge_bonus_location(c, k) for c in DLC_STORY_MISSIONS
                               for k in range(BONUS_PER_CHALLENGE + 1, BONUS_PER_MISSION + 1)]),
}
LOCATION_NAME_TO_ID: dict[str, int] = {}
for _start, _names in _RANGES.values():
    assert len(_names) <= {0: 100, 100: 600, 700: 300, 1000: 200, 1200: 200, 1400: 400, 1800: 600, 2400: 1100, 3500: 1500,
                       5000: 400}[_start],         _start
    for _i, _name in enumerate(_names):
        assert _name not in LOCATION_NAME_TO_ID, _name
        LOCATION_NAME_TO_ID[_name] = LOCATION_ID_BASE + _start + _i


def create_location(world: AgeOfCalamityWorld, region, name: str) -> AgeOfCalamityLocation:
    location = AgeOfCalamityLocation(world.player, name, LOCATION_NAME_TO_ID[name], region)
    region.locations.append(location)
    return location


def korok_name(source: str, index: int) -> str:
    return korok_location(source, index)
