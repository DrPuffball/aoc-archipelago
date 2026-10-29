from dataclasses import dataclass

from Options import (
    Choice,
    DeathLink,
    DefaultOnToggle,
    OptionCounter,
    OptionGroup,
    OptionSet,
    PerGameCommonOptions,
    Range,
    StartInventoryPool,
    Toggle,
    Visibility,
)

from .data import (
    ALL_CHARACTERS,
    BASE_CHARACTERS,
    LOCKABLE_FEATURES,
    DEFAULT_FILLER_WEIGHTS,
    FILLER_ITEMS,
)
from .data_rewards import ITEM_RENAMES, REWARD_GROUPS, reward_quest_count

# Korok seeds (and in-mission chests) stay local and vanilla: no checks (their location ids stay registered).
SIDE_CATEGORIES = ["Weapons", "Challenges", "Quests"]


class StartingCharacterCount(Range):
    """
    How many heroes you start with, picked at random from the starting character pool.
    Story missions let you bring any party, so four is enough for anything; the rest arrive as items.
    """

    display_name = "Starting Character Count"
    range_start = 1
    range_end = 20
    default = 4


class StartingCharacterPool(OptionSet):
    """
    Characters that may be picked as starting heroes. Defaults to the 18 base-game characters.
    Terrako, Calamity Ganon and the Great Fairies are fine to start with. Purah & Robbie and Sooga
    only exist when include_dlc is on.
    """

    display_name = "Starting Character Pool"
    valid_keys = frozenset(ALL_CHARACTERS)
    default = frozenset(BASE_CHARACTERS)


class WeaponChecks(Toggle):
    """
    Weapon pickups hold checks. Off by default: when each weapon drops is not verified.
    Korok seeds and treasure chests inside missions stay vanilla (no checks). Main story missions always hold checks.
    """

    display_name = "Weapon Checks"


class ChallengeChecks(DefaultOnToggle):
    """Challenge missions hold checks."""

    display_name = "Challenge Checks"


class QuestChecks(DefaultOnToggle):
    """Side quests hold checks (and quest reward items need this on)."""

    display_name = "Quest Checks"


class SideContent(OptionSet):
    """
    Older form of the three check toggles above (any of Weapons, Challenges, Quests; [] = story only).
    If set to anything other than its default, it overrides the toggles. New YAMLs should use the toggles.
    """

    display_name = "Side Content Checks (old form)"
    visibility = Visibility.none
    valid_keys = frozenset(SIDE_CATEGORIES)
    default = frozenset({"Challenges", "Quests"})


class SideCheckDensity(Range):
    """
    Percentage of the enabled quests, challenges and Korok seeds that actually hold checks, chosen at random.
    The rest stay vanilla. Lower this for shorter games.
    """

    display_name = "Side Check Density"
    range_start = 5
    range_end = 100
    default = 100


class IncludeDLC(Toggle):
    """
    Include Expansion Pass content: the EX challenges and quests, Vicious Monster Battles, DLC weapons, and the
    characters Purah & Robbie and Sooga. Off (default): the DLC is left exactly as in the vanilla game (no checks,
    no items, the client never locks or changes it). On is EXPERIMENTAL: Purah & Robbie and Sooga can be received
    but do not show on the Allies screen yet.
    """

    display_name = "Include DLC"
    visibility = Visibility.none  # hidden for the public release (DLC heroes do not show in Allies); still read from YAML


class MissionOrder(Choice):
    """
    Order of the 20 main story missions. The client rewrites the game's mission unlock rules so each clear opens the
    next mission of the seed's order (missions the game would open itself stay locked).

    Vanilla: the normal order.
    Shuffle Within Chapter: missions swap places inside their chapter.
    Shuffle All: any mission can appear in any slot; the slot structure (what unlocks what) stays as in the story.
    The Battle of Hyrule Field stays first (the starter save has it cleared); first_mission sets the second slot.
    """

    display_name = "Mission Order"
    option_vanilla = 0
    option_shuffle_within_chapter = 1
    option_shuffle_all = 2
    default = option_vanilla


class FirstMission(Choice):
    """
    Which story mission you play first. The client installs a starter save that skips the game's forced opening (The
    Battle of Hyrule Field with Link and Impa): that mission is already cleared in it, and its check is sent when you
    start. You begin on the world map with your starting heroes and this mission open (with unlock items: it is one
    of your starting unlocks).
    Random Early: a random mission of chapters 1-2. Random Any: any story mission (it can be a hard one).
    Vanilla: Road to the Ancient Lab.
    """

    display_name = "First Mission"
    option_vanilla = 0
    option_random_early = 1
    option_random_any = 2
    default = option_random_early


