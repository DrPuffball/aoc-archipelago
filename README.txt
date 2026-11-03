HYRULE WARRIORS: AGE OF CALAMITY - ARCHIPELAGO RANDOMIZER
=========================================================

An Archipelago (https://archipelago.gg) multiworld randomizer for Hyrule Warriors: Age of Calamity, played on
the Ryujinx or Eden emulator on Windows. A live client runs beside the game and does everything automatically: it sends
your checks, gives you the items your friends find, locks and unlocks heroes, missions, challenges and quests, and
shows short notices over the game window.

DOWNLOAD THE APWORLD (latest version):
  https://github.com/DrPuffball/aoc-archipelago/releases/latest/download/hyrule_warriors_aoc.apworld

Latest version, ready to install (double-click it). All versions and notes: https://github.com/DrPuffball/aoc-archipelago/releases.

Testing release. The game is huge and there is a lot of ground to cover. Please report anything odd (see
REPORTING PROBLEMS below).

WHAT YOU NEED
-------------

- Computer: Windows (the client reads and writes the emulator's memory; Linux/macOS are not supported)
- Emulator: Ryujinx (tested 1.3.3) or Eden (tested 0.2.1), set up with your own keys and firmware dumped from your
  own Switch. The client detects which one you use; open only one at a time. No emulator, keys, firmware or game
  files are provided or linked here.
- Game: Your own legally dumped Hyrule Warriors: Age of Calamity (Switch, title ID 01002B00111A2000) updated to v1.4.1. The Expansion Pass (both waves) is used by default; without it, set include_dlc: false. This project contains no game files.
- Archipelago: 0.6.7 or newer (download: https://github.com/ArchipelagoMW/Archipelago/releases/latest)
- This world: hyrule_warriors_aoc.apworld (direct download: https://github.com/DrPuffball/aoc-archipelago/releases/latest/download/hyrule_warriors_aoc.apworld)

INSTALLATION (ONCE)
-------------------

1. Install Archipelago.
2. Download hyrule_warriors_aoc.apworld
   (https://github.com/DrPuffball/aoc-archipelago/releases/latest/download/hyrule_warriors_aoc.apworld)
   and double-click it (or copy it into Archipelago's custom_worlds folder,
   usually C:\ProgramData\Archipelago\custom_worlds). Restart the Archipelago Launcher.
3. Emulator setting. Ryujinx: Options > Settings > System > Memory Manager Mode: Software, then save (the client
   can't read the game without it). Eden: leave CPU accuracy on Auto (the default).
4. Make sure the game is updated to v1.4.1 in your emulator.
5. Start the game once in your emulator so a save exists (if you never played: New Game, wait for the first
   cutscene, close the game).

MAKING YOUR OPTIONS
-------------------

Archipelago Launcher > Options Creator > Hyrule Warriors: Age of Calamity, or edit the sample
Hyrule Warriors Age of Calamity.yaml (change name:). Give the YAML to whoever generates the multiworld; they need
this apworld installed too. The defaults are the tested setup; the options most people change:

- starting_character_count: random heroes you start with (default 4).
- challenge_checks / quest_checks / weapon_checks: which side content holds checks (default: challenges and quests on, weapons off).
- challenge_unlock_order / quest_unlock_order: randomized (default) or vanilla.
- mission_unlocks: items (default) = each story mission opens with its own item from the multiworld (you start
  with 2); story_order = in order.
- first_mission: which missions you can start on (default any story mission; random_early = chapters 1-2).
- goal_story_missions / goal_challenges: what the goal needs (default 20 of the 28 story missions and 25
  challenges). With final_mission_goal (on), The Future of Hyrule opens once you have them and clearing it wins.
- game_mode: standard, story_only (every check on story missions, each clear opens the next) or challenges_only
  (every check on challenges, no story or map quests).
- difficulty_checks / difficulty_lock: extra checks for harder clears, or clears below a difficulty don't count.
- Start Open: Sheikah Sensor, stables, shops and dye shop open from the start (on); trackers pre-done (off).
- hint_mission_unlocks / hint_heroes: free hints; hero_level_cap: heroes stay at 99 (level-ups still refill you).
- filler_weights: filler mix (default about 40% material bundles in three sizes).
- death_link: share deaths with the other players.

GENERATING AND HOSTING A ROOM (the host does this once per run)
---------------------------------------------------------------

The archipelago.gg website can't generate games for custom worlds like this one, so the host generates locally:

1. Install this apworld (see above) and put every player's YAML into Archipelago's "Players" folder
   (usually C:\ProgramData\Archipelago\Players).
2. Archipelago Launcher > Generate. The finished game appears as a .zip in Archipelago's "output" folder.
3. Host it: upload that .zip at https://archipelago.gg/uploads (free, gives you a room address to share),
   or Archipelago Launcher > Host to run the server on your own PC.
4. Every player connects the Age of Calamity Client to that room address with their slot name.

PLAYING
-------

1. Keep the game closed. Archipelago Launcher > Age of Calamity Client > connect to the room (address, e.g.
   archipelago.gg:38281, and your slot name).
2. For a new seed the client installs a starter save by itself ("Starter save installed"): the game's forced
   opening (The Battle of Hyrule Field) comes pre-cleared, and you start on the world map with your random starting
   heroes and the seed's first mission. Your previous save is kept (see below).
3. Start Age of Calamity in Ryujinx or Eden and pick Continue. The client finds the game by itself.
4. Play normally. Notices appear in the emulator window: items sent and received, what a gift went to, and - when you
   highlight a mission, challenge or quest on the world map - what its checks hold.

Switching emulators: the client keeps a seed's save the same in Ryujinx and Eden. Start the game once in the other
emulator, close it, and type /sync_saves; after that, whenever no game runs, the newest save is copied over the
older one (with a backup; never a New Game over progress).

Switching between seeds: each save belongs to the room it was played in. Close the game and connect to another
room: the client swaps the saves (yours are kept in %USERPROFILE%\AoC_Archipelago\saves) and gives each room its own
save back. It never replaces a save while the game runs, nor a save with progress it can't place
(/starter_save does that on purpose, keeping a copy).

Client commands (optional): /todo (goal progress, what to play), /inventory, /check_hook, /deliver, /saves, /sync_saves, /ryujinx_folder,
/starter_save, /goal_banner, /probe. Full details: SETUP_GUIDE.md.

HOW THE RANDOMIZER WORKS
------------------------

- Checks: clearing story missions, challenges and quests (weapon pickups optional). When there are more items than
  checks, a few extra "bonus" checks go on story clears and challenges.
- Items: heroes, per-hero upgrades (hearts, combo moves, special gauge, abilities), quest rewards, mission unlock
  items, the Cryonis / Magnesis / Stasis runes, and filler (hero XP gifts, weapon bundles, rupees, material bundles,
  meals). Most quest-reward items give their reward directly (recipes, Sheikah Sensor, rune and stat upgrades,
  discounts, Smithy upgrades, lessons, dyes...). A few (research quests, Maz Koshia's trials and the Expansion Pass reward quests) still open their quest, and you
  complete it for the reward (the client says which).
- Side content opens at random by default: a few challenges and quests are open from the start and every completion
  opens 2-4 more (post-story ones included). Either kind can be set to the game's own order instead.
- Story safety: Calamity Strikes needs Mipha, Daruk, Revali and Urbosa (the game traps any Champion you don't have
  after it). Other story missions, including Water and Fire and Air and Lightning, follow the seed's order.
- Heroes you don't have are locked (never during a battle); story missions put your own heroes in their forced party
  slots.
- When another player releases or collects, quests whose checks are gone are completed for you (with their reward
  where the client knows it).

KNOWN LIMITATIONS
-----------------

- Windows only, game v1.4.1 only. Ryujinx needs Memory Manager Mode Software; Eden needs CPU accuracy Auto. Both are
  tested in full play (Eden 0.2.1: a whole session of missions, quests, items, DLC and save switching).
- Remote Bombs is always yours (the game ties it to the Sheikah Slate). Cryonis is an item in logic, but the game
  still gives it outside The Battle of Hyrule Field.
- The Expansion Pass is on by default (include_dlc): the Guardian of Remembrance missions are story missions, EX
  challenges and quests hold checks, and Purah & Robbie, Sooga and the Battle-Tested Guardian are items. EX Alerts
  stay playable but never hold checks (except Forgotten Temple). Without the DLC in your emulator, the client
  takes the DLC out of the goal and sends its checks, so the seed stays winnable; or set include_dlc: false.
- Post-story missions started before the story ends are untested: report any that won't load or behave oddly.
- The world map has twice got stuck in its "new icons appear" sequence (under investigation): returning to the title
  screen usually helps; save often.
- A few quest rewards (research quests, Maz Koshia's trials and the Expansion Pass reward quests) still open their quest, which you complete for the reward.
- Universal Tracker works without your YAML: connect it to your slot and it rebuilds the seed from the server.

REPORTING PROBLEMS
------------------

First see TROUBLESHOOTING.md (the usual fixes: close the game before switching seeds, pause and go back
to the map once on a new seed, /todo for what the goal needs).

Open an issue: https://github.com/DrPuffball/aoc-archipelago/issues with: what happened and what you expected, your YAML, the client log (Archipelago's
logs folder, newest Launcher_*.txt).
Testers can also type /probe on in the client: it then records which of its changes the game kept
or undid, quest rewards, and the client's last actions if the game crashes, in
%USERPROFILE%\AoC_Archipelago\probe\findings.jsonl; attach that file too.

SOURCE
------

hyrule_warriors_aoc/ is the world (logic, items, options), its client (client/) and tests (test/).
REVERSE_ENGINEERING.md explains how the game keeps its state and how the client reads and changes it (for anyone,
human or AI, picking up the project).
