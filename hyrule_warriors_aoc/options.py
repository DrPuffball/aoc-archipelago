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

# Docstrings are what players read in the Options Creator and the YAML template (reworded 2026-11-02): one summary
# line, then each choice on its own line, plain words, option names as they appear in the YAML.


# --- Game mode and goal ---------------------------------------------------------------------------------------------

class GameMode(Choice):
    """
    The shape of the run.

    Standard: story missions, challenges and quests, as the other options set them.
    Story Only: every check is on story missions (the Expansion Pass story too, with include_dlc). Each story clear
    opens one new random story mission. The goal is goal_story_missions clears; goal_challenges is ignored.
    Challenges Only: every check is on challenge missions. Story missions (except The Battle of Hyrule Field) and map
    quests are hidden. A few challenges are open at the start and each clear opens 3-8 more. The goal is
    goal_challenges clears (0 = 50); the story options and final_mission_goal are ignored.

    Both special modes open every service (shops, stables, dye shop, Smithy, Sheikah Sensor) from the start and spread
    the checks evenly over the levels. Recipes become items (one per recipe); if quest_reward_items turns recipes off,
    you know every recipe from the start instead.
    """

    display_name = "Game Mode"
    option_standard = 0
    option_story_only = 1
    option_challenges_only = 2
    default = option_standard


class Goal(Choice):
    """
    What you need on top of the story missions to finish.

    Story: only the story missions (goal_story_missions) and challenges (goal_challenges).
    Story And Side Missions: also complete goal_side_missions challenges or quests.
    Story And All Characters: also unlock every hero.
    """

    display_name = "Goal"
    option_story = 0
    option_story_and_side_missions = 1
    option_story_and_all_characters = 2
    default = option_story


class GoalStoryMissions(Range):
    """
    How many story missions the goal needs, in any order.

    The base game has 20. With include_dlc, the 8 Guardian of Remembrance missions count as story missions too (28).
    A number above what your seed has means all of them. Post-story content still waits for the base story, as in the
    game.
    """

    display_name = "Goal Story Missions"
    range_start = 2
    range_end = 28
    default = 20  # (user, 2026-11-02: default run review)


class GoalChallenges(Range):
    """
    How many challenge missions the goal also needs, in any order (0 = none).

    Lowered to the number of challenges in your seed (challenge_checks must be on for there to be any). goal_difficulty
    applies to these too.
    """

    display_name = "Goal Challenges"
    range_start = 0
    range_end = 168  # the base game's challenges (no Expansion Pass), so the goal is always reachable
    default = 25  # (user, 2026-11-02: default run review)


class GoalSideMissions(Range):
    """
    With goal: Story And Side Missions, how many challenges or quests you must complete.

    Lowered automatically if your seed has fewer.
    """

    display_name = "Goal Side Missions"
    range_start = 1
    range_end = 300
    default = 25


class FinalMissionGoal(DefaultOnToggle):
    """
    Make The Future of Hyrule (the last story mission) the final goal.

    It stays closed, with no unlock item, until you have everything else the goal needs (goal_story_missions - 1 other
    story missions, goal_challenges challenges and the goal option's extras). Then it opens, and clearing it wins.
    Off: the goal completes as soon as you have those clears, in any order.
    """

    display_name = "The Future of Hyrule Is the Goal"


class GoalDifficulty(Choice):
    """
    The lowest difficulty a goal clear counts on.

    Each story mission and challenge the goal needs must be cleared on this difficulty or harder. A harder clear counts
    for every easier one, so nothing has to be replayed. The client reads the game's own clear records; logic doesn't
    change.
    Any: any difficulty counts.
    """

    display_name = "Goal Difficulty"
    option_any = 0
    option_easy = 1
    option_normal = 2
    option_hard = 3
    option_very_hard = 4
    option_apocalyptic = 5
    default = 0


# --- Story ----------------------------------------------------------------------------------------------------------

