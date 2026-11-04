from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from BaseClasses import Tutorial
from Options import OptionError
from worlds.AutoWorld import WebWorld, World

from . import items, locations, pacing, regions, rules
from .data import (
    FINAL_MISSION,
    ALL_CHARACTERS,
    BASE_CHARACTERS,
    DLC_CHARACTERS,
    BOSS_CHALLENGES,
    FILLER_ITEMS,
    FEATURES,
    GLOBAL_UPGRADES,
    GAME_NAME,
    MISSION_PARTY,
    MISSION_SUPPORT,
    MISSION_NAMES,
    MISSIONS,
    ITEM_RUNES,
    RUNES,
    WEAPONS,
)
from .data_challenges import (CALAMITY, CHALLENGE_BY_NAME, CHALLENGE_QUEST_PREREQS, CHALLENGES, CHAMPIONS,
                              DLC_STORY_MISSIONS)
from .data_quests import QUEST_BY_NAME, QUESTS, UNUSED_QUESTS
from .data_quest_unlocks import GAME_QUEST_PREREQS
from .data_lab import FUTURE_OF_HYRULE, LAB_ITEM_COPIES, LAB_MISSION_CONDITION, LAB_NODES, LAB_WEAPON_ITEMS
from .data_rewards import (ROYAL_GIFTS, RESEARCH_REWARDS, ALL_GROUPS, SPLIT_INTO, DYE_SHOP_QUEST, FEATURE_CHALLENGES, OPEN_SERVICE_QUESTS, REWARD_GROUPS, canonical,
                           reward_quest_count)
from .data_save import BASIC_WEAPONS
from .options import (
    AgeOfCalamityOptions, ChallengeUnlockOrder, FirstMission, GameMode, QuestUnlockOrder, Goal, MissionOrder, MissionRewards, MissionUnlocks, SheikahRunes, SideContent, SideUnlocks, StoryParty, option_groups,
    WeaponCheckLogic, presets,
)

CHAINED_MISSIONS = ("Calamity Strikes", "Water and Fire", "Air and Lightning")  # never the first mission
WORLD_VERSION = "0.9.82"

# side_unlocks random: side content open from the start (at least this many challenges and quests each, when there
# are that many) and how many more open after each completion.
RANDOM_SIDE_START = 10
RANDOM_SIDE_MIN_EACH = 3
RANDOM_SIDE_STEP = (2, 4)
CHALLENGES_ONLY_STEP = (3, 8)  # Challenges Only: each clear opens 3-8 more (user, 2026-11-02)
CHALLENGES_ONLY_GOAL = 50  # Challenges Only with goal_challenges 0
COMPLETIONS = rules.COMPLETIONS  # state counter of completion events (kept by collect/remove)


def _post_story_challenge(name: str, _seen: frozenset = frozenset()) -> bool:
    """The game opens it only after the final story mission: its vanilla unlock row needs that mission, or a challenge
    that does (at any depth)."""
    import struct
    from .data_save import MISSION_RECORD_IDS, VANILLA_CHALLENGE_UNLOCK
    row = VANILLA_CHALLENGE_UNLOCK.get(MISSION_RECORD_IDS[name][0])
    if not row:
        return False
    final = MISSION_RECORD_IDS[MISSIONS[-1].name]
    needs = [r for r in struct.unpack_from("<5H", bytes.fromhex(row)) if r]
    if any(r in final for r in needs):
        return True
    names = {r: n for n, ids in MISSION_RECORD_IDS.items() for r in ids}
    return any(names.get(r) in CHALLENGE_BY_NAME and names[r] not in _seen
               and _post_story_challenge(names[r], _seen | {name}) for r in needs)



# EX Alerts that need a sighting (a monster the game picks when the alert appears): never checks (see generate_early).
SIGHTING_ALERTS = frozenset(c.name for c in CHALLENGES if c.name.startswith("EX Alert:")) - {"EX Alert: Forgotten Temple"}

class AgeOfCalamityWebWorld(WebWorld):
    game = GAME_NAME
    theme = "grassFlowers"
    option_groups = option_groups
    options_presets = presets
    setup_en = Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Hyrule Warriors Age of Calamity for Archipelago.",
        "English",
        "setup_en.md",
        "setup/en",
        ["Archipelago community"],
    )
    tutorials = [setup_en]


