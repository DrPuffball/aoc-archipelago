# Hyrule Warriors: Age of Calamity - reverse-engineering notes

This file explains how the game keeps its state and how the Archipelago client reads and changes it. It is written
for the next person (human or AI) working on this project. Read it before changing anything in `hyrule_warriors_aoc/client`.

All addresses are for **game version 1.4.1** (main NSO build id `e5f275b5...`). The code is the source of truth:
every constant below also lives in the client (`client/live_hook.py`, `client/ryujinx.py`, `data_save.py`,
`data_rewards.py`), usually with a comment saying how it was found.

Confidence labels used throughout:
- **[confirmed]** seen working in the running game (usually by writing it and watching the result)
- **[read]** read from game data, code or memory, but the effect has not been tested by writing it
- **[guess]** inferred from a pattern; needs a test

No game files, dumps or saves are part of this repository. To repeat the static work you need your own legally
dumped copy of the game (RomFS + ExeFS).

---

## 1. Getting at the game's memory

The client never patches the game. It reads and writes the emulator's process memory (Windows, `ReadProcessMemory`
/ `WriteProcessMemory`), so everything here is about finding guest (Switch) addresses inside the emulator process.

The game's main module is called "the module" below. All module-relative addresses assume the module's guest
address in Ryujinx, `MODULE_BASE = 0x8504000`.

### Ryujinx (tested on 1.3.3)
- Memory Manager Mode must be **Software**. Ryujinx then keeps a page table in its own memory: one u64 per 4 KiB guest
  page holding that page's host address.
- To find the table, the client looks at each large allocation, takes the entry for the page of the game's save
  writer function (module + `0x9ACF60`), and checks whether that host page holds the function's first 64 bytes
  (`WRITER_SIG`). [confirmed]

### Eden (tested on 0.2.1; yuzu family)
- With "fastmem" on (the default; CPU accuracy Auto), guest address `g` lives at host `arena + g`. [confirmed]
- The arena start is **not** a memory-region boundary, so it can't be found directly. The module, however, starts
  exactly at a committed region. Reading `WRITER_SIG` at `region + 0x9ACF60` for each region finds it with one read
  per region. [confirmed]
- The module loads at a different guest address than in Ryujinx (`0x8071A000` seen). The slot at module offset
  `0x263E000` (start of `.data`) holds its own guest address, so `M = [module + 0x263E000] - 0x263E000` and
  `arena = module host - M`. [confirmed]
- Module-relative addresses are relocated by `M - MODULE_BASE`. Heap pointers read from memory are real guest
  addresses and need no change.
- A loose "save loaded" check passes on empty memory. The client validates a layout with `LiveGame.save_ok()`: the
  save blocks have distinct pointers, the quest states vary and start with 1, and a mission is cleared.
- Eden's DLC record: `cache/game_list/01002B00111A2000.pv.txt` lists add-ons (`DLC (1, 1, 2, 2, 3, 3, 4, 4)`; 3 =
  Pulse of the Ancients, 4 = Guardian of Remembrance). `config/qt-config.ini [DisabledAddOns]` lists ones turned
  off. Ryujinx: `games/01002b00111a2000/dlc.json`.
- Saves: Ryujinx `bis/user/save/<id>/0/svdt` (`/1` is a working copy); Eden
  `nand/user/save/0000000000000000/<user id>/01002B00111A2000/svdt`.

---

## 2. The save manager and its blocks

`P = [module + 0x2780A48]` is the game-state manager. Most save-backed data hangs off it: `[P + field]` points to a
block. Several blocks keep a "saved copy" that the game copies back on save or load, so the client writes both.
[confirmed for each block it writes]

