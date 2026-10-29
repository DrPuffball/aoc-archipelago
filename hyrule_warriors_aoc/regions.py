from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification, Region

from .locations import (
    AgeOfCalamityLocation,
    challenge_location,
    create_location,
    mission_location,
    quest_location,
    weapon_location,
)
from .data_koroks import korok_location

if TYPE_CHECKING:
    from .world import AgeOfCalamityWorld

VICTORY_EVENT = "Victory"
POST_STORY_EVENT = "Post-Story Open"  # post-story challenges and quests open (post_story_unlock story clears)
STORY_EVENT = "Story Complete"  # all 20 story missions: what post-story content waits for (the goal may need fewer)


def cleared_event(mission_name: str) -> str:
    return f"Cleared: {mission_name}"


def challenge_event(name: str) -> str:
    return f"Done challenge: {name}"


def quest_event(name: str) -> str:
    return f"Done quest: {name}"


def _event(world: AgeOfCalamityWorld, region: Region, location_name: str, item_name: str) -> AgeOfCalamityLocation:
    location = AgeOfCalamityLocation(world.player, location_name, None, region)
    region.locations.append(location)
    location.place_locked_item(Item(item_name, ItemClassification.progression, None, world.player))
    return location


def create_regions(world: AgeOfCalamityWorld) -> None:
    player, multiworld = world.player, world.multiworld
    menu = Region("Menu", player, multiworld)
    multiworld.regions.append(menu)

    # One region per story mission, filled according to the (possibly shuffled) slot assignment.
    # Clearing it grants an event that later missions and side content key off. Events instead of
    # "can reach" rules keep the logic simple and cache-safe.
    for mission in world.mission_order:
        region = Region(mission, player, multiworld)
        multiworld.regions.append(region)
        menu.connect(region, f"Start {mission}")
        create_location(world, region, mission_location(mission))
        _event(world, region, f"Event: Cleared {mission}", cleared_event(mission))

    story = Region("Story Complete", player, multiworld)
    multiworld.regions.append(story)
    menu.connect(story, "Finish The Story")
    _event(world, story, "Event: Story Complete", STORY_EVENT)

    post = Region("Post-Story Open", player, multiworld)
    multiworld.regions.append(post)
    menu.connect(post, "Open Post-Story Content")
    _event(world, post, "Event: Post-Story Open", POST_STORY_EVENT)

    victory = Region("Victory", player, multiworld)
    multiworld.regions.append(victory)
    menu.connect(victory, "Finish All Main Missions")
    _event(world, victory, "Event: Beat All Main Missions", VICTORY_EVENT)

    side = Region("Side Content", player, multiworld)
    multiworld.regions.append(side)
    menu.connect(side, "Visit Side Content")

    # Events exist for every enabled challenge and quest even when its check is not shuffled, because
    # other quests and Korok seeds depend on completing them.
    for name in world.active_challenges:
        _event(world, side, f"Event: Challenge {name}", challenge_event(name))
        if name in world.checked_challenges:
            create_location(world, side, challenge_location(name))
    for name in world.active_quests:
        _event(world, side, f"Event: Quest {name}", quest_event(name))
        if name in world.checked_quests:
            create_location(world, side, quest_location(name))
    for source, kind, index in world.checked_koroks:
        create_location(world, side, korok_location(source, index))
    for name in world.checked_weapons:
        create_location(world, side, weapon_location(name))