class AgeOfCalamityWorld(World):
    """
    Hyrule Warriors Age of Calamity is a hack-and-slash prequel to Breath of the Wild. Clear all
    twenty main story missions; heroes, upgrades, weapons and rewards are shuffled across the multiworld.
    """

    game = GAME_NAME
    web = AgeOfCalamityWebWorld()
    topology_present = False

    options_dataclass = AgeOfCalamityOptions
    options: AgeOfCalamityOptions

    item_name_to_id = items.ITEM_NAME_TO_ID
    location_name_to_id = locations.LOCATION_NAME_TO_ID

    item_name_groups = {
        "Characters": {items.character_item(c) for c in ALL_CHARACTERS},
        "Weapons": {items.weapon_item(w.name) for w in WEAPONS},
        "Features": {f"Feature: {f}" for f in FEATURES},
        "Runes": {items.rune_item(r) for r in RUNES},
        "Mission Unlocks": {items.unlock_item(m) for m in [*MISSION_NAMES, *DLC_STORY_MISSIONS]},
        "Quest Rewards": {g.item for g in REWARD_GROUPS},
        **{
            f"{family}s": {items.upgrade_item(family, c) for c in ALL_CHARACTERS}
            for family in items.UPGRADE_FAMILIES
        },
    }
    location_name_groups = {
        "Missions": {locations.mission_location(m.name) for m in MISSIONS},
        "Weapon Pickups": {locations.weapon_location(w.name) for w in WEAPONS},
        "Challenges": {locations.challenge_location(c.name) for c in CHALLENGES},
        "Quests": {locations.quest_location(q.name) for q in QUESTS},
        "Korok Seeds": {locations.korok_name(s, i) for s, _, i in locations.KOROKS},
        **{
            f"Chapter {c}": {locations.mission_location(m.name) for m in MISSIONS if m.chapter == c}
            for c in range(1, 8)
        },
    }

    # Filled in generate_early.
    characters: list[str]
    starting_characters: list[str]
    characters_matter: bool
    mission_order: list[str]
    slot_to_mission: dict[str, str]
    slot_prerequisites: dict[str, tuple[str, ...]]
    active_challenges: list[str]
    active_quests: list[str]
    checked_challenges: set[str]
    checked_quests: set[str]
    checked_koroks: list[tuple[str, str, int]]
    checked_weapons: list[str]
    active_weapons: list[str]
    side_counted: list[str]
    goal_side_required: int
    post_goal_weapons: list[str]
    bonus_checks: dict[str, int]
    challenge_bonus_checks: dict[str, int] = {}
    difficulty_levels: int = 0  # per-difficulty checks: Normal (1) .. Very Hard (3)
    boss_goal: bool
    featured_challenge: str | None
    mission_party: dict[str, tuple[str, ...]]
    party_needs: dict[str, list[str]]
    starting_unlocks: list[str]
    slot_side_required: dict[str, int]
    reward_copies: dict[str, int]
    item_quests: dict[str, str]
    unlock_quests: dict[str, str]
    group_copies: dict[str, int]
    fairy_locked: bool
    goal_challenge_pool: list[str]
    reward_progression: set[str]
    side_random: bool  # challenges and/or quests open by completion count
    challenge_random: bool = False
    quest_random: bool = False
    completion_events: list[str]
    challenge_open_at: dict[str, int]
    quest_open_at: dict[str, int]
    _completion_set: frozenset[str] = frozenset()
    ut_data: dict[str, Any] | None = None  # Universal Tracker: this slot's slot_data, to rebuild the same seed

    # Universal Tracker regenerates the seed from slot_data alone (no YAML needed)
    ut_can_gen_without_yaml = True

    @staticmethod
    def interpret_slot_data(slot_data: dict[str, Any]) -> dict[str, Any]:
        return slot_data

    def _restore_ut_options(self) -> None:
        """Universal Tracker: the seed's own option values (slot_data "ut_options", 0.9.73+)."""
        for name, value in (self.ut_data or {}).get("ut_options", {}).items():
            current = getattr(self.options, name, None)
            if current is not None:
                setattr(self.options, name, type(current).from_any(value))

    def generate_early(self) -> None:
        passthrough = getattr(self.multiworld, "re_gen_passthrough", None) or {}
        self.ut_data = passthrough.get(self.game)
        ut = self.ut_data
        if ut:
            self._restore_ut_options()
        options = self.options
        if options.side_content.value == SideContent.default:  # the toggles decide unless the old list form was set
            options.side_content.value = {k for k, on in (("Weapons", options.weapon_checks), ("Challenges", options.challenge_checks),
                                                          ("Quests", options.quest_checks)) if on}
        dlc = bool(options.include_dlc)
        self.characters = list(ALL_CHARACTERS if dlc else BASE_CHARACTERS)
        if options.goal_all_heroes and options.goal == Goal.option_story:
            options.goal.value = Goal.option_story_and_all_characters
        self.game_mode = options.game_mode.value
        self._apply_game_mode()

        pool = sorted(c for c in options.starting_character_pool.value if c in self.characters)
        count = options.starting_character_count.value
        if not pool:
            raise OptionError(f"{self.player_name}: starting_character_pool has no usable characters.")
        if count > len(pool):
            logging.warning("%s: only %d starting characters are available, not %d.", self.player_name, len(pool), count)
            count = len(pool)
        self.starting_characters = self.random.sample(pool, count)
        if ut:
            self.starting_characters = list(ut["starting_characters"])

        # Story slots keep the vanilla unlock structure; mission order decides which mission sits in each slot.
        slots = [m.name for m in MISSIONS]
        assigned = list(slots)
        unlock_items = options.mission_unlocks == MissionUnlocks.option_items
        if unlock_items:
            if options.mission_order != MissionOrder.option_vanilla:
                logging.warning("%s: mission_unlocks: items ignores mission_order.", self.player_name)
        elif options.mission_order == MissionOrder.option_shuffle_all:
            rest = assigned[1:]
            self.random.shuffle(rest)
            assigned[1:] = rest
        elif options.mission_order == MissionOrder.option_shuffle_within_chapter:
            for chapter in {m.chapter for m in MISSIONS}:
                idx = [i for i, m in enumerate(MISSIONS) if m.chapter == chapter and i > 0]
                names = [assigned[i] for i in idx]
                self.random.shuffle(names)
                for i, n in zip(idx, names):
                    assigned[i] = n
        # Slot 1 stays The Battle of Hyrule Field: the game replays its opening until that mission is cleared, so the
        # starter save has it cleared (its check is sent at the start). first_mission picks the mission of slot 2,
        # the first one you play (with unlock items: always one of your starting unlocks).
        pick = MISSIONS[1].name
        if options.first_mission != FirstMission.option_vanilla:
            any_mission = options.first_mission == FirstMission.option_random_any
            # (never The Future of Hyrule: the final-mission rule moved it to the end and put the last slot's mission
            # first - Calamity Strikes, which needs all four Champions: the fill failed, option fuzz 2026-11-02)
            pick = self.random.choice([m.name for m in MISSIONS[1:]
                                       if (any_mission or m.chapter <= 2) and m.name not in CHAINED_MISSIONS
                                       and m.name != FINAL_MISSION])
            i = assigned.index(pick)
            assigned[1], assigned[i] = assigned[i], assigned[1]
        # (0.9.66-0.9.71 pinned Calamity Strikes and the rescues to their story slots. The user saw no Champion trap
        # once all four were received, so since 0.9.72 they are shuffled like any mission and have unlock items;
        # Calamity Strikes still needs the four Champions.)
        if options.final_mission_goal:  # the goal mission sits in the last story slot (and is never the first)
            i = assigned.index(FINAL_MISSION)
            assigned[i], assigned[-1] = assigned[-1], assigned[i]
        if ut:
            assigned = [ut["mission_slots"][s] for s in slots]
        self.slot_to_mission = dict(zip(slots, assigned))
        self.slot_prerequisites = {m.name: m.prerequisites for m in MISSIONS}
        self.mission_order = assigned
        self.story_chain: list[str] = []
        if self.game_mode == GameMode.option_story_only:
            self._plan_story_chain(pick)
        elif self.game_mode == GameMode.option_challenges_only:  # no story but the pre-cleared first mission
            first = MISSIONS[0].name
            self.slot_to_mission, self.slot_prerequisites, self.mission_order = {first: first}, {first: ()}, [first]
            pick = first
        # With unlock items the story has no order: the player starts with a few unlocks for early missions.
        early = [m.name for m in MISSIONS[1:] if m.chapter <= 2 and m.name != pick]
        count = min(options.starting_mission_unlocks.value, len(early) + 1) if unlock_items else 0
        if count == 1 and options.story_party == StoryParty.option_vanilla:
            # Fixed parties leave a single starting mission (one check) to begin the fill from: about 4 in 5 such seeds
            # failed to generate (option fuzz 2026-11-02). A second starting unlock always worked.
            logging.warning("%s: story_party vanilla with one starting mission unlock: using 2.", self.player_name)
            count = 2
        self.starting_unlocks = ([pick] + self.random.sample(early, count - 1)) if count else []
        if ut:
            self.starting_unlocks = list(ut.get("starting_unlocks", self.starting_unlocks))

        # Missions open before any check is reachable: the first two slots, or the first one plus the starting unlocks.
        playable_first = [self.mission_order[0], *self.starting_unlocks] if unlock_items else self.mission_order[:2]
        vanilla_party = options.story_party == StoryParty.option_vanilla
        self.mission_party = dict(MISSION_PARTY) if vanilla_party else {}
        if vanilla_party:
            # The missions open from the start must be playable from the start: before them the only reachable
            # check is slot 1, so a hero they need would have nowhere to go (this made ~15% of such seeds fail).
            for mission in playable_first:
                for needed in self.mission_party.get(mission, ()):
                    if needed not in self.starting_characters:
                        self.starting_characters.append(needed)
        # A story mission plays its support heroes as AI allies and won't let you pick them, so with a free party it
        # needs one other hero. Missions open from the start get one as a starter; later missions require one in logic.
        self.party_needs = {}
        if not vanilla_party:
            for mission in self.mission_order:
                allowed = [c for c in self.characters if c not in MISSION_SUPPORT.get(mission, ())]
                if any(c in allowed for c in self.starting_characters):
                    continue
                if mission in playable_first:
                    self.starting_characters.append(self.random.choice([c for c in pool if c in allowed] or allowed))
                else:
                    self.party_needs[mission] = allowed
        if ut:
            self.party_needs = {m: list(c) for m, c in ut["mission_party_any"].items()}

        if options.sheikah_runes == SheikahRunes.option_shuffled:  # rune items are hinted for free from the start
            options.start_hints.value |= {items.rune_item(r) for r in ITEM_RUNES}
        side = options.side_content.value
        boss_goal = False  # the boss rush goal was removed (user, 2026-11-02); old seeds still finish in the client
        self.boss_goal = boss_goal
        self.characters_matter = bool(side) or vanilla_party or options.goal == Goal.option_story_and_all_characters
        self.characters_matter |= bool(self.party_needs)
        self.characters_matter = True  # 0.9.66: Calamity Strikes needs the four Champions (heroes are progression)
        if options.local_filler:
            options.local_items.value |= set(FILLER_ITEMS)
        density = options.side_check_density.value / 100

        def pick(names: list[str]) -> list[str]:
            keep = max(1, round(len(names) * density)) if names else 0
            return self.random.sample(names, keep) if keep < len(names) else list(names)

        if self.game_mode == GameMode.option_story_only:
            self.active_challenges = [c for c in self.story_chain if c in DLC_STORY_MISSIONS]  # the DLC story only
        elif side:
            # EX Alerts stay vanilla (playable, replayable, never checks): the game assigns each one a sighting (monster)
            # when it appears, which the client can't set yet; one opened by hand crashed in its loading screen (user,
            # 2026-11-02). "EX Alert: Forgotten Temple" is the Battle-Tested Guardian fight, a normal mission: it stays.
            self.active_challenges = [c.name for c in CHALLENGES if (dlc or not c.is_ex) and c.name not in SIGHTING_ALERTS]
        else:
            self.active_challenges = list(BOSS_CHALLENGES) if boss_goal else []
        active = set(self.active_challenges)
        # Heroes gate any active challenge whose party the game fixes (e.g. boss challenges), so they must be progression.
        self.characters_matter |= any(CHALLENGE_BY_NAME[c].required_characters for c in self.active_challenges)
        # Quests that depend on content that isn't present are dropped (cascading).
        quests = {q.name: q for q in QUESTS}
        alive: dict[str, bool] = {}

        def is_alive(name: str) -> bool:
            if name not in alive:
                alive[name] = False  # guards against cycles
                q = quests[name]
                alive[name] = all(c in active for c in q.challenge_prereqs) and all(is_alive(p) for p in q.quest_prereqs)
            return alive[name]

        self.active_quests = [q.name for q in QUESTS if side and (dlc or not q.is_ex) and is_alive(q.name)
                              and q.name not in UNUSED_QUESTS and self.game_mode != GameMode.option_challenges_only]
        # Post-story content that only opens after a story-only goal holds no checks (user, 2026-10-28): reaching it
        # means the game is won and everything released. post_story_unlock below the goal keeps it in.
        o = options
        self.post_goal_side = (o.goal == Goal.option_story and not o.goal_challenges.value
                               and not o.goal_quests.value and not o.goal_difficulty.value
                               and o.post_story_unlock.value >= min(o.goal_story_missions.value, len(MISSIONS)))
        self.checked_challenges = set(pick([c for c in self.active_challenges
                                            if not (self.post_goal_side and _post_story_challenge(c))]))             if "Challenges" in side else set()
        # Challenges that count for goal_challenges: every challenge of the seed's content
        # With include_dlc, Guardian of Remembrance's missions are story missions (goal, unlock items), not challenges
        self.dlc_story = [c for c in DLC_STORY_MISSIONS if c in self.active_challenges
                          and self.game_mode != GameMode.option_challenges_only]  # (there they are challenges)
        self.goal_challenge_pool = [c for c in self.active_challenges if c not in self.dlc_story] if "Challenges" in side else []
        self.checked_challenges |= set(self.dlc_story)  # story missions always hold their clear check
        if options.goal_challenges.value > len(self.goal_challenge_pool):
            logging.warning("%s: goal_challenges %d lowered to %d (challenges in the seed).", self.player_name,
                            options.goal_challenges.value, len(self.goal_challenge_pool))
        if ut:
            self.checked_challenges = set(ut["challenge_ids"])
        self.featured_challenge = None
        if options.featured_challenge and self.checked_challenges:
            choices = sorted(c for c in self.checked_challenges if not CHALLENGE_BY_NAME[c].is_ex)
            if choices:
                self.featured_challenge = self.random.choice(choices)
                options.priority_locations.value.add(locations.challenge_location(self.featured_challenge))
        if ut:
            self.featured_challenge = ut.get("featured_challenge")
        # Quest reward items: copies per group (capped at the quests the client enforces; 0 = vanilla).
        wanted = {canonical(k): v for k, v in self.options.quest_reward_items.value.items()}  # old names allowed
        quests_on = "Quests" in side  # quest-locking groups only make sense when quests are checks
        self.reward_copies = {g.item: max(0, min(int(wanted.get(g.item, 0)), reward_quest_count(g)))
                              if (dlc or not g.dlc) and (quests_on or g.kind == "store") else 0 for g in REWARD_GROUPS}
        # Other items that drive quests the same way: locked features, Weapon Fusion (the Smithy), Seal Slots.
        features = self.options.locked_features.value
        extra = {f"Feature: {f}": 1 for f in ("Cooking", "Shops", "Terrako Guardian") if f in features and quests_on}
        if "Shops" in features:
            self.reward_copies["Progressive Shop Unlock"] = 0  # one Feature: Shops opens every shop instead
        if self.options.weapon_fusion:
            extra["Weapon Fusion"] = 1
        if self.options.seal_slot_upgrades:
            extra["Progressive Seal Slot"] = self.options.seal_slot_upgrades.value
            self.reward_copies[canonical("Progressive Seal Removal")] = 0  # the same two seal-removal rewards
        # Quests done from the start (no check, no item): the services the options open, plus the Smithy, the Training
        # Camp and cooking unless an item holds them. Store rewards of those quests are given in full (pre_granted).
        o = self.options
        start_done = set(OPEN_SERVICE_QUESTS)
        if dlc:  # the Ancient Tech Lab: open from the start (else only after Road to the Ancient Lab)
            start_done.add("EX Ancient Tech Lab")
        self.pre_granted: dict[str, int] = {}

        def open_group(item: str, quests=None, grant: bool = False) -> None:
            group = ALL_GROUPS[item]
            start_done.update(quests if quests is not None else group.known)
            self.reward_copies[item] = 0
            extra.pop(item, None)
            if grant:
                self.pre_granted[item] = reward_quest_count(group)

        if o.start_with_sheikah_sensor:
            open_group("Progressive Sheikah Sensor", ("Needed: Researchers!",))
        if o.start_with_trackers:
            start_done.add("The Treasure Hunter's Technique")
            for g in ALL_GROUPS.values():
                if g.kind == "store" and {"The Treasure Detector", "A Most Peculiar Korok"} & set(g.known):
                    open_group(g.item, grant=True)
        if o.open_stables:
            open_group("Progressive Stable Unlock")
        shop_quests = [q for q in ALL_GROUPS["Progressive Shop Unlock"].known if q != DYE_SHOP_QUEST]
        if o.open_shops:
            open_group("Progressive Shop Unlock", shop_quests)
            open_group("Feature: Shops", shop_quests)
        if o.open_dye_shop:
            start_done.add(DYE_SHOP_QUEST)
        self.reward_copies["Progressive Region Hope"] = 0  # Hope quests complete by map %, nothing to buy or unlock
        if self.game_mode and not self.reward_copies.get("Progressive Recipe"):
            open_group("Progressive Recipe", grant=True)  # both modes: recipe items, else every recipe from the start
                                                          # (no quests on the map to earn them)
        # 0.9.81: Royal Ancient Lab nodes hold checks (the client clears their kill-count conditions and opens them all)
        self.checked_lab, self.lab_items, self.forced_items = [], {}, []
        if dlc and o.lab_checks and not self.game_mode:
            # (No checks behind The Future of Hyrule when clearing it wins: those nodes keep the game's reward.)
            self.checked_lab = [n.name for n in LAB_NODES if n.name not in LAB_MISSION_CONDITION
                                or LAB_MISSION_CONDITION[n.name] in self.active_challenges
                                or (LAB_MISSION_CONDITION[n.name] == FUTURE_OF_HYRULE and not o.final_mission_goal)]
            self.lab_items = {item: copies for item, copies in LAB_ITEM_COPIES.items()
                              if any(n.item == item and n.name in self.checked_lab for n in LAB_NODES)}
            self.forced_items += list(LAB_WEAPON_ITEMS)
        if ut:
            self.checked_lab = list(ut.get("lab_ids", ()))
        # 0.9.81: royal gifts: the quest row is emptied and the champion weapon is an item of its own
        self.emptied_quests = []
        if self.reward_copies.get("Progressive EX Reward Quest"):
            self.forced_items += [f"Weapon: {w}" for w in ROYAL_GIFTS.values()]
            self.emptied_quests += list(ROYAL_GIFTS)
        if self.reward_copies.get("Progressive Research Quest"):
            self.emptied_quests += list(RESEARCH_REWARDS)
        # 0.9.78: groups of individual rewards become one item per quest (the counters stay progressive)
        for old, parts in SPLIT_INTO.items():
            if self.reward_copies.get(old):
                self.reward_copies[old] = 0
                for part in parts:  # (a quest open from the start, like the dye shop, needs no item)
                    if not set(ALL_GROUPS[part].known) <= start_done:
                        self.reward_copies[part] = reward_quest_count(ALL_GROUPS[part])
        self.group_copies = {**self.reward_copies, **extra}
        self.fairy_locked = "Fairy Fountains" in features
        # Quests whose service follows the quest state (shops, stables, the Smithy): buying is the check, the service
        # opens only once the item is in too.
        self.item_quests = {q: g.item for g in ALL_GROUPS.values() if g.kind == "quest" and self.group_copies.get(g.item)
                            for q in g.known}
        # Quests locked until their item arrives (reward address unknown): they stay checks, gated by the item.
        self.unlock_quests = {q: g.item for g in ALL_GROUPS.values() if g.kind == "unlock" and self.group_copies.get(g.item)
                              for q in g.known}
        self.open_quests = start_done - set(self.item_quests) - set(self.unlock_quests)
        # challenges opened by quests in the game (Trial of the Ancients, fairy fountains): kept when those quests exist
        self.challenge_quests = {c: qs for c, qs in CHALLENGE_QUEST_PREREQS.items()
                                 if c in self.active_challenges and all(q in self.active_quests for q in qs)}
        no_check = set(self.open_quests)  # open from the start: nothing to buy
        hope = {q for q in self.active_quests if q.startswith("The Hope of ")}
        no_check |= {"The Hope of All Hyrule"} | (set() if o.region_hope_checks else hope)
        self.checked_quests = set(pick([q for q in self.active_quests if q not in no_check
                                        and not (self.post_goal_side and QUEST_BY_NAME[q].gate == "HOPE")]))             if "Quests" in side else set()
        if ut:
            self.checked_quests = set(ut["quest_ids"])
        # Their items gate logic only through checked quests that need one of those quests first (at any depth).
        self.reward_progression = set()

        def needs(name: str, seen: set[str]) -> None:
            for p in set(QUEST_BY_NAME[name].quest_prereqs) | set(GAME_QUEST_PREREQS.get(name, ())):
                if p in self.item_quests or p in self.unlock_quests:
                    self.reward_progression.add(self.item_quests.get(p) or self.unlock_quests[p])
                elif p not in seen:
                    seen.add(p)
                    needs(p, seen)

        for q in self.checked_quests:
            needs(q, set())
            if q in self.unlock_quests:
                self.reward_progression.add(self.unlock_quests[q])
        if self.fairy_locked and set(FEATURE_CHALLENGES["Fairy Fountains"]) & set(self.active_challenges):
            self.reward_progression.add("Feature: Fairy Fountains")
        self.checked_koroks = []
        if "Korok Seeds" in side:
            all_koroks = [k for k in locations.KOROKS if k[1] == "mission" or k[0] in active]
            names = {locations.korok_name(s, i): (s, k, i) for s, k, i in all_koroks}
            chosen = set(pick(list(names)))
            if ut:
                chosen = set(ut["korok_ids"])
            self.checked_koroks = [v for n, v in names.items() if n in chosen]
        self.active_weapons = [w.name for w in WEAPONS if dlc or not w.dlc]
        # A hero's basic weapon is no check: a new game already hands several out, and the client gives the rest.
        self.checked_weapons = [w for w in self.active_weapons if w not in BASIC_WEAPONS
                                and f"Weapon: {w}" not in self.forced_items] if "Weapons" in side else []
        shuffled = options.side_unlocks == SideUnlocks.option_shuffled  # (old option: game_rules = both vanilla)
        self.challenge_random = (shuffled and options.challenge_unlock_order == ChallengeUnlockOrder.option_randomized
                                 or self.game_mode == GameMode.option_challenges_only)
        self.quest_random = shuffled and options.quest_unlock_order == QuestUnlockOrder.option_randomized
        self.side_random = self.challenge_random or self.quest_random
        self.completion_events = ([regions.cleared_event(m) for m in self.mission_order]
                                  + [regions.challenge_event(c) for c in self.active_challenges]
                                  + [regions.quest_event(q) for q in self.active_quests])
        self._completion_set = frozenset(self.completion_events)
        # per-difficulty checks (none with a difficulty lock: one clear on the locked difficulty sends everything)
        self.difficulty_levels = 0 if options.difficulty_lock else options.difficulty_checks.value
        self.challenge_open_at, self.quest_open_at = self._plan_random_side() if self.side_random else ({}, {})
        if ut:
            self.challenge_open_at, self.quest_open_at = dict(ut["challenge_open_at"]), dict(ut["quest_open_at"])
        self._plan_side_gates()
        self.post_goal_weapons = self._post_goal_weapons()
        self.checked_weapons = [w for w in self.checked_weapons if w not in self.post_goal_weapons]
        if ut:
            self.checked_weapons = [w for w in self.active_weapons if w in ut["weapon_ids"]]

    def _apply_game_mode(self) -> None:
        """Story Only / Challenges Only (user, 2026-11-02) override the options they replace."""
        o = self.options
        if self.game_mode:  # both modes: every service open from the start (user, 2026-11-02)
            for name in ("open_shops", "open_stables", "open_dye_shop", "start_with_sheikah_sensor"):
                getattr(o, name).value = 1
            o.weapon_fusion.value = 0
            o.locked_features.value = set()
        if self.game_mode == GameMode.option_story_only:
            o.side_content.value = set()  # every check on story missions (bonus checks), DLC story included
            o.mission_unlocks.value = MissionUnlocks.option_story_order  # each clear opens the next (story_chain)
            o.goal.value = Goal.option_story
            o.goal_challenges.value = 0
            o.goal_quests.value = 0
            o.goal_side_missions.value = 0
            o.side_missions_per_unlock.value = 0
        elif self.game_mode == GameMode.option_challenges_only:
            o.side_content.value = {"Challenges"}
            o.mission_unlocks.value = MissionUnlocks.option_story_order
            o.final_mission_goal.value = 0
            o.goal.value = Goal.option_story
            o.goal_quests.value = 0
            o.goal_side_missions.value = 0
            o.side_missions_per_unlock.value = 0
            if not o.goal_challenges.value:
                o.goal_challenges.value = CHALLENGES_ONLY_GOAL
            o.side_unlocks.value = SideUnlocks.option_shuffled
            if o.sheikah_runes == SheikahRunes.option_vanilla:  # the vanilla runes come from story missions
                o.sheikah_runes.value = SheikahRunes.option_shuffled

    def _plan_story_chain(self, first: str) -> None:
        """Story Only: a random chain of every story mission (the DLC story too with include_dlc); clearing one opens
        the next. The Battle of Hyrule Field is first (pre-cleared), `first` second; with final_mission_goal The Future
        of Hyrule is the goal_story_missions-th."""
        o = self.options
        rest = [m.name for m in MISSIONS[1:] if m.name != first]
        if o.include_dlc:
            rest += list(DLC_STORY_MISSIONS)
        self.random.shuffle(rest)
        chain = [MISSIONS[0].name, first] + rest
        if o.final_mission_goal and FINAL_MISSION in chain:
            chain.remove(FINAL_MISSION)
            chain.insert(max(2, min(o.goal_story_missions.value, len(chain) + 1) - 1), FINAL_MISSION)
        if self.ut_data and self.ut_data.get("story_chain"):
            chain = list(self.ut_data["story_chain"])
        self.story_chain = chain
        base = [m for m in chain if m in MISSION_NAMES]
        self.mission_order = base
        self.slot_to_mission = {m: m for m in base}
        self.slot_prerequisites = {m: ((chain[chain.index(m) - 1],) if chain.index(m) else ()) for m in base}

    def chain_before(self, name: str) -> str | None:
        """Story Only: the mission whose clear opens this one."""
        i = self.story_chain.index(name) if name in self.story_chain else 0
        return self.story_chain[i - 1] if i else None

    def _post_goal_weapons(self) -> list[str]:
        """Weapon drops the logic only opens after the whole story (weapon_check_logic after_story, unverified timing)
        come after a story-only goal, so they hold no check: nothing can hide behind the win condition."""
        o = self.options
        if o.weapon_check_logic == WeaponCheckLogic.option_after_character:
            return []
        if (o.goal != Goal.option_story or o.goal_challenges.value or o.goal_quests.value or self.goal_side_required
                or o.goal_difficulty.value):
            return []  # the goal needs more than story clears, so the story (and these drops) can come first
        by_name = {w.name: w for w in WEAPONS}
        return [w for w in self.checked_weapons if not by_name[w].verified]

    def _plan_random_side(self) -> tuple[dict[str, int], dict[str, int]]:
        """side_unlocks random: challenge/quest -> completions (story clears, challenges, quests) it opens after. A
        random order: RANDOM_SIDE_START open from the start (at least RANDOM_SIDE_MIN_EACH of each kind), then
        RANDOM_SIDE_STEP more per completion. Boss challenges of a boss-rush goal and services open from the start keep
        their own rules."""
        # post-story content joins the random openings unless post_story_unlock is 20 (vanilla: after the whole story)
        vanilla_post = self.options.post_story_unlock.value >= 20
        only = self.game_mode == GameMode.option_challenges_only  # every challenge joins (no story to wait for)
        challenges = [c for c in self.active_challenges if only or not (self.boss_goal and c in BOSS_CHALLENGES)
                      and not (vanilla_post and _post_story_challenge(c) and not only) and c not in self.challenge_quests
                      and c not in self.dlc_story  # story missions: unlock items or the game's chain, not side counts
                      and self.challenge_random]
        # Expansion Pass quests carry a conservative after-the-story gate in our data, but all of them can be handed in
        # whenever they're open (77 forced open, 2026-11-02): they join the random order (user: DLC pops up anytime)
        quests = [q for q in self.active_quests if q not in self.open_quests and not q.startswith("The Hope of ")
                  and not (vanilla_post and QUEST_BY_NAME[q].gate == "HOPE" and not q.startswith("EX "))
                  and self.quest_random]
        self.random.shuffle(challenges)
        self.random.shuffle(quests)
        first = challenges[:RANDOM_SIDE_MIN_EACH] + quests[:RANDOM_SIDE_MIN_EACH]
        rest = [("c", c) for c in challenges[RANDOM_SIDE_MIN_EACH:]] + [("q", q) for q in quests[RANDOM_SIDE_MIN_EACH:]]
        self.random.shuffle(rest)
        entries = [("c", c) for c in challenges[:RANDOM_SIDE_MIN_EACH]] + [("q", q) for q in quests[:RANDOM_SIDE_MIN_EACH]]
        entries += rest
        thresholds = [0] * max(len(first), RANDOM_SIDE_START)
        done = 0
        while len(thresholds) < len(entries):
            done += 1
            thresholds += [done] * self.random.randint(*(CHALLENGES_ONLY_STEP if only else RANDOM_SIDE_STEP))
        opens: dict[str, dict[str, int]] = {"c": {}, "q": {}}
        for (kind, name), at in zip(entries, thresholds):
            opens[kind][name] = at
        return opens["c"], opens["q"]

    def _plan_side_gates(self) -> None:
        """Compute how many side missions each story slot needs, lowering anything that could deadlock."""
        per = self.options.side_missions_per_unlock.value
        if per and self.options.mission_unlocks == MissionUnlocks.option_items:
            logging.warning("%s: mission_unlocks: items ignores side_missions_per_unlock.", self.player_name)
            per = 0
        self.side_counted = []
        self.goal_side_required = 0
        self.slot_side_required = {m.name: 0 for m in MISSIONS}
        wants_goal = self.options.goal == Goal.option_story_and_side_missions
        if not per and not wants_goal:
            return
        if not self.active_challenges and not self.active_quests:
            logging.warning("%s: side-mission gates/goal need challenges or quests; ignoring them.", self.player_name)
            return
        # Only side missions that need no particular character count in logic (always safe).
        free_challenges = [c for c in self.active_challenges if not CHALLENGE_BY_NAME[c].required_characters]
        # (quests done from the start, the services the options open, are no side mission you complete: until 0.9.75
        # they counted, and a new seed showed "Side 23/30" before anything was played - user, 2026-11-02)
        quests = {q: QUEST_BY_NAME[q] for q in self.active_quests
                  if q not in self.item_quests and q not in self.unlock_quests and q not in self.open_quests}

        def counted_with(cleared: set[str]) -> set[str]:
            """Side events reachable once these missions are cleared (plain-Python mirror of rules.py)."""
            full = False  # Victory itself may depend on this count, so nothing behind Victory can count
            got: set[str] = set()
            if self.side_random:  # opens by completion count: grow until nothing more opens
                while True:
                    done = len(cleared) + len(got)
                    more = {regions.challenge_event(c) for c in free_challenges
                            if self.challenge_open_at.get(c, 0) <= done
                            and all(r in cleared_events(cleared, full) for r in rules.challenge_requirements(self, c)
                                    if not r.startswith("Character: "))}
                    more |= {regions.quest_event(q) for q in quests if q in self.quest_open_at
                             and self.quest_open_at[q] <= done}
                    more |= {regions.quest_event(name) for name, q in quests.items() if name not in self.quest_open_at
                             and all(regions.quest_event(p) in got for p in q.quest_prereqs)
                             and all(regions.challenge_event(c) in got for c in q.challenge_prereqs)
                             and rules.quest_gate_open(q.gate, cleared_events(cleared, full))}  # vanilla quests
                    if more <= got:
                        return got
                    got |= more
            for c in free_challenges:
                req = rules.challenge_requirements(self, c)
                if all(r in cleared_events(cleared, full) for r in req if not r.startswith("Character: ")):
                    got.add(regions.challenge_event(c))
            changed = True
            while changed:
                changed = False
                for name, q in quests.items():
                    ev = regions.quest_event(name)
                    if ev in got or not all(regions.quest_event(p) in got for p in q.quest_prereqs):
                        continue
                    if not all(regions.challenge_event(c) in got for c in q.challenge_prereqs):
                        continue
                    if rules.quest_gate_open(q.gate, cleared_events(cleared, full)):
                        got.add(ev)
                        changed = True
            return got

        def cleared_events(cleared: set[str], full: bool) -> set[str]:
            events = {regions.cleared_event(m) for m in cleared}
            if full:
                events.add(regions.STORY_EVENT)
                events.add(regions.POST_STORY_EVENT)
            return events

        order = [m.name for m in MISSIONS]
        required = {slot: per * i for i, slot in enumerate(order)}
        everything = counted_with({m.name for m in MISSIONS})
        self.side_counted = sorted(everything)
        if wants_goal:
            wanted = self.options.goal_side_missions.value
            self.goal_side_required = min(wanted, len(everything))
            if wanted > len(everything):
                logging.warning("%s: goal needs %d side missions but only %d can count; lowering it.",
                                self.player_name, wanted, len(everything))
        if not per:
            return
        cleared_slots: set[str] = set()
        while len(cleared_slots) < len(order):
            missions = {self.slot_to_mission[s] for s in cleared_slots}
            count = len(counted_with(missions))
            ready = [
                s for s in order
                if s not in cleared_slots
                and all(p in cleared_slots for p in self.slot_prerequisites[s])
            ]
            doable = [s for s in ready if required[s] <= count]
            if doable:
                cleared_slots.update(doable)
                continue
            lowest = min(ready, key=lambda s: required[s])
            logging.warning(
                "%s: story slot '%s' would need %d side missions but only %d are available by then; lowering it.",
                self.player_name, lowest, required[lowest], count,
            )
            required[lowest] = count
        self.slot_side_required = required

    def create_regions(self) -> None:
        regions.create_regions(self)

    def create_items(self) -> None:
        items.create_all_items(self)

    def set_rules(self) -> None:
        rules.set_all_rules(self)
        self.post_goal_excluded = pacing.exclude_post_goal(self)
        rules.apply_steady_rewards(self)
        for loc in self.multiworld.get_locations(self.player):  # a harder clear needs what the clear itself needs
            base = getattr(loc, "difficulty_of", None)
            if base:
                loc.access_rule = self.get_location(base).access_rule

    def pre_fill(self) -> None:
        pacing.ensure_room(self)
        pacing.front_load(self)

    def collect(self, state, item) -> bool:
        """Also count completion events in one counter, so side_unlocks rules are one lookup, not a 600-name sum."""
        changed = super().collect(state, item)
        if changed and item.name in self._completion_set:
            state.prog_items[self.player][COMPLETIONS] += 1
        return changed

    def remove(self, state, item) -> bool:
        changed = super().remove(state, item)
        if changed and item.name in self._completion_set:
            state.prog_items[self.player][COMPLETIONS] -= 1
        return changed

    def create_item(self, name: str) -> items.AgeOfCalamityItem:
        return items.create_item(self, name)

    def get_filler_item_name(self) -> str:
        return items.get_filler_item_name(self)

    def write_spoiler(self, spoiler_handle) -> None:
        spoiler_handle.write(f"\n{self.player_name} (Age of Calamity) story order:\n")
        spoiler_handle.write(f"  starting heroes: {', '.join(self.starting_characters)}\n")
        for i, (slot, mission) in enumerate(self.slot_to_mission.items(), 1):
            need = self.slot_side_required.get(slot, 0)
            spoiler_handle.write(f"  {i:2}. {mission}" + (f"  (needs {need} side missions)" if need else "") + "\n")

    def extend_hint_information(self, hint_data: dict[int, dict[int, str]]) -> None:
        info = {}
        for i, (slot, mission) in enumerate(self.slot_to_mission.items(), 1):
            info[locations.LOCATION_NAME_TO_ID[locations.mission_location(mission)]] = f"Story slot {i}"
        hint_data[self.player] = info

    def pace(self) -> dict[str, Any]:
        """Hero level settings the client applies live."""
        o = self.options
        return {"min_level": o.minimum_character_level.value, "catch_up": bool(o.catch_up_levels.value)}

    def mission_reward_plan(self) -> dict[str, Any]:
        """Mission rewards for the client: mode and, when shuffled, record -> record whose vanilla rewards it gives.
        Only missions of the active content take part (the Expansion Pass stays vanilla without include_dlc)."""
        from .data_mission_rewards import has_rewards
        from .data_save import MISSION_RECORD_IDS
        mode = self.options.mission_rewards.value
        if not mode:
            return {"mode": 0}
        dlc = bool(self.options.include_dlc)
        records = sorted({r for name, recs in MISSION_RECORD_IDS.items() for r in recs
                          if (dlc or not name.startswith("EX ")) and has_rewards(r)})
        if mode == MissionRewards.option_none:
            return {"mode": mode, "records": records}
        if not hasattr(self, "_reward_shuffle"):
            sources = list(records)
            self.random.shuffle(sources)
            self._reward_shuffle = dict(zip(records, sources))
        return {"mode": mode, "map": {str(k): v for k, v in self._reward_shuffle.items()}}

    def _dlc_location_ids(self) -> list[int]:
        """This seed's checks in Expansion Pass content (EX challenges, quests, DLC weapons, Koroks in EX challenges,
        and their bonus / per-difficulty checks): the client sends them itself when the DLC isn't installed."""
        import re
        ex = {c.name for c in CHALLENGES if c.is_ex} | {q.name for q in QUESTS if q.is_ex}
        ex |= {w.name for w in WEAPONS if w.dlc} | {n.name for n in LAB_NODES}
        out = []
        for loc in self.multiworld.get_locations(self.player):
            if loc.address is None:
                continue
            name = re.sub(r" \((Bonus \d+|Normal|Hard|Very Hard)\)$", "", loc.name.partition(": ")[2])
            name = re.sub(r" #\d+$", "", name) if loc.name.startswith("Korok: ") else name
            if name in ex:
                out.append(loc.address)
        return sorted(out)

    def goal_quest_pool(self) -> set[str]:
        """Checked quests that count for goal_quests: those you can finish before the goal. A quest that waits for the
        end of the story (at any depth) would lock the goal behind itself."""
        def early(name: str, seen: set[str]) -> bool:
            quest = QUEST_BY_NAME[name]
            if quest.gate in ("HOPE", FINAL_MISSION) or quest.challenge_prereqs:
                return False
            seen.add(name)
            return all(p in seen or early(p, seen) for p in set(quest.quest_prereqs) | set(GAME_QUEST_PREREQS.get(name, ())))
        return {q for q in self.checked_quests if q in self.quest_open_at or early(q, set())}

    def _own_option_names(self) -> list[str]:
        from Options import PerGameCommonOptions
        common = set(PerGameCommonOptions.type_hints)
        return [n for n in self.options_dataclass.type_hints if n not in common]

    def fill_slot_data(self) -> Mapping[str, Any]:
        ids = locations.LOCATION_NAME_TO_ID
        option_names = [
            "side_content", "side_check_density", "include_dlc", "mission_order", "mission_unlocks", "side_missions_per_unlock", "story_pacing", "story_party", "goal", "minimum_character_level", "challenge_logic",
            "weapon_check_logic", "death_link", "combo_upgrades", "sheikah_runes",
        ]
        data = self.options.as_dict(*option_names)
        data["side_content"] = sorted(data["side_content"])
        pace = self.pace()
        data["combo_upgrades"] = getattr(self, "upgrade_copies", {}).get("Combo Upgrade", data["combo_upgrades"])
        data["upgrade_copies"] = dict(getattr(self, "upgrade_copies", {}))
        data["upgrade_copies"].update({name: int(getattr(self.options, option).value) for name, option in GLOBAL_UPGRADES.items()})
        data["quest_reward_items"] = {k: v for k, v in getattr(self, "group_copies", {}).items() if v}
        data["open_quests"] = sorted(getattr(self, "open_quests", ()))
        data["pre_granted"] = dict(getattr(self, "pre_granted", {}))
        data["hero_level_cap"] = int(bool(self.options.hero_level_cap))
        data["goal_banner"] = int(bool(self.options.goal_banner))
        data["mission_rewards"] = self.mission_reward_plan()
        return {
            "world_version": WORLD_VERSION,
            "pace": pace,
            "starting_characters": list(self.starting_characters),
            "starting_unlocks": list(self.starting_unlocks),
            # every option of this world, so Universal Tracker can rebuild the seed without the YAML
            "ut_options": self.options.as_dict(*self._own_option_names()),
            "mission_ids": {m: ids[locations.mission_location(m)] for m in self.mission_order},
            # extra checks sent together with a story clear (items outnumbered the checks)
            "mission_bonus_ids": {m: [ids[locations.bonus_location(m, k)] for k in range(1, n + 1)]
                                  for m, n in getattr(self, "bonus_checks", {}).items()},
            "challenge_bonus_ids": {c: [ids[locations.challenge_bonus_location(c, k)] for k in range(1, n + 1)]
                                    for c, n in self.challenge_bonus_checks.items()},
            # slot (vanilla mission) -> mission that sits there
            "mission_slots": dict(self.slot_to_mission),
            "mission_slot_prerequisites": {s: list(p) for s, p in self.slot_prerequisites.items()},
            "side_missions_required": dict(self.slot_side_required),
            "mission_party_required": {m: list(c) for m, c in self.mission_party.items()},
            # free parties: a mission whose support heroes can't be picked needs one of these heroes (any)
            "mission_party_any": {m: list(c) for m, c in self.party_needs.items()},
            # 0.9.65+: missions opened by another mission's clear instead of an unlock item (the rescues)
            "opened_by_clear": {},  # (0.9.66-0.9.71: the rescues opened with Calamity Strikes' clear)
            "calamity_unlock_item": 1,
            "final_goal": int(bool(self.options.final_mission_goal)),
            "challenge_quests": {c: list(q) for c, q in getattr(self, "challenge_quests", {}).items()},  # Calamity Strikes has an unlock item (mission_unlocks: items) since 0.9.72
            # 0.9.66+: Calamity Strikes opens once all four Champions are yours (no unlock item)
            "opened_by_heroes": {CALAMITY: list(CHAMPIONS)},
            "all_characters": list(self.characters),
            "goal_side_missions": self.goal_side_required,
            "goal_difficulty": self.options.goal_difficulty.value,
            "goal_story_missions": self.options.goal_story_missions.value,
            "goal_challenges": min(self.options.goal_challenges.value, len(self.goal_challenge_pool)),
            "goal_challenge_pool": list(self.goal_challenge_pool),
            "goal_quests": min(self.options.goal_quests.value, len(self.goal_quest_pool())),
            "goal_quest_pool": sorted(self.goal_quest_pool()),
            "dlc_story_missions": list(self.dlc_story),
            "game_mode": self.game_mode,
            "story_chain": list(self.story_chain),
            "post_story_unlock": self.options.post_story_unlock.value,
            # side_unlocks random: challenge/quest -> completions it opens after; what counts as a completion
            "side_unlocks": self.options.side_unlocks.value,
            "challenge_open_at": dict(self.challenge_open_at),
            "quest_open_at": dict(self.quest_open_at),
            "completion_challenges": list(self.active_challenges),
            "completion_quests": list(self.active_quests),
            # quests the logic opens after post_story_unlock clears (gate HOPE); the client opens them in game
            "post_story_quests": sorted(q for q in self.active_quests if QUEST_BY_NAME[q].gate == "HOPE"),
            "boss_rush": list(BOSS_CHALLENGES) if self.boss_goal else [],
            "featured_challenge": self.featured_challenge,
            "hint_every_missions": self.options.mission_hint_every.value,
            "stuck_rescue_minutes": self.options.stuck_rescue_minutes.value,
            "locked_features": sorted(self.options.locked_features.value),
            "final_mission": MISSIONS[-1].name,
            "starter_save": True,
            "rune_items": list(ITEM_RUNES),  # 0.9.58+: the client keeps Remote Bombs on and enforces these three  # the client may install the starter save (skips the forced first mission)
            "first_mission": self.mission_order[0],
            "weapon_ids": {n: ids[locations.weapon_location(n)] for n in self.checked_weapons},
            "challenge_ids": {n: ids[locations.challenge_location(n)] for n in sorted(self.checked_challenges)},
            "quest_ids": {n: ids[locations.quest_location(n)] for n in sorted(self.checked_quests)},
            "lab_ids": {n: ids[locations.lab_location(n)] for n in self.checked_lab},
            "lab_items": dict(self.lab_items),
            "emptied_quests": list(self.emptied_quests),
            "korok_ids": {locations.korok_name(s, i): ids[locations.korok_name(s, i)] for s, _, i in self.checked_koroks},
            # "<mission or challenge> (<difficulty>)" -> id: sent when the game shows it cleared on that difficulty+
            "difficulty_ids": {loc.name.partition(": ")[2]: loc.address for loc in self.multiworld.get_locations(self.player)
                               if getattr(loc, "difficulty_of", None)},
            "difficulty_lock": self.options.difficulty_lock.value,
            "dlc_location_ids": self._dlc_location_ids() if self.options.include_dlc else [],
            **data,
        }
