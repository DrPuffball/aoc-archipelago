# Hyrule Warriors: Age of Calamity Randomizer Setup Guide

## What you need

- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases/latest) 0.6.7 or newer
- `hyrule_warriors_aoc.apworld`, installed into Archipelago
- Ryujinx (Windows) with your own legally dumped copy of the game, updated to v1.4.1
- Ryujinx > Options > Settings > System > **Memory Manager Mode: Software** (the client reads and writes the game's
  memory through it)

## 1. Make your YAML
Install the apworld (double-click it, or put it in `custom_worlds`). Open the Options Creator in the Archipelago
Launcher, or edit the sample YAML. Then generate as in the
[Archipelago Setup Guide](/tutorial/Archipelago/setup_en#generating-a-game).

## 2. Before the first session
Start the game once on your Ryujinx profile so a save exists (if you have never played, pick New Game, wait for the
first cutscene, then close the game).

## 3. Play
With the game **closed**, open **Age of Calamity Client** from the Archipelago Launcher and connect to your room
with your slot name. The client sets up this seed's save by itself: a new seed gets a starter save (your previous save
is kept and comes back when you connect to its seed again; switching between seeds works the same way). Then start
Age of Calamity in Ryujinx and pick **Continue**. Everything else is automatic:

- The client finds the running game by itself and says `Connected to Age of Calamity in Ryujinx`.
- Story missions, challenges, quests and weapons you complete or find are sent the moment the game registers them.
- Everything you receive is applied in game while you play: heroes become playable (and heroes you don't have are
  locked), upgrades, quest rewards, runes, mission unlocks, weapons, rupees, materials and XP.
- The world map follows the seed: only missions and challenges your seed has opened can be started.
- If the game isn't running, consumables you receive are written into the save file instead (backups in
  `%USERPROFILE%\AoC_Archipelago\backups`); everything else is applied the next time the game runs.
- Starting a New Game is detected, and everything you received is given again.
- The client finds Ryujinx's data in the usual place (`%APPDATA%\Ryujinx`) and next to a portable Ryujinx. If yours is
  elsewhere it tells you; then type `/ryujinx_folder <folder>` (in Ryujinx: File > Open Ryujinx Folder shows it).

Useful commands (information only, nothing needs to be typed to play): `/check_hook` shows the game connection,
`/todo` what you can play now, `/inventory` what you have received, `/deliver` what is still waiting for the game,
`/saves` which save belongs to which seed, `/ryujinx_folder` where the client looks for your saves.

## Troubleshooting
- **Game not detected:** load a save (not just the title screen), check that Memory Manager Mode is "Software" and that
  the game is v1.4.1, and close any other Age of Calamity client window. The client warns after two minutes when
  Ryujinx shows the game but it can't read it. Built and tested with Ryujinx 1.3.3 on Windows.
- **No save found:** start the game once on your profile; with a portable or moved Ryujinx use `/ryujinx_folder`.
- **Something went wrong:** quit without saving, or restore your save backup.
- **Version warning on connect:** the seed was made with an older apworld. New client features work with it; options
  added later only apply to newly generated seeds.