class MissionUnlocks(Choice):
    """
    How story missions open.
    Story Order: a mission opens once the missions before it are cleared (in the order mission_order sets).
    Items: every story mission except the first (first_mission) opens only when its "Unlock: <mission>" item is
    found, so the story is played in a random order. Victory still needs every story mission cleared.
    mission_order, side_missions_per_unlock and story_pacing do not apply. Missions are not level-gated: a late,
    harder mission can open early.
    """

    display_name = "Mission Unlocks"
    option_story_order = 0
    option_items = 1
    default = option_story_order


class StartingMissionUnlocks(Range):
    """With mission_unlocks: items, how many unlock items for early missions (chapters 1 and 2) you start with (at least
    one: with only the first mission open, small seeds have no room to place the first unlocks)."""

    display_name = "Starting Mission Unlocks"
    range_start = 1
    range_end = 5
    default = 2


class SideMissionsPerUnlock(Range):
    """
    Gate the story behind side missions. Each story slot after the first needs this many completed
    side missions (challenges and quests) per position in the story, so slot 5 needs 5x this number.
    0 turns it off. It works with any mission order, and it counts side missions whether or not they hold
    a check. Needs the Challenges or Quests side content to be enabled and challenge logic "by level"
    (or quests) to be playable early. Impossible requirements are lowered automatically with a warning
    in the generation log, so a seed never locks you out.
    """

    display_name = "Side Missions Per Story Unlock"
    range_start = 0
    range_end = 10
    default = 0


class StoryParty(Choice):
    """
    Free: any party can play any story mission (the hook overrides forced parties). Four heroes are always enough.
    Vanilla: story missions keep the characters the story forces into the party, and those characters must
    be unlocked first. Choose this if the hook cannot override forced parties or you want the original feel.
    """

    display_name = "Story Party"
    option_free = 0
    option_vanilla = 1
    default = option_free


class Goal(Choice):
    """
    What finishes the game.
    Story: clear all 20 main story missions.
    Story And Side Missions: also complete goal_side_missions challenges and quests.
    Story And All Characters: also unlock every character.
    Story And Boss Rush: also beat the Divine Beast battles and the Versus boss challenges after the story.
    """

    display_name = "Goal"
    option_story = 0
    option_story_and_side_missions = 1
    option_story_and_all_characters = 2
    option_story_and_boss_rush = 3
    default = option_story


class PostStoryUnlock(Range):
    """
    Post-story challenges and quests mix into the run before the goal (the client opens them in game).
    With side_unlocks shuffled (default) they join the random openings and can open at any time (any number below 20).
    With side_unlocks game_rules they open after this many story clears.
    20 = vanilla: they open after the whole story, and with a story-only goal they hold no checks.
    Post-story weapon drops can't be moved and still wait for the whole story.
    """

    display_name = "Post-Story Unlock"
    range_start = 1
    range_end = 20
    default = 10  # (user, 2026-10-28: post-story content mixed in before the goal; 20 = vanilla, no checks on it)


class GoalStoryMissions(Range):
    """
    How many main story missions the goal needs (any of them, in whatever order the seed opens them). 20 = all.
    Post-story content still opens only after the whole story, as in the game.
    """

    display_name = "Goal Story Missions"
    range_start = 2
    range_end = 20
    default = 20


class GoalChallenges(Range):
    """
    How many challenge missions the goal also needs (any of them; 0 = none). Lowered to the number of challenges in
    the seed (challenge_checks must be on for any to exist). goal_difficulty applies to these too.
    """

    display_name = "Goal Challenges"
    range_start = 0
    range_end = 200
    default = 0


class GoalDifficulty(Choice):
    """
    Difficulty for the goal's story missions and challenges (goal_story_missions, goal_challenges): each must be cleared
    on this difficulty or a higher one (a clear on a higher difficulty counts for every lower one, so nothing has to be
    replayed). Any: any difficulty.
    Read from the game's per-difficulty clear times; logic is unaffected (the missions are the same).
    """

    display_name = "Goal Difficulty"
    option_any = 0
    option_easy = 1
    option_normal = 2
    option_hard = 3
    option_very_hard = 4
    option_apocalyptic = 5
    default = 0


class GoalSideMissions(Range):
    """Challenges and quests to complete for the Story And Side Missions goal (lowered if fewer are possible)."""

    display_name = "Goal Side Missions"
    range_start = 1
    range_end = 300
    default = 25


