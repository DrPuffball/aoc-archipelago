# Troubleshooting: Hyrule Warriors: Age of Calamity in Archipelago

## The normal way to start (avoids most problems)

1. Keep the game **closed**. Open the Archipelago Launcher > **Age of Calamity Client** and connect to your room.
2. The client puts the right save in place by itself: a new seed gets a starter save ("Starter save installed"), and a
   seed you played before gets its own save back. Whatever save was there is backed up first.
3. Start the game in Ryujinx or Eden and pick **Continue**.
4. On a new seed, **pause and go back to the map once** (a banner on the emulator window asks for this) so the
   Smithy, the Military Training Camp and every opened mission show up.

The game only reads its save when it boots, so the client can only switch saves while the game is closed.

## Common problems

**A banner says "This save belongs to another seed".**
The game loaded the save of a different seed (or a save the client doesn't know). Close the emulator and wait until the
client says the save was set up (about 10 seconds), then start the game again. If the client says it won't replace
a save with progress it can't place, type `/starter_save` (that save is kept in `%USERPROFILE%\AoC_Archipelago\saves`).

**The Smithy, the Training Camp or new icons are missing on the map.**
Pause and return to the map once: the map is drawn before the client finishes setting up. If the Smithy is still
missing, check your YAML: with `weapon_fusion: true` it opens only with the Weapon Fusion item (and its quest bought).

**The client says it can't find or read the game.**
Load your save (the title screen isn't enough). Ryujinx: Options > Settings > System > Memory Manager Mode
**Software**. Eden: CPU accuracy **Auto**. The game must be v1.4.1. Open only one emulator at a time.

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
That's expected: a received death holds your health at 0 until your next hit, which brings up the defeat menu.
Healing and switching heroes won't save you. Leaving the mission or restarting it from the pause menu ends it.

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
