# Setup guide: Hyrule Warriors: Age of Calamity in Archipelago

Going forward, development focuses on the Eden emulator: new features are built and tested on Eden first. The new Royal Ancient Lab features in 0.9.81 have been tested on Eden only.

For a new player, from nothing to playing. Windows only: the client works with the emulator's memory. Two emulators
are supported, **Ryujinx** and **Eden**. The client detects which one you are using.

## What you need

1. **Your own copy of Age of Calamity, updated to v1.4.1**, running in **Ryujinx** (tested with 1.3.3) or **Eden**
   (tested with 0.2.1) on Windows. The Expansion Pass (both waves) is used by default; without it, set
   `include_dlc: false`.
2. **Archipelago 0.6.7 or newer**: https://github.com/ArchipelagoMW/Archipelago/releases/latest (install it normally).
3. **`hyrule_warriors_aoc.apworld`** (from this project).

No emulator, keys, firmware or game files are provided or linked here.

## One-time setup

1. **Install the apworld:** double-click `hyrule_warriors_aoc.apworld`, or copy it into Archipelago's
   `custom_worlds` folder (usually `C:\ProgramData\Archipelago\custom_worlds`). Restart the Archipelago Launcher.
2. **Emulator setting:**
   - **Ryujinx:** Options > Settings > System > **Memory Manager Mode: Software**. Save, and restart the game if it
     was running. The client can't see the game without this.
   - **Eden:** leave **CPU accuracy on Auto** (the default). The client needs Eden's fast memory mapping, which the
     stricter accuracy settings turn off.
3. **Have a save:** start Age of Calamity once in your emulator so a save exists. If you never played, pick New Game,
   wait for the first cutscene, then close the game. Your existing save is safe: the client keeps every save it
   replaces and gives it back (see "Switching seeds").

**Open only one emulator at a time.** With Ryujinx and Eden both open, the client leaves the game and your saves
alone until one is closed.

## Make your options (YAML)

Open the Archipelago Launcher > **Options Creator**, pick Hyrule Warriors: Age of Calamity, set what you like and
export the YAML. Or edit `Hyrule Warriors Age of Calamity.yaml` from this project. Give the YAML to whoever generates
the multiworld (they need the apworld too). Every option has a tooltip; good defaults are already set. The options
most people change:

- `starting_character_count`: how many random heroes you start with (default 4).
- `challenge_checks`, `quest_checks`, `lab_checks`, `weapon_checks`: what holds checks (default: challenges, quests and
  the Royal Ancient Lab on, weapons off).
- `challenge_unlock_order`, `quest_unlock_order`: randomized (a few open, 2-4 more after each completion) or vanilla.
- `mission_unlocks`: `items` (default) = each story mission opens with its own item from the multiworld (you start
  with 2, hinted for free); `story_order` = in order. `first_mission` (default any) picks the starting ones.
- `goal_story_missions`, `goal_challenges`, `goal_quests`, `goal_all_heroes`: what the goal needs (default 20 of the 28 story missions and 25
  challenges). With `final_mission_goal` (on), The Future of Hyrule opens once you have those and clearing it wins.
- `game_mode`: `standard`, `story_only` (every check on story missions, each clear opens the next) or
  `challenges_only` (every check on challenges; no story missions or map quests).
