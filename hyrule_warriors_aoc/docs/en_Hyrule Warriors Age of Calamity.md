# Hyrule Warriors: Age of Calamity

## Before you start: the starter save

Start the Archipelago client and connect to your slot **before** booting the game. For a new seed the client
installs a **starter save** on your Ryujinx profile (your old save is backed up in `%USERPROFILE%/AoC_Archipelago/
backups`). Then boot Age of Calamity and pick **Continue**: the game's forced opening (The Battle of Hyrule Field
with Link and Impa) is skipped and you start on the world map with your starting heroes and the seed's first mission
(`first_mission`, default a random chapter 1-2 mission).

**Switching seeds:** each save belongs to the seed it was played with. Connect to another seed with the game closed
and the client swaps the saves: the current one is kept in `%USERPROFILE%/AoC_Archipelago/saves`, and the other
seed gets its own save back (or a starter save if it's new). Switch back the same way, as often as you like. While
the game runs another seed's save, the client leaves the game alone until you close it. A save with progress the
client has never seen with any seed is only replaced by `/starter_save` (it's kept as "unclaimed"). `/saves` lists
which save belongs to which seed. Your profile needs an Age of Calamity save to exist (start the game once). Seeds
made before 0.9.54 keep the vanilla opening but can still be switched to and from.

## Where is the options page?

The [player options page for this game](../player-options) contains all the options you need to configure and export a
config file.

## What does randomization do to this game?

Your goal is to clear all 20 main story missions, ending with "The Future of Hyrule". Heroes, upgrades, weapons and
filler are shuffled into the multiworld; the things you accomplish become checks that send items to other players.

**Checks (locations)** - story mission clears always; optionally (any combination, set in `side_content`,
default weapons, challenges and quests): weapon pickups, challenge missions and side quests. When there are more items
than checks, story clears get bonus checks (spread evenly, sent with the clear) instead of items being handed out.
With a story-only goal and `weapon_check_logic: after_story`, weapon drops are no checks (they'd only open after the
goal); they drop as vanilla weapons. `side_check_density` thins the quest, challenge and
Korok checks for shorter games. Expansion Pass content only appears with `include_dlc`.

**Items**
- Heroes: you start with `starting_character_count` (default 4) random heroes from `starting_character_pool`;
  the rest arrive as items.
- Upgrades: Heart Containers, Combo Upgrades, Special Gauge Upgrades and Enhanced Abilities per hero, plus
  Progressive Weapon Capacity, Progressive Seal Slot and Weapon Fusion.
- Quest rewards (`quest_reward_items`, copies per item, 0 = vanilla): Inner Power/Knowing/Protection, rune upgrades,
  hot springs, tailored clothes, tactics research, treasure detector, blacksmith and rust/seal upgrades, shops and
  stables. The client undoes a quest's own reward until its item arrives. Shop and stable quests hold no check
  then. The Smithy and the Military Training Camp are open from the start.
- Weapons.
- Filler (weights set by `filler_weights`): character XP gifts, weapon XP gifts, extra weapons, rupees, materials, meals.

## Goal

`goal_story_missions` (2-20, default 20) sets how many main story missions the goal needs (any of them), and
`goal_challenges` (default 0) how many challenge missions on top. `goal_difficulty` (any / easy / normal / hard /
very_hard / apocalyptic) makes both count only when cleared on that difficulty or a harder one; a harder clear counts
for every easier difficulty, so nothing has to be replayed. Post-story content still opens only after the whole story.

## Pacing and DeathLink

There are no traps. With `steady_rewards` (on by default) story mission clears never hold your own filler, so every
clear pays out a hero, upgrade or weapon; filler lands on side checks. With `death_link` on, your hero's HP reaching 0
in a mission is sent to the others, and a death from someone else knocks you out and restarts your mission.

## Side content

With `side_unlocks: shuffled` (default) a random handful of challenges and quests is open from the start and every
completion (story clear, challenge or quest) opens 2-4 more, picked at random per seed. The client opens and closes
them in game and shows "Now open: ..." over Ryujinx. `side_unlocks: game_rules` keeps the game's own order instead.

## Sheikah Slate runes

Remote Bombs is always yours: the game ties it to the Sheikah Slate itself (without it every rune is hidden). With
`sheikah_runes: shuffled` Cryonis, Magnesis and Stasis are items, everyone gets a free hint for where they are when
the room starts, and the client keeps Magnesis and Stasis off until you receive them. Cryonis is an item in logic only
for now: the game still gives it to you (its switch outside The Battle of Hyrule Field isn't found yet).

## Rules of the story

Any party can play any story mission, so four heroes are always enough. Only challenges that restrict the party in the
base game (for example "Daruk's Training") need the matching hero.

`mission_order` can shuffle which mission sits in each story slot. `side_missions_per_unlock` makes each
later slot also require completed challenges and quests (slot N needs N x that many).

## Known limitations

- The starter save (top of this page) is new in 0.9.54 and not yet confirmed in game.
- Purah & Robbie and Sooga (Expansion Pass) don't appear on the Allies screen when received; keep `include_dlc` off.
- Only Ryujinx on Windows is supported (the client reads and writes the emulator's memory).