| field | block | contents |
|---|---|---|
| `0x550` | story flags | one byte per story flag at `+0x18C` (save `0x14..0x8F`); copies 0x700 apart (0 current, 3 saved). Rune flags at `+0x18C+5..8` = Remote Bombs, Cryonis, Magnesis, Stasis [confirmed] |
| `0x560` | quests | quest state bytes at `+0x809` (1101 entries; 1 not available, 2 available, 3 done); saved copy `+0x2550` [confirmed] |
| `0x568` | weapon pools | `[[pool+0x30]]` current, `[[pool+0x48]]` saved; 2139 records x 0x90, 71 per hero; `+0x0C` XP (u32), `+0x10` kind (u16), `+0x14` attack bonus (u16; shown damage = base + this), `+0x78` level - 1, `+0x87` rusted (1 = hidden until restored) [confirmed 2026-11-02]. The game recomputes level and attack bonus from XP (fusing did it), so a level written without XP lasts only until then. `+0x79` is not the level (meaning unknown) |
| `0x570` | ? | dye colours suspected around `+0x2D73` [guess] |
| `0x578` | research | Sheikah Sensor levels at `+0x780/+0x781/+0x783` [read] |
| `0x580` | heroes | rows at `+0x224`, 0x20 each, slot order below; saved copy `+3*0x560` [confirmed] |
| `0x588` | profile | rupees u32 `+0x1E8`; materials u16 `+0x3E4 + 2*i`; "discovered" u8 `+0x7A9 + i`; combo levels `+0x73B + category`; copies at stride `0xC30` (copy 3 = saved) [confirmed] |
| `0x598` | missions | live mission records at `+0xE08`, 0xF4 each; six u32 clear times per difficulty just before (`-0x10`) [confirmed] |
| `0x5A0` | flags | general flags, e.g. max weapon level `+0x63F`; saved copy `+0x19B0` [confirmed for the ones the client writes] |
| `0x5A8` | map state | world-map cursor: u16 id `+0x148`, kind byte `+0x14A` (2 story, 3 challenge, 4 quest); per-mission map states `+0x14C`, `+0x81C` [confirmed]; quest icons at `+0x2DC + quest id` (saved copy `+0x6D0`; 3 = done/grey, 2 = available/orange): a hand-in sets these as well as the quest block [confirmed 2026-11-02] |

Hero row (live, 0x20 bytes): `+0x04` XP u32, `+0x08` hearts/ATK/DEF u16 x3, `+0x0E` level-1, `+0x10` equipped weapon
type, `+0x15` playable, `+0x16..0x18` roster flags. Hero slots: Link 0, Zelda 1, King Rhoam 2, Mipha 3, Daruk 4,
Revali 5, Urbosa 6, Impa 7, Sidon 8, Yunobo 9, Teba 10, Riju 11, Hestu 12, Great Fairies 13, Master Kohga 14, Monk Maz
Koshia 15, Terrako 16, Calamity Ganon 17, (18 Battle-Tested Guardian), Purah & Robbie 19, Sooga 20.

XP per level and hearts per level come from the game's own table (LinkData2 `007bd714`; `data_save.HERO_XP_TABLE`,
`HERO_HEARTS_TABLE`). ATK and DEF rise by 3 per level. [confirmed by recorded level-ups]

### Battle, HP and DeathLink
- Battle object `B = [[module + 0x2B63708] + 0x30]`, controlled character `[B + 0x8]`, display HP float `+0x28`,
  max `+0x2C` (400 per heart). Outside missions a stale object can remain, so a valid battle needs a sane max HP
  (400..60000). [confirmed]
- Real HP: unit table `[[module + 0x2780A80] + 0x8] + 0x176E70 + unit*0x6C`, HP float at `+0x44`. [confirmed]
  The record starts with (unit, kind) u32s. The character's first field is not always its unit index: on Eden
  (2026-11-02) it read 0 while the controlled hero was record 50 (same kind 9, HP 5200/5200). The client falls back
  to the record of that kind whose (HP, max HP) match the character's display copy. [confirmed layout; fallback
  untested in a live DeathLink]
- Mission flow: u32 at `[module + 0x2780A80] + 0xB0`, low byte 0 playing, 4 defeated, 12 defeat menu. A natural KO on
  Eden (2026-11-03): `00 04` playing, `04 04` at the hit, `0C 04` about 2 s later with the menu up, `0C 25` when Retry is
  picked, then `00 75`, `00 54` playing again. [confirmed]
