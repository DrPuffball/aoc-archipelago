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


class IncludeDLC(DefaultOnToggle):
    """
    Include the Expansion Pass (both waves needed): the Guardian of Remembrance story missions count as story missions
    (goal, unlock items), the EX challenges and quests are checks like the base game's, DLC weapons, and the heroes
    Purah & Robbie, Sooga and the Battle-Tested Guardian are items. EX Alerts stay playable but never hold checks
    (except Forgotten Temple). If the game turns out not to have the DLC, the client keeps the seed winnable: the DLC
    is taken out of the goal and its checks are sent.
    """

    display_name = "Include DLC"


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
    default = option_shuffle_all  # (user, 2026-11-02)


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
    default = option_random_any  # (user, 2026-11-02)


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
    default = option_items  # (user, 2026-11-02: default run review)


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
    """

    display_name = "Goal"
    option_story = 0
    option_story_and_side_missions = 1
    option_story_and_all_characters = 2
    default = option_story


class GameMode(Choice):
    """
    Standard: the usual run (story, challenges and quests, as the other options set them).
    Both modes open every service (shops, stables, dye shop, Smithy, Sheikah Sensor) from the start and put every
    check on level clears, spread evenly over the levels (bonus checks sent with each clear). Recipes are items
    (Progressive Recipe); with no recipe items in quest_reward_items you know every recipe from the start.
    Story Only: every check is on story missions (the DLC story too with include_dlc): no challenge or quest checks.
    Each story clear opens one new random story mission (The Battle of
    Hyrule Field is open). The goal: goal_story_missions story clears (goal_challenges is ignored).
    Challenges Only: every check is on challenge missions; story missions (except The Battle of Hyrule Field) and map
    quests don't appear. A few challenges are open at the start and each clear opens 3-8 more at random. The goal:
    goal_challenges clears (0 = 50); story options and final_mission_goal are ignored.
    """

    display_name = "Game Mode"
    option_standard = 0
    option_story_only = 1
    option_challenges_only = 2
    default = option_standard


class PostStoryUnlock(Range):
    """
    Post-story challenges and quests mix into the run before the goal (the client opens them in game).
    With a randomized unlock order (Challenge / Quest Unlock Order, default) they join the random openings and can
    open at any time (any number below 20). With a vanilla unlock order they open after this many story clears.
    20 = vanilla: they open after the whole story, and with a story-only goal they hold no checks.
    Post-story weapon drops can't be moved and still wait for the whole story.
    """

    display_name = "Post-Story Unlock"
    range_start = 1
    range_end = 20
    default = 10  # (user, 2026-10-28: post-story content mixed in before the goal; 20 = vanilla, no checks on it)


class FinalMissionGoal(DefaultOnToggle):
    """
    The Future of Hyrule (the final story mission) is the goal: it stays closed, with no unlock item, until you have
    cleared goal_story_missions - 1 other story missions and goal_challenges challenges (plus the goal option's
    extras). Then it opens, and clearing it wins. Off: the goal is just those clears, in any order.
    """

    display_name = "The Future of Hyrule Is the Goal"


class GoalStoryMissions(Range):
    """
    How many story missions the goal needs (any of them, in whatever order the seed opens them). The base game has 20;
    with include_dlc the 8 Guardian of Remembrance missions are story missions too (28). A number above what the
    seed has means all of them. Post-story content still opens only after the base story, as in the game.
    """

    display_name = "Goal Story Missions"
    range_start = 2
    range_end = 28
    default = 20  # (user, 2026-11-02: default run review)


class GoalChallenges(Range):
    """
    How many challenge missions the goal also needs (any of them; 0 = none). Lowered to the number of challenges in
    the seed (challenge_checks must be on for any to exist). goal_difficulty applies to these too.
    """

    display_name = "Goal Challenges"
    range_start = 0
    range_end = 168  # the base game's challenges (no Expansion Pass), so the goal is always reachable
    default = 25  # (user, 2026-11-02: default run review)


class DifficultyChecks(Choice):
    """
    Extra checks for clearing story missions (and challenges, see Difficulty Checks on Challenges) on harder
    difficulties: every difficulty from Normal up to this one adds one check per mission. A clear sends the checks of
    its difficulty and of every easier one (a Hard clear also sends the Normal check), so nothing has to be replayed.
    Off: one check per mission, any difficulty. The client reads the game's own per-difficulty clear records.
    Ignored when Difficulty Lock is on.
    """

    display_name = "Difficulty Checks"
    option_off = 0
    option_normal = 1
    option_hard = 2
    option_very_hard = 3
    default = 0


class DifficultyChecksChallenges(DefaultOnToggle):
    """With Difficulty Checks: challenges get the extra per-difficulty checks too (story missions always do)."""

    display_name = "Difficulty Checks on Challenges"


class DifficultyLock(Choice):
    """
    Lock clears to a difficulty, so lowering it can't be used to cheese: a story mission or challenge only counts
    (sends its checks, opens what it opens, counts for the goal) when cleared on this difficulty or a harder one. A clear
    on an easier difficulty counts for nothing and the client tells you to replay it. Every check of a mission comes
    from that one clear (no per-difficulty checks). The Battle of Hyrule Field, already cleared in the starter save, is
    exempt. The game's own difficulty menu is not changed.
    """

    display_name = "Difficulty Lock"
    option_off = 0
    option_normal = 1
    option_hard = 2
    option_very_hard = 3
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
    default = frozenset({"Terrako Guardian", "Fairy Fountains"})  # cooking is open from the start unless locked here (user, 2026-11-02)


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
    default = 30  # (user, 2026-11-02: default run review)






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
    visibility = Visibility.none  # 0.9.73: Challenge Unlock Order / Quest Unlock Order (game_rules here still wins)


class ChallengeUnlockOrder(Choice):
    """
    How challenges open.
    Randomized: a few are open from the start and 2-4 more challenges or quests open after every completion (story
    clear, challenge or quest), in a random order; the client opens them in game. Heroes and runes a challenge needs
    still apply.
    Vanilla: challenges open as in the game, following challenge_logic.
    """

    display_name = "Challenge Unlock Order"
    option_randomized = 0
    option_vanilla = 1
    default = option_randomized


class QuestUnlockOrder(Choice):
    """
    How quests open.
    Randomized: a few are open from the start and 2-4 more challenges or quests open after every completion (story
    clear, challenge or quest), in a random order; the client opens them in game. Reward items a quest needs still
    apply.
    Vanilla: quests open as in the game (its story gates and quest prerequisites; post-story ones after
    post_story_unlock story clears).
    """

    display_name = "Quest Unlock Order"
    option_randomized = 0
    option_vanilla = 1
    default = option_randomized


class ChallengeLogic(Choice):
    """
    When challenge checks are expected to be available, with Challenge Unlock Order: vanilla (randomized order
    ignores this). The real unlock conditions are not verified.

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
    Character XP Gift levels up a hero. Weapons: Extra Weapon = 1 random weapon, Weapon Bundle = 3 and Large Weapon
    Bundle = 5 (each for a different hero). Weapon XP Gift (older seeds) now also gives 1 weapon. Material bundles:
    Small = 10 each of 3 materials, Material Bundle = 15 each of 5, Large = 25 each of 8. Rupee Pouch = 1000 rupees,
    Hearty Meal = cooking ingredients.
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


