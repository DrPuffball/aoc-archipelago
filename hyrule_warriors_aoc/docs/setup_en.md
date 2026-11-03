# Hyrule Warriors: Age of Calamity Randomizer Setup Guide

## What you need

- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases/latest) 0.6.7 or newer
- `hyrule_warriors_aoc.apworld`, installed into Archipelago
- Your own legally dumped copy of the game, updated to v1.4.1, in **Ryujinx** or **Eden** on Windows
- Ryujinx: Options > Settings > System > **Memory Manager Mode: Software**. Eden: **CPU accuracy Auto** (the default).
  The client reads and writes the game's memory through these.

## 1. Make your YAML
Install the apworld (double-click it, or put it in `custom_worlds`). Open the Options Creator in the Archipelago
Launcher, or edit the sample YAML. Then generate as in the
[Archipelago Setup Guide](/tutorial/Archipelago/setup_en#generating-a-game).

## 2. Before the first session
Start the game once in your emulator so a save exists (if you have never played, pick New Game, wait for the first
cutscene, then close the game). Open only one emulator at a time.

## 3. Play
With the game **closed**, open **Age of Calamity Client** from the Archipelago Launcher and connect to your room
with your slot name. The client sets up this seed's save by itself: a new seed gets a starter save (your previous save
is kept and comes back when you connect to its seed again; switching between seeds works the same way). Then start
Age of Calamity and pick **Continue** (on a new seed, pause and go back to the map once so everything shows up).
The game reads its save only when it boots, so connect the client before starting the game. Everything else is
automatic:

- The client finds the running game by itself and says `Connected to Age of Calamity in Ryujinx` (or `in Eden`).
- Story missions, challenges, quests and weapons you complete or find are sent the moment the game registers them.
- Everything you receive is applied in game while you play: heroes become playable (and heroes you don't have are
  locked), upgrades, quest rewards, runes, mission unlocks, weapons, rupees, materials and XP.
- The world map follows the seed: only missions and challenges your seed has opened can be started.
- If the game isn't running, consumables you receive are written into the save file instead (backups in
  `%USERPROFILE%\AoC_Archipelago\backups`); everything else is applied the next time the game runs.
- Starting a New Game is detected, and everything you received is given again.
- The same seed can be played in both emulators: start the game once in the other one, close it, and type
  `/sync_saves`. From then on the newest save is copied over the older one whenever no game runs (with a backup).
- The client finds Ryujinx's data in `%APPDATA%\Ryujinx` and next to a portable Ryujinx, and Eden's in
  `%APPDATA%\eden` (a portable Eden while it runs). If your Ryujinx is elsewhere, type `/ryujinx_folder <folder>`.

Useful commands (information only, nothing needs to be typed to play): `/check_hook` shows the game connection,
`/todo` your goal progress and what you can play now, `/inventory` what you have received, `/deliver` what is still waiting for the game,
`/saves` which save belongs to which seed, `/sync_saves` copies your save to the other emulator now.

Universal Tracker works with this world without your YAML.

## Troubleshooting
- **Game not detected:** load a save (not just the title screen). Ryujinx: Memory Manager Mode "Software". Eden: CPU
  accuracy Auto. The game must be v1.4.1. Close any other Age of Calamity client window and any second emulator.
- **No save found:** start the game once in your emulator; with a portable or moved Ryujinx use `/ryujinx_folder`.
- **Something went wrong:** quit without saving, or restore your save backup.
- **Version warning on connect:** the seed was made with an older apworld. New client features work with it; options
  added later only apply to newly generated seeds.
