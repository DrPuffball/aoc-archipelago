"""
Story pacing. The plain Archipelago fill puts items wherever it likes, and since most locations unlock late,
heroes and upgrades pile up near the end. This pass places a share of the "power" items (heroes, upgrades,
features, weapons) into locations spread evenly across the story, so you get a steady stream of rewards.

A location's *stage* is how far into the story it unlocks: 1..20 is the story slot whose clear opens it, 21 is
post-story. Only locations that need no particular character are used, so placing a hero can never lock itself.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from BaseClasses import CollectionState, LocationProgressType
from Fill import fill_restrictive
from worlds.generic.Rules import add_item_rule

from .data import LEVEL_BAND_GATES
from .data_challenges import CHALLENGE_BY_NAME
from .data_chests import chest_location
from .data_koroks import korok_location
from .data_quests import CHAPTER_TWO_MISSIONS, QUEST_BY_NAME
from .items import UNLOCK_PREFIX
from .regions import VICTORY_EVENT, cleared_event
from .locations import mission_location, quest_location
from .options import ChallengeLogic, MissionUnlocks

if TYPE_CHECKING:
    from .world import AgeOfCalamityWorld

POST_STORY = 21


def _slot(world: AgeOfCalamityWorld, mission: str) -> int:
    return world.mission_order.index(mission) + 1


def challenge_stage(world: AgeOfCalamityWorld, name: str) -> int:
    if world.options.challenge_logic == ChallengeLogic.option_by_level:
        gate = LEVEL_BAND_GATES[CHALLENGE_BY_NAME[name].band]
        return _slot(world, gate) if gate else POST_STORY
    return POST_STORY


def quest_stage(world: AgeOfCalamityWorld, name: str, _seen: frozenset = frozenset()) -> int:
    quest = QUEST_BY_NAME[name]
    gate = quest.gate
    if gate == "HOPE":
        stage = POST_STORY
    elif gate == "ANY2":
        stage = min(_slot(world, m) for m in CHAPTER_TWO_MISSIONS)
    elif gate == "FOUR2":
        stage = sorted(_slot(world, m) for m in CHAPTER_TWO_MISSIONS)[3]
    else:
        stage = _slot(world, gate)
    parts = [stage]
    parts += [quest_stage(world, q, _seen | {name}) for q in quest.quest_prereqs if q not in _seen]
    parts += [challenge_stage(world, c) for c in quest.challenge_prereqs]
    return max(parts)


def quest_needs_characters(name: str, _seen: frozenset = frozenset()) -> bool:
    quest = QUEST_BY_NAME[name]
    if any(CHALLENGE_BY_NAME[c].required_characters for c in quest.challenge_prereqs):
        return True
    return any(quest_needs_characters(q, _seen | {name}) for q in quest.quest_prereqs if q not in _seen)


def candidate_locations(world: AgeOfCalamityWorld) -> dict[str, int]:
    """Character-free locations of this world and their stages."""
    stages: dict[str, int] = {}
    for mission in world.mission_order:
        party = world.mission_party.get(mission, ())
        if not party and world.clear_checked(mission):
            stages[mission_location(mission)] = _slot(world, mission)
    for name in () if world.quest_random else world.checked_quests:  # random quest unlocks: no story stage
        if not quest_needs_characters(name):
            stages[quest_location(name)] = quest_stage(world, name)
    for source, kind, index in world.checked_koroks:
        if kind == "mission" and not world.mission_party.get(source, ()):
            stages[korok_location(source, index)] = _slot(world, source)
    for mission, index in world.checked_chests:
        if mission in world.mission_order and not world.mission_party.get(mission, ()):
            stages[chest_location(mission, index)] = _slot(world, mission)
    return stages


def front_load(world: AgeOfCalamityWorld) -> None:
    percent = world.options.story_pacing.value
    if world.options.mission_unlocks == MissionUnlocks.option_items:
        return  # stages follow the story order, which unlock items replace
    if not percent or world.mission_party or world.party_needs:
        # With story_party: vanilla (or a mission that needs a hero the starters can't cover) the heroes already gate
        # the story, so it paces itself; and spending the few early checks on anything else could starve the heroes
        # the story needs.
        return
    player = world.player
    pool = world.multiworld.itempool
    # useful items only: progression (heroes, the Champions Calamity Strikes needs) is left to the normal fill, which
    # can't strand them (placing them here sometimes failed generation once Calamity Strikes needed the Champions)
    power = [i for i in pool if i.player == player and not i.filler and not i.advancement]
    if not power:
        return
    stages = candidate_locations(world)
    free = {
        loc.name: loc for loc in world.multiworld.get_unfilled_locations(player)
        if loc.name in stages and loc.progress_type != LocationProgressType.EXCLUDED
    }
    if not free:
        return
    by_stage: dict[int, list[str]] = {}
    for name, loc in free.items():
        by_stage.setdefault(stages[name], []).append(name)
    for names in by_stage.values():
        names.sort()
    world.random.shuffle(power)
    count = min(len(power), round(len(power) * percent / 100), len(free))

    # Progression items (heroes, when logic uses them) are placed with the real fill so they can never be
    # locked behind themselves. The base state holds everything except the items about to be placed.
    multiworld = world.multiworld
    # Built from scratch (not by removing items from an all-items state, which would leave swept events behind).
    placing = {id(i) for i in power if i.advancement}
    base_state = CollectionState(multiworld)
    for item in pool:
        if item.advancement and id(item) not in placing:
            base_state.collect(item, True)
    base_state.sweep_for_advancements()

    # Even share per story stage, capped by the stage's free checks (a stage whose checks come after the goal, e.g.
    # the last one, holds fewer); the rest is spread over the other stages.
    room = {st: len(names) for st, names in by_stage.items() if st <= 20}
    share = dict.fromkeys(room, 0)
    left = min(count, sum(room.values()))
    while left:
        open_stages = sorted(st for st in room if share[st] < room[st])
        each = max(1, left // len(open_stages))
        for st in open_stages:
            give = min(each, room[st] - share[st], left)
            share[st] += give
            left -= give
            if not left:
                break
    targets = [st for st in sorted(share) for _ in range(share[st])]
    assignments = [(targets[k] if k < len(targets) else 20, power[k]) for k in range(count)]
    # Progression first, so useful items can never crowd it out of the early checks it needs.
    assignments.sort(key=lambda pair: not pair[1].advancement)
    leftover = sum(1 for i in power if i.advancement)
    # Checks reachable before any unplaced progression is found: the only places leftover heroes can still go.
    reachable = {n for n, loc in free.items() if loc.can_reach(base_state)}

    def choose(target: int, item) -> str | None:
        """Nearest-stage free check for this item (or None)."""
        reach_left = sum(1 for names in by_stage.values() for n in names if n in reachable)
        for stage in sorted((s for s in by_stage if s <= 20), key=lambda s: (s > target, abs(s - target))):
            names = by_stage[stage]
            if item.advancement:
                names = [n for n in names if n in reachable]
            elif reach_left <= leftover + 2:
                names = [n for n in names if n not in reachable]
            if names:
                # Story clears first, so every clear pays out before side checks take their share.
                clears = [n for n in names if n.startswith("Clear: ")]
                return clears[0] if clears else world.random.choice(names)
        return None

    for target, item in assignments:
        loc_name = choose(target, item)
        if loc_name is None:
            continue
        location = free[loc_name]
        if item.advancement:
            attempt = [item]
            fill_restrictive(multiworld, base_state, [location], attempt, single_player_placement=True,
                             swap=False, lock=True, allow_partial=True, name="AoC story pacing")
            if attempt:  # could not be placed there safely; leave it to the normal fill
                by_stage[stages[loc_name]].remove(loc_name)
                continue
            leftover -= 1
        else:
            location.place_locked_item(item)
        for names in by_stage.values():
            if loc_name in names:
                names.remove(loc_name)
        # Items compare equal by name, so remove this exact object, not an equal one.
        del pool[next(n for n, it in enumerate(pool) if it is item)]


def exclude_post_goal(world: AgeOfCalamityWorld) -> list[str]:
    """No check that only opens after the win condition may hold anything: such checks are excluded (filler only).
    Pre-goal = reachable with everything collected except whatever would finish the goal: events are collected in
    story slot order first and one that would meet the goal is held back (so for "any N story missions" the
    missions past the Nth slot, the whole-story weapon drops, and post-story content opening after the goal count
    as post-goal). When there is too little filler for them, extra bonus checks on pre-goal story clears and as much
    filler are added, so every other item still has a pre-goal check. Returns the excluded location names."""
    multiworld, player = world.multiworld, world.player
    finish = world.get_entrance("Finish All Main Missions")
    state = CollectionState(multiworld)
    for item in multiworld.itempool:
        if item.player == player and item.advancement:
            state.collect(item, True)
    for loc in multiworld.get_filled_locations(player):
        if loc.address is not None and loc.item and loc.item.advancement and loc.item.player == player:
            state.collect(loc.item, True, loc)
    slot_of = {cleared_event(m): i for i, m in enumerate(world.mission_order)}
    events = sorted((loc for loc in multiworld.get_locations(player)
                     if loc.address is None and loc.item and loc.item.name != VICTORY_EVENT),
                    key=lambda loc: slot_of.get(loc.item.name, len(slot_of)))
    held: set[str] = set()
    changed = True
    while changed:
        changed = False
        for loc in events:
            name = loc.item.name
            if name in held or state.has(name, player) or not loc.can_reach(state):
                continue
            state.collect(loc.item, True, loc)
            if finish.access_rule(state):  # this one would finish the goal: it only happens after winning
                state.remove(loc.item)
                held.add(name)
            else:
                changed = True
    post_goal = [loc for loc in multiworld.get_locations(player)
                 if loc.address is not None and not loc.item and not loc.can_reach(state)]
    # Bonus checks on story clears past the goal only hold filler: take them out and give that many back to pre-goal
    # clears instead, evenly (user, 2026-11-15: 10 on late missions, 16-18 on the rest).
    moved = _drop_post_goal_bonus(world, post_goal)
    if moved:
        post_goal = [loc for loc in post_goal if loc.parent_region is not None]
    filler = sum(1 for i in multiworld.itempool if i.player == player and i.filler)
    shortage = len(post_goal) - filler
    reachable = [m for m in world.mission_order
                 if world.clear_checked(m) and world.get_location(mission_location(m)).can_reach(state)]
    from .locations import challenge_location  # the DLC story missions are story missions too: same share
    reachable += [c for c in getattr(world, "dlc_story", ()) if world.get_location(challenge_location(c)).can_reach(state)]
    if moved:  # the dropped bonus checks come back on pre-goal clears (their items still need room)
        add_more_bonus_checks(world, reachable, moved)
    if shortage > 0:  # more bonus checks before the goal, each with a filler item
        added = add_more_bonus_checks(world, reachable, shortage)
        multiworld.itempool += [world.create_item(world.get_filler_item_name()) for _ in range(added)]
        filler += added
        if added < shortage:
            logging.warning("%s: %d post-goal checks, filler for %d; the rest may hold items.", world.player_name,
                            len(post_goal), filler)
    world.random.shuffle(post_goal)
    # story clears past the goal first (latest slot first): they are the checks a player reaches last, so with too
    # little filler for every post-goal check, those are the ones that must not hold items
    slot = {mission_location(m): i for i, m in enumerate(world.mission_order)}
    post_goal.sort(key=lambda loc: -slot.get(loc.name, -1))
    excluded = []
    own_only = bool(world.options.local_filler)
    for loc in post_goal[:filler]:
        loc.progress_type = LocationProgressType.EXCLUDED
        if own_only:  # local_filler keeps our filler here, so other worlds' filler mustn't take these spots: the
            # excluded fill draws from every world's filler, and one of ours was left with nowhere to go (fuzz
            # 2026-11-14: "No more spots to place 1 items", a 3-player seed)
            add_item_rule(loc, lambda item, p=player: item.player == p)
        excluded.append(loc.name)
    return excluded


def _drop_post_goal_bonus(world: AgeOfCalamityWorld, post_goal: list) -> int:
    """Remove story-clear bonus checks that are post-goal (all of a mission's, so numbering stays 1..n). Returns how
    many were removed (their region link is cleared)."""
    from .locations import bonus_location
    names = {loc.name for loc in post_goal}
    removed = 0
    for mission, n in list(getattr(world, "bonus_checks", {}).items()):
        if not n or bonus_location(mission, 1) not in names:
            continue
        region = world.get_region(mission)
        for k in range(1, n + 1):
            loc = world.get_location(bonus_location(mission, k))
            if loc.item is None and loc in region.locations:
                region.locations.remove(loc)
                world.multiworld.regions.location_cache[world.player].pop(loc.name, None)
                loc.parent_region = None
                removed += 1
        del world.bonus_checks[mission]
    return removed


def _bonus_count(world: AgeOfCalamityWorld, name: str) -> int:
    if name in getattr(world, "dlc_story", ()):
        return world.challenge_bonus_checks.get(name, 0)
    return world.bonus_checks.get(name, 0)


def add_more_bonus_checks(world: AgeOfCalamityWorld, missions: list[str], count: int) -> int:
    """Up to `count` more bonus checks spread over these story clears (BONUS_PER_MISSION each at most)."""
    from .locations import BONUS_PER_MISSION, bonus_location, challenge_bonus_location, create_location
    missions = [m for m in missions if m not in world.mission_order[:world.first_real_slot]]  # (a pre-cleared HF)
    added = 0
    while added < count:  # always the clear with the fewest so far: they come out even
        open_missions = [m for m in missions if _bonus_count(world, m) < BONUS_PER_MISSION]
        if not open_missions:
            break
        mission = min(open_missions, key=lambda m: _bonus_count(world, m))
        if mission in getattr(world, "dlc_story", ()):  # a DLC story mission (a challenge record): its bonus list
            k = world.challenge_bonus_checks.get(mission, 0) + 1
            create_location(world, world.get_region("Side Content"), challenge_bonus_location(mission, k))
            world.challenge_bonus_checks[mission] = k
        else:
            k = world.bonus_checks.get(mission, 0) + 1
            create_location(world, world.get_region(mission), bonus_location(mission, k))
            world.bonus_checks[mission] = k
        added += 1
    return added


def place_local_filler(world: AgeOfCalamityWorld) -> None:
    """local_filler: put this world's filler into its own checks before the main fill. The option makes the filler
    local (it may only go into this world's checks), but nothing else keeps room for it: in a multiworld the other
    worlds' items can take every one of our checks first, leaving our filler nowhere to go (fuzz 2026-11-20, a
    3-player seed: "No more spots to place 10 items", our filler refused by the last 11 checks of the others).
    Filler never matters to logic, so placing it first is safe. Excluded (post-goal) checks take it first, then
    random checks that accept it (story clears with steady_rewards don't); priority checks are left for the fill."""
    multiworld, player = world.multiworld, world.player
    if not world.options.local_filler or multiworld.players == 1:
        return  # (alone, every check is ours: the counts match)
    filler = [i for i in multiworld.itempool if i.player == player and i.filler]
    if not filler:
        return
    free = [loc for loc in multiworld.get_unfilled_locations(player)
            if loc.address is not None and loc.progress_type != LocationProgressType.PRIORITY]
    world.random.shuffle(free)
    free.sort(key=lambda loc: loc.progress_type != LocationProgressType.EXCLUDED)  # excluded first (stable sort)
    world.random.shuffle(filler)
    for loc in free:
        if not filler:
            break
        item = next((i for i in filler if loc.can_fill(multiworld.state, i, False)), None)
        if item is None:
            continue
        loc.place_locked_item(item)
        loc.locked = False  # (an ordinary check: collect/release treat it as any other)
        filler.remove(item)
        multiworld.itempool.remove(item)


def ensure_room(world: AgeOfCalamityWorld) -> None:
    """Every progression item of this world must fit in a check that can be reached before the story is beaten
    (after it, most checks need a hero, so a hero there could lock itself away). When there are fewer such checks
    than progression items (e.g. weapons-only side content with mission unlock items), the surplus is given at the
    start of the run instead, heroes first so mission unlocks stay checks, and filler takes its place in the pool."""
    multiworld, player = world.multiworld, world.player
    mine = [i for i in multiworld.itempool if i.player == player and i.advancement]
    state = CollectionState(multiworld)
    for item in multiworld.itempool:
        if item.advancement:
            state.collect(item, True)
    for loc in multiworld.get_filled_locations():
        if loc.item and loc.item.advancement and loc.item.name != VICTORY_EVENT:
            state.collect(loc.item, True, loc)
    room = sum(1 for loc in multiworld.get_unfilled_locations(player)
               if loc.can_reach(state) and loc.progress_type != LocationProgressType.EXCLUDED)
    surplus = len(mine) - (room - 2)  # keep a little slack for the fill
    if surplus <= 0:
        return
    mine.sort(key=lambda i: i.name.startswith(UNLOCK_PREFIX))  # heroes and others first, unlocks last
    for item in mine[:surplus]:
        multiworld.itempool.remove(item)
        multiworld.push_precollected(item)
        multiworld.itempool.append(world.create_item(world.get_filler_item_name()))