- `difficulty_checks` (extra checks for harder clears) or `difficulty_lock` (clears below a difficulty don't count).
- "Open from the Start" group: Sheikah Sensor, stables, shops and the dye shop open from the start (on), trackers (off).
- `hint_mission_unlocks`, `hint_heroes`: free hints at the start. `hero_level_cap`: heroes stay at 99.
- `death_link`: share deaths with the other players.

## Play

1. Keep the game **closed**. Open the Archipelago Launcher > **Age of Calamity Client** and connect to the room:
   the address (for example `archipelago.gg:38281`) and your slot name.
2. The client sets up this seed's save by itself and says so in its window ("Starter save installed").
   A new seed starts on the world map with your random starting heroes.
3. Start Age of Calamity in your emulator and pick **Continue**. The client finds the game by itself
   ("Connected to Age of Calamity in Ryujinx" or "... in Eden"). On a new seed, pause and go back to the map once
   (a banner asks for it) so everything the client opened shows up.
4. Play. Everything is automatic:
   - Clears, quests and challenges you complete are sent to the multiworld.
   - Heroes, upgrades, quest rewards, runes, weapons, rupees, materials and XP you receive appear in game.
   - The world map only lets you start what your seed has opened, and new challenges and quests open as you go.
   - Short notices appear in the corner of the emulator window, including what a highlighted mission or quest holds.
   - When other players release or collect, quests whose checks are already gone are completed for you. Their
     reward is given too where the client knows it; otherwise they stay open so you can still earn it.

## Switching seeds

Each save belongs to the seed it was played with. To play another seed, close the game, then connect the client to
the other room: it swaps the saves (the one you leave is kept in `%USERPROFILE%\AoC_Archipelago\saves`). Connecting
back to the first room brings its save back, with every hero, level, weapon and clear as you left them. If the game
is still open when you connect, the client waits and switches as soon as you close it.

## Switching emulators (Ryujinx and Eden with one seed)

The client keeps a seed's save the same in both emulators, so you can go back and forth:

1. Start the game once in the other emulator (the title screen is enough) and close it.
2. Type `/sync_saves` in the client. The other emulator's save now belongs to your seed and gets your progress
   (its old content is backed up first).
3. From then on, whenever no game is running, the client copies the newest save over the older one, with a backup in
   `%USERPROFILE%\AoC_Archipelago\backups\save_sync`. It never copies a save with fewer story clears over one with
   more (for example after a New Game); `/sync_saves force` does that on purpose.

Close the game in one emulator before opening the other, and keep the client connected for a few seconds in
between.

## Universal Tracker

Universal Tracker works with this world without your YAML: connect it to your slot and it rebuilds the seed from the
server.

## Client commands (optional)

`/todo` your goal progress and what you can play now · `/inventory` what you have received · `/check_hook` the game connection ·
`/deliver` items waiting for the game · `/saves` which save belongs to which seed · `/sync_saves` copy your save to
the other emulator now · `/ryujinx_folder` where the client looks for Ryujinx saves · `/starter_save` replace a save
the client doesn't recognise (it is kept, not deleted) · `/goal_banner on|off` the goal progress banner on the map ·
`/research on|off` game research for testers: records what the game did with each change, on your PC only.

## Troubleshooting

The full guide is `TROUBLESHOOTING.md`. The most common ones:


- **"No Age of Calamity save found":** start the game once in your emulator. If your Ryujinx is portable or keeps
  its data elsewhere, open Ryujinx > File > Open Ryujinx Folder, copy that folder's path and type
  `/ryujinx_folder <that path>` in the client. A portable Eden is found while Eden is running.
- **"An emulator is running Age of Calamity but the client can't read the game":** Ryujinx: check Memory Manager
  Mode is Software (then restart the game). Eden: check CPU accuracy is Auto. Both: the game must be v1.4.1 (the
  window title shows it), and pick Continue to load a save.
- **"Several emulators are open":** close all but one.
- **"Save not changed: ...":** the client refused to replace a save it can't place (it says why). Nothing is lost.
- **Something looks wrong in game:** quit without saving, or restore a copy from `%USERPROFILE%\AoC_Archipelago\backups`.
- **Version warning when connecting:** the room was made with an older apworld; it still works, but options added
  later only apply to new rooms.

## Known limits

- Remote Bombs is always yours (the game ties it to the Sheikah Slate itself); with shuffled runes, Cryonis,
  Magnesis and Stasis are the rune items, but the game still gives you Cryonis for now (being researched).
- The Expansion Pass is on by default (include_dlc): the Guardian of Remembrance missions are story missions, EX
  challenges and quests hold checks, and Purah & Robbie, Sooga and the Battle-Tested Guardian are items. EX Alerts
  stay playable but never hold checks (except Forgotten Temple). Without the DLC in your emulator, the client
  takes the DLC out of the goal and sends its checks, so the seed stays winnable; or set include_dlc: false.
- Maz Koshia's trials: each trial is the next fight, so its item opens the quest. Other quest rewards come straight from their items.
- Ryujinx and Eden are both tested in full play (Eden 0.2.1).