class LockedFeatures(OptionSet):
    """
    Services that stay locked until their item is found. Cooking: the quest that teaches cooking (Hot Meals in a Pot)
    opens with Feature: Cooking. Shops: every shop opens with Feature: Shops (instead of Progressive Shop Unlock).
    Fairy Fountains: the Fairy Fountain challenges open with Feature: Fairy Fountains. Terrako Guardian: Terrako's
    Return opens with Feature: Terrako Guardian. Services not listed keep their vanilla unlock.
    """

    display_name = "Locked Features"
    valid_keys = frozenset(LOCKABLE_FEATURES)
    default = frozenset({"Cooking", "Terrako Guardian"})


class SheikahRunes(Choice):
    """
    The four Sheikah Slate runes: Remote Bombs, Cryonis, Magnesis, Stasis.

    Vanilla: you get them in the story (Remote Bombs and Cryonis in The Battle of Hyrule Field, Magnesis and Stasis in
    Road to the Ancient Lab).
    Shuffled: Cryonis, Magnesis and Stasis are items ("Rune: Stasis" ...) somewhere in the multiworld, hinted for free
    from the start; the client keeps each off until you receive it, and each Mastering <rune> challenge expects its
    rune. Remote Bombs is always yours (it is the Sheikah Slate itself: without it the game hides every rune).
    Cryonis is an item in logic only for now: outside The Battle of Hyrule Field the game gives it anyway.
    Start With All: all four runes from the start (no rune items).
    """

    display_name = "Sheikah Slate Runes"
    option_vanilla = 0
    option_shuffled = 1
    option_start_with_all = 2
    default = option_shuffled


class MinimumCharacterLevel(Range):
    """Level characters are raised to when you unlock them or start (never lowers a higher level)."""

    display_name = "Minimum Character Level"
    range_start = 1
    range_end = 100
    default = 1


















class CatchUpLevels(DefaultOnToggle):
    """Characters you unlock join at the level of your lowest-level unlocked character (if that is higher than their own)."""

    display_name = "Catch-Up Levels"


class FeaturedChallenge(Toggle):
    """Pick one random challenge as the featured challenge: its check is a priority location and holds a progression item."""

    display_name = "Featured Challenge"










class SteadyRewards(DefaultOnToggle):
    """
    Keep progression steady: story mission clears never hold filler from your own world, so every clear
    pays out a hero, upgrade or weapon (or another player's item). Filler goes to side checks instead.
    Skipped automatically if your pool has too few real items to do this.
    """

    display_name = "Steady Rewards"


class StoryPacing(Range):
    """
    Spread your heroes, upgrades and weapons evenly over the story. This percentage of them is placed in
    your own story-time checks (mission clears, early quests, mission Koroks), one wave per story mission,
    instead of being scattered at random. The rest are shuffled normally into the multiworld. 0 = fully random.
    Ignored when story_party is vanilla, because the heroes already pace the story then.
    """

    display_name = "Story Pacing"
    range_start = 0
    range_end = 100
    default = 0


class StuckRescueMinutes(Range):
    """
    If you report no new check for this many minutes while connected, the client reveals a hint for one unchecked
    location, so you always have a next target. 0 turns it off. It only fires once per quiet spell.
    """

    display_name = "Stuck Rescue Minutes"
    range_start = 0
    range_end = 180
    default = 45






class MissionHintEvery(Range):
    """Get a free hint for an unchecked location every this many story missions you clear. 0 turns it off."""

    display_name = "Free Hint Every N Missions"
    range_start = 0
    range_end = 10
    default = 0




class LocalFiller(Toggle):
    """Keep all of your filler items in your own world, so they don't flood other players' worlds."""

    display_name = "Local Filler"


class SideUnlocks(Choice):
    """
    How challenges and quests open.
    Shuffled: every seed picks at random which challenges and quests open, a few from the start and 2-4 more after
    every completion (story clear, challenge or quest), so new side content keeps opening at an even pace. The game's
    own unlock order and prerequisites are ignored (the client opens and closes them in game); heroes, runes and
    reward items a challenge or quest needs still apply. challenge_logic and post_story_unlock do not apply.
    Game Rules: challenges follow challenge_logic, quests the game's story gates, post-story content
    post_story_unlock.
    """

    display_name = "Side Unlocks"
    option_shuffled = 0
    option_game_rules = 1
    default = option_shuffled


class ChallengeLogic(Choice):
    """
    When challenge checks are expected to be available. The real unlock conditions are not verified.

    After Story: challenges are expected only once every main mission is cleared. Safe.
    By Level: each challenge is expected once the story has reached roughly its level bracket. Shorter
    and more fun but may be optimistic if a challenge unlocks later in the real game.
    """

    display_name = "Challenge Logic"
    option_after_story = 0
    option_by_level = 1
    default = option_after_story