class MissionUnlocks(Choice):
    """
    How story missions open.

    Items: each story mission opens when you find its "Unlock: <mission>" item, so the story is played in a random
    order. You start with starting_mission_unlocks of them. Missions are not level-gated, so a late, harder mission can
    open early. mission_order and side_missions_per_unlock don't apply.
    Story Order: a mission opens once the missions before it are cleared, in the order mission_order sets.
    """

    display_name = "Mission Unlocks"
    option_story_order = 0
    option_items = 1
    default = option_items  # (user, 2026-11-02: default run review)


class StartingMissionUnlocks(Range):
    """
    With mission_unlocks: Items, how many story missions are open at the start.

    One is first_mission's pick; the rest are random chapter 1-2 missions.
    """

    display_name = "Starting Mission Unlocks"
    range_start = 1
    range_end = 5
    default = 2


class FirstMission(Choice):
    """
    Which story mission you can play first.

    The client installs a starter save that skips the game's opening (The Battle of Hyrule Field is already cleared,
    and its check is sent when you start). You begin on the world map with your starting heroes and this mission open.
    Random Any: any story mission (it can be a hard one).
    Random Early: a random mission from chapters 1-2.
    Vanilla: Road to the Ancient Lab.
    """

    display_name = "First Mission"
    option_vanilla = 0
    option_random_early = 1
    option_random_any = 2
    default = option_random_any  # (user, 2026-11-02)


class MissionOrder(Choice):
    """
    With mission_unlocks: Story Order, the order the story missions open in.

    The client rewrites the game's unlock rules so each clear opens the next mission of the seed's order.
    Shuffle All: any mission can be in any slot (The Battle of Hyrule Field stays first).
    Shuffle Within Chapter: missions only swap places inside their chapter.
    Vanilla: the normal order.
    """

    display_name = "Mission Order"
    option_vanilla = 0
    option_shuffle_within_chapter = 1
    option_shuffle_all = 2
    default = option_shuffle_all  # (user, 2026-11-02)


class StoryParty(Choice):
    """
    Who can play story missions and challenges.

    Free: your own heroes. When a mission forces a hero you don't have, the client swaps in one of yours, so four heroes
    are always enough.
    Vanilla: missions keep the heroes the game forces into the party, and you need those heroes first.
    """

    display_name = "Story Party"
    option_free = 0
    option_vanilla = 1
    default = option_free


class SideMissionsPerUnlock(Range):
    """
    With mission_unlocks: Story Order, gate the story behind side content.

    Each story slot after the first needs this many completed challenges or quests per position (slot 5 needs 5 times
    this number). Any completed side mission counts, check or not. Requirements your seed can't meet are lowered
    automatically, with a warning in the generation log. 0 turns it off.
    """

    display_name = "Side Missions Per Story Unlock"
    range_start = 0
    range_end = 10
    default = 0


# --- Checks ---------------------------------------------------------------------------------------------------------

class ChallengeChecks(DefaultOnToggle):
    """Challenge missions hold checks."""

    display_name = "Challenge Checks"


class QuestChecks(DefaultOnToggle):
    """Map quests hold checks. Quest reward items need this on (except rewards the client gives directly)."""

    display_name = "Quest Checks"


class WeaponChecks(Toggle):
    """
    Picking up each weapon holds a check.

    Off by default: when each weapon drops isn't fully verified. Story mission clears always hold checks; Korok seeds
    and in-mission chests never do.
    """

    display_name = "Weapon Checks"


class SideContent(OptionSet):
    """
    Older form of the check toggles (any of Weapons, Challenges, Quests; [] = story only).

    If set to anything other than its default, it overrides the toggles. New YAMLs should use the toggles.
    """

    display_name = "Side Content Checks (old form)"
    visibility = Visibility.none
    valid_keys = frozenset(SIDE_CATEGORIES)
    default = frozenset({"Challenges", "Quests"})