class HintMissionUnlocks(DefaultOnToggle):
    """
    Every story mission unlock item (mission_unlocks: items) is hinted for free when the room starts, so you can see
    where each mission's unlock is. Off: find them the normal way.
    """

    display_name = "Auto-Hint Mission Unlocks"


class HintHeroes(DefaultOnToggle):
    """Every hero (Character item) you can receive is hinted for free when the room starts."""

    display_name = "Auto-Hint Heroes"


class GoalBanner(DefaultOnToggle):
    """
    While you're on the world map, a small banner at the top of the emulator window shows your goal progress (story
    missions, challenges and side missions still needed, and the goal difficulty). "/goal_banner on|off" in the
    client changes it for your own game.
    """

    display_name = "Goal Progress Banner"


class HeroLevelCap(Toggle):
    """
    Heroes stop at level 99: the client lets them level up in game as usual (which refills hearts and the special
    gauge), and when one reaches 100 it puts them back to 99 a few seconds later.
    """

    display_name = "Cap Heroes at Level 99"


class StartWithSheikahSensor(DefaultOnToggle):
    """
    Start with the Sheikah Sensor (the quest Needed: Researchers! is already done), so it points you to materials
    from the first mission. Its quest holds no check, and Progressive Sheikah Sensor items are not used.
    """

    display_name = "Start with the Sheikah Sensor"


class StartWithTrackers(Toggle):
    """
    Start with the treasure trackers and the Korok tracker: The Treasure Hunter's Technique, The Treasure Detector
    (and its upgrade) and A Most Peculiar Korok are already done and hold no checks.
    """

    display_name = "Start with Treasure and Korok Trackers"


class OpenStables(DefaultOnToggle):
    """Every stable is open from the start: its quest is already done and holds no check, and no stable items."""

    display_name = "Stables Open from the Start"


class OpenShops(DefaultOnToggle):
    """
    Every shop (except the dye shop) is open from the start: their quests are already done and hold no checks, and
    no shop items are used (overrides Shops in locked_features).
    """

    display_name = "Shops Open from the Start"


class OpenDyeShop(DefaultOnToggle):
    """The dye shop (Dyeing to Make Contact) is open from the start: its quest is already done and holds no check."""

    display_name = "Dye Shop Open from the Start"


class RegionHopeChecks(Toggle):
    """
    The "Hope of <region>" quests complete by themselves when a region's map is 100% done. On: each region's Hope
    completion holds a check. Off (default): they hold no checks. The Hope of All Hyrule (every quest and mission on
    the map) never holds a check: by then the goal is long done.
    """

    display_name = "Region Hope Checks"


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


option_groups = [
    OptionGroup("Characters", [StartingCharacterCount, StartingCharacterPool, IncludeDLC]),
    OptionGroup("Checks", [WeaponChecks, ChallengeChecks, QuestChecks, SideCheckDensity, MissionOrder, FirstMission, MissionUnlocks, StartingMissionUnlocks,
                           SideMissionsPerUnlock]),
    OptionGroup("Goal and Logic", [GameMode, Goal, FinalMissionGoal, GoalStoryMissions, GoalChallenges, PostStoryUnlock, RegionHopeChecks, GoalSideMissions, GoalDifficulty, StoryParty, SideUnlocks, ChallengeUnlockOrder, QuestUnlockOrder, ChallengeLogic, WeaponCheckLogic, SheikahRunes]),
    OptionGroup("Difficulty", [DifficultyChecks, DifficultyChecksChallenges, DifficultyLock]),
    OptionGroup("Pace", [CatchUpLevels, MinimumCharacterLevel, HeroLevelCap]),
    OptionGroup("Start Open", [StartWithSheikahSensor, StartWithTrackers, OpenStables, OpenShops, OpenDyeShop]),
    OptionGroup("Hints", [HintMissionUnlocks, HintHeroes, GoalBanner]),
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