- DeathLink: real HP and display copy held at 0; the next hit is a real KO with the death animation and defeat menu,
  and Retry works. [confirmed on Eden, without the client's other writes running] Forcing requests at `+0xB8` (flag
  byte 2 at `+0xB3`) is taken next frame but has no animation or menu: 4 then 12 froze on the sepia picture on Eden
  in both a story and a challenge mission (state stays `0C 04`). Do not use it.

- Instant-KO experiments (Eden, 2026-11-03, none shipped). A recorded KO changes real HP +0x48 to 0 and char `+0x4C`
  (u32) by +4000 (older notes said u16 = 4000: wrong). Those writes alone: hero stays standing at 0 hearts. With
  request 4 from play: death animation, controls off; then request 12: sepia, no menu, stuck (byte 1 set to 0x25 or
  0x54 afterwards, or 0x54 beforehand, changes nothing). With request 4 sent from the pause menu (flow low byte 0x60):
  animation on unpause, no sepia, then request 12 restarted the mission in 1.1 s (seen once). The defeat menu itself
  only came from a real hit. Byte 1 read 0x04 on first attempts and 0x54 after a restart. Forced 4 then 12 on an attempt
  already restarted: animation, sepia, restart in about 1 s (3 of 3); on a first attempt it freezes even with `+0xB1`,
  `+0xC9` = 0x54 and `+0x120` = 0 set first, so what is missing lies outside this object.

### Game data tables in memory
`[[module + 0x2780A38] + field] + 0x60`: `0x698` mission parameters (400 rows), `0x308` mission unlock table
(which clears open a mission), `0x300` quest unlock table (1000 x 36 bytes; `+4` five u16 records, `+14` five u16
quests needed). The client rewrites rows of these tables to change unlock order. [confirmed]

---

## 3. The save file (`svdt`, 1 MiB, unencrypted, no checksum)

- Byte 0 = format `0x89`. Mission records: 400 x 0x84 at `0x2CF34`. A mission is cleared when any of the six u32 at
  `record+4` is non-zero (slot 0 Easy, 1 Normal, 2 Hard, 3 Very Hard). [confirmed]
- Record numbers come from the game's mission text table (LinkData2). Two-part story missions have two records, and
  both must be cleared. Mapping: `data_save.MISSION_RECORD_IDS`.
- Rupees u32 `0x2C3A4`; materials u16 `0x2C14E + 2*i`; discovered `0x2C2DD + i`; heroes 30-byte rows at `0x2BCAD`.
  [confirmed; partly from a public save editor]
- The client edits the file only while no emulator runs the game. A starter save (the first mission pre-cleared)
  lets a seed skip the forced opening.

---

## 4. Quests and their rewards

Static data: the quest table (LinkData2 `0086ee94`, 1000 rows x 80 bytes after a 16-byte header; row index = quest
state id).
- `+0x10` cost amounts (u16 x6) and `+0x26..+0x2A` material ids.
- `+0x1E` **reward type** (inventory in `tools/QUEST_TYPES.md`).
- `+0x30..+0x3F` type-specific parameters.

| type | reward | where it lands | status |
|---|---|---|---|
| 1 | combo upgrade | profile `+0x73B + category` | [confirmed] client forces |
| 2 | enhanced ability | profile `+0x121 + category` | [confirmed] |
| 3 / 4 | hearts / special gauge | profile `+0xAFC + hero` / `+0xB19 + hero` | [confirmed] |
| 15 | weapon capacity | profile `+0x7A6` tier | [confirmed] |
| 16 | shops | follow the quest state (+ flags `0x319..0x323` [read]) | [confirmed] |
| 17 | stables | quest state + flag pair (e.g. `0x5BB` on, `0x72E` off) [read] | partly |
| 18 / 19 | regional discounts | counters = number of the type's quests handed in: flags `0x5DA/0x5DB/0x5DC/0x5DE` type 18 (Rebuilding Akkala Bridge raised all four 3 -> 4), `0x5D9/0x5DD` type 19 (Great Bridge Repairs, What Bad Weather?, The Lazy Guards, The Marita Exchange) | [confirmed for 18; 19 by the same rule] |
| 29 | Sheikah Sensor | profile `+0xC7B` = 1 | [read] |
| 30 | sensor research | research `+0x780/+0x781/+0x783` = row `+0x34..+0x36` (1/1/1, 3/3/2, 4/4/2) | [read] |
| 32 / 34 | cooking / recipes | profile `+0x2B5 + row[+0x38]` = 1 (matches all 19 measured) | [read] |
| 33 | cooking lesson | row `+0x37` = 1; Snowbound Cook flag `0x643` | [guess] |
| 43 | Divine Beast upgrade | row `+0x3B` = beast 1..4; profile `0x871 + beast` = 1 | [confirmed: Surveying the Volcano set 0x873] |
| 35, 36, 48, ... | Maz Koshia trial, research, dyes, ... | see `tools/QUEST_TYPES.md` | unknown |

