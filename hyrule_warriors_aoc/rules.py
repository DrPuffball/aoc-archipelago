from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import LocationProgressType, ItemClassification
from worlds.generic.Rules import add_item_rule, set_rule

from .data import BOSS_CHALLENGES, FINAL_MISSION, ITEM_RUNES, MISSION_BY_NAME, RUNE_CHALLENGES, WEAPON_BY_NAME
from .data_challenges import (CALAMITY, CHALLENGE_BY_NAME, CHAMPIONS, GAME_LEVEL, challenge_gate,
                              vanilla_prerequisites)
from .data_chests import CHEST_RUNES, CHEST_RUNES_ALL, DLC_CHESTS, SHARED_CHESTS, chest_location
from .data_koroks import KOROK_RUNES, korok_location
from .data_quest_unlocks import GAME_QUEST_PREREQS
from .data_rewards import ALL_GROUPS, FEATURE_CHALLENGES
from .data_quests import CHAPTER_TWO_MISSIONS, QUEST_BY_NAME
from .items import character_item, rune_item, unlock_item
from .data_lab import (FUTURE_OF_HYRULE, LAB_BY_NAME, LAB_MISSION_CONDITION, LAB_ROD_CONDITION, LAB_RUNE_CONDITION,
                       LAB_WEAPON_CONDITION)
from .locations import (challenge_bonus_location, challenge_location, lab_location, mission_location, quest_location,
                        weapon_location)
from .options import ChallengeLogic, GameMode, Goal, MissionUnlocks, SheikahRunes, StoryParty, WeaponCheckLogic
HOPE_OF_ALL_HYRULE = "The Hope of All Hyrule"
from .regions import POST_STORY_EVENT, STORY_EVENT, VICTORY_EVENT, challenge_event, cleared_event, quest_event

if TYPE_CHECKING:
    from .world import AgeOfCalamityWorld

RUNE_SOURCE = {"Remote Bombs": "The Battle of Hyrule Field", "Cryonis": "The Battle of Hyrule Field",
               "Magnesis": "Road to the Ancient Lab", "Stasis": "Road to the Ancient Lab"}
COMPLETIONS = "Completions"  # world.COMPLETIONS: completion events collected (world.collect keeps the count)

# Logic principle: where the real game's requirements are uncertain, demand *more* than the game
# does (later gates, extra prerequisites). That can only make a seed harder to roll, never impossible.
#
# Story missions need nothing but their prerequisites: the hook lets any party play any story mission, except that
# a mission's support heroes (AI allies) can't be picked, so it needs one other hero (world.party_needs).
# Characters matter only for restricted challenges (and what depends on them) and weapon checks.
# Only progression items may appear in rules; characters are progression whenever side content is on.


def _rule(player: int, all_of=(), any_of=(), count_of=(), count=0):
    all_of, any_of, count_of = tuple(all_of), tuple(any_of), tuple(count_of)

    def rule(state) -> bool:
        return (
            state.has_all(all_of, player)
            and (not any_of or state.has_any(any_of, player))
            and (not count_of or state.has_from_list(count_of, player, count))
        )

    return rule


def _copies_rule(player: int, item: str, copies: int):
    return lambda state: state.has(item, player, copies)


