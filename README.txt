HYRULE WARRIORS: AGE OF CALAMITY - ARCHIPELAGO RANDOMIZER
=========================================================

An Archipelago (https://archipelago.gg) multiworld randomizer for Hyrule Warriors: Age of Calamity, played on
the Ryujinx emulator on Windows. A live client runs beside the game and does everything automatically: it sends
your checks, gives you the items your friends find, locks and unlocks heroes, missions, challenges and quests, and
shows short notices over the game window.

DOWNLOAD THE APWORLD (latest version):
  https://github.com/DrPuffball/aoc-archipelago/releases/latest/download/hyrule_warriors_aoc.apworld

Latest version, ready to install (double-click it). All versions and notes: https://github.com/DrPuffball/aoc-archipelago/releases.

Testing release. The game is huge and there is a lot of ground to cover. Please report anything odd (see
REPORTING PROBLEMS below).

WHAT YOU NEED
-------------

- Computer: Windows (the client reads and writes Ryujinx's memory; Linux/macOS are not supported)
- Emulator: Ryujinx, version 1.3.3 (the tested version; others untested), set up with your own keys and
  firmware dumped from your own Switch. No emulator, keys, firmware or game files are provided or linked here.
- Game: Your own legally dumped Hyrule Warriors: Age of Calamity (Switch, title ID 01002B00111A2000) updated to v1.4.1. The Expansion Pass is optional and is not used by the randomizer yet. This project contains no game files.
- Archipelago: 0.6.7 or newer (download: https://github.com/ArchipelagoMW/Archipelago/releases/latest)
- This world: hyrule_warriors_aoc.apworld (direct download: https://github.com/DrPuffball/aoc-archipelago/releases/latest/download/hyrule_warriors_aoc.apworld)

INSTALLATION (ONCE)
-------------------

1. Install Archipelago.
2. Download hyrule_warriors_aoc.apworld
   (https://github.com/DrPuffball/aoc-archipelago/releases/latest/download/hyrule_warriors_aoc.apworld)
   and double-click it (or copy it into Archipelago's custom_worlds folder,
   usually C:\ProgramData\Archipelago\custom_worlds). Restart the Archipelago Launcher.
3. In Ryujinx: Options > Settings > System > Memory Manager Mode: Software. Save. The client can't read the game
   without this.
4. Make sure the game is updated to v1.4.1 in Ryujinx (right-click the game > Manage Title Updates).
5. Start the game once on your Ryujinx user profile so a save exists (if you never played: New Game, wait for the first
   cutscene, close the game).

MAKING YOUR OPTIONS
-------------------

Archipelago Launcher > Options Creator > Hyrule Warriors: Age of Calamity, or edit the sample
Hyrule Warriors Age of Calamity.yaml (change name:). Give the YAML to whoever generates the multiworld; they need
this apworld installed too. The defaults are the tested setup; the options most people change:

- starting_character_count: random heroes you start with (default 4).
- side_content: Challenges and Quests as checks (default); Weapons optional.
- mission_unlocks: items = each story mission opens with its own item from the multiworld; story_order = in order.
- first_mission: the first mission you play (default a random early one).
- goal_story_missions: story missions needed to win (default all 20).
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
3. Start Age of Calamity in Ryujinx and pick Continue. The client finds the game by itself.
4. Play normally. Notices appear in the Ryujinx window: items sent and received, what a gift went to, and - when you
   highlight a mission, challenge or quest on the world map - what its checks hold.

Switching between seeds: each save belongs to the room it was played in. Close the game and connect to another
room: the client swaps the saves (yours are kept in %USERPROFILE%\AoC_Archipelago\saves) and gives each room its own
save back. It never replaces a save while the game runs, nor a save with progress it can't place
(/starter_save does that on purpose, keeping a copy).

Client commands (optional): /todo, /inventory, /check_hook, /deliver, /saves, /ryujinx_folder,
/starter_save. Full details: SETUP_GUIDE.md.

HOW THE RANDOMIZER WORKS
------------------------

- Checks: clearing story missions, challenges and quests (weapon pickups optional). When there are more items than
  checks, a few extra "bonus" checks go on story clears and challenges.
- Items: heroes, per-hero upgrades (hearts, combo moves, special gauge, abilities), quest rewards (shops, recipes,
  discounts, Divine Beast upgrades - each copy unlocks the next quest in the game's own order), mission unlock items,
  the Cryonis / Magnesis / Stasis runes, and filler (XP gifts, extra weapons, rupees, materials).
- Side content opens at random: a few challenges and quests are open from the start and every completion opens 2-4
  more (post-story ones included).
- Story safety: Calamity Strikes opens only once Mipha, Daruk, Revali and Urbosa are all yours (the game traps any
  Champion you don't have after it), and it opens Water and Fire and Air and Lightning itself.
- Heroes you don't have are locked; story missions put your own heroes in their forced party slots.

KNOWN LIMITATIONS
-----------------

- Windows + Ryujinx only, game v1.4.1 only, Memory Manager Mode Software required.
- Remote Bombs is always yours (the game ties it to the Sheikah Slate). Cryonis is an item in logic, but the game
  still gives it outside The Battle of Hyrule Field.
- The Expansion Pass stays vanilla (include_dlc: false); Purah & Robbie and Sooga don't appear in Allies when
  received.
- Post-story missions started before the story ends are untested: report any that won't load or behave oddly.
- The world map has twice got stuck in its "new icons appear" sequence (under investigation): returning to the title
  screen usually helps; save often.
- Some quest rewards stay vanilla (their memory addresses aren't found yet).
- Built and tested on Ryujinx 1.3.3 only.

REPORTING PROBLEMS
------------------

Open an issue: https://github.com/DrPuffball/aoc-archipelago/issues with: what happened and what you expected, your YAML, the client log (Archipelago's
logs folder, newest Launcher_*.txt) and %USERPROFILE%\AoC_Archipelago\probe\findings.jsonl (the client's
recorder notes which of its changes the game kept or undid).

SOURCE
------

hyrule_warriors_aoc/ is the world (logic, items, options), its client (client/) and tests (test/).