Unknown rewards, read from recorded hand-ins (materials were at max, so some rewards can't show) [read, 2026-11-03]:
- Maz Koshia trials (type 35): `[0x578]+0x2B0/2B2/2B4` u16 list + flag: Stones 358, Monsters 357 (and FLAGS `0x70F` = 4),
  Mighty Foe 359. Offering Help on the Road changes nothing beyond its cost. They open Trial of the Ancients.
- Research quests (type 36): quest table `+0x3A` material index + 1, `+0x3D` outfit id: every one has a material, and
  Rumor about Skull Lake, Cold Desert Nights and Visiting a Special Shop add outfits 19, 20, 21. Amounts seen: 2-3.
- Terrako's Return: profile `+0xB37` 2 -> 3 (meaning unknown). Hot Meals in a Pot: FLAGS `0x1A07`, profile `+0x2C3`.
- Never handed in yet: 29 EX reward quests, Ancient-Material Delivery, Seething Malice, Reigning Malice, Fiery Inspiration.

### The Battle of Hyrule Field and the rune flags
Its script sets the rune flags (story flags 0x19-0x1C) itself before the last wave and waits for them: the three moblins spawn only then [confirmed 2026-11-07: forcing Cryonis/Magnesis/Stasis off soft-locked the mission; switching them on spawned the moblins at once]. The client doesn't touch runes during that mission.

### One-shot flags: never force them
`[0x5A0]+0x65B` is the "Contributions to Hyrule" tutorial-seen flag [confirmed: forcing it to 0 replays the tutorial, and unrelated hand-ins set it]. `+0x65C` is also set by unrelated hand-ins, and `+0x651` sits beside them [guess: same kind]. The client leaves all three alone.

### Royal Ancient Lab (Expansion Pass) [confirmed live on Eden, 2026-11-04]
- 35 nodes: state list `[0x550]+0x4AE2 + node`, mirror `[0x5A0]+0x3AA5 + node` (1 locked, 2 open, 3 done). Writing 2 opens a node.
- The lab shows on the map once `[0x5A0]+0x1A0F` is 1 (Road to the Ancient Lab's clear sets it).
- Node table in memory, rows 0x40 apart (found by node 26's costs 2, 5, 10 at +0x23 and 0xA9 at +0; reloaded whenever the lab opens):
  `+0x1B` u32 condition target, `+0x23` five u16 costs, `+0x2D` condition mission record, `+0x2F` reward weapon kind, `+0x31` attack
  bonus, `+0x33` reward material count, `+0x35` five material index + 1, `+0x3A` condition type, `+0x3B` condition weapon type,
  `+0x3C` ally given, `+0x3D` bonus weapon type, `+0x3E` weapon capacity bonus.
- Condition types, in text order: 1 defeat with weapon type, 2 copy weapons, 3 perfect dodges, 4 Remote Bomb kills, 5 Magnesis throw-backs,
  6 Stasis stops, 7 Cryonis freezes, 8 complete a mission, 9 fire rod kills.
- The client keeps kill-count conditions in a normal game; it clears none. The two relic nodes ask for The Future of Hyrule, so they hold no checks when that mission is the goal.
- Clearing target AND type (`+0x1B`, `+0x3A`, `+0x3B`) makes a conditioned node buy like a plain one, reward included. Clearing only
  the target shows the reward screen, but the purchase changes nothing.
- Zeroing `+0x2F`, `+0x31`, `+0x3E` or `+0x3C` removes that reward from a purchase; the node still costs materials and finishes.
- Stored rewards are in tools/QUEST_MAP.md and `data_lab.py`. Profile `+0xC0F` rod duration, `+0xC10..0xC13` bomb [inferred from the
  other three], Magnesis, Stasis, Cryonis damage, `+0xC2C/+0xC2D` attack research counters (+10 attack at weapon record `+0x76`), `+0xC88`
  Seal Boost, `+0xC89` baked apples; flags `[0x5A0]+0x1A03, 0x1A08..0x1A0B, 0x1A0D, 0x1A0E, 0x640`; `[0x570]+0xF555` relic counter 0-2.
  Weapon capacity is profile `+0x7A6`, the same byte the capacity quests use. `[0x578] + 0x25A0 = [0x588]`, so `[0x578]+0x31AF` is profile `+0xC0F`.
- The Technology of Disassembly changes only its node state; Roll Out the Research and Sensor of the Heart showed no separate byte either [not seen].

- Selected node: the panel keeps a pointer to its title (UTF-16 at pointer + 6) in a heap object that moves each boot. The client scans for pointers to node titles and keeps the one that changes to another node's title [pointer followed one hover live; the client's use of it not yet seen].

### Quest table in memory
Rows of 80 bytes from `+0x10`, found 213168 bytes past the quest unlock table. Zeroing a row's reward fields (`+0x30..0x3F` research,
`+0x1C` royal gift weapon) stops the vanilla reward: the panel shows the reward as x0 [panel seen; a full hand-in with an empty row not yet watched].

How the client uses this (`data_rewards.py`):
- **store** groups: the reward item sets the bytes; the client forces them to what the received items give.
- **quest** groups: the service follows the quest state, opened once the item arrives.
- **unlock** groups: the quest is locked until its item arrives; new seeds use this only where the quest is the reward (Maz Koshia's trials, locked features).
- **research** groups: the quest row is emptied and the item gives materials and outfit once.
- When two groups touch one byte, the higher value wins. A vanilla-completed quest of an inactive group keeps its
  reward.
- `data_save.QUEST_EFFECTS` holds bytes the client sets when it marks a quest done itself (open from the start, or
  collected by another player's release).

---

## 5. Tools

The client and probe ship in this repository. The research scripts under `tools/` are kept in the project's working
folder and are not published yet (they expect local game dumps); they are listed so their role is known.

- `client/probe.py`: **the research probe** (`/probe on` in the client). It is read-only and writes JSON lines to
  `%USERPROFILE%/AoC_Archipelago/probe/`. Findings:
  - `quest_done`: save-block diff at each quest hand-in; the main way rewards are found.
  - `state_change`: save changes on the map outside quest hand-ins (menu choices, unlocks).
  - `mission_start` / `mission_end`: diffs around a battle, with the map cursor.
  - `clear_slot`: difficulty slot of each clear.
  - `effect`: every client write re-checked after 20 s / 5 min / after a mission.
  - `reverted` / `fight`: the game undoing a client write.
  - `game_lost`: the client's last writes when the game disappears.
  - `level_up`, `ko`, `runes`, `deathlink`, `check`, `received`.
- `tools/aoc_extract.py`, `aoc_unchunk.py`: unpack LinkData2 (chunked zlib) into its ~2228 tables.
- `tools/aoc_dis.py`, `a64.py`, `aoc_xref.py`: ARM64 disassembly and cross-references over the NSO.
- `tools/aoc_mem.py`, `aoc_recorder.py`, `aoc_hunt.py`, `aoc_snap.py`: older live-memory scanners and recorders,
  from before the probe existed.
- `tools/make_starter_save.py`: builds the starter save template.

### Research method that works
1. Check the quest table and game data first. A row parameter often names the exact byte (recipes, sensor).
2. Turn the probe on and do one thing in game: one hand-in, one menu change, one mission.
3. Read `findings.jsonl`. Separate materials and rupees (the costs) from reward bytes. A byte with a twin at
   `+0x2490` (profile) is that byte's saved copy.
4. Test by writing on a backed-up save. Record the result as [confirmed] in this file and in `tools/RESEARCH.md`.

---

## 6. Open questions

- EX Alert sightings: where the game stores the monster an Alert gets (needed before Alerts can be checks or
  open from the start).
- Battle-Tested Guardian's combo / ability category is 26 by elimination [guess]; confirm with its quests.
- The difficulty selector byte. Not in any block under the save manager or the param holder (about 400 blocks,
  0x8000 each, diffed across Hard / Very Hard / Easy on 2026-11-02): only the save timestamp changed (manager
  `+0x740` u32 ticks, `+0x744` year u16, then month, day, hour, minute bytes). Probably the system/options data.
- The weapon XP curve (XP -> level, per weapon; samples: 644 XP = level 13 on one weapon, 655 = level 12 on the
  Master Sword). Would allow a weapon level gift that lasts past a fusion (dropped for weapon bundles in 0.9.74).
- Terrako's level only showing after a reload: what refreshes the hero display.
- Rewards still unknown: research quests (type 36), Maz Koshia trials (35), dyes (48), training lessons (31),
  cooking lessons (33).
- DLC (2026-11-02, both waves installed, Eden) [confirmed]: opening EX missions works like base ones (unlock row
  zeroed + the four state lists = 2); EX quests like base quests (quest state 2 + map icon 2). Purah & Robbie (slot 19)
  and Sooga (slot 20) show on the hero list when granted like any hero; the earlier "not shown" result was with Pulse
  of the Ancients missing. Battle-Tested Guardian = hero slot 18, weapon type `+0x12` = 221 (types step by 10 per slot; owned-weapon kinds
  likewise come in blocks of 10 from each hero's starter kind: 191-193 claymores are King Rhoam's only, 201-202
  Mipha's, 221-222 Revali's [confirmed by the user in game, 2026-11-03]),
  starter weapon kind 371 (Battle-Tested Screw); granted the same way, it shows and is playable. EX Alerts other
  than Forgotten Temple (the Guardian fight) need a sighting: forced open without one, the mission crashed loading.
- Save loading [confirmed 2026-11-02, Eden]: the game reads the save file only when it boots. Back at the title screen
  the save manager still holds the loaded save, and Continue does not re-read the file (a different save swapped in
  at the title screen was ignored; the game would write its own copy back on the next save). So a save can only be
  switched while the game is closed.
- Service flags [confirmed 2026-11-02]: flags `0x318 + service id` (quest table type 16 row `+0x32`): shops 1-6,
  Smithy 8 (`0x320`), dye shop 9, Military Training Camp 10 (`0x322`), Relief for Soldier Stress 11. The facility only
  appears on the map with its flag set; marking the quest done alone left the Training Camp missing.
- Challenge forced parties: mission parameter table `t009cc294` `+71..+74` (support `+75..+79`), 71 challenge
  records force heroes (shipped as data_save.VANILLA_CHALLENGE_PARTY); the client swaps in your heroes like the story.
- EX Safe Roads, Safe Rides (411) and EX Burning Desire (433), both type 1: combo-upgrade category 24 went 5 -> 6 and
  27 0 -> 1 (profile `0x73B + category`), plus profile `0x398`/`0x399` 0 -> 1, `0xAF8` 1 -> 19, flags `0xF2E` 0 -> 1
  [read, one hand-in pass; which byte belongs to which quest not separated].
- 2026-11-02: forcing every mission/challenge/quest open (unlock rows zeroed, 118 states set) while the player was
  handing in a quest froze the game (Eden). The save on disk was untouched. Never rewrite the quest unlock table or
  quest states during a hand-in; retest the force-open in steps with the player idle.
- Random emulator crashes reported by one player: no data yet (the probe's `game_lost` exists for this).

The chronological lab notebook with every session's raw findings is kept privately (`tools/RESEARCH.md`, not
published, since it holds local paths). This file is its curated summary.
