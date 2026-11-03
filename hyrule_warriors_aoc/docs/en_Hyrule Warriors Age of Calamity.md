# Hyrule Warriors: Age of Calamity

## Before you start: the starter save

Start the Archipelago client and connect to your slot **before** booting the game. For a new seed the client
installs a **starter save** in your emulator (your old save is backed up in `%USERPROFILE%/AoC_Archipelago/
backups`). Then boot Age of Calamity in Ryujinx or Eden and pick **Continue**: the game's forced opening (The Battle
of Hyrule Field with Link and Impa) is skipped and you start on the world map with your starting heroes and the
seed's first missions (`first_mission`, default any story mission; with the default `mission_unlocks: items` you
start with 2 unlocked).

**Switching seeds:** each save belongs to the seed it was played with. Connect to another seed with the game closed
and the client swaps the saves: the current one is kept in `%USERPROFILE%/AoC_Archipelago/saves`, and the other
seed gets its own save back (or a starter save if it's new). While the game runs another seed's save, the client
leaves the game alone until you close it. A save with progress the client has never seen with any seed is only
replaced by `/starter_save` (it's kept as "unclaimed"). `/saves` lists which save belongs to which seed.

**Switching emulators:** one seed's save can live in both Ryujinx and Eden. Start the game once in the other
emulator, close it, and type `/sync_saves`; the client then keeps both copies the same whenever no game runs. Open
only one emulator at a time.

## Where is the options page?

The [player options page for this game](../player-options) contains all the options you need to configure and export a
config file.

## What does randomization do to this game?

Heroes, upgrades, quest rewards, weapons and filler are shuffled into the multiworld; the things you accomplish become
checks that send items to other players.

**Checks (locations)** - story mission clears always; optionally (the `weapon_checks`, `challenge_checks` and
`quest_checks` toggles, default challenges and quests): weapon pickups, challenge missions and side quests.
`difficulty_checks` adds one check per mission (and challenge) for each harder difficulty you clear it on. When
there are more items than checks, story and challenge clears get bonus checks (sent with the clear).
`side_check_density` thins the quest, challenge and Korok checks for shorter games. Quests for services open from
the start (stables, shops, dye shop, Sheikah Sensor, the Expansion Pass's Ancient Tech Lab; options in the "Start Open" group) hold no check. Expansion Pass
content (on by default with `include_dlc`) is treated like the base game's: the 8 Guardian of Remembrance missions
are story missions (goal, unlock items), EX challenges and quests are checks, and the DLC heroes are items. Without
the DLC in your emulator the client takes it out of the goal and sends its checks.

**Items**
- Heroes: you start with `starting_character_count` (default 4) random heroes from `starting_character_pool`;
  the rest arrive as items. `hint_heroes` hints them all from the start.
- Mission unlocks (`mission_unlocks: items`): each story mission opens with its own item; `hint_mission_unlocks`
  hints them all.
- Upgrades: Heart Containers, Combo Upgrades, Special Gauge Upgrades and Enhanced Abilities per hero, plus
  Progressive Weapon Capacity, Progressive Seal Slot and Weapon Fusion.
- Quest rewards (`quest_reward_items`, copies per item, 0 = vanilla). Most give their reward directly: recipes, the
  Sheikah Sensor and its research, Divine Beast upgrades, rune cooldowns, heart recovery, damage taken, enemy XP, treasure detector,
  blacksmith and rust/seal upgrades, discounts, Smithy upgrades, Training Camp and cooking lessons, dyes, apple
  capacity. The client undoes a quest's own reward until its item arrives. A few (research quests, Maz Koshia's trials and the Expansion Pass reward quests)
  still open their quest, and you complete it for its reward.
- Weapons.
- Filler (weights set by `filler_weights`): character XP gifts, free weapons (Extra Weapon 1, Weapon Bundle 3, Large
  Weapon Bundle 5, for different heroes), Rupee Pouches, Small / regular / Large Material Bundles, Hearty Meals.

## Goal

`goal_story_missions` (2-28, default 20; the base game has 20, the DLC adds 8) sets how many story missions the
goal needs, and `goal_challenges`
(0-168, default 25) how many challenge missions on top. With `final_mission_goal` (on by default) The Future of Hyrule
has no unlock item: it opens once you have the other clears, and clearing it wins. `goal_difficulty` makes the goal's
clears count only on that difficulty or a harder one (a harder clear counts for every easier difficulty).
`difficulty_lock` goes further: no clear below that difficulty counts for anything.

## Game modes

`game_mode` changes the shape of the run. Both alternatives open every service from the start and put every check
on level clears, spread evenly (bonus checks sent with each clear); recipes are items.
- **Story Only:** every check is on story missions (the Guardian of Remembrance missions too with the DLC). Each
  clear opens one new random story mission. The goal is `goal_story_missions` clears.
- **Challenges Only:** every check is on challenge missions; story missions (except the pre-cleared Battle of
  Hyrule Field) and map quests don't appear. Each clear opens 3-8 more challenges. The goal is `goal_challenges`
  clears (0 = 50).

## Pacing and DeathLink

There are no traps. With `steady_rewards` (on by default) story mission clears never hold your own filler.
`hero_level_cap` keeps heroes at 99 (they still level up and refill). With `death_link` on, your hero's HP reaching 0
in a mission is sent to the others, and a death from someone else restarts your mission; deaths that arrive while
you're not in a mission are ignored.

## Side content

With `challenge_unlock_order` and `quest_unlock_order` randomized (default), a random handful of challenges and
quests is open from the start and every completion (story clear, challenge or quest) opens 2-4 more. The client opens
and closes them in game and shows "Now open: ..." over the emulator window. Set either to vanilla to keep the game's
own order. Maz Koshia's trial and the fairy fountain challenges still wait for their quests. When another player
releases or collects, quests whose checks are already gone are completed for you (with their reward when the client
knows it). `region_hope_checks` makes each region's 100% "Hope" quest a check.

## Sheikah Slate runes

Remote Bombs is always yours: the game ties it to the Sheikah Slate itself (without it every rune is hidden). With
`sheikah_runes: shuffled` Cryonis, Magnesis and Stasis are items, everyone gets a free hint for where they are when
the room starts, and the client keeps Magnesis and Stasis off until you receive them. Cryonis is an item in logic only
for now: the game still gives it to you.

## Rules of the story

Story missions start with your own heroes in their party (`story_party: free`); a hero you don't have yet is never
forced in. Calamity Strikes needs Mipha, Daruk, Revali and Urbosa (the game traps any Champion you don't have after
it). Only challenges that restrict the party in the base game (for example "Daruk's Training") need the matching hero.

`mission_order` can shuffle which mission sits in each story slot. `side_missions_per_unlock` makes each
later slot also require completed challenges and quests (slot N needs N x that many).

## Known limitations

- EX Alerts stay playable but never hold checks (except Forgotten Temple): the game gives each one a monster when it
  appears, which the client can't set yet.
- Windows only; Ryujinx (Memory Manager Mode Software) or Eden (CPU accuracy Auto); both tested in full play.
- Universal Tracker works with this world without your YAML.