class MissionRewards(Choice):
    """
    What a mission gives on its first clear (the materials shown on the mission card).
    Vanilla: unchanged. Shuffled: each mission gives another mission's rewards (fixed per seed). None: missions give
    no reward materials (items from Archipelago replace them).
    The client rewrites the game's reward table while it is connected; nothing here affects logic.
    """

    display_name = "Mission Rewards"
    option_vanilla = 0
    option_shuffled = 1
    option_none = 2
    default = 0


class WeaponCheckLogic(Choice):
    """
    When weapon pickup checks are expected to be available.

    After Story: only once every main mission is cleared. Safe, because the real timing is not fully verified.
    After Character: as soon as the wielder is yours and the mission that introduces the weapon is cleared.
    """

    display_name = "Weapon Check Logic"
    option_after_story = 0
    option_after_character = 1
    default = option_after_story


class HeartContainers(Range):
    """Heart Container items per character (extra hearts for that character)."""

    display_name = "Heart Containers per Character"
    range_start = 0
    range_end = 5
    default = 1


class ComboUpgrades(Range):
    """Combo Upgrade items per character. The world-map quests that teach combos become checks, and a hero's combo
    levels (up to 5) come only from these items: with 5, one item per level; with fewer, each item unlocks its share
    (1 = all of that hero's combos at once). 0 leaves combo upgrades vanilla."""

    display_name = "Combo Upgrades per Character"
    range_start = 0
    range_end = 5
    default = 5


class SpecialGaugeUpgrades(Range):
    """Special Gauge Upgrade items per character (bigger special-attack gauge)."""

    display_name = "Special Gauge Upgrades per Character"
    range_start = 0
    range_end = 3
    default = 1


class EnhancedAbilities(Range):
    """Enhanced Ability items per character (skill-tree perk for that character's unique ability)."""

    display_name = "Enhanced Abilities per Character"
    range_start = 0
    range_end = 3
    default = 1


class WeaponCapacityUpgrades(Range):
    """Progressive Weapon Capacity items (how many weapons you can carry)."""

    display_name = "Weapon Capacity Upgrades"
    range_start = 0
    range_end = 10
    default = 5


class SealSlotUpgrades(Range):
    """
    Progressive Seal Slot items: the game's seal-removal upgrades (Caring for the Statues, Secret of the Rito
    Artisans), which come only from these items. 0 leaves them to quest_reward_items' Progressive Seal Removal (...).
    """

    display_name = "Seal Slot Upgrades"
    range_start = 0
    range_end = 2
    default = 2


class WeaponFusion(Toggle):
    """Add a Weapon Fusion item: the Smithy (Hylian Blacksmith Guild, weapon fusion) opens only when you find it, and
    buying its quest is a check. Off (default): the Smithy is open from the start."""

    display_name = "Weapon Fusion Item"


class WeaponItems(Range):
    """
    How many different weapons are also added as items, so other worlds can send you a specific weapon.
    The rest of the roughly 150 weapons are only checks (found in game). Weapons are low-impact items, so a
    handful is plenty; they never gate progress.
    """

    display_name = "Weapon Items"
    range_start = 0
    range_end = 164
    default = 20


class FillerWeights(OptionCounter):
    """
    Relative weights for the filler items that pad the pool. Set a weight to 0 to remove an item.
    Character XP Gift and Weapon XP Gift grant experience, Extra Weapon grants a random weapon.
    """

    display_name = "Filler Weights"
    min = 0
    valid_keys = frozenset(FILLER_ITEMS)
    default = dict(DEFAULT_FILLER_WEIGHTS)


class QuestRewardItems(OptionCounter):
    """
    Quest rewards that become items: copies of each progressive item (0 = that reward stays vanilla). Each copy
    stands for its share of the quests behind it, in order. Buying a quest is always its check. Stored rewards
    (upgrades) come only from the items; "unlock" groups keep their quests closed until the item arrives (then the
    game's own reward applies); with Shop/Stable Unlock copies a bought shop opens only once its item is in too.
    Default: every quest group itemized except shops and stables (vanilla service). Groups other than the stored
    upgrades need quest_checks on.
    """

    display_name = "Quest Reward Items"
    min = 0
    valid_keys = frozenset(g.item for g in REWARD_GROUPS) | frozenset(ITEM_RENAMES)  # old names still accepted
    # Shops and stables keep their vanilla service by default (buying the quest is still a check).
    default = {g.item: 0 if g.item in ("Progressive Shop Unlock", "Progressive Stable Unlock") else reward_quest_count(g)
               for g in REWARD_GROUPS}


