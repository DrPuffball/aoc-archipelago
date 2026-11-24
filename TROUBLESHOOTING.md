# Troubleshooting: Hyrule Warriors: Age of Calamity in Archipelago

## The normal way to start (avoids most problems)

1. Keep the game **closed**. Open the Archipelago Launcher > **Age of Calamity Client** and connect to your room.
2. The client puts the right save in place by itself: a new seed gets a starter save ("Starter save installed"), and a
   seed you played before gets its own save back. Whatever save was there is backed up first. It also installs or
   updates the "AoC Archipelago" game mod in Eden and Ryujinx.
3. Start the game in Ryujinx or Eden and pick **Continue**.

The game only reads its save when it boots, so the client can only switch saves while the game is closed.

## Common problems

**A banner says "This save belongs to another seed".**
The game loaded the save of a different seed (or a save the client doesn't know). Close the emulator and wait until the
client says the save was set up (about 10 seconds), then start the game again. If the client says it won't replace
a save with progress it can't place, type `/starter_save` (that save is kept in `%USERPROFILE%\AoC_Archipelago\saves`).

**The Smithy, the Training Camp or new icons are missing on the map.**
The client redraws the map by itself, but only while the Map tab is showing (not the Chapters or Quests list): go
back to the Map tab, or pause and return to the map once. If the Smithy is still missing, check your YAML: with
`weapon_fusion: true` it opens only with the Weapon Fusion item (and its quest bought).

**The client holds clears back and asks for `/accept_save`** (notice "Clears held back").
The save in the emulator showed many clears the server has never seen, or would finish your goal at once. That usually
means another seed's save is in the slot. Close the game and check `/saves`. Type `/accept_save` only if the save
really is this seed's (for example you played offline for a while).

**I can't finish a mission: it needs Remote Bombs and I don't have them.**
Revali, the Rito Warrior (rocks on the updrafts); Urbosa, the Gerudo Chief (defeat the Yiga with bombs); and When Courage
Fails (topple the trees) can't be finished without them. Leave the mission and come back later: `!hint Rune: Remote Bombs`
shows where they are. Seeds made before 0.9.93 could expect you to finish these without bombs; new seeds never do. If such
a seed is truly stuck, the host can send the rune with `/send <your name> Rune: Remote Bombs`.

**Runes: the Sheikah Slate shows runes I don't have, or none of mine.**
The game mod isn't active. Close the emulator with the client open: it installs the mod within about 10 seconds. Check
"AoC Archipelago" is enabled in the game's Add-Ons list (Eden: right-click the game > Properties; Ryujinx: right-click
the game > Manage Mods). When the game starts, the client log says "Archipelago game mod active".

**The frame rate stays at 30, or the game runs too fast or too slow.**
`frame_rate` above 30 is experimental and needs the client connected and the game mod active. Check the mode with
`/fps` (or the client's Options tab) and change it there or with `/fps 60`, `/fps unlimited` and so on. Remove any
other 60 FPS cheat or mod for the game. In Eden keep "Fast CPU time" off (it makes the game run fast). Cutscenes and the
world map always stay at 30; the pause menu does too unless switched on in the Options tab. `/fps off` leaves the
game's frame timing alone.

**A rod or apples are missing from my item palette.**
With `rod_items` (or `apple_items`) each one appears once you have its item, from the next mission you start: one
found mid-mission shows after that mission.

**The client says it can't find or read the game.**
Load your save (the title screen isn't enough). Ryujinx: Options > Settings > System > Memory Manager Mode
**Software**. Eden: CPU accuracy **Unsafe** or **Auto** (not Accurate or Paranoid). The game must be v1.4.1. Open only one emulator at a time.

**"Several emulators are open".**
Close all but one. The client won't touch the game or your saves while it can't tell which one is playing.

**The goal isn't completing.**
Type `/todo`: it lists what the goal still needs. The banner on the map shows it too. Check `goal_difficulty`: if it's
set, only clears on that difficulty or harder count (a notice tells you when a clear was too easy).

**A mission or challenge isn't open.**
`/todo` lists the story missions you can play. With `mission_unlocks: items`, a story mission needs its "Unlock:"
item. Challenges and quests open a few at a time as you complete things (the client shows "Now open: ...").

**I don't have the Expansion Pass.**
Set `include_dlc: false` in your YAML. If a seed includes the DLC anyway, the client warns you
when the game starts. Type `/no_dlc` to take it out of the goal and send its checks, so the seed stays winnable. If you
do have the DLC, check it's installed and enabled for the game in your emulator, and ignore the warning.

**An EX Alert won't hold a check / can't be opened early.**
That's expected: the game gives each Alert its monster when it appears, which the client can't do yet. Alerts appear
and play as in the normal game (Forgotten Temple, the Battle-Tested Guardian fight, is a normal check).

**DeathLink: my health went to 0 but I'm still alive.**
With the game mod active a received death defeats your hero at once. Without it (an older mod, or the mod off) the
death holds your health at 0 until your next hit, which brings up the defeat menu; healing and switching heroes won't
save you, and leaving or restarting the mission ends it. Close the emulator with the client open to install the mod.

**Switching between Ryujinx and Eden.**
Start the game once in the other emulator, close it, and type `/sync_saves`. After that the client keeps both copies
of your seed's save the same whenever no game is running.

**Something went wrong in game.**
Quit without saving, or restore a copy from `%USERPROFILE%\AoC_Archipelago\backups` (the client backs up every save it
replaces).

## Reporting a problem

Open an issue on GitHub with what happened and what you expected, your YAML, and the client log (Archipelago `logs`
folder, newest `Launcher_*.txt`). Testers can type `/research on` in the client and attach
`%USERPROFILE%\AoC_Archipelago\research\findings.jsonl` too.
