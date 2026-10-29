from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import LocationProgressType, ItemClassification
from worlds.generic.Rules import add_item_rule, set_rule

from .data import BOSS_CHALLENGES, ITEM_RUNES, RUNE_CHALLENGES, WEAPON_BY_NAME
from .data_challenges import CALAMITY, CHALLENGE_BY_NAME, CHAMPIONS, GAME_LEVEL, RESCUES, challenge_gate
from .data_koroks import korok_location
from .data_quest_unlocks import GAME_QUEST_PREREQS
from .data_rewards import ALL_GROUPS, FEATURE_CHALLENGES
from .data_quests import CHAPTER_TWO_MISSIONS, QUEST_BY_NAME
from .items import character_item, rune_item, unlock_item
from .locations import challenge_bonus_location, challenge_location, mission_location, quest_location, weapon_location
from .options import ChallengeLogic, Goal, MissionUnlocks, SheikahRunes, WeaponCheckLogic
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


def quest_gate_open(gate: str, events: set[str]) -> bool:
    """Plain-Python version of a quest gate, used by generation-time planning."""
    all_of, any_of, count_of, count = _gate_parts(gate)
    return (
        all(e in events for e in all_of)
        and (not any_of or any(e in events for e in any_of))
        and (not count_of or sum(e in events for e in count_of) >= count)
    )


def level_gate(name: str) -> str | None:
    """First story mission (vanilla order) whose recommended level reaches the challenge's; None = after the story."""
    return challenge_gate(name, by_level=True) if GAME_LEVEL.get(name) else None


def challenge_requirements(world: AgeOfCalamityWorld, name: str) -> list[str]:
    challenge = CHALLENGE_BY_NAME[name]
    if name in world.challenge_open_at:
        required = []  # side_unlocks random: opens by completion count (side_open_count), not by a story gate
    else:
        by_level = world.options.challenge_logic == ChallengeLogic.option_by_level
        gate = challenge_gate(name, by_level, world.boss_goal)
        required = [cleared_event(gate) if gate else POST_STORY_EVENT]
    if name in RUNE_CHALLENGES:
        rune = RUNE_CHALLENGES[name]
        if world.options.sheikah_runes == SheikahRunes.option_shuffled and rune in ITEM_RUNES:
            required.append(rune_item(rune))  # (Remote Bombs is always on: the client keeps the Slate)
        if world.options.sheikah_runes == SheikahRunes.option_vanilla:  # the game hands it out in that mission
            required.append(cleared_event(RUNE_SOURCE[rune]))
    if world.fairy_locked and name in FEATURE_CHALLENGES["Fairy Fountains"]:
        required.append("Feature: Fairy Fountains")
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
    for slot, mission in world.slot_to_mission.items():
        if mission == CALAMITY:  # opens once all four Champions are yours (they can't be trapped then)
            required = tuple(character_item(c) for c in CHAMPIONS)
            if not unlock_items:
                required += tuple(cleared_event(world.slot_to_mission[p]) for p in world.slot_prerequisites[slot])
        elif unlock_items and mission in RESCUES:  # opened by Calamity Strikes' clear (no unlock item)
            required = (cleared_event(CALAMITY),)
        elif unlock_items:  # a mission opens with its unlock item alone (the first one is open from the start)
            required = (unlock_item(mission),) if mission != first else ()
        else:
            required = tuple(cleared_event(world.slot_to_mission[p]) for p in world.slot_prerequisites[slot])
        required += tuple(character_item(c) for c in world.mission_party.get(mission, ()))
        party = [character_item(c) for c in world.party_needs.get(mission, ())]  # any hero it lets you pick
        side_needed = world.slot_side_required.get(slot, 0)
        if required or side_needed or party:
            rule = _rule(player, required, party, count_of=world.side_counted if side_needed else (), count=side_needed)
            set_rule(world.get_entrance(f"Start {mission}"), rule)
    set_rule(world.get_entrance("Finish The Story"), _rule(player, victory_needs))
    # Post-story challenges and quests: open after post_story_unlock story clears (20 = the whole story, as vanilla)
    post_needed = min(world.options.post_story_unlock.value, len(victory_needs))
    set_rule(world.get_entrance("Open Post-Story Content"),
             lambda state: sum(state.has(e, player) for e in victory_needs) >= post_needed)
    # The goal: goal_story_missions story clears (any of them; 20 = all) plus the goal option's extras.
    story_needed = min(world.options.goal_story_missions.value, len(victory_needs))
    goal_all = []
    if world.options.goal == Goal.option_story_and_all_characters:
        goal_all += [character_item(c) for c in world.characters]
    if world.boss_goal:
        goal_all += [challenge_event(c) for c in BOSS_CHALLENGES]
    goal_count = world.goal_side_required
    extras = _rule(player, goal_all, count_of=world.side_counted if goal_count else (), count=goal_count)
    challenge_events = [challenge_event(c) for c in world.goal_challenge_pool]
    challenges_needed = min(world.options.goal_challenges.value, len(challenge_events))
    set_rule(world.get_entrance("Finish All Main Missions"),
             lambda state: extras(state) and sum(state.has(e, player) for e in victory_needs) >= story_needed
             and sum(state.has(e, player) for e in challenge_events) >= challenges_needed)
    world.multiworld.completion_condition[player] = lambda state: state.has(VICTORY_EVENT, player)

    for name in world.active_challenges:
        opens = side_open_count(world, "challenge", name)
        rule = _rule(player, challenge_requirements(world, name), count_of=(COMPLETIONS,) if opens else (), count=opens)
        set_rule(world.get_location(f"Event: Challenge {name}"), rule)
        if name in world.checked_challenges:
            set_rule(world.get_location(challenge_location(name)), rule)
            for k in range(1, world.challenge_bonus_checks.get(name, 0) + 1):  # sent with the challenge's clear
                set_rule(world.get_location(challenge_bonus_location(name, k)), rule)

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

        for pre in () if world.side_random else GAME_QUEST_PREREQS.get(name, ()):  # the game only shows this quest once these are done in game
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
        gate = cleared_event(source) if kind == "mission" else challenge_event(source)
        set_rule(world.get_location(korok_location(source, index)), _rule(player, [gate]))

    optimistic = world.options.weapon_check_logic == WeaponCheckLogic.option_after_character
    for name in world.checked_weapons:
        weapon = WEAPON_BY_NAME[name]
        gate = cleared_event(weapon.gate_mission) if (weapon.verified or optimistic) else STORY_EVENT
        needs = [gate] + ([character_item(weapon.character)] if weapon.character else [])
        set_rule(world.get_location(weapon_location(name)), _rule(player, needs))


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
    for mission in world.mission_order[1:]:  # (Hyrule Field holds a locked filler: pre-cleared in the starter save)
        location = world.get_location(mission_location(mission))
        if location.progress_type == LocationProgressType.EXCLUDED:
            continue  # after the goal: filler only
        add_item_rule(
            location,
            lambda item, p=player: item.player != p or item.classification != ItemClassification.filler,
        )