class SideCheckDensity(Range):
    """
    The percentage of challenges and quests that hold checks, picked at random.

    The rest are still playable but hold nothing. Lower this for a shorter game.
    """

    display_name = "Side Check Density"
    range_start = 5
    range_end = 100
    default = 100


class RegionHopeChecks(Toggle):
    """
    Each region's "Hope of <region>" quest holds a check.

    These quests complete by themselves when a region's map is 100% done. The Hope of All Hyrule never holds a check:
    by then the goal is long done.
    """

    display_name = "Region Hope Checks"


class DifficultyChecks(Choice):
    """
    Extra checks for clearing missions on harder difficulties.

    Every difficulty from Normal up to this one adds one check per story mission (and per challenge, see
    difficulty_checks_challenges). A clear sends the checks of its difficulty and every easier one, so a Hard clear
    also sends the Normal check. Ignored when difficulty_lock is on.
    Off: one check per mission, on any difficulty.
    """

    display_name = "Difficulty Checks"
    option_off = 0
    option_normal = 1
    option_hard = 2
    option_very_hard = 3
    default = 0


class DifficultyChecksChallenges(DefaultOnToggle):
    """With difficulty_checks: challenges get the extra per-difficulty checks too (story missions always do)."""

    display_name = "Difficulty Checks on Challenges"


class DifficultyLock(Choice):
    """
    Only clears on this difficulty or harder count.

    An easier clear sends nothing, opens nothing and doesn't count for the goal; the client tells you to replay it.
    Each mission's checks all come from that one clear. The Battle of Hyrule Field (cleared in the starter save) is
    exempt. The game's own difficulty menu isn't changed.
    Off: any difficulty counts.
    """

    display_name = "Difficulty Lock"
    option_off = 0
    option_normal = 1
    option_hard = 2
    option_very_hard = 3
    default = 0


# --- Side content unlocks -------------------------------------------------------------------------------------------

class ChallengeUnlockOrder(Choice):
    """
    How challenges open.

    Randomized: a few are open at the start, and 2-4 more challenges or quests open after every completion (story clear,
    challenge or quest). The client opens them in game. Heroes and runes a challenge needs still apply.
    Vanilla: challenges open as in the game, following challenge_logic.
    """

    display_name = "Challenge Unlock Order"
    option_randomized = 0
    option_vanilla = 1
    default = option_randomized


class QuestUnlockOrder(Choice):
    """
    How map quests open.

    Randomized: a few are open at the start, and 2-4 more challenges or quests open after every completion (story clear,
    challenge or quest). The client opens them in game. Reward items a quest needs still apply.
    Vanilla: quests open as in the game (its story gates and quest chains; post-story quests after post_story_unlock
    story clears).
    """

    display_name = "Quest Unlock Order"
    option_randomized = 0
    option_vanilla = 1
    default = option_randomized


class SideUnlocks(Choice):
    """
    Older form of challenge_unlock_order and quest_unlock_order (both at once).

    Shuffled: both randomized. Game Rules: both vanilla.
    """

    display_name = "Side Unlocks"
    option_shuffled = 0
    option_game_rules = 1
    default = option_shuffled
    visibility = Visibility.none  # 0.9.73: Challenge Unlock Order / Quest Unlock Order (game_rules here still wins)


class PostStoryUnlock(Range):
    """
    When post-story challenges and quests can open.

    With a randomized unlock order, they join the random openings and can appear at any time (any value below 20).
    With a vanilla unlock order, they open after this many story clears.
    20: vanilla, after the whole story (with a story-only goal they then hold no checks).
    Post-story weapon drops still wait for the whole story.
    """

    display_name = "Post-Story Unlock"
    range_start = 1
    range_end = 20
    default = 10  # (user, 2026-10-28: post-story content mixed in before the goal; 20 = vanilla, no checks on it)


class ChallengeLogic(Choice):
    """
    With challenge_unlock_order: Vanilla, when logic expects each challenge to be open.

    After Story: once every story mission is cleared. Safe.
    By Level: once the story reaches roughly the challenge's level. Shorter, but may be optimistic for challenges the
    game opens later.
    """

    display_name = "Challenge Logic"
    option_after_story = 0
    option_by_level = 1
    default = option_after_story


