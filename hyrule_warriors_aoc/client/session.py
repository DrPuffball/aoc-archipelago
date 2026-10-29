"""
Pure game-state logic for the Age of Calamity client. No Archipelago or networking imports, so
it can be unit-tested on its own.

A Session is built from the slot_data the generator sent, then fed:
  * items the multiworld has granted           -> apply_received_item_names()
  * locations the server already considers checked -> apply_checked_location_ids()
  * things the player did in game               -> on_mission_cleared() / on_weapon_obtained()
and answers: what is unlocked, which missions may be entered, which location ids to report, and
whether the goal is complete.
"""

from __future__ import annotations

import struct
from typing import Any

UPGRADE_NAMES = {
    "Heart Container", "Combo Upgrade", "Special Gauge Upgrade", "Enhanced Ability",
    "Progressive Weapon Capacity", "Progressive Seal Slot", "Weapon Fusion",
}



def _reward_items() -> set[str]:
    from ..data_rewards import REWARD_BY_ITEM
    return set(REWARD_BY_ITEM)  # (Weapon Fusion and Progressive Seal Slot are in UPGRADE_NAMES)


CHARACTER_PREFIX = "Character: "
WEAPON_PREFIX = "Weapon: "
RUNE_PREFIX = "Rune: "
UNLOCK_PREFIX = "Unlock: "

# Location kinds the game can report, with the slot_data key holding their name -> id map.
LOCATION_KINDS = {
    "mission": "mission_ids",
    "weapon": "weapon_ids",
    "challenge": "challenge_ids",
    "quest": "quest_ids",
    "korok": "korok_ids",
}


NOTICE_MAX = 44  # characters; the game's message boxes are small


def game_text(text: str, limit: int = NOTICE_MAX) -> str:
    """Plain, short text the game's font can draw: ASCII only, no control characters, trimmed with '...'."""
    table = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u2026": "..."}
    out = "".join(table.get(c, c) for c in text)
    out = "".join(c if 32 <= ord(c) < 127 else "?" for c in out).strip()
    return out if len(out) <= limit else out[: limit - 3].rstrip() + "..."


def make_notice(kind: str, **fields: str) -> dict[str, Any]:
    """
    A structured on-screen message for the hook. `text` is a ready one-liner; the parts (item, player, location) let
    the hook lay it out in the game's own style. kind: received | sent | hint | goal | info | death.
    """
    # long enough for reward names with their quests in brackets (shown by the overlay over Ryujinx)
    item, player = game_text(fields.get("item", ""), 130), game_text(fields.get("player", ""), 20)
    me = game_text(fields.get("me", ""), 20) or "you"
    templates = {  # who sent it and who gets it, every time (user request)
        "received": "{player} sent {item} to {me}" if player else "{me} found {item}",
        "sent": "{me} sent {item} to {player}",
        "hint": "Hint: {item} is at {location}",
        "goal": "{text}",
        "info": "{text}",
        "death": "{text}",
    }
    text = templates.get(kind, "{text}").format(
        item=item, player=player, me=me, location=game_text(fields.get("location", ""), 30),
        text=game_text(fields.get("text", "")),
    )
    return {"type": "notice", "kind": kind, "text": game_text(text, 170), "item": item, "player": player}