@dataclass
class AgeOfCalamityOptions(PerGameCommonOptions):
    starting_character_count: StartingCharacterCount
    starting_character_pool: StartingCharacterPool
    weapon_checks: WeaponChecks
    challenge_checks: ChallengeChecks
    quest_checks: QuestChecks
    side_content: SideContent
    side_check_density: SideCheckDensity
    include_dlc: IncludeDLC
    mission_order: MissionOrder
    first_mission: FirstMission
    mission_unlocks: MissionUnlocks
    starting_mission_unlocks: StartingMissionUnlocks
    story_party: StoryParty
    goal: Goal
    goal_side_missions: GoalSideMissions
    goal_difficulty: GoalDifficulty
    goal_story_missions: GoalStoryMissions
    post_story_unlock: PostStoryUnlock
    goal_challenges: GoalChallenges
    locked_features: LockedFeatures
    sheikah_runes: SheikahRunes
    minimum_character_level: MinimumCharacterLevel
    catch_up_levels: CatchUpLevels
    featured_challenge: FeaturedChallenge
    mission_hint_every: MissionHintEvery
    stuck_rescue_minutes: StuckRescueMinutes
    steady_rewards: SteadyRewards
    story_pacing: StoryPacing
    local_filler: LocalFiller
    side_missions_per_unlock: SideMissionsPerUnlock
    side_unlocks: SideUnlocks
    challenge_logic: ChallengeLogic
    weapon_check_logic: WeaponCheckLogic
    mission_rewards: MissionRewards
    heart_containers: HeartContainers
    combo_upgrades: ComboUpgrades
    special_gauge_upgrades: SpecialGaugeUpgrades
    enhanced_abilities: EnhancedAbilities
    weapon_capacity_upgrades: WeaponCapacityUpgrades
    seal_slot_upgrades: SealSlotUpgrades
    weapon_fusion: WeaponFusion
    weapon_items: WeaponItems
    quest_reward_items: QuestRewardItems
    filler_weights: FillerWeights
    death_link: DeathLink
    start_inventory_from_pool: StartInventoryPool


option_groups = [
    OptionGroup("Characters", [StartingCharacterCount, StartingCharacterPool, IncludeDLC]),
    OptionGroup("Checks", [WeaponChecks, ChallengeChecks, QuestChecks, SideCheckDensity, MissionOrder, FirstMission, MissionUnlocks, StartingMissionUnlocks,
                           SideMissionsPerUnlock]),
    OptionGroup("Goal and Logic", [Goal, GoalStoryMissions, GoalChallenges, PostStoryUnlock, GoalSideMissions, GoalDifficulty, StoryParty, SideUnlocks, ChallengeLogic, WeaponCheckLogic, SheikahRunes]),
    OptionGroup("Pace", [CatchUpLevels, MinimumCharacterLevel]),
    OptionGroup("Multiworld Extras", [StuckRescueMinutes, SteadyRewards, StoryPacing, MissionHintEvery, FeaturedChallenge]),
    OptionGroup(
        "Upgrades",
        [
            HeartContainers,
            ComboUpgrades,
            SpecialGaugeUpgrades,
            EnhancedAbilities,
            WeaponCapacityUpgrades,
            SealSlotUpgrades,
            WeaponFusion,
            WeaponItems,
            QuestRewardItems,
            MissionRewards,
            LockedFeatures,
        ],
    ),
    OptionGroup("Filler", [FillerWeights, LocalFiller]),
]

presets = {
    # Plain-language entry points; everything else is a detail.
    "Story": {"weapon_checks": False, "challenge_checks": False, "quest_checks": False},
    "Standard": {"weapon_checks": True, "challenge_checks": True, "quest_checks": False, "mission_hint_every": 4},
    "Everything": {
        "weapon_checks": True, "challenge_checks": True, "quest_checks": True,
        "side_check_density": 100,
        "mission_hint_every": 3,
    },
    "Sync Friendly": {
        "weapon_checks": True, "challenge_checks": True, "quest_checks": True,
        "side_check_density": 30,
        "mission_hint_every": 2,
        "stuck_rescue_minutes": 30,
        "challenge_logic": "by_level",
    },
    "Vanilla Feel": {"story_party": "vanilla", "weapon_checks": True, "challenge_checks": True, "quest_checks": True, "side_unlocks": "game_rules",
                     "challenge_logic": "by_level"},
    "Chaos": {"mission_order": "shuffle_all", "side_missions_per_unlock": 2,
              "weapon_checks": True, "challenge_checks": True, "quest_checks": True, "challenge_logic": "by_level",
              "locked_features": LOCKABLE_FEATURES},
}