def copies_needed(group, quest: str, copies: int) -> int:
    """Fewest received copies of a reward group's item that stand for this quest (each copy worth its share)."""
    index = group.known.index(quest) + 1
    return -(-index * copies // len(group.known))


def _gate_parts(gate: str):
    """Translate a quest gate into (all_of, any_of, count_of, count)."""
    if gate == "ANY2":
        return [], [cleared_event(m) for m in CHAPTER_TWO_MISSIONS], [], 0
    if gate == "FOUR2":
        return [], [], [cleared_event(m) for m in CHAPTER_TWO_MISSIONS], 4
    if gate == "HOPE":
        return [POST_STORY_EVENT], [], [], 0
    return [cleared_event(gate)], [], [], 0


def lab_needs(world, name: str) -> tuple[list[str], list[str]]:
    """(all of, any of): items and events a lab node's condition needs."""
    from .items import character_item, rune_item, weapon_item
    from .options import SheikahRunes
    all_of, any_of = [], []
    if name in LAB_MISSION_CONDITION:
        mission = LAB_MISSION_CONDITION[name]
        all_of.append(cleared_event(mission) if mission == FUTURE_OF_HYRULE else challenge_event(mission))
    if (name in LAB_RUNE_CONDITION and world.options.sheikah_runes == SheikahRunes.option_shuffled
            and LAB_RUNE_CONDITION[name] in world.item_runes):  # (0.9.58-0.9.88 seeds: Remote Bombs always on)
        all_of.append(rune_item(LAB_RUNE_CONDITION[name]))
    if name in LAB_ROD_CONDITION and world.options.rod_items:
        all_of.append(LAB_ROD_CONDITION[name])
    if name in LAB_WEAPON_CONDITION:
        hero, weapons = LAB_WEAPON_CONDITION[name]
        all_of.append(character_item(hero))
        any_of += [weapon_item(w) for w in weapons]
    return all_of, any_of


def quest_gate_open(gate: str, events: set[str]) -> bool:
    """Plain-Python version of a quest gate, used by generation-time planning."""
    all_of, any_of, count_of, count = _gate_parts(gate)
    return (
        all(e in events for e in all_of)
        and (not any_of or any(e in events for e in any_of))
        and (not count_of or sum(e in events for e in count_of) >= count)
    )


def rune_needs(world: AgeOfCalamityWorld, runes) -> list[str]:
    """What logic needs for these runes: the rune item when shuffled, the clear that hands it out when vanilla, nothing
    with start_with_all (or for a rune that is no item in this seed: Remote Bombs before 0.9.89)."""
    if world.options.sheikah_runes == SheikahRunes.option_shuffled:
        return [rune_item(r) for r in runes if r in world.item_runes]
    if world.options.sheikah_runes == SheikahRunes.option_vanilla:
        return [cleared_event(RUNE_SOURCE[r]) for r in runes]
    return []


def level_gate(name: str) -> str | None:
    """First story mission (vanilla order) whose recommended level reaches the challenge's; None = after the story."""
    return challenge_gate(name, by_level=True) if GAME_LEVEL.get(name) else None


def challenge_requirements(world: AgeOfCalamityWorld, name: str) -> list[str]:
    challenge = CHALLENGE_BY_NAME[name]
    if name in world.dlc_story and world.options.mission_unlocks == MissionUnlocks.option_items:
        required = [unlock_item(name)]  # a DLC story mission opens with its own unlock item, like the base story
    elif name in world.dlc_story and world.story_chain:  # Story Only: the previous mission of the chain
        before = world.chain_before(name)
        required = [cleared_event(before) if before in MISSION_BY_NAME else challenge_event(before)]
    elif name in world.dlc_story:  # story order: the game's own chain (after Calamity Strikes ...), not post-story
        required = [cleared_event(n) if n in MISSION_BY_NAME else challenge_event(n) for n in vanilla_prerequisites(name)]
    elif name in world.challenge_item_unlocks:
        required = [unlock_item(name)]  # challenge_unlock_order items: opens with its own item
    elif name in world.challenge_open_at:
        required = []  # side_unlocks random: opens by completion count (side_open_count), not by a story gate
    else:
        by_level = world.options.challenge_logic == ChallengeLogic.option_by_level
        gate = challenge_gate(name, by_level, world.boss_goal)
        required = [cleared_event(gate) if gate else POST_STORY_EVENT]
    if name in RUNE_CHALLENGES:
        required += rune_needs(world, [RUNE_CHALLENGES[name]])  # (0.9.58-0.9.88 seeds: Remote Bombs always on)
    required += [quest_event(q) for q in world.challenge_quests.get(name, ())]  # the game's own quest gate
    if world.fairy_locked and name in FEATURE_CHALLENGES["Fairy Fountains"]:
        required.append("Feature: Fairy Fountains")
    if world.options.story_party != StoryParty.option_vanilla:  # free: your heroes go in; borrowed: lent
        return required  # (0.9.74, user: challenges open whenever the randomizer says, like the story)
    return required + [character_item(c) for c in challenge.required_characters]


def side_open_count(world: AgeOfCalamityWorld, kind: str, name: str) -> int:
    """side_unlocks random: completions (story clears, challenges, quests) this challenge/quest opens after; 0 = open
    (or not random)."""
    return (world.challenge_open_at if kind == "challenge" else world.quest_open_at).get(name, 0)


def set_all_rules(world: AgeOfCalamityWorld) -> None:
    player = world.player
    victory_needs = tuple(cleared_event(m) for m in world.mission_order)

    # Story slots: a mission is gated by whichever missions sit in the prerequisite slots.
    unlock_items = world.options.mission_unlocks == MissionUnlocks.option_items
    first = world.mission_order[0]
    final_goal = bool(world.options.final_mission_goal)
    for slot, mission in world.slot_to_mission.items():
        if final_goal and mission == FINAL_MISSION:
            continue  # opens when the goal's counts are met (below)
        if unlock_items:  # a mission opens with its unlock item alone (the first one is open from the start)
            required = (unlock_item(mission),) if mission != first else ()
        else:
            required = tuple(cleared_event(world.slot_to_mission[p]) if p in world.slot_to_mission else challenge_event(p)
                             for p in world.slot_prerequisites[slot])  # (Story Only: a DLC story mission can come before)
        required += tuple(character_item(c) for c in world.mission_party.get(mission, ()))
        if mission == CALAMITY:  # also all four Champions yours (a Champion you don't have would be trapped)
            required += tuple(character_item(c) for c in CHAMPIONS)
        party = [character_item(c) for c in world.party_needs.get(mission, ())]  # any hero it lets you pick
        side_needed = world.slot_side_required.get(slot, 0)
        if required or side_needed or party:
            rule = _rule(player, required, party, count_of=world.side_counted if side_needed else (), count=side_needed)
            set_rule(world.get_entrance(f"Start {mission}"), rule)
    set_rule(world.get_entrance("Finish The Story"), _rule(player, victory_needs))
    # Post-story challenges and quests: open after post_story_unlock story clears (20 = the whole story, as vanilla)
    # With final_mission_goal The Future of Hyrule is the goal itself: post-story content opens after the other story
    # missions, or a goal needing challenges or side missions would wait on itself (option fuzz 2026-11-02: 4 of 300
    # random combinations were unbeatable that way).
    post_events = victory_needs if not final_goal else tuple(e for e in victory_needs if e != cleared_event(FINAL_MISSION))
    post_needed = min(world.options.post_story_unlock.value, len(post_events))
    set_rule(world.get_entrance("Open Post-Story Content"),
             lambda state: sum(state.has(e, player) for e in post_events) >= post_needed)
    # The goal: goal_story_missions story clears (any of them; 20 = all) plus the goal option's extras.
    # Story missions for the goal: the 20 (in their slots) plus, with include_dlc, Guardian of Remembrance's 8
    story_events = victory_needs + tuple(challenge_event(c) for c in world.dlc_story)
    story_needed = min(world.options.goal_story_missions.value, len(story_events))
    if world.game_mode == GameMode.option_challenges_only:
        story_needed = 0  # the goal is challenges alone
    goal_all = []
    if world.options.goal == Goal.option_story_and_all_characters:
        goal_all += [character_item(c) for c in world.characters]
    if world.boss_goal:
        goal_all += [challenge_event(c) for c in BOSS_CHALLENGES]
    hope_all = []
    if world.options.goal_hope_of_all_hyrule:  # 100% map: every hero, challenge and quest of the seed, after the story
        hope_all = [POST_STORY_EVENT, *(character_item(c) for c in world.characters),
                    *(challenge_event(c) for c in world.active_challenges if c not in world.dlc_story),
                    *(quest_event(q) for q in world.active_quests if q != HOPE_OF_ALL_HYRULE)]
    # (Some of that content opens only after The Future of Hyrule, so with final_mission_goal the 100% map comes after
    # its clear, not before: fuzz 2026-11-14, 10 of 32 Hope seeds were unbeatable the other way.)
    hope = _rule(player, hope_all)
    goal_count = world.goal_side_required
    extras = _rule(player, goal_all, count_of=world.side_counted if goal_count else (), count=goal_count)
    challenge_events = [challenge_event(c) for c in world.goal_challenge_pool]
    if final_goal:
        # (fuzz 2026-11-19, seed 9017: challenge_unlock_order vanilla gates the hardest challenges on The Future of
        # Hyrule's clear, so "every challenge before The Future of Hyrule" could never be met.) Those don't count
        # towards opening it; goal_challenges is lowered to what can (slot_data carries it to the client).
        before = [c for c in world.goal_challenge_pool
                  if cleared_event(FINAL_MISSION) not in challenge_requirements(world, c)]
        if world.options.goal_challenges.value > len(before):
            import logging
            logging.warning("%s: goal_challenges %d lowered to %d (challenges open before The Future of Hyrule).",
                            world.player_name, world.options.goal_challenges.value, len(before))
            world.options.goal_challenges.value = len(before)
    challenges_needed = min(world.options.goal_challenges.value, len(challenge_events))
    quest_events = [quest_event(q) for q in sorted(world.goal_quest_pool())]
    quests_needed = min(world.options.goal_quests.value, len(quest_events))
    if final_goal:  # The Future of Hyrule opens after goal_story_missions - 1 other clears (+ challenges, extras)
        others = tuple(e for e in story_events if e != cleared_event(FINAL_MISSION))
        heroes = _rule(player, tuple(character_item(c) for c in world.mission_party.get(FINAL_MISSION, ())),
                       [character_item(c) for c in world.party_needs.get(FINAL_MISSION, ())])
        set_rule(world.get_entrance(f"Start {FINAL_MISSION}"),
                 lambda state: extras(state) and heroes(state)
                 and sum(state.has(e, player) for e in others) >= story_needed - 1
                 and sum(state.has(e, player) for e in challenge_events) >= challenges_needed
                 and sum(state.has(e, player) for e in quest_events) >= quests_needed)
        set_rule(world.get_entrance("Finish All Main Missions"),
                 lambda state: state.has(cleared_event(FINAL_MISSION), player) and hope(state))
    else:
        set_rule(world.get_entrance("Finish All Main Missions"),
                 lambda state: extras(state) and hope(state) and sum(state.has(e, player) for e in story_events) >= story_needed
                 and sum(state.has(e, player) for e in challenge_events) >= challenges_needed
                 and sum(state.has(e, player) for e in quest_events) >= quests_needed)
    world.multiworld.completion_condition[player] = lambda state: state.has(VICTORY_EVENT, player)

    for name in world.active_challenges:
        opens = side_open_count(world, "challenge", name)
        rule = _rule(player, challenge_requirements(world, name), count_of=(COMPLETIONS,) if opens else (), count=opens)
        set_rule(world.get_location(f"Event: Challenge {name}"), rule)
        if name in world.checked_challenges:
            set_rule(world.get_location(challenge_location(name)), rule)
            for k in range(1, world.challenge_bonus_checks.get(name, 0) + 1):  # sent with the challenge's clear
                set_rule(world.get_location(challenge_bonus_location(name, k)), rule)

    # Lab nodes are open from the start (client): the logic asks for some play first for the materials, deeper nodes more,
    # and for what the node's own condition needs (lab_needs).
    for name in world.checked_lab:
        opens = LAB_BY_NAME[name].tier
        all_of, any_of = lab_needs(world, name)
        set_rule(world.get_location(lab_location(name)),
                 _rule(player, all_of, any_of, count_of=(COMPLETIONS,) if opens else (), count=opens))

    for name in world.active_quests:
        quest = QUEST_BY_NAME[name]
        if name in world.quest_open_at:  # side_unlocks random: opened by completion count, game gates ignored
            opens = side_open_count(world, "quest", name)
            rule = _rule(player, count_of=(COMPLETIONS,) if opens else (), count=opens)
        else:
            all_of, any_of, count_of, count = _gate_parts(quest.gate)
            all_of = all_of + [quest_event(q) for q in quest.quest_prereqs]
            all_of = all_of + [challenge_event(c) for c in quest.challenge_prereqs]
            rule = _rule(player, all_of, any_of, count_of, count)

        def both(first, second):
            return lambda state: first(state) and second(state)

        def copies_for(item: str, quest: str):
            return _copies_rule(player, item, copies_needed(ALL_GROUPS[item], quest, world.group_copies[item]))

        for pre in () if name in world.quest_open_at else GAME_QUEST_PREREQS.get(name, ()):  # the game only shows this quest once these are done in game
            locker = world.item_quests.get(pre) or world.unlock_quests.get(pre)
            if locker in world.reward_progression:
                rule = both(rule, copies_for(locker, pre))
        item = world.unlock_quests.get(name)  # kept locked by the client until its item arrives
        if item in world.reward_progression:
            rule = both(rule, copies_for(item, name))
        if name in world.checked_quests:
            set_rule(world.get_location(quest_location(name)), rule)  # buying it is the check
        item = world.item_quests.get(name)  # shop/stable/Smithy: done in game (service open) only with its item too
        if item in world.reward_progression:
            rule = both(rule, copies_for(item, name))
        set_rule(world.get_location(f"Event: Quest {name}"), rule)

    for source, kind, index in world.checked_koroks:
        gate = cleared_event(source) if kind == "mission" else challenge_event(source)  # also its unlock (item)
        needs = [gate] + rune_needs(world, KOROK_RUNES.get(source, ()))  # a rune never sits behind itself
        set_rule(world.get_location(korok_location(source, index)), _rule(player, needs))
    for mission, index in world.checked_chests:
        runes = rune_needs(world, CHEST_RUNES_ALL + CHEST_RUNES.get(mission, ()))  # half-buried chests: Magnesis
        if mission in DLC_CHESTS:  # an Expansion Pass story mission (a challenge to the world); a shared stage: either one
            other = SHARED_CHESTS.get(mission)
            events = [challenge_event(mission)] + ([challenge_event(other)] if other in world.active_challenges else [])
            set_rule(world.get_location(chest_location(mission, index)), _rule(player, runes, any_of=events))
        else:
            set_rule(world.get_location(chest_location(mission, index)), _rule(player, [cleared_event(mission)] + runes))

    optimistic = world.options.weapon_check_logic == WeaponCheckLogic.option_after_character
    for name in world.checked_weapons:
        weapon = WEAPON_BY_NAME[name]
        gate = cleared_event(weapon.gate_mission) if (weapon.verified or optimistic) else STORY_EVENT
        needs = [gate] + ([character_item(weapon.character)] if weapon.character else [])
        set_rule(world.get_location(weapon_location(name)), _rule(player, needs))
    set_progress_rules(world)


def hero_level_gate(level: int) -> str:
    """The event a hero (or weapon) level expects first: the first story mission (by its recommended level,
    data_challenges.STORY_LEVEL) at or above that level; past the story's levels, the whole story."""
    from .data_challenges import STORY_LEVEL
    mission = next((m for m, lv in STORY_LEVEL.items() if lv >= level), None)
    return cleared_event(mission) if mission else STORY_EVENT


def story_progress_rule(world: AgeOfCalamityWorld, events: list[str], extra=()):
    """A rule for "this far into the story" (story clear events, any one of them; STORY_EVENT = the whole story).
    Challenges Only has no story (fuzz 2026-11-19: every progress check there was unreachable): there it is that share
    of the seed's challenge clears instead - the gate mission's place in the vanilla story (1-20, the whole story 21)
    out of 21, times the challenges in the seed."""
    from .data import MISSIONS as _M
    player = world.player
    if world.game_mode != GameMode.option_challenges_only:
        return _rule(player, list(extra), any_of=events)
    order = [m.name for m in _M]
    places = [order.index(e[len("Cleared: "):]) + 1 if e.startswith("Cleared: ") and e[len("Cleared: "):] in order
              else len(order) + 1 for e in events] or [len(order) + 1]
    # (scaled to the goal's challenge count, and always below it: fuzz seed 9135, goal = every challenge, put the
    # "whole story" checks exactly at the goal, after the win)
    goal = min(world.options.goal_challenges.value, len(world.goal_challenge_pool)) or len(world.goal_challenge_pool)
    need = goal * min(places) // (len(order) + 2)
    return _rule(player, list(extra), count_of=(COMPLETIONS,) if need else (), count=need)


def gather_gate(world: AgeOfCalamityWorld, enemy: str, tier: int) -> list[str]:
    """Events of which any one lets the logic count on meeting an enemy for a gathering tier (data_progress)."""
    from . import data_progress as progress
    source = progress.ENEMIES[enemy][2]
    gates = progress.SOURCE_GATES.get(source)
    if gates is not None:
        mission = gates[tier - 1]
        return [cleared_event(mission) if mission else STORY_EVENT]
    events = [challenge_event(source)] if source in world.active_challenges else []  # a challenge built around it
    return events + ([STORY_EVENT] if enemy in progress.ALSO_IN_STORY else [])


def set_progress_rules(world: AgeOfCalamityWorld) -> None:
    """0.9.90 progress checks: hero levels, weapon levels, enemies defeated, materials gathered (data_progress)."""
    from . import data_progress as progress
    player = world.player
    for hero, level in world.checked_hero_levels:
        set_rule(world.get_location(progress.hero_level_location(hero, level)),
                 story_progress_rule(world, [hero_level_gate(level)], [character_item(hero)]))
    fusion = ["Weapon Fusion"] if world.options.weapon_fusion else []  # (the Smithy opens with it; world: progression)
    for hero, level in world.checked_weapon_levels:
        needs = [character_item(hero)] + fusion
        if level > 20:  # the game's weapon level cap is raised by these quests (their events include their items)
            needs.append(quest_event("A Monumental Undertaking"))
        if level > 25:
            needs.append(quest_event("The Legendary Blacksmith"))
        set_rule(world.get_location(progress.weapon_level_location(hero, level)),
                 story_progress_rule(world, [hero_level_gate(level)], needs))
    for material, tier in world.checked_gathered:
        _, _, (kind, source) = progress.MATERIALS[material]
        loc = world.get_location(progress.gathered_location(material, tier))
        if kind == "missions":  # its story missions give it again on every clear: any of them, replayed
            set_rule(loc, _rule(player, any_of=[cleared_event(m) for m in source]))
        else:
            set_rule(loc, _gather_rule(world, source, tier))
    for enemy, tier in world.checked_defeated:
        set_rule(world.get_location(progress.defeated_location(enemy, tier)), _gather_rule(world, enemy, tier))


def _gather_rule(world: AgeOfCalamityWorld, enemy: str, tier: int):
    """An enemy met through the story (Challenges Only: through challenge clears) or its own challenge."""
    events = gather_gate(world, enemy, tier)
    story = [e for e in events if e.startswith("Cleared: ") or e == STORY_EVENT]
    if world.game_mode != GameMode.option_challenges_only or not story:
        return _rule(world.player, any_of=events)
    by_story = story_progress_rule(world, story)
    own = [e for e in events if e not in story]
    return lambda state: by_story(state) or (bool(own) and state.has_any(own, world.player))


def apply_steady_rewards(world: AgeOfCalamityWorld) -> None:
    """Story clears never hold this player's own filler, so every clear pays out something real."""
    if not world.options.steady_rewards:
        return
    player = world.player
    real = sum(
        1 for item in world.multiworld.itempool
        if item.player == player and item.classification != ItemClassification.filler
    )
    missions = len(world.mission_order)
    if real < missions + 5:  # not enough real items of our own to keep every clear (and the fill) feasible
        return
    for mission in world.mission_order[world.first_real_slot:]:  # (a pre-cleared Hyrule Field holds a locked filler)
        if not world.clear_checked(mission):
            continue  # the goal mission's clear: no check
        location = world.get_location(mission_location(mission))
        if location.progress_type == LocationProgressType.EXCLUDED:
            continue  # after the goal: filler only
        add_item_rule(
            location,
            lambda item, p=player: item.player != p or item.classification != ItemClassification.filler,
        )