class WeaponCheckLogic(Choice):
    """
    With weapon_checks, when logic expects each weapon pickup.

    After Story: once every story mission is cleared. Safe, since drop timing isn't fully verified.
    After Character: as soon as you have the weapon's hero and the mission that introduces the weapon is cleared.
    """

    display_name = "Weapon Check Logic"
    option_after_story = 0
    option_after_character = 1
    default = option_after_story


# --- Expansion Pass -------------------------------------------------------------------------------------------------

class IncludeDLC(DefaultOnToggle):
    """
    Include the Expansion Pass (both waves).

    The Guardian of Remembrance missions count as story missions (goal and unlock items), the EX challenges and quests
    hold checks like the base game's, the DLC weapons are in, and Purah & Robbie, Sooga and the Battle-Tested Guardian
    are hero items. EX Alerts stay playable but hold no checks (except Forgotten Temple).
    If your game turns out not to have the DLC, the client keeps the seed winnable: it takes the DLC out of the goal
    and sends its checks.
    """

    display_name = "Include DLC"


# --- Heroes ---------------------------------------------------------------------------------------------------------

class StartingCharacterCount(Range):
    """
    How many heroes you start with, picked at random from starting_character_pool.

    With story_party: Free, four is enough for anything; the rest arrive as items.
    """

    display_name = "Starting Character Count"
    range_start = 1
    range_end = 20
    default = 4


class StartingCharacterPool(OptionSet):
    """
    Heroes that can be picked as starting heroes (default: the 18 base-game heroes).

    Terrako, Calamity Ganon and the Great Fairies are fine to start with. Purah & Robbie, Sooga and the Battle-Tested
    Guardian need include_dlc.
    """

    display_name = "Starting Character Pool"
    valid_keys = frozenset(ALL_CHARACTERS)
    default = frozenset(BASE_CHARACTERS)


class MinimumCharacterLevel(Range):
    """The level heroes are raised to when you start or unlock them (never lowers a higher level)."""

    display_name = "Minimum Character Level"
    range_start = 1
    range_end = 100
    default = 1


class CatchUpLevels(DefaultOnToggle):
    """New heroes join at the level of your lowest-level hero, if that's higher than their own."""

    display_name = "Catch-Up Levels"


class HeroLevelCap(Toggle):
    """
    Cap heroes at level 99.

    Heroes level up in game as usual (which refills hearts and the special gauge); one that reaches 100 is put back to
    99 a few seconds later.
    """

    display_name = "Cap Heroes at Level 99"


# --- Services and features ------------------------------------------------------------------------------------------

class StartWithSheikahSensor(DefaultOnToggle):
    """
    Start with the Sheikah Sensor, which points you to materials from the first mission.

    Its quest (Needed: Researchers!) is already done and holds no check.
    """

    display_name = "Start with the Sheikah Sensor"


class StartWithTrackers(Toggle):
    """
    Start with the treasure trackers and the Korok tracker.

    The Treasure Hunter's Technique, The Treasure Detector (and its upgrade) and A Most Peculiar Korok are already done
    and hold no checks.
    """

    display_name = "Start with Treasure and Korok Trackers"


class OpenShops(DefaultOnToggle):
    """
    Every shop except the dye shop is open from the start.

    Their quests are already done and hold no checks, and there are no shop items. Overrides Shops in locked_features.
    """

    display_name = "Shops Open from the Start"


class OpenStables(DefaultOnToggle):
    """Every stable is open from the start. Their quests are already done and hold no checks."""

    display_name = "Stables Open from the Start"


class OpenDyeShop(DefaultOnToggle):
    """The dye shop (Dyeing to Make Contact) is open from the start. Its quest is already done and holds no check."""

    display_name = "Dye Shop Open from the Start"


