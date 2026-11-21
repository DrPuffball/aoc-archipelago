# Hyrule Warriors: Age of Calamity

## Before you start: the starter save

Start the Archipelago client and connect to your slot **before** booting the game. For a new seed the client
installs a **starter save** in your emulator (your old save is backed up in `%USERPROFILE%/AoC_Archipelago/
backups`). Then boot Age of Calamity in Ryujinx or Eden and pick **Continue**: the game's forced opening (The Battle
of Hyrule Field with Link and Impa) is skipped and you start on the world map with your starting heroes and the
seed's first missions (`first_mission`, default any story mission; with the default `mission_unlocks: items` you
start with 2 unlocked).

**The Battle of Hyrule Field** is a normal story mission: it can be in any slot,
has its own unlock item and real checks, and plays as the game's own first mission (the opening, then the battle as
Link) when you get to it. The client's game mod stops the game from forcing it at the start; the client installs the
mod by itself while the emulator is closed. (In Challenges Only it comes cleared in the starter save.)

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
the start (stables, shops, dye shop, Sheikah Sensor, the Expansion Pass's Royal Ancient Lab; options in the "Open from the Start" group) hold no check. Expansion Pass
content (on by default with `include_dlc`) is treated like the base game's: the 8 Guardian of Remembrance missions
are story missions (goal, unlock items), EX challenges and quests are checks, and the DLC heroes are items. Without
the DLC in your emulator the client warns you, and `/no_dlc` takes it out of the goal and sends its checks.

**Items**
- Heroes: you start with `starting_character_count` (default 4) random heroes from `starting_character_pool`;
  the rest arrive as items. `hint_heroes` hints them all from the start.
- Mission unlocks (`mission_unlocks: items`): each story mission opens with its own item; `hint_mission_unlocks`
  hints them all.
- Upgrades: Heart Containers, Combo Upgrades, Special Gauge Upgrades and Enhanced Abilities per hero, plus
  Progressive Weapon Capacity, Progressive Seal Slot and Weapon Fusion.
- Quest rewards (`quest_reward_items`, 0 = vanilla). Rewards that only raise a number (hearts, lessons, apple
  capacity...) are progressive items; groups of different rewards (recipes, shops, stables, discounts, Smithy
  upgrades, research quests, dyes, Divine Beast upgrades, EX reward quests) are one item per reward, named after
  its quest, such as `Recipe (A Feast of Greens)`. Most give their reward directly: recipes, the
  Sheikah Sensor and its research, Divine Beast upgrades, rune cooldowns, heart recovery, damage taken, enemy XP, treasure detector,
  blacksmith and rust/seal upgrades, discounts, Smithy upgrades, Training Camp and cooking lessons, dyes, apple
  capacity, research rewards, Expansion Pass abilities and royal gift weapons. The client undoes a quest's own reward until its item arrives. Maz Koshia's trials are the exception: each trial is the next fight, so its item opens the quest.
- Royal Ancient Lab rewards (with `lab_checks`): each node you buy sends a check; its reward is an item, such as `Buy Apples (An Abundance of Apples)` or a lab weapon. All 35 nodes are open from the start; each still needs its materials and its own condition, such as defeating 100 enemies with Remote Bombs.
- Weapons.
- Filler (weights set by `filler_weights`): character XP gifts, free weapons (Extra Weapon 1, Weapon Bundle 3, Large
  Weapon Bundle 5, for different heroes), Rupee Pouches, Small / regular / Large Material Bundles, Hearty Meals.

## Goal

`goal_story_missions` (2-28, default 20; the base game has 20, the DLC adds 8) sets how many story missions the
goal needs, and `goal_challenges`
(0-168, default 25) how many challenge missions on top. With `final_mission_goal` (on by default) The Future of Hyrule
has no unlock item: it opens once you have the other clears, and clearing it wins. `goal_difficulty` makes the goal's
clears count only on that difficulty or a harder one (a harder clear counts for every easier difficulty).
`difficulty_lock` goes further: no clear below that difficulty counts for anything, and the client raises the game's
difficulty setting to at least that level whenever you are on the map.
`goal_hope_of_all_hyrule` adds The Hope of All Hyrule (every region's map at 100%) to the goal: a very long run. With `final_mission_goal`, clear The Future of Hyrule first (some of the map opens only after it); the goal is done once both are. Not available in `challenges_only`.

## Game modes

`game_mode` changes the shape of the run. Both alternatives open every service from the start and put every check
on level clears, spread evenly (bonus checks sent with each clear); recipes are items.
- **Story Only:** every check is on story missions (the Guardian of Remembrance missions too with the DLC). Each
  clear opens one new random story mission; with `mission_unlocks: items` (the default) story missions open by
  their unlock items instead, as in Standard. The goal is `goal_story_missions` clears. Korok seed and chest checks
  are the story missions' own (122 seeds, 153 chests, plus the Expansion Pass story's 28 chests).
- **Challenges Only:** every check is on challenge missions; story missions (except the pre-cleared Battle of
  Hyrule Field) and map quests don't appear. Each clear opens 3-8 more challenges; with
  `challenge_unlock_order: items` each challenge opens by its own unlock item instead, and 12 start unlocked. The goal
  is `goal_challenges` clears (0 = 50). Korok seed checks are the 12 seeds inside challenges; chest checks are only
  the Expansion Pass story's 28 chests (with the DLC those missions are challenges here).

## Pacing and DeathLink

There are no traps. With `steady_rewards` (on by default) story mission clears never hold your own filler.
`hero_level_cap` keeps heroes at 99 (they still level up and refill). With `death_link` on, your hero's HP reaching 0
in a mission is sent to the others, and a death from someone else defeats you at once: your health drops to 0 and the
game's normal defeat menu comes up (Restart Battle / Exit Scenario). Deaths that arrive while you're not in a mission are
ignored, and one that arrives while the game is paused lands when you unpause. (This needs the client's game mod from
0.9.91; with an older copy still installed your health stays at 0 until the next hit instead. Close the emulator once
and the client updates it.)

## Side content

With `challenge_unlock_order` and `quest_unlock_order` randomized (default), a random handful of challenges and
quests is open from the start and every completion (story clear, challenge or quest) opens 2-4 more. The client opens
and closes them in game and shows "Now open: ..." over the emulator window. Set either to vanilla to keep the game's
own order. `challenge_unlock_order: items` (off by default) makes every challenge open with its own
"Unlock: <challenge>" item instead, like story missions with `mission_unlocks: items`; it needs challenge checks.
Maz Koshia's trial and the fairy fountain challenges still wait for their quests. When another player
releases or collects, quests whose checks are already gone are completed for you (with their reward when the client
knows it). `region_hope_checks` makes each region's 100% "Hope" quest a check.

## Korok seeds, chests and progress checks

`korok_checks` and `chest_checks` (on by default) make every Korok seed ("Korok Seed: <mission> #n") and treasure chest
("Treasure Chest: <mission> #n") a check, sent the moment you find it. Seeds and chests that need a rune (Stasis
targets, bombable rocks, half-buried chests) expect that rune first.

Off by default ("Progress Checks" group):
- `hero_level_checks`: a check per hero every `hero_level_check_interval` levels up to `hero_level_check_max`
  ("Hero Level: Link Lv 20"). Higher levels expect more of the story first.
- `weapon_level_checks`: a check per hero when their best weapon reaches every `weapon_level_check_interval` levels
  up to `weapon_level_check_max` ("Weapon Level: Link Lv 10"). The game caps weapons at 20, 25 after A Monumental
  Undertaking and 30 after The Legendary Blacksmith; levels above a cap need its quest (or are left out).
- `enemy_defeat_checks`: enough of an enemy type defeated, counted by the trophies earned in total ("Defeated: Lynel
  (1)"). `material_checks`: enough of a material gathered in total ("Gathered: Hyrule Herb (2)"). Up to
  `gathering_check_tiers` rising counts each, scaled by `enemy_defeat_scale` / `material_scale` (percent). The client
  keeps the totals from the moment the seed first connects: spending doesn't lower them, and materials the client
  hands you don't count. Type `/gathered` (or use the Options tab) to see your totals and the next count each needs.
  A material held at the game's 999 limit gains nothing until some is spent.

## Sheikah Slate runes

`sheikah_runes` (default `shuffled`): all four runes from the start (`start_with_all`), `shuffled` (each rune is an item, Remote
Bombs too) or `vanilla` (from the story: Remote Bombs and Cryonis in The Battle of Hyrule Field, Magnesis and Stasis in
Road to the Ancient Lab).
The unmodded game hands runes out whenever those story missions count as cleared, so the client installs a small game
patch (the "AoC Archipelago" mod for game version 1.4.1, which also does the frame rates below) into Eden's and Ryujinx's mod folders while the emulator is
closed. With it, the game shows exactly the runes the client gives. Start the client before the game.

## Elemental rods and apples

`rod_items` (default on): the Fire Rod, Ice Rod and Lightning Rod are items. A rod whose item hasn't been found has no
slot in the item palette (hold L) at all, and one picked up in a mission is taken away again. The palette is set up when
a mission loads, so a rod found mid-mission appears from the next mission on. The lab's
"An Apple a Day" research (fire rod kills) expects the Fire Rod first. Off: the rods work as in the normal game.

`apple_items` (default off): healing apples are an item ("Apples"). Until it is found the apple slot (hold L, then B)
has no slot in the palette, and the apple count stays at 0 in missions as a fail-safe. Like the rods, it appears
from the next mission after the item arrives.

## Frame rate

`frame_rate` (default `off`, the game's own 30 left alone; the higher modes are experimental): `fps_60`, `fps_120` or `unlimited` let the game draw up to that many frames a second
in gameplay (cutscenes, menus and the world map stay at the game's own 30). An older YAML's `fps_30` means `off`. The game normally slows down when it can't draw its target frame rate; the client keeps it at real-time
speed whatever your PC draws, by choosing how many of the game's 1/60 s steps each drawn frame takes. How many frames
you get depends on your PC and emulator settings (resolution scale and GPU accuracy cost the most).
In the client, the Options tab or `/fps 60`, `/fps 120`, `/fps unlimited`, `/fps off` or `/fps seed` change it for your game;
`/fps` shows it. Remove other 60 FPS cheats for the game: they fight the client.

## Rules of the story

Story missions start with your own heroes in their party (`story_party: free`); a hero you don't have yet is never
forced in. With `story_party: borrowed` missions keep their own forced heroes, and any you
don't have are lent to you for that mission only (while the map cursor is on it and during the battle). Calamity Strikes needs Mipha, Daruk, Revali and Urbosa (the game traps any Champion you don't have after
it). Only challenges that restrict the party in the base game (for example "Daruk's Training") need the matching hero.

`mission_order` can shuffle which mission sits in each story slot. `side_missions_per_unlock` makes each
later slot also require completed challenges and quests (slot N needs N x that many).

## Known limitations

- EX Alerts stay playable but never hold checks (except Forgotten Temple): the game gives each one a monster when it
  appears, which the client can't set yet.
- Windows only; Ryujinx (Memory Manager Mode Software) or Eden (CPU accuracy Unsafe or Auto; recommended); both tested in full play.
- Universal Tracker works with this world without your YAML.