def batch_notices(notices: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    """Avoid flooding the screen: past `limit` notices of one kind arriving together, show a single summary."""
    out: list[dict[str, Any]] = []
    for kind in dict.fromkeys(n["kind"] for n in notices):
        group = [n for n in notices if n["kind"] == kind]
        if len(group) <= limit:
            out += group
        else:
            word = {"received": "Received", "sent": "Sent"}.get(kind, "")
            out.append(make_notice("info", text=f"{word} {len(group)} items".strip()) | {"kind": kind})
    return out


def title_info(connected: bool, slot: str = "", seed: str = "", server: str = "", world_version: str = "",
               checked: int = 0, total: int = 0, goal_complete: bool = False) -> dict[str, Any]:
    """What the title screen should show: who you are in the multiworld and whether it is connected."""
    status = "Connected" if connected else "Not connected"
    lines = [f"Archipelago: {status}"]
    if connected:
        lines += [f"Slot: {game_text(slot, 24)}", f"Seed: {game_text(seed, 24)}", f"Checks: {checked}/{total}"]
        if goal_complete:
            lines.append("Goal complete!")
    return {
        "type": "title_info", "connected": connected, "slot": slot, "seed": seed, "server": server,
        "world_version": world_version, "checks": checked, "total_checks": total,
        "goal_complete": goal_complete, "lines": lines,
    }


class Session:
    def __init__(self, slot_data: dict[str, Any]) -> None:
        self.ids: dict[str, dict[str, int]] = {
            kind: dict(slot_data.get(key, {})) for kind, key in LOCATION_KINDS.items()
        }
        self.mission_ids = self.ids["mission"]
        self.weapon_ids = self.ids["weapon"]
        # slot (vanilla mission position) -> mission placed there; slot -> prerequisite slots
        self.mission_slots: dict[str, str] = dict(slot_data["mission_slots"])
        self.slot_prerequisites: dict[str, list[str]] = {
            k: list(v) for k, v in slot_data["mission_slot_prerequisites"].items()
        }
        self._slot_of = {mission: slot for slot, mission in self.mission_slots.items()}
        self.side_required: dict[str, int] = dict(slot_data.get("side_missions_required", {}))
        self.side_done: set[str] = set()
        self.party_required: dict[str, list[str]] = {
            k: list(v) for k, v in slot_data.get("mission_party_required", {}).items()
        }
        self.all_characters: list[str] = list(slot_data.get("all_characters", []))
        self.party_any: dict[str, list[str]] = {k: list(v) for k, v in slot_data.get("mission_party_any", {}).items()}
        self.opened_by_clear: dict[str, str] = dict(slot_data.get("opened_by_clear", {}))
        self.opened_by_heroes: dict[str, list[str]] = {k: list(v) for k, v in slot_data.get("opened_by_heroes", {}).items()}
        # include_dlc off: the Expansion Pass stays vanilla (its challenges and heroes are never touched).
        self.include_dlc = bool(slot_data.get("include_dlc", 1))
        self.goal = slot_data.get("goal", 0)
        self.boss_rush: list[str] = list(slot_data.get("boss_rush", []))
        self.challenges_done: set[str] = set()
        self.hint_every = int(slot_data.get("hint_every_missions", 0))
        self.world_version = str(slot_data.get("world_version", "unknown"))
        self.stuck_minutes = int(slot_data.get("stuck_rescue_minutes", 0))
        self.last_activity: float | None = None
        self.rescue_sent = False
        self.hints_given = 0
        self.featured_challenge = slot_data.get("featured_challenge")
        self.goal_side_missions = int(slot_data.get("goal_side_missions", 0))
        self.goal_story_missions = int(slot_data.get("goal_story_missions", 20))
        self.goal_challenges = int(slot_data.get("goal_challenges", 0))
        self.post_story_unlock = int(slot_data.get("post_story_unlock", 20))
        self.post_story_quests: list[str] = list(slot_data.get("post_story_quests", []))
        self.goal_challenge_pool: set[str] = set(slot_data.get("goal_challenge_pool", []))
        # side_unlocks random (0.9.53+): challenge/quest -> completions (story clears, challenges, quests) it opens after
        self.challenge_open_at: dict[str, int] = dict(slot_data.get("challenge_open_at", {}))
        self.quest_open_at: dict[str, int] = dict(slot_data.get("quest_open_at", {}))
        self.side_random = int(slot_data.get("side_unlocks", 1)) == 0 and bool(self.challenge_open_at or self.quest_open_at)
        self.completion_names: set[str] = set(slot_data.get("completion_challenges", [])) |             set(slot_data.get("completion_quests", []))
        self.game_done: set[str] = set()  # missions, challenges and quests the game shows done (client, live)
        self.cleared_any: set[str] = set()  # every mission/challenge the game shows cleared (client, any difficulty)
        self.goal_difficulty = int(slot_data.get("goal_difficulty", 0))  # 0 any, 1 Easy .. 4 Very Hard, 5 Apocalyptic
        self.difficulty_cleared: set[str] = set()  # missions/challenges cleared on goal_difficulty or higher (client)
        self.final_mission: str = slot_data["final_mission"]
        # 0.9.54+: the seed may start on any mission; the client installs a starter save that skips the forced one
        self.starter_save = bool(slot_data.get("starter_save", False))
        self.first_mission: str = slot_data.get("first_mission", "The Battle of Hyrule Field")
        self.locked_features: list[str] = list(slot_data.get("locked_features", []))
        self.min_level = int(slot_data.get("minimum_character_level", 1))
        self.pace: dict = dict(slot_data.get("pace", {}))
        self.death_link = bool(slot_data.get("death_link", False))
        # story_party 0 = free: any party plays any story mission (the hook replaces the forced parties)
        self.story_party_free = int(slot_data.get("story_party", 0)) == 0
        self.combo_copies = int(slot_data.get("combo_upgrades", 0))
        # Copies of each upgrade item the seed has (seeds before 0.9.23 lack it: the option defaults then).
        self.upgrade_copies: dict[str, int] = {"Heart Container": 1, "Special Gauge Upgrade": 1,
                                               **slot_data.get("upgrade_copies", {})}
        self.challenge_by_level = int(slot_data.get("challenge_logic", 0)) == 1
        # Seeds before 0.9.19 have no sheikah_runes: runes stay vanilla there.
        self.runes_shuffled = int(slot_data.get("sheikah_runes", 0)) == 1
        self.runes_all = int(slot_data.get("sheikah_runes", 0)) == 2  # start_with_all
        self.runes: set[str] = set()
        self.rune_items: list[str] = list(slot_data.get("rune_items", []))  # 0.9.58+ (see rune_flags)
        self.unlock_items = int(slot_data.get("mission_unlocks", 0)) == 1  # story missions open by unlock items
        self.mission_unlocks: set[str] = set()
        self.mission_rewards: dict = dict(slot_data.get("mission_rewards", {"mode": 0}))
        # Quest reward items: group item -> copies in the seed (absent = that reward stays vanilla).
        from ..data_rewards import canonical
        self.reward_copies: dict[str, int] = {canonical(k): int(v)  # rooms from before the rename use old names
                                              for k, v in slot_data.get("quest_reward_items", {}).items()}

        self.starting_characters: list[str] = list(slot_data["starting_characters"])
        self.unlocked_characters: set[str] = set(self.starting_characters)
        self.unlocked_weapons: set[str] = set()
        self.upgrades: dict[str, int] = {}
        self.features: set[str] = set()
        self.cleared_missions: set[str] = set()
        self.done: dict[str, set[str]] = {kind: set() for kind in LOCATION_KINDS}
        self.done["mission"] = self.cleared_missions
        self.obtained_weapons = self.done["weapon"]

        self._by_id = {i: (kind, name) for kind, ids in self.ids.items() for name, i in ids.items()}
        self.mission_bonus_ids: dict[str, list[int]] = {
            m: list(v) for m, v in slot_data.get("mission_bonus_ids", {}).items()}
        self.mission_bonus_ids.update({c: list(v) for c, v in slot_data.get("challenge_bonus_ids", {}).items()})

    # --- inputs from the multiworld ------------------------------------------------------

    def apply_received_item_names(self, names: list[str]) -> bool:
        """Apply granted items. Returns True if anything about the unlocked state changed."""
        from ..data_rewards import canonical
        changed = False
        for name in map(canonical, names):  # rooms from before the reward rename send the old names
            if name.startswith(CHARACTER_PREFIX):
                character = name[len(CHARACTER_PREFIX):]
                if character not in self.unlocked_characters:
                    self.unlocked_characters.add(character)
                    changed = True
            elif name.startswith(WEAPON_PREFIX):
                weapon = name[len(WEAPON_PREFIX):]
                if weapon not in self.unlocked_weapons:
                    self.unlocked_weapons.add(weapon)
                    changed = True
            elif name.startswith(RUNE_PREFIX):
                if name[len(RUNE_PREFIX):] not in self.runes:
                    self.runes.add(name[len(RUNE_PREFIX):])
                    changed = True
            elif name.startswith(UNLOCK_PREFIX):
                if name[len(UNLOCK_PREFIX):] not in self.mission_unlocks:
                    self.mission_unlocks.add(name[len(UNLOCK_PREFIX):])
                    changed = True
            elif name.startswith("Feature: "):
                self.features.add(name[len("Feature: "):])
                changed = True
            elif name in UPGRADE_NAMES or name.partition(": ")[0] in UPGRADE_NAMES or name in _reward_items():
                self.upgrades[name] = self.upgrades.get(name, 0) + 1
                changed = True
            # Anything else is filler; the game side decides what it grants.
        return changed

    def apply_checked_location_ids(self, ids: set[int]) -> bool:
        """Mark locations the server already knows about (e.g. after a reconnect or a release)."""
        changed = False
        for location_id in ids:
            found = self._by_id.get(location_id)
            if found and found[0] in ("challenge", "quest"):
                self.side_done.add(f"{found[0]}:{found[1]}")
                if found[0] == "challenge":
                    self.challenges_done.add(found[1])
            if found and found[1] not in self.done[found[0]]:
                self.done[found[0]].add(found[1])
                changed = True
        return changed

    # --- inputs from the game ------------------------------------------------------------

    def _report(self, kind: str, name: str) -> int | None:
        """Returns the location id to report, or None if unknown / already reported."""
        if name not in self.ids[kind] or name in self.done[kind]:
            return None
        self.done[kind].add(name)
        return self.ids[kind][name]

    def on_mission_cleared(self, mission: str) -> int | None:
        return self._report("mission", mission)

    def bonus_ids(self, mission: str) -> set[int]:
        """Extra checks sent together with this story or challenge clear."""
        return set(self.mission_bonus_ids.get(mission, ()))

    def on_weapon_obtained(self, weapon: str) -> int | None:
        return self._report("weapon", weapon)

    def on_challenge_cleared(self, challenge: str) -> int | None:
        self.side_done.add(f"challenge:{challenge}")
        self.challenges_done.add(challenge)
        return self._report("challenge", challenge)

    def on_quest_completed(self, quest: str) -> int | None:
        self.side_done.add(f"quest:{quest}")
        return self._report("quest", quest)

    def on_korok_found(self, korok: str) -> int | None:
        return self._report("korok", korok)

    # --- derived state -------------------------------------------------------------------

    def mission_available(self, mission: str) -> bool:
        slot = self._slot_of.get(mission)
        if slot is None:
            return False
        party_any = self.party_any.get(mission)  # free parties: one hero besides its support heroes
        if party_any and not any(c in self.unlocked_characters for c in party_any):
            return False
        if mission in self.opened_by_clear:  # the rescues: open with Calamity Strikes' clear
            return self.opened_by_clear[mission] in self.cleared_missions
        if mission in self.opened_by_heroes:  # Calamity Strikes: all four Champions yours (no unlock item)
            if not all(c in self.unlocked_characters for c in self.opened_by_heroes[mission]):
                return False
            if self.unlock_items:
                return True
        if self.unlock_items:  # opened by its unlock item alone; the first slot is open from the start
            if slot != next(iter(self.mission_slots)) and mission not in self.mission_unlocks:
                return False
            return all(c in self.unlocked_characters for c in self.party_required.get(mission, []))
        if len(self.side_done) < self.side_required.get(slot, 0):
            return False
        if any(c not in self.unlocked_characters for c in self.party_required.get(mission, [])):
            return False
        return all(self.mission_slots[p] in self.cleared_missions for p in self.slot_prerequisites[slot])

    def combo_levels(self) -> dict[int, int]:
        """Upgrade category -> combo level the hero has earned from received Combo Upgrade items (every category of a
        hero rises together; each item is worth its share of the category's levels). Empty when combos are vanilla."""
        from ..data_save import QUEST_UPGRADE_CATEGORY, UPGRADE_CATEGORY_HERO
        if not self.combo_copies:
            return {}
        top: dict[int, int] = {}
        for category in QUEST_UPGRADE_CATEGORY.values():
            top[category] = top.get(category, 0) + 1
        levels = {}
        for category, hero in UPGRADE_CATEGORY_HERO.items():
            got = min(self.upgrades.get(f"Combo Upgrade: {hero}", 0), self.combo_copies)
            levels[category] = -(-got * top.get(category, 0) // self.combo_copies)
        return levels

    def hero_bonus(self, family: str, extra: int = 0) -> dict[int, int]:
        """Hero slot -> how many of this per-hero reward (bonus hearts, extra special gauges) the game should show: each
        received item gives its share of what the vanilla quests give (hearts 3, gauges 2), so all copies = vanilla.
        Empty when the seed has none (rewards stay vanilla); DLC heroes are left out when the Expansion Pass is vanilla."""
        from ..data import DLC_CHARACTERS
        from ..data_save import HERO_BONUS_MAX, HERO_SLOTS
        copies = int(self.upgrade_copies.get(family, 0))
        if not copies:
            return {}
        top = HERO_BONUS_MAX[family]
        return {slot: extra + -(-min(self.upgrades.get(f"{family}: {hero}", 0), copies) * top // copies)
                for hero, slot in HERO_SLOTS.items() if self.include_dlc or hero not in DLC_CHARACTERS}

    def profile_rewards(self) -> dict[int, int]:
        """Profile offset -> value for rewards that follow received items: enhanced-ability flags (each Enhanced
        Ability: <hero> unlocks its share of that hero's abilities) and the weapon capacity level. Empty parts stay
        vanilla (the seed has no such items)."""
        from ..data import DLC_CHARACTERS
        from ..data_save import ABILITY_CATEGORIES, ABILITY_CATEGORIES_DLC, ABILITY_FLAGS, WEAPON_CAPACITY_LEVEL,             WEAPON_CAPACITY_MAX
        values: dict[int, int] = {}
        copies = int(self.upgrade_copies.get("Enhanced Ability", 1))
        if copies:
            for hero, categories in ABILITY_CATEGORIES.items():
                if not self.include_dlc and hero in DLC_CHARACTERS:
                    continue
                got = min(self.upgrades.get(f"Enhanced Ability: {hero}", 0), copies)
                on = -(-got * len(categories) // copies)
                for k, category in enumerate(categories):
                    values[ABILITY_FLAGS + category] = int(k < on)
        copies = int(self.upgrade_copies.get("Progressive Weapon Capacity", 5))
        if copies:
            got = min(self.upgrades.get("Progressive Weapon Capacity", 0), copies)
            values[WEAPON_CAPACITY_LEVEL] = min(WEAPON_CAPACITY_MAX, -(-got * WEAPON_CAPACITY_MAX // copies))
        return values

    def mission_reward_rows(self) -> dict[int, bytes]:
        """Record -> reward row the game should use (empty when rewards are vanilla): shuffled gives each mission
        another mission's vanilla rewards, none clears the reward counts."""
        from ..data_mission_rewards import vanilla_row
        mode = int(self.mission_rewards.get("mode", 0))
        if mode == 1:
            return {int(r): vanilla_row(int(src)) for r, src in self.mission_rewards.get("map", {}).items()}
        if mode == 2:
            rows = {}
            for r in self.mission_rewards.get("records", []):
                row = bytearray(vanilla_row(int(r)))
                row[0x04:0x20] = bytes(0x1C)  # no first-clear or second-list counts
                rows[int(r)] = bytes(row)
            return rows
        return {}

    def reward_writes(self) -> dict[tuple[int, int], int]:
        """(block, offset) -> value for stored quest rewards that follow received items (each copy worth its share of
        its group's quests, in order). Groups the seed has no copies of stay vanilla."""
        from ..data_rewards import ALL_GROUPS, given_quests, reward_writes
        values: dict[tuple[int, int], int] = {}
        for item, copies in self.reward_copies.items():
            group = ALL_GROUPS.get(item)
            if group and group.kind == "store" and copies:
                values.update(reward_writes(group, given_quests(group, self.received_count(item), copies)))
        return values

    def unlocked_by(self, item: str) -> list[str]:
        """Quests a quest reward group item stands for so far (its first copies, in vanilla order)."""
        from ..data_rewards import ALL_GROUPS, given_quests
        group, copies = ALL_GROUPS.get(item), self.reward_copies.get(item, 0)
        if not group or not copies:
            return []
        return list(group.known[:given_quests(group, self.received_count(item), copies)])

    def received_count(self, item: str) -> int:
        """Copies received of an upgrade-like item; Feature items count once."""
        if item.startswith("Feature: "):
            return int(item[len("Feature: "):] in self.features)
        return self.upgrades.get(item, 0)

    def quest_states(self) -> dict[str, int]:
        """Quest -> state the client keeps (live_hook.set_quest_states codes):
        - Smithy / Training Camp open from the start: 3 (done).
        - Shops, stables, the Smithy with Weapon Fusion ("quest" groups, service = quest done): buying the quest is
          its check. Bought and the item (share) in: 3, service open. Bought without the item: 1, closed again until
          the item arrives. Not bought yet: left to the game, so it can be bought.
        - "unlock" groups: -1 (not available unless already done) until the item share is in, then 2 (available; the
          player completes it normally and the game gives its reward).
        Groups without copies in the seed are left alone."""
        from ..data_rewards import ALL_GROUPS, OPEN_SERVICE_QUESTS, given_quests
        states = {q: 3 for q in OPEN_SERVICE_QUESTS}  # Weapon Fusion (below) overrides the Smithy when in the seed
        bought = self.done["quest"]
        if self.side_random:  # open (available) by completion count, else held back unless already done
            done = self.completions
            states.update({q: 2 if done >= at else -1 for q, at in self.quest_open_at.items()
                           if q not in OPEN_SERVICE_QUESTS})
        elif self.post_story_open:  # post-story quests opened early (available; groups below may still hold them)
            states.update({q: 2 for q in self.post_story_quests if q not in OPEN_SERVICE_QUESTS})
        for item, copies in self.reward_copies.items():
            group = ALL_GROUPS.get(item)
            if not group or not copies or group.kind not in ("quest", "unlock"):
                continue
            given = given_quests(group, self.received_count(item), copies)
            for i, q in enumerate(group.known):
                if group.kind == "unlock":
                    states[q] = 2 if i < given and self.side_open("quest", q) else -1
                elif q not in self.ids.get("quest", {}):
                    states[q] = 3 if i < given else 1  # no check for it in this seed (0.9.25-0.9.32): item alone
                elif q in bought:
                    states[q] = 3 if i < given else 1
                elif self.side_random:
                    states[q] = 2 if self.side_open("quest", q) else -1
                else:
                    states.pop(q, None)  # (the Smithy with Weapon Fusion: buyable like any shop quest)
        return states

    def selection_checks(self, sel_id: int, kind: int) -> tuple[str, list[int]] | None:
        """The world-map cursor's mission/challenge/quest and its location ids in this seed (with bonus checks)."""
        from ..data_save import MISSION_RECORD_IDS, QUEST_STATE_IDS
        if kind == 4:
            name = next((q for q, i in QUEST_STATE_IDS.items() if i == sel_id), None)
            ids = [self.ids["quest"][name]] if name in self.ids["quest"] else []
        elif kind in (2, 3):  # 2 story mission, 3 challenge (incl. Divine Beast battles) [read live]
            name = next((n for n, recs in MISSION_RECORD_IDS.items() if sel_id in recs), None)
            ids = [i for kind_ in ("mission", "challenge") for n, i in self.ids[kind_].items() if n == name]
        else:
            return None
        if name is None:
            return None
        return name, ids + sorted(self.bonus_ids(name))

    def quest_rows(self) -> dict[str, tuple[tuple[int, ...], tuple[int, ...]]]:
        """side_unlocks random: the game's quest unlock rows follow the client (as the mission and challenge rows do),
        so the game itself never closes a quest the seed opened, nor opens one it keeps closed: an open quest needs
        nothing, a closed one needs itself (never true). Empty for other seeds (vanilla rows)."""
        if not self.side_random:
            return {}
        from ..data_save import QUEST_STATE_IDS
        rows = {}
        for quest, state in self.quest_states().items():
            if quest not in self.quest_open_at:
                continue
            if state == 2:
                rows[quest] = ((), ())
            elif state == -1:
                rows[quest] = ((), (QUEST_STATE_IDS[quest],))
        return rows

    @property
    def completions(self) -> int:
        """Story clears, challenges and quests done (what opens random side content). Counts everything the game shows
        done, so it is never below the logic's count."""
        done = self.game_done | self.cleared_missions | {n.partition(":")[2] for n in self.side_done}
        return sum(m in done for m in self.mission_ids) + len(done & self.completion_names)

    def side_open(self, kind: str, name: str) -> bool:
        """side_unlocks random: whether this challenge/quest has opened (True when it isn't random)."""
        opens = (self.challenge_open_at if kind == "challenge" else self.quest_open_at).get(name)
        return opens is None or self.completions >= opens

    def side_opened(self) -> set[str]:
        """side_unlocks random: challenges and quests opened by the completion count so far (a challenge also needs
        its forced heroes, a quest held by a reward item its item)."""
        from ..data_challenges import CHALLENGE_BY_NAME
        done = self.completions
        held = {q for q, state in self.quest_states().items() if state == -1}  # still waiting for a reward item
        quests = {q for q, at in self.quest_open_at.items() if done >= at and q not in held}
        return quests | {c for c, at in self.challenge_open_at.items() if done >= at and all(
            h in self.unlocked_characters for h in CHALLENGE_BY_NAME[c].required_characters)}

    @property
    def post_story_open(self) -> bool:
        """post_story_unlock below 20 and that many story missions cleared."""
        return self.post_story_unlock < 20 and \
            sum(m in self.cleared_missions for m in self.mission_ids) >= self.post_story_unlock

    def held_quests(self) -> set[str]:
        """Quests the client may move back from done (bought shop quests waiting for their item): never a sign of a
        New Game."""
        from ..data_rewards import ALL_GROUPS
        return {q for item, copies in self.reward_copies.items() if copies
                for g in [ALL_GROUPS.get(item)] if g and g.kind == "quest" for q in g.known}

    def hearts_for_all(self) -> int | None:
        """+1 bonus heart for every hero per Progressive Heart for All share received (the vanilla Painter's Pilgrimage
        quests' reward); None when the seed has no such item (then those quests stay vanilla)."""
        from ..data_rewards import ALL_GROUPS, HEART_FOR_ALL, given_quests
        copies = self.reward_copies.get(HEART_FOR_ALL, 0)
        if not copies:
            return None
        return given_quests(ALL_GROUPS[HEART_FOR_ALL], self.received_count(HEART_FOR_ALL), copies)

    def rune_flags(self) -> dict[str, bool]:
        """Rune -> whether the game should have it (only runes the client enforces); empty when runes are vanilla.
        0.9.58+ seeds (slot data rune_items): Remote Bombs (the Slate) always on, Cryonis/Magnesis/Stasis by item;
        older seeds enforce Magnesis and Stasis only, as they were generated."""
        from ..data import ENFORCED_RUNES
        if not (self.runes_all or self.runes_shuffled):
            return {}
        enforced = self.rune_items or list(ENFORCED_RUNES)
        flags = {"Remote Bombs": True} if self.rune_items else {}
        flags.update({r: self.runes_all or r in self.runes for r in enforced})
        return flags

    def challenge_unlocks(self) -> dict[int, tuple[int, ...]]:
        """Challenge record -> story records the game should require before it opens, matching the logic: the
        challenge's gate mission, or (gate = after the whole story) its vanilla story prerequisites, else the final
        mission. Challenge and quest prerequisites are dropped (the logic has neither; Link: One-Handed Weapons loads
        and plays without its vanilla quests); rows vanilla leaves open stay.
        A challenge whose forced heroes haven't been received stays closed (it requires its own clear) until they
        arrive, as in logic: the game forces them in even when locked, and a locked hero plays broken (no model, one
        heart, no damage: Zelda's Training: Bows, 2026-10-27)."""
        from ..data_challenges import CHALLENGE_BY_NAME, challenge_gate, champions_needed
        from ..data_save import MISSION_RECORD_IDS, VANILLA_CHALLENGE_UNLOCK, VANILLA_STORY_UNLOCK

        story = {name: max(ids) for name, ids in MISSION_RECORD_IDS.items() if ids[0] in VANILLA_STORY_UNLOCK}
        story_records = {r for name, ids in MISSION_RECORD_IDS.items() if name in story for r in ids}
        unlocks = {}
        for name, ids in MISSION_RECORD_IDS.items():
            vanilla = VANILLA_CHALLENGE_UNLOCK.get(ids[0])
            if name not in CHALLENGE_BY_NAME or vanilla is None:
                continue
            if CHALLENGE_BY_NAME[name].is_ex and not self.include_dlc:
                continue  # the Expansion Pass plays vanilla
            if any(c not in self.unlocked_characters for c in CHALLENGE_BY_NAME[name].required_characters):
                unlocks[ids[0]] = (ids[0],)  # its own clear: closed until its forced heroes are yours
                continue
            if self.calamity_cleared and any(c not in self.unlocked_characters for c in champions_needed(name)):
                unlocks[ids[0]] = (ids[0],)  # needs a Champion who is trapped (not yours) since Calamity Strikes
                continue
            if self.side_random and name in self.challenge_open_at:  # closed = needs its own clear (never opens)
                unlocks[ids[0]] = () if self.side_open("challenge", name) else (ids[0],)
                continue
            needs = [r for r in struct.unpack_from("<5H", bytes.fromhex(vanilla)) if r]
            if not needs:
                continue  # open from the start in vanilla
            gate = challenge_gate(name, self.challenge_by_level, bool(self.boss_rush))
            if not gate and self.post_story_open:
                unlocks[ids[0]] = ()  # post-story challenge, opened early by post_story_unlock
            elif gate:
                unlocks[ids[0]] = (story[gate],)
            else:
                unlocks[ids[0]] = tuple(r for r in needs if r in story_records) or (story[self.final_mission],)
        if "Fairy Fountains" in self.locked_features and "Fairy Fountains" not in self.features:
            from ..data_rewards import FEATURE_CHALLENGES
            for name in FEATURE_CHALLENGES["Fairy Fountains"]:  # closed until the item (opens after the final mission)
                unlocks[MISSION_RECORD_IDS[name][0]] = (story[self.final_mission],)
        return unlocks

    @property
    def calamity_cleared(self) -> bool:
        from ..data_challenges import CALAMITY
        return CALAMITY in self.cleared_missions or CALAMITY in self.game_done

    def available_missions(self) -> list[str]:
        return [m for m in self.mission_ids if m not in self.cleared_missions and self.mission_available(m)]

    @property
    def goal_complete(self) -> bool:
        needed = min(self.goal_story_missions, len(self.mission_ids))
        if sum(m in self.cleared_missions for m in self.mission_ids) < needed:
            return False
        if len(self.side_done) < self.goal_side_missions:
            return False
        if self.goal_difficulty and sum(m in self.difficulty_cleared for m in self.mission_ids) < needed:
            return False
        challenges = self.difficulty_cleared if self.goal_difficulty else self.cleared_any | self.challenges_done
        if len(self.goal_challenge_pool & challenges) < self.goal_challenges:
            return False
        if self.goal == 2 and not set(self.all_characters) <= self.unlocked_characters:
            return False
        if self.goal == 3 and not set(self.boss_rush) <= self.challenges_done:
            return False
        return True

    def note_activity(self, now: float) -> None:
        """Call whenever a new check is reported (or on connect) so quiet spells can be measured."""
        self.last_activity = now
        self.rescue_sent = False

    def rescue_due(self, now: float) -> bool:
        """True once per quiet spell when no check has been reported for stuck_rescue_minutes."""
        if self.stuck_minutes <= 0 or self.rescue_sent or self.last_activity is None or self.goal_complete:
            return False
        if now - self.last_activity >= self.stuck_minutes * 60:
            self.rescue_sent = True
            return True
        return False

    def total_checks(self) -> int:
        return sum(len(ids) for ids in self.ids.values())

    def checks_done(self) -> int:
        return sum(len(names & set(self.ids[kind])) for kind, names in self.done.items())

    def hints_due(self) -> int:
        """How many free hints are owed for the story missions cleared so far (and marks them as given)."""
        if self.hint_every <= 0:
            return 0
        owed = len(self.cleared_missions) // self.hint_every - self.hints_given
        if owed > 0:
            self.hints_given += owed
            return owed
        return 0

    def tracker_html(self) -> str:
        """A small self-refreshing page for a browser tab or an OBS browser source."""
        from html import escape

        def li(items):
            return "".join(f"<li>{escape(str(i))}</li>" for i in items) or "<li><i>none</i></li>"

        rows = []
        for slot, mission in self.mission_slots.items():
            state = "cleared" if mission in self.cleared_missions else (
                "available" if self.mission_available(mission) else "locked")
            need = self.side_required.get(slot, 0)
            note = f" (needs {need} side missions)" if need and state == "locked" else ""
            rows.append(f'<li class="{state}">{escape(mission)} <small>{state}{note}</small></li>')
        extras = ""
        if self.boss_rush:
            extras += f"<h2>Boss rush {len(set(self.boss_rush) & self.challenges_done)}/{len(self.boss_rush)}</h2>"
        if self.featured_challenge:
            extras += f"<h2>Featured challenge</h2><p>{escape(self.featured_challenge)}</p>"
        return (
            "<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=3><title>AoC Tracker</title>"
            "<style>body{font:14px sans-serif;background:#111;color:#eee;margin:16px}"
            ".cleared{color:#6c6}.available{color:#fd6}.locked{color:#888}small{color:#999}"
            "div{display:flex;gap:32px;flex-wrap:wrap}</style>"
            f"<h1>Age of Calamity</h1><p>Side missions done: {len(self.side_done)}"
            f" | Goal: {'COMPLETE' if self.goal_complete else 'in progress'}</p>"
            f"<div><section><h2>Story</h2><ol>{''.join(rows)}</ol></section>"
            f"<section><h2>Heroes</h2><ul>{li(sorted(self.unlocked_characters))}</ul></section>"
            f"<section><h2>Upgrades</h2><ul>{li(f'{k} x{v}' for k, v in sorted(self.upgrades.items()))}</ul>"
            f"<h2>Features</h2><ul>{li(sorted(self.features))}</ul></section></div>{extras}"
        )

    def snapshot(self) -> dict[str, Any]:
        """What the game-side hook needs to enforce this seed, in a stable JSON-friendly shape."""
        return {
            "type": "state",
            "unlocked_characters": sorted(self.unlocked_characters),
            "unlocked_weapons": sorted(self.unlocked_weapons),
            "upgrades": dict(sorted(self.upgrades.items())),
            "unlocked_features": sorted(self.features),
            "locked_features_enabled": self.locked_features,
            "cleared_missions": sorted(self.cleared_missions),
            "available_missions": self.available_missions(),
            "mission_slots": self.mission_slots,
            "completed": {kind: sorted(names) for kind, names in self.done.items() if kind != "mission"},
            "side_missions_completed": len(self.side_done),
            "side_missions_required": self.side_required,
            "settings": {
                "minimum_character_level": self.min_level,
                "pace": self.pace,
                "death_link": self.death_link,
            },
            "goal_complete": self.goal_complete,
        }