class WeaponFusion(Toggle):
    """
    The Smithy (weapon fusion) stays closed until you find the Weapon Fusion item.

    Buying its quest is then a check. Off (default): the Smithy is open from the start.
    """

    display_name = "Weapon Fusion Item"


class LockedFeatures(OptionSet):
    """
    Features that stay locked until you find their item.

    Cooking: Hot Meals in a Pot (the quest that teaches cooking) opens with Feature: Cooking.
    Shops: every shop opens with Feature: Shops (instead of one item per shop).
    Fairy Fountains: the Fairy Fountain challenges open with Feature: Fairy Fountains.
    Terrako Guardian: Terrako's Return opens with Feature: Terrako Guardian.
    Features not listed open as in the game.
    """

    display_name = "Locked Features"
    valid_keys = frozenset(LOCKABLE_FEATURES)
    default = frozenset({"Terrako Guardian", "Fairy Fountains"})  # cooking is open from the start unless locked here (user, 2026-11-02)


class SheikahRunes(Choice):
    """
    The Sheikah Slate runes: Remote Bombs, Cryonis, Magnesis and Stasis.

    Shuffled: Cryonis, Magnesis and Stasis are items ("Rune: Stasis" ...), hinted for free from the start. The client
    keeps each off until you receive it. Remote Bombs is always yours (it is the Sheikah Slate itself). Cryonis is an
    item in logic only for now: outside The Battle of Hyrule Field the game gives it anyway.
    Vanilla: you get them in the story (Remote Bombs and Cryonis in The Battle of Hyrule Field, Magnesis and Stasis in
    Road to the Ancient Lab).
    Start With All: all four from the start.
    """

    display_name = "Sheikah Slate Runes"
    option_vanilla = 0
    option_shuffled = 1
    option_start_with_all = 2
    default = option_shuffled


# --- Items ----------------------------------------------------------------------------------------------------------

class HeartContainers(Range):
    """Heart Container items per hero (each adds hearts to that hero)."""

    display_name = "Heart Containers per Character"
    range_start = 0
    range_end = 5
    default = 1


class ComboUpgrades(Range):
    """
    Combo Upgrade items per hero.

    The world-map quests that teach combos become checks, and a hero's combo levels (up to 5) come only from these
    items. With 5, each item is one level; with fewer, each item gives its share (1 = every combo at once).
    0: combo upgrades stay vanilla.
    """

    display_name = "Combo Upgrades per Character"
    range_start = 0
    range_end = 5
    default = 5


class SpecialGaugeUpgrades(Range):
    """Special Gauge Upgrade items per hero (a bigger special-attack gauge)."""

    display_name = "Special Gauge Upgrades per Character"
    range_start = 0
    range_end = 3
    default = 1


class EnhancedAbilities(Range):
    """Enhanced Ability items per hero (the skill-tree perks for that hero's unique ability)."""

    display_name = "Enhanced Abilities per Character"
    range_start = 0
    range_end = 3
    default = 1


class WeaponCapacityUpgrades(Range):
    """Progressive Weapon Capacity items (each lets you carry more weapons)."""

    display_name = "Weapon Capacity Upgrades"
    range_start = 0
    range_end = 10
    default = 5


class SealSlotUpgrades(Range):
    """
    Progressive Seal Slot items: the game's two seal-removal upgrades.

    Those upgrades (from Caring for the Statues and Secret of the Rito Artisans) then come only from these items.
    0: they follow quest_reward_items instead.
    """

    display_name = "Seal Slot Upgrades"
    range_start = 0
    range_end = 2
    default = 2


class WeaponItems(Range):
    """
    How many specific weapons are also items, so other players can send you one.

    The rest of the roughly 150 weapons are found in game as usual. Weapons never gate progress.
    """

    display_name = "Weapon Items"
    range_start = 0
    range_end = 164
    default = 20


