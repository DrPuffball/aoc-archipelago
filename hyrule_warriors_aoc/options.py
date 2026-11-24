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

# 0.9.90: Korok seeds and treasure chests in story missions can hold checks again (korok_checks, chest_checks).
SIDE_CATEGORIES = ["Weapons", "Challenges", "Quests", "Korok Seeds", "Chests"]

# Docstrings are what players read in the Options Creator and the YAML template (reworded 2026-11-02): one summary
# line, then each choice on its own line, plain words, option names as they appear in the YAML.


# --- Game mode and goal ---------------------------------------------------------------------------------------------

class GameMode(Choice):
    """
    The shape of the run.

    Standard: story missions, challenges and quests, as the other options set them.
    Story Only: every check is on story missions (the Expansion Pass story too, with include_dlc). With
    mission_unlocks: story_order each story clear opens one new random story mission; with mission_unlocks: items
    (the default) they open by their unlock items, as in Standard. The goal is goal_story_missions clears;
    goal_challenges is ignored.
    Challenges Only: every check is on challenge missions. Story missions (except The Battle of Hyrule Field) and map
    quests are hidden. A few challenges are open at the start and each clear opens 3-8 more; with
    challenge_unlock_order: items each challenge opens by its own unlock item instead (12 start unlocked). The goal is
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
    Older form of the goal (new YAMLs use goal_quests and goal_all_heroes).

    Story: only the goal counts. Story And Side Missions: also goal_side_missions challenges or quests.
    Story And All Characters: also every hero.
    """

    display_name = "Goal (old form)"
    visibility = Visibility.none
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


class GoalQuests(Range):
    """
    How many map quests the goal also needs, in any order (0 = none).

    Only quests that hold checks count, so quest_checks must be on. Lowered to the number your seed has.
    """

    display_name = "Goal Quests"
    range_start = 0
    range_end = 300
    default = 0


class GoalAllHeroes(Toggle):
    """The goal also needs every hero unlocked."""

    display_name = "Goal Needs Every Hero"


class GoalHopeOfAllHyrule(Toggle):
    """
    The goal also needs The Hope of All Hyrule: every region's map 100% complete (every quest and challenge done).

    A long goal. Logic expects every hero, every challenge and every quest of your seed first. With final_mission_goal,
    clear The Future of Hyrule first (some of the map only opens after it); the goal is done once both are.
    Not available with game_mode: challenges_only (map quests stay closed there).
    """

    display_name = "Goal Needs The Hope of All Hyrule"


class GoalSideMissions(Range):
    """Older form: with goal: Story And Side Missions, how many challenges or quests must be completed."""

    display_name = "Goal Side Missions (old form)"
    visibility = Visibility.none
    range_start = 1
    range_end = 300
    default = 25


