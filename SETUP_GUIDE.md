# Setup guide: Hyrule Warriors: Age of Calamity in Archipelago

For a new player, from nothing to playing. Windows only (the client works with the Ryujinx emulator's memory).

## What you need

1. **Your own copy of Age of Calamity, updated to v1.4.1**, running in **Ryujinx** on Windows (built and tested with
   Ryujinx 1.3.3). The Expansion Pass is optional.
2. **Archipelago 0.6.7 or newer**: https://github.com/ArchipelagoMW/Archipelago/releases/latest (install it normally).
3. **`hyrule_warriors_aoc.apworld`** (from this project).

## One-time setup

1. **Install the apworld:** double-click `hyrule_warriors_aoc.apworld`, or copy it into Archipelago's
   `custom_worlds` folder (usually `C:\ProgramData\Archipelago\custom_worlds`). Restart the Archipelago Launcher.
2. **Ryujinx setting:** Options > Settings > System > **Memory Manager Mode: Software**. Save, and restart the game
   if it was running. The client can't see the game without this.
3. **Have a save:** start Age of Calamity once on your Ryujinx user profile so a save exists. If you never played,
   pick New Game, wait for the first cutscene, then close the game.
   Your existing save is safe: the client keeps every save it replaces and gives it back (see "Switching seeds").

## Make your options (YAML)

Open the Archipelago Launcher > **Options Creator**, pick Hyrule Warriors: Age of Calamity, set what you like and
export the YAML. Or edit `Hyrule Warriors Age of Calamity.yaml` from this project. Give the YAML to whoever
generates the multiworld (they need the apworld too). Good defaults are already set; the options most people
change:

- `starting_character_count`: how many random heroes you start with (default 4).
- `challenge_checks`, `quest_checks`, `weapon_checks`: which side content holds checks (default: challenges and quests on, weapons off).
- `mission_unlocks`: `items` = each story mission opens with its own item from the multiworld.
- `first_mission`: which mission you start on (default a random early one).
- `goal_story_missions`: how many story missions win the game (default all 20).
- `death_link`: share deaths with the other players.

## Play

1. Keep the game **closed**. Open the Archipelago Launcher > **Age of Calamity Client** and connect to the room:
   the address (for example `archipelago.gg:38281`) and your slot name.
2. The client sets up this seed's save by itself and says so in its window ("Starter save installed").
   A new seed starts on its first mission with your random starting heroes, all at level 1 with a starter weapon.
3. Start Age of Calamity in Ryujinx and pick **Continue**. The client finds the game by itself
   ("Connected to Age of Calamity in Ryujinx").
4. Play. Everything is automatic: clears, quests and challenges you complete are sent to the multiworld; heroes,
   upgrades, runes, weapons, rupees, materials and XP you receive appear in game; the world map only lets you start
   what your seed has opened; new challenges and quests open as you complete things. Short notices appear in the
   corner of the Ryujinx window.

## Switching seeds

Each save belongs to the seed it was played with. To play another seed, close the game, then connect the client to
the other room: it swaps the saves (the one you leave is kept in `%USERPROFILE%\AoC_Archipelago\saves`). Connecting
back to the first room brings its save back, with every hero, level, weapon and clear as you left them. If the game
is still open when you connect, the client waits and switches as soon as you close it.

## Client commands (optional)

`/todo` what you can play now · `/inventory` what you have received · `/check_hook` the game connection ·
`/deliver` items waiting for the game · `/saves` which save belongs to which seed · `/ryujinx_folder` where the client
looks for your saves · `/starter_save` replace a save the client doesn't recognise (it is kept, not deleted).

## Troubleshooting

- **"No Age of Calamity save found":** start the game once on your Ryujinx profile. If your Ryujinx is portable or
  keeps its data elsewhere, open Ryujinx > File > Open Ryujinx Folder, copy that folder's path and type
  `/ryujinx_folder <that path>` in the client.
- **"Ryujinx is running Age of Calamity but the client can't read the game":** check Memory Manager Mode is Software
  (then restart the game), the game is v1.4.1 (Ryujinx shows the version in its window title), and pick Continue to
  load a save.
- **"Save not changed: ...":** the client refused to replace a save it can't place (it says why). Nothing is lost.
- **Something looks wrong in game:** quit without saving, or restore a copy from `%USERPROFILE%\AoC_Archipelago\backups`.
- **Version warning when connecting:** the room was made with an older apworld; it still works, but options added
  later only apply to new rooms.

## Known limits

- Remote Bombs is always yours (the game ties it to the Sheikah Slate itself); with shuffled runes, Cryonis,
  Magnesis and Stasis are the rune items, but the game still gives you Cryonis for now (being researched).
- Purah & Robbie and Sooga (Expansion Pass) don't show on the Allies screen when received.
- Only Ryujinx on Windows is supported.