class QuestRewardItems(OptionCounter):
    """
    Quest rewards that become items (0 = that reward stays vanilla). Buying a quest is always its check.

    Rewards that just raise a number (hearts, lessons, apple capacity, seal slots...) are progressive: the value is how
    many copies, and each copy gives its share of the group's quests, in the game's order.
    Groups of different rewards (recipes, shops, stables, regional discounts, Smithy upgrades, research quests, dyes,
    Divine Beast upgrades, Expansion Pass reward quests) become one item per reward, named after its quest (for
    example "Recipe (A Feast of Greens)"): any value above 0 turns on the whole group.
    Most rewards are given by their items directly. A few (research quests, Maz Koshia's trials, the Expansion Pass
    reward quests) instead keep their quest closed until the item arrives; you then complete it for the game's reward.
    By default every group is on except shops and stables. Groups other than the directly-given ones need
    quest_checks.
    """

    display_name = "Quest Reward Items"
    min = 0
    valid_keys = frozenset(g.item for g in REWARD_GROUPS) | frozenset(ITEM_RENAMES)  # old names still accepted
    # Shops and stables keep their vanilla service by default (buying the quest is still a check).
    default = {g.item: 0 if g.item in ("Progressive Shop Unlock", "Progressive Stable Unlock") else reward_quest_count(g)
               for g in REWARD_GROUPS}


class MissionRewards(Choice):
    """
    The materials a mission gives on its first clear (shown on the mission card).

    Vanilla: unchanged.
    Shuffled: each mission gives another mission's rewards (fixed per seed).
    None: missions give no reward materials.
    The client changes the game's reward table while it's connected; logic isn't affected.
    """

    display_name = "Mission Rewards"
    option_vanilla = 0
    option_shuffled = 1
    option_none = 2
    default = 0


class FillerWeights(OptionCounter):
    """
    How often each filler item fills the pool (0 removes it).

    Character XP Gift: levels up a hero.
    Extra Weapon / Weapon Bundle / Large Weapon Bundle: 1 / 3 / 5 random weapons, each for a different hero.
    Small Material Bundle / Material Bundle / Large Material Bundle: 10 each of 3 / 15 each of 5 / 25 each of 8
    materials.
    Rupee Pouch: 1000 rupees. Hearty Meal: cooking ingredients.
    Weapon XP Gift (older seeds) gives 1 weapon.
    """

    display_name = "Filler Weights"
    min = 0
    valid_keys = frozenset(FILLER_ITEMS)
    default = dict(DEFAULT_FILLER_WEIGHTS)


class LocalFiller(Toggle):
    """Keep your filler items in your own world, so they don't crowd other players' worlds."""

    display_name = "Local Filler"


# --- Hints and help -------------------------------------------------------------------------------------------------

class HintMissionUnlocks(DefaultOnToggle):
    """With mission_unlocks: Items, every "Unlock: <mission>" item is hinted for free when the room starts."""

    display_name = "Auto-Hint Mission Unlocks"


class HintHeroes(DefaultOnToggle):
    """Every hero you can receive is hinted for free when the room starts."""

    display_name = "Auto-Hint Heroes"


class MissionHintEvery(Range):
    """A free hint for one of your unchecked locations every this many story clears. 0 turns it off."""

    display_name = "Free Hint Every N Missions"
    range_start = 0
    range_end = 10
    default = 0


class StuckRescueMinutes(Range):
    """
    A free hint when you've found nothing for this many minutes.

    If you send no new check for this long while connected, the client hints one of your unchecked locations, so you
    always have a next target. It fires once per quiet spell. 0 turns it off.
    """

    display_name = "Stuck Rescue Minutes"
    range_start = 0
    range_end = 180
    default = 30  # (user, 2026-11-02: default run review)


class GoalBanner(DefaultOnToggle):
    """
    A banner at the top of the emulator window with your goal progress and what to do next.

    It shows on the world map: story missions, challenges and side missions still needed, the goal difficulty, and
    setup steps while you start the game. Type "/goal_banner on" or "/goal_banner off" in the client to change it for
    your own game.
    """

    display_name = "Goal Progress Banner"