class FinalMissionGoal(DefaultOnToggle):
    """
    Make The Future of Hyrule (the last story mission) the final goal.

    It stays closed, with no unlock item, until you have everything else the goal needs (goal_story_missions - 1 other
    story missions, goal_challenges, goal_quests and goal_all_heroes). Then it opens, and clearing it wins.
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

    The client installs a starter save that skips the game's opening. You begin on the world map with your starting
    heroes and this mission open.
    Random Any: any story mission (it can be a hard one).
    Random Early: a random mission from chapters 1-2.
    Vanilla: The Battle of Hyrule Field.
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
    Borrowed: missions keep the heroes the game forces into the party; a forced hero you don't have yet is lent to you
    for that mission only (unlocked while the map cursor is on it and during the battle, locked again afterwards).
    """

    display_name = "Story Party"
    option_free = 0
    option_vanilla = 1
    option_borrowed = 2
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

    Off by default: when each weapon drops isn't fully verified. Story mission clears always hold checks.
    """

    display_name = "Weapon Checks"


class KorokChecks(DefaultOnToggle):  # (0.9.90, user: on by default)
    """
    Each Korok seed holds a check: 122 in story missions, 12 in challenges (those need challenges in the seed).
    Story Only: the 122 story seeds. Challenges Only: the 12 challenge seeds.

    The check is sent once the game records the seed.
    """

    display_name = "Korok Seed Checks"


class ChestChecks(DefaultOnToggle):  # (0.9.90, user: on by default)
    """
    Each treasure chest in a story mission holds a check (153 chests; 28 more in Expansion Pass missions with include_dlc).
    Challenges Only: only the 28 Expansion Pass chests (with include_dlc), since those missions are challenges there.

    The check is sent the moment you open the chest; you still get what the chest holds.
    """

    display_name = "Treasure Chest Checks"


class HeroLevelChecks(Toggle):
    """
    Heroes reaching levels hold checks ("Hero Level: Link Lv 10"): one per hero every Hero Level Check Interval levels,
    up to Hero Level Check Max. Higher levels expect more of the story cleared first.
    """

    display_name = "Hero Level Checks"


class HeroLevelCheckMax(Range):
    """The highest hero level that holds a check (with Hero Level Checks)."""

    display_name = "Hero Level Check Max"
    range_start = 2
    range_end = 100
    default = 50


class HeroLevelCheckInterval(Range):
    """Levels between hero level checks: 1 = every level, 5 = levels 5, 10, 15 ..."""

    display_name = "Hero Level Check Interval"
    range_start = 1
    range_end = 50
    default = 10


class WeaponLevelChecks(Toggle):
    """
    A hero's best weapon reaching levels holds checks ("Weapon Level: Link Lv 10"): one per hero every Weapon Level
    Check Interval levels, up to Weapon Level Check Max. The game caps weapon levels at 20 at first, 25 after
    A Monumental Undertaking and 30 after The Legendary Blacksmith, so levels above 20 and 25 need those quests (and are
    left out when the seed doesn't have them).
    """

    display_name = "Weapon Level Checks"


class WeaponLevelCheckMax(Range):
    """The highest weapon level that holds a check (with Weapon Level Checks; the game's own maximum is 30)."""

    display_name = "Weapon Level Check Max"
    range_start = 2
    range_end = 30
    default = 20


class WeaponLevelCheckInterval(Range):
    """Levels between weapon level checks: 1 = every level, 5 = levels 5, 10, 15 ..."""

    display_name = "Weapon Level Check Interval"
    range_start = 1
    range_end = 29
    default = 5


class EnemyDefeatChecks(Toggle):
    """
    Defeating enough of an enemy type holds checks ("Defeated: Lynel (1)"), counted by the trophies you have earned in
    total (spending them later doesn't take progress back). The counts follow how many a mission has: Bokoblins
    500 / 2000 / 5000, Moblins 10 / 30 / 75, Lynels 2 / 6 / 15 (tier 1 about a mission or two of play, tier 3 about
    twelve). 10 enemy types (enemies not yet seen in story missions are left out), up to Gathering Check Tiers each.
    """

    display_name = "Enemy Defeat Checks"


class EnemyDefeatScale(Range):
    """Percent applied to every enemy defeat count (100 = the standard counts, 50 = half as many, 200 = twice)."""

    display_name = "Enemy Defeat Scale"
    range_start = 10
    range_end = 400
    default = 100


class MaterialChecks(Toggle):
    """
    Gathering enough of a material holds checks ("Gathered: Hyrule Herb (1)"), counted by what you have gathered in
    total since connecting (spending doesn't take progress back; materials the client gives you don't count). Counts
    follow the material's rarity (common 20 / 60 / 150 ... very rare 1 / 3 / 8). 97 materials that story missions give
    on every clear or that their enemies drop (gems and other one-time rewards are left out), up to Gathering Check
    Tiers checks each. A material held at the game's 999 limit gains
    nothing until some is spent.
    """

    display_name = "Material Checks"


class MaterialScale(Range):
    """Percent applied to every material count (100 = the standard counts, 50 = half as many, 200 = twice)."""

    display_name = "Material Scale"
    range_start = 10
    range_end = 400
    default = 100


class GatheringCheckTiers(Range):
    """Checks per material and per enemy type for Material Checks and Enemy Defeat Checks (1-3 rising counts)."""

    display_name = "Gathering Check Tiers"
    range_start = 1
    range_end = 3
    default = 2


class SideContent(OptionSet):
    """
    Older form of the check toggles (any of Weapons, Challenges, Quests, Korok Seeds, Chests; [] = story only).

    If set to anything other than its default, it overrides the toggles. New YAMLs should use the toggles.
    """

    display_name = "Side Content Checks (old form)"
    visibility = Visibility.none
    valid_keys = frozenset(SIDE_CATEGORIES)
    default = frozenset({"Challenges", "Quests"})


class LabChecks(DefaultOnToggle):
    """
    Every research node in the Royal Ancient Lab holds a check, and its reward becomes an item.

    All 35 nodes are open from the start: the client removes the game's unlock order. Each node still needs its materials
    and its own condition (such as "use Remote Bombs to defeat 100 enemies"), and the logic accounts for them. The two relic
    nodes ask for The Future of Hyrule: with final_mission_goal they hold no checks. Needs include_dlc. Off: the lab is left as the game has it.
    """

    display_name = "Lab Checks"


class SideCheckDensity(Range):
    """
    The percentage of challenges and quests that hold checks, picked at random.

    The rest are still playable but hold nothing. Lower this for a shorter game.
    In game_mode challenges_only every challenge holds a check (this is ignored for challenges there).
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
    exempt. The client also raises the game's difficulty setting to at least this level (on the map).
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
    Items: each challenge opens when its own "Unlock: <challenge>" item arrives, like story missions with
    mission_unlocks: items (needs challenge_checks; else it plays as Randomized). Adds one item per challenge.
    Works in game_mode challenges_only too (12 challenges start unlocked); story_only has no challenges.
    """

    display_name = "Challenge Unlock Order"
    option_randomized = 0
    option_vanilla = 1
    option_items = 2
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
    If your emulator doesn't list the DLC, the client warns you; type /no_dlc to take it out of the goal and send its
    checks, which keeps the seed winnable.
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

    Shuffled: all four are items ("Rune: Stasis" ...), hinted for free from the start. The Sheikah Slate (rune menu)
    works as soon as you have any rune. Needs the Archipelago rune mod, which the client installs into Eden and
    Ryujinx by itself while the emulator is closed (start the client before the game). Without it the game hands
    runes out with story clears.
    Vanilla: you get them in the story (Remote Bombs and Cryonis in The Battle of Hyrule Field, Magnesis and Stasis in
    Road to the Ancient Lab).
    Start With All: all four from the start.

    Some missions, challenges, Korok seeds, chests and lab nodes can't be done without a certain rune (Remote Bombs for
    Revali, Urbosa and When Courage Fails, for example). Logic waits for it, and you never start with such a mission.
    """

    display_name = "Sheikah Slate Runes"
    option_vanilla = 0
    option_shuffled = 1
    option_start_with_all = 2
    default = option_shuffled  # 0.9.89 (user): shuffled by default, with the game mod


class RodItems(DefaultOnToggle):
    """
    The Fire Rod, Ice Rod and Lightning Rod are items. Until a rod's item is found the client keeps that rod at 0 uses
    in missions: it shows greyed out in the item palette (hold L) and can't be used. Off: the rods work as in the
    normal game.
    """

    display_name = "Elemental Rod Items"


class AppleItems(Toggle):
    """
    Healing apples are an item ("Apples"). Until it is found the apple slot of the item palette (hold L, then B) is
    hidden and the apple count is held at 0 in missions, so you can't heal with them. Off by default.
    """

    display_name = "Apple Item"


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
    Rewards are given by their items directly; buying the quest only sends its check. Maz Koshia's trials are the one
    exception: each trial is the next fight, so its quest stays closed until the item arrives.
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

class HintMissionUnlocks(Toggle):  # (0.9.90, user: free pre-hints off by default, runes aside)
    """With mission_unlocks: Items, every "Unlock: <mission>" item is hinted for free when the room starts."""

    display_name = "Auto-Hint Mission Unlocks"


class HintHeroes(Toggle):  # (0.9.90, user: free pre-hints off by default, runes aside)
    """Every hero you can receive is hinted for free when the room starts."""

    display_name = "Auto-Hint Heroes"


class HintRunes(DefaultOnToggle):
    """With sheikah_runes: Shuffled, the four rune items are hinted for free when the room starts."""

    display_name = "Auto-Hint Runes"


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


class FrameRate(Choice):
    """
    The game's frame rate in gameplay, set by the client, with the game kept at real-time speed at any frame rate.

    60, 120, Unlimited: draw up to that many frames a second while you play (cutscenes, menus and the world map stay at
    the game's own 30). The game advances its time in 1/60 s steps; the client chooses how many steps each drawn frame
    takes, so a PC that draws 45 frames still plays at full speed, and above 60 some frames take none.
    Off: the game's own 30 FPS; the client leaves the frame rate alone (also what to pick with another frame-rate mod).
    Type "/fps 60", "/fps 120", "/fps unlimited", "/fps off" or "/fps seed" in the client (or use its Options tab) to
    change it for your own game.
    """

    display_name = "Frame Rate"
    option_fps_60 = 0
    option_off = 2
    option_fps_120 = 3
    option_unlimited = 4
    alias_fps_30 = 2  # 0.9.90 (user): "30" and "off" merged; an older YAML's fps_30 is off
    default = option_off  # 0.9.89 (user): the higher modes are experimental, off by default


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
    lab_checks: LabChecks
    korok_checks: KorokChecks
    chest_checks: ChestChecks
    hero_level_checks: HeroLevelChecks
    hero_level_check_max: HeroLevelCheckMax
    hero_level_check_interval: HeroLevelCheckInterval
    weapon_level_checks: WeaponLevelChecks
    weapon_level_check_max: WeaponLevelCheckMax
    weapon_level_check_interval: WeaponLevelCheckInterval
    enemy_defeat_checks: EnemyDefeatChecks
    enemy_defeat_scale: EnemyDefeatScale
    material_checks: MaterialChecks
    material_scale: MaterialScale
    gathering_check_tiers: GatheringCheckTiers
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
    goal_quests: GoalQuests
    goal_all_heroes: GoalAllHeroes
    goal_hope_of_all_hyrule: GoalHopeOfAllHyrule
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
    rod_items: RodItems
    apple_items: AppleItems
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
    hint_runes: HintRunes
    hero_level_cap: HeroLevelCap
    goal_banner: GoalBanner
    frame_rate: FrameRate
    game_mode: GameMode
    start_with_sheikah_sensor: StartWithSheikahSensor
    start_with_trackers: StartWithTrackers
    open_stables: OpenStables
    open_shops: OpenShops
    open_dye_shop: OpenDyeShop
    region_hope_checks: RegionHopeChecks
    death_link: DeathLink
    start_inventory_from_pool: StartInventoryPool


# Groups in the order a new player decides things (reordered 2026-11-04): what kind of run and what wins it, what holds
# checks, how story and side content open, then heroes, services, items, hints and pacing. Hidden older options sit in
# no group.
option_groups = [
    OptionGroup("Game Mode and Goal", [GameMode, IncludeDLC, FinalMissionGoal, GoalStoryMissions, GoalChallenges, GoalQuests,
                                       GoalAllHeroes, GoalHopeOfAllHyrule, GoalDifficulty]),
    OptionGroup("What Holds Checks", [ChallengeChecks, QuestChecks, LabChecks, WeaponChecks, KorokChecks, ChestChecks,
                                      SideCheckDensity,
                                      RegionHopeChecks, DifficultyChecks, DifficultyChecksChallenges, DifficultyLock]),
    OptionGroup("Progress Checks", [HeroLevelChecks, HeroLevelCheckMax, HeroLevelCheckInterval, WeaponLevelChecks,
                                    WeaponLevelCheckMax, WeaponLevelCheckInterval, EnemyDefeatChecks, EnemyDefeatScale,
                                    MaterialChecks, MaterialScale, GatheringCheckTiers]),
    OptionGroup("Story", [MissionUnlocks, StartingMissionUnlocks, FirstMission, MissionOrder, StoryParty,
                          SideMissionsPerUnlock]),
    OptionGroup("Challenges and Quests", [ChallengeUnlockOrder, QuestUnlockOrder, PostStoryUnlock, ChallengeLogic,
                                          WeaponCheckLogic]),
    OptionGroup("Heroes", [StartingCharacterCount, StartingCharacterPool, MinimumCharacterLevel, CatchUpLevels,
                           HeroLevelCap]),
    OptionGroup("Open from the Start", [StartWithSheikahSensor, StartWithTrackers, OpenShops, OpenStables, OpenDyeShop]),
    OptionGroup("Locked Features", [WeaponFusion, LockedFeatures, SheikahRunes, RodItems, AppleItems]),
    OptionGroup("Upgrade Items", [HeartContainers, ComboUpgrades, SpecialGaugeUpgrades, EnhancedAbilities,
                                  WeaponCapacityUpgrades, SealSlotUpgrades, WeaponItems, QuestRewardItems]),
    OptionGroup("Filler and Mission Rewards", [FillerWeights, LocalFiller, MissionRewards]),
    OptionGroup("Hints and Help", [HintMissionUnlocks, HintHeroes, HintRunes, MissionHintEvery, StuckRescueMinutes, GoalBanner, FrameRate,
                                   FeaturedChallenge]),
    OptionGroup("Multiworld Pacing", [SteadyRewards, StoryPacing]),
]

presets = {
    # Plain-language entry points; everything else is a detail.
    "Story": {"weapon_checks": False, "challenge_checks": False, "quest_checks": False, "lab_checks": False},
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