class FeaturedChallenge(Toggle):
    """One random challenge is the featured challenge: its check always holds a progression item."""

    display_name = "Featured Challenge"


# --- Multiworld pacing ----------------------------------------------------------------------------------------------

class SteadyRewards(DefaultOnToggle):
    """
    Story mission clears never hold filler from your own world.

    Every clear pays out a hero, upgrade or weapon (or another player's item); your filler goes to side checks instead.
    Skipped automatically if your pool has too few real items.
    """

    display_name = "Steady Rewards"


class StoryPacing(Range):
    """
    Spread your heroes, upgrades and weapons evenly over the story.

    This percentage of them is placed in your own story-time checks, one wave per story mission, instead of anywhere
    in the multiworld. 0 = fully random. Ignored with story_party: Vanilla (the forced heroes already pace the story).
    """

    display_name = "Story Pacing"
    range_start = 0
    range_end = 100
    default = 0


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
    difficulty_checks: DifficultyChecks
    difficulty_checks_challenges: DifficultyChecksChallenges
    difficulty_lock: DifficultyLock
    final_mission_goal: FinalMissionGoal
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
    challenge_unlock_order: ChallengeUnlockOrder
    quest_unlock_order: QuestUnlockOrder
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
    hint_mission_unlocks: HintMissionUnlocks
    hint_heroes: HintHeroes
    hero_level_cap: HeroLevelCap
    goal_banner: GoalBanner
    game_mode: GameMode
    start_with_sheikah_sensor: StartWithSheikahSensor
    start_with_trackers: StartWithTrackers
    open_stables: OpenStables
    open_shops: OpenShops
    open_dye_shop: OpenDyeShop
    region_hope_checks: RegionHopeChecks
    death_link: DeathLink
    start_inventory_from_pool: StartInventoryPool


# Groups in the order a new player decides things (2026-11-02): what kind of run, how the story opens, what holds
# checks, how side content opens, then heroes, services, items, hints and pacing.
option_groups = [
    OptionGroup("Game Mode and Goal", [GameMode, Goal, GoalStoryMissions, GoalChallenges, GoalSideMissions,
                                       FinalMissionGoal, GoalDifficulty]),
    OptionGroup("Story", [MissionUnlocks, StartingMissionUnlocks, FirstMission, MissionOrder, StoryParty,
                          SideMissionsPerUnlock]),
    OptionGroup("Checks", [ChallengeChecks, QuestChecks, WeaponChecks, SideCheckDensity, RegionHopeChecks,
                           DifficultyChecks, DifficultyChecksChallenges, DifficultyLock]),
    OptionGroup("Side Content Unlocks", [ChallengeUnlockOrder, QuestUnlockOrder, PostStoryUnlock, ChallengeLogic,
                                         WeaponCheckLogic, SideUnlocks]),
    OptionGroup("Expansion Pass", [IncludeDLC]),
    OptionGroup("Heroes", [StartingCharacterCount, StartingCharacterPool, MinimumCharacterLevel, CatchUpLevels,
                           HeroLevelCap]),
    OptionGroup("Services and Features", [StartWithSheikahSensor, StartWithTrackers, OpenShops, OpenStables,
                                          OpenDyeShop, WeaponFusion, LockedFeatures, SheikahRunes]),
    OptionGroup("Items", [HeartContainers, ComboUpgrades, SpecialGaugeUpgrades, EnhancedAbilities,
                          WeaponCapacityUpgrades, SealSlotUpgrades, WeaponItems, QuestRewardItems, MissionRewards,
                          FillerWeights, LocalFiller]),
    OptionGroup("Hints and Help", [HintMissionUnlocks, HintHeroes, MissionHintEvery, StuckRescueMinutes, GoalBanner,
                                   FeaturedChallenge]),
    OptionGroup("Multiworld Pacing", [SteadyRewards, StoryPacing]),
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
