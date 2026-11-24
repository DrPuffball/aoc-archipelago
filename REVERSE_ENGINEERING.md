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
- With "fastmem" on (CPU accuracy Auto or Unsafe; Accurate/Paranoid turn it off), guest address `g` lives at host `arena + g`. [confirmed]
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
- DeathLink, instant (2026-11-19, Eden GDB stub, shipped in the game mod 0.9.91) [confirmed on Eden]:
  - The flow "state" is a u64 bitfield at `F+0xB0` (F = `[main+0x2780A80]`; `[F]` points at `F+0xB0`), `+0xB8` is a
    pending-set word and `+0xC0` a pending-clear word. The battle flow update (text 0x863120, once per frame on the
    logic thread) does state = (state | pending) & ~clear, then zeroes both. Bit 2 = defeated, bit 3 = defeat menu,
    bit 25 = hero KO'd, bit 40 = end the battle without the menu (restarts it).
  - A real KO: the hit code (text 0x3FA20, `comp->vtbl[0x350](comp, damage, flag)` = per-class damage handler, the
    hero's is text 0x19C400) calls addHP (0x6BE310, which calls setHP 0x6BE1A0, store at 0x6BE2FC) and returns "died";
    then "unit defeated" text 0x6B41C0 (w0 victim unit index, w1 killer, x2 hit info, w3 0) sets pending bit 25 for a
    party hero and queues the "hero defeated" event. The mission script answers the same frame with EndBattle (text
    0x6D3A50, w0 = 1: pending bit 2; w0 = 0 also sets bit 40), and about 2 s later its command at text 0x6F57D4 sets
    pending bit 3: the defeat menu (state 12). Restart Battle works.
  - Calling 0x6B41C0(hero unit, same, 0, 0) on the logic thread does all of that with no hit (the hero has no death
    animation; the screen goes to the defeat picture and menu). Setting bit 25 or the state bits from outside does not:
    the script needs the event; bit 2 alone stays on a HUD-less field, bit 2 then bit 3 restarts the mission.
  - Game mod: text 0x863120 branches to a hook (a chain of unused alignment gaps from text 0x1B40054, see "Code
    caves") that calls 0x6B41C0(word - 1, word - 1, 0, 0) when the word at
    `main+0x26A2298` (unused data) is set, and clears it. The client writes the hero's unit index + 1 (the unit record
    `real HP - 0x44` starts with it) after setting the HP to 0.
  - GDB stub notes: Eden randomizes the load address (tools/deathlink/find_base.py); watchpoints and breakpoints stop
    before the instruction, so step that thread (`Hg`/`Hc` to the stop's thread, `s`) with the watch off, then `Hc-1`
    before `c` or only that thread runs; never send `D` (the stub stops listening); hardware breakpoints (Z1) are
    unsupported; a watch covers its 16-byte block. Tools: tools/deathlink/gdbrsp.py, ko_watch.py, call_func.py.
- DeathLink before 0.9.91 (still the fallback without the hook): real HP and display copy held at 0; the next hit is a
  real KO with the death animation and defeat menu,
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

### World-map refresh [confirmed on Eden, 2026-11-19]
- The map draws its icons only when it is rebuilt; closing the pause menu does that. The map scene is
  `[[[main+0x2780AA8]+0x48]+0x80]` (vtable at module offset 0x26CAF00, same object `[...+0x48]+0x4A8`), updated by
  text 0xBDCF60 (x0 = scene, s0 = dt; jump table by current state). `+0x134` = current state, `+0x138` = requested;
  when they differ, the entry code of the new state runs (switch at 0xBE1914, table rodata 0x1F000E4). States seen:
  0 pause menu open, 1 rebuild (entry 0xBE1940: map object `[scene+0x58]` methods 0xBFAD70, 0xBFAF70, vtbl+0x198 =
  0xDDFB80 which reads the mission states, 0xBFB070, 0xBFB240, 0xBFD9A0), then 2 3 4 5 7 9 11 12 13 and 14 = idle.
  The map object's own state is `+0x88` (0 hidden, 1-2 opening, 8 idle).
- State 9 walks the entry list `[[scene+0x58]+0x68]+0xA980` (20-byte entries); any entry with byte `+0xD` = 0 sends it
  to 10, the "new icon" reveal, which waits for map object state 4/5. Missions opened in the two map lists only
  (profile lists left at 1) or cleared/iconless missions (Hyrule Field) made the reveal wait forever (map 3), also
  through a real menu close: no input until a restart. With all four lists written (as set_mission_states does) the
  flow skips 10.
- Client (live_hook.refresh_map): only at 14/14, request 0, wait for it to be taken, request 1: the same states as a
  real menu close, new icons appear, the menu works afterwards. Requesting 1 straight from 14 left the scene in 10
  with no input. Input is ignored for ~2 s while it runs. Found with read-watches on `[P+0x5A8]+0x14C` during a menu
  close (readers 0xDE0F44 / 0xDE1094 from 0xBE196C) and the saved registers on the reader's stack.
- Open tab: scene `+0x19C` (i32) = 3 Services, 4 Map, 5 Chapters, 7 Quests (6 likely Challenges); kept through the
  pause menu [read live 2026-11-20]. The cursor kind at `[P+0x5A8]+0x14A` does NOT tell tabs apart (kind 1 on empty
  map ground and in the Chapters list alike, kind 5 on a service). A redraw while the Chapters list is open closes
  the list and jumps to the map, so the client redraws only on tab 4.
- Seen through the real client on a local seed (2026-11-20): an unlock sent on the Map tab redrew within a tick; one
  sent with the Chapters list open waited and redrew on returning to the Map tab; input normal afterwards.
- Eden GDB stub: software breakpoints (Z0) never hit; reading guest stack memory via `m` failed (read it through the
  process instead). A script that died with a watch set left the game halted with a half-closed menu (UI broken
  until restart) - always clear watches in a finally.

### World-map scroll speed [confirmed on Eden, 2026-11-19]
- The world map scrolls under a fixed centre cursor. Text 0xce7254..0xce72b4 (the map update): new = old + stick
  (ints at [x19+0xb4], [x19+0xb8]) * speed (float param at +0x1e0 of the map parameter table), once per drawn frame,
  then 0xbf2790 clamps it and places the info panel; the result lands in [P+0x5A8]+0x120 / +0x128.
- The game mod scales that speed by frame step / 2 (cave chain from 0x1B41A64), so the scroll follows real time.

### Elemental rods [confirmed on Eden, 2026-11-19]
- Item palette (hold L in a mission): Y Fire Rod, X Ice Rod, A Lightning Rod, B baked apple.
- Uses left this mission: u32 per rod at `[B + 0x3C8] + 0x910` (Fire), `+0x914` (Ice), `+0x918` (Lightning), B = the
  battle object `[[module + 0x2B63708] + 0x30]` (1.4.1). Same block: `+0x92C` 5, `+0x934` 2, `+0x938` 3, `+0x94C` 2
  (apples and capacities, unmapped). Writing 0 greys the rod out (empty bar) and L + its button does nothing; the game
  doesn't write it back on its own. Using the Ice Rod (L + X) enters aim mode ("X Bombard, B Cancel").
- The save's start count per rod is table B `0x140 + rod` (story flag object `[P + 0x550] + 0x254`, saved copy
  `+0x1754`, a mission's copy `+0x954`); 3 each in a save with one Rod Mastery upgrade (profile `+0x7A5` = 1). A
  fresh game has 0 (no item palette until a rod is picked up).
- Palette drawing (text 0xf5a6b8 loop over 5 slots): uses read from the battle object (rods +0x2bd0 + 4 * slot, apples
  +0x2bec from `[[x23 + 0xa80] + 0x10]`); layout animations picked by id = index into the name table at data 0x2682030
  (stay_carry_<btn>_on/off, out_guide_carry_<btn>, shot_carry_gaugeMinToMax_<btn>; a 30-33, b 34-37, x 38-41,
  y 42-45). A greyed slot = its stay_carry_*_off anim at its end frame and the gauge anim at 20. Anim object: +0x28
  flags, +0x2c frame, +0x34/+0x38 start/end, +0x3c speed. No per-slot hide found yet.
- Rod OBTAINED flags (save 0x52F Fire, 0x530 Ice, 0x531 Lightning): live at [P+0x550] + 0x121 + rod, saved copy
  +0x1621. The palette is built when a mission loads: a rod with flag 0 has no slot at all (not even greyed); with
  all three 0 and no apples there is no palette. Changing them mid-mission does nothing until the next load
  [confirmed on Eden 2026-11-19]. How found: the in-memory save image ([P+0x5F0], save offset = image offset) is
  rebuilt at every mission start by a serializer (text 0x9edb44.., object [P+0x550]+0x1620 -> image); a write-watch
  on the image bytes gave the source fields. Table B (start counts) is the same object's +0x254 / +0x1754. Apple slot
  flag: not 0x535 or 0x53D (tried, slot stayed hidden); unknown.
- Apples (from the code, 2026-11-19): the same structure S = [P+0x550]+0x120 is saved (writer text 0x9edb44..)
  as S+0..6 -> save 0x52E..0x534, S+0x522 -> 0x535 (apples carried), S+0x524..0x52A -> 0x536..0x53C (per kind;
  plain = +0x526), S+0x631 -> 0x53D (apples obtained; zeroed for older save versions). Mission start (0x6e375c) loads
  the count from S+0x522 into the battle object (+0x2bec, per kind +0x2bf0..). The palette check (0xd868bc) shows the
  palette only if S+1..3 (rods) or S+0x631 is set. Live: [P+0x550]+0x751 (saved +0x1C51). Fresh save: 0; saves with
  apples: 1. Confirmed in game 2026-11-19 (Revali mission, flag set on the world map before entering): 0 = no B slot, 1 = apple on B. The apple uses counter (+0x1C) still loads even when the slot is hidden, so the client also holds it at 0.
- The client's rod lock (rod_items, 0.9.92) holds a locked rod's counter at 0 every tick in missions and gives the
  held uses back when the item arrives mid-mission (live_hook.hold_rods).

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
- Korok seeds [confirmed on Eden, 2026-11-18]: one byte per seed (1 = found) at `0x8DD + 20*r + slot`, r = story
  mission in story order (0 = The Battle of Hyrule Field ... 19 = The Future of Hyrule, not record numbers). Live:
  `[P+0x560] + 0x5B2` (last-saved copy `+0x2B02`). Each mission's used slots are the ones a 100% save has set
  (`data_koroks.KOROK_SLOTS`; per-mission totals match the guides exactly). Block 20 holds the 12 challenge seeds:
  0 Innkeeper's Request, 1 Mipha's Training, 2 Anti-Ice Training: II, 3 Defend Zora's Domain, 4-5 Elemental Uproar,
  6 Polishing His Technique, 7 Winged Escort, 8 Cross the Hebra Mountains, 9 Hunting Partners, 10 Hair-Width Trial:
  Expert+, 11 Defend Hyrule Castle [confirmed in game]. The Expansion Pass story missions show no Korok icons (no
  seeds). Bytes `0x865..0x882` (10 set in the 100% save, also in saves without DLC progress) are something else. The
  Korok Seed material only rises at the mission's end, but the live flag is set at pickup [confirmed in a real seed
  2026-11-18: Hyrule Field seeds sent one by one mid-mission].
- Mapping method [2026-11-18]: with A Most Peculiar Korok's byte (profile `+0xC7C`) and the Treasure Detector's
  (`+0xC7D/+0xC7E`) set, the Chapters and Challenges lists draw a row of chest and Korok icons per mission, lit when the
  flag is set (story/EX missions only once cleared). Writing flags in binary patterns and reading the icons from
  screenshots (tools: scratch `walk.py`, `exwalk.py`) maps every slot without playing. Missions opened by memory only
  get a list panel after the map rebuilds (title screen, Continue).
- Treasure chests [confirmed on Eden, 2026-11-18]: one byte per chest at `0x2CB4B + 10*r + slot`, same mission
  order; live `[P+0x588] + 0x3260` (saved copy `+0x4070`), set the instant the chest opens. Counts match the Zelda
  Dungeon wiki (Hyrule Field 5, Akkala Tower 7, ...; 153 in the story). Blocks 20-23 are the Expansion Pass stages
  30-33 (mission parameter table `t009cc294` `+59` = stage id): 20 EX To Zelda's Side / EX Guardian of Remembrance
  (shared stage; slots 0-3, 5, 6 shown, slot 4 no icon), 21 EX Battle of Goponga Village (5), 22 EX Battle for
  Kakariko Village (8), 23 EX The Princess and the King (9) [confirmed in game]. EX missions on story stages (Searching
  Hyrule Forest 11, Liberate the Ancient Lab 2, The Yiga Clan's Retreat 12) share that story mission's chests.
  Found by diffing the save from the mission's start (the game saves there) with the one after it.
- Mission records, beyond the clear times [save, 2026-11-19]: per difficulty slot the 0x84-byte record also holds
  a second u32 (HF 0x12C on two slots), a third (0xC8 = 200, rank/score?), `+0x48..+0x50` three u32 0x10001-like
  values, and from `+0x58` / `+0x70` per-slot values such as 0x2EA / 0x179 on Hyrule Field (a best KO count, guess).
  No outpost/camp capture count anywhere in the save [checked: test save vs 100% save].
- Material totals: the game keeps only the current count (u16, profile `+0x3E4` live / save `0x2C14E`), lowered by
  spending. Trophies are earned per defeat (Bokoblin Trophy 1727, Lizalfos 727 after ~5 story missions on the test
  save; Keese 18, Octorok 16, Chuchu 9, Wizzrobe 11, Lynel 3, Guardian 21, Moblin 21; Pebblit/Hinox/Talus/Molduga 0).
- Story clear rewards [LinkData2 009cba94]: the second list (`+0x10` counts, `+0x32` ids) is 10 each of five
  everyday materials per mission; the first list (`+0x04`/`+0x24`) holds the gems and other first-clear rewards.
- Weapon levels: record byte `+0x78` = level - 1; weapon kind u16 `+0x10` (0 = empty slot); first pool used.

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
- The Master Chef (quest 377, the only type 42): a repeatable trade, `+0x0C` u32 rupees paid (1000), `+0x10` u16 count
  (100), `+0x26` material (0xA5 Mighty Banana). No stored reward byte [hand-in diff: only the bananas and a rupee stat at
  `[P+0x5D8]+0x19C` changed; matches online guides]. Since 0.9.87 the client zeroes `+0x0C` and its item gives the rupees.
- Terrako's Return: profile `+0xB37` 2 -> 3 (meaning unknown). Hot Meals in a Pot: FLAGS `0x1A07`, profile `+0x2C3`.
- Never handed in yet: 29 EX reward quests, Ancient-Material Delivery, Seething Malice, Reigning Malice, Fiery Inspiration.

### The Battle of Hyrule Field and the rune flags
Its script sets the rune flags (story flags 0x19-0x1C) itself before the last wave and waits for them: the three moblins spawn only then [confirmed 2026-11-07: forcing Cryonis/Magnesis/Stasis off soft-locked the mission; switching them on spawned the moblins at once]. The client doesn't touch runes during that mission.

### Runes come from mission clears too
At mission load the game gives Magnesis and Stasis when their flag is set OR when Road to the Ancient Lab (mission
record 2) is cleared [confirmed 2026-11-09 on Eden: on a save with every story mission cleared and flags 0x1B/0x1C at 0
in all copies, all four runes were there and Stasis could be used in Relentless as a Waterfall and Road to the Ancient
Lab; with record 2's clear times zeroed and its state lists set to open, Relentless as a Waterfall loaded with only
Remote Bombs and Cryonis]. So the flags only hold Magnesis/Stasis back while Road to the Ancient Lab is uncleared.
What counts is record 2's profile mission state (profile `+0x876` list, current and saved copy, value 3 = cleared):
setting only those two bytes to 2 removed the runes; zeroing the clear times or changing the map-block lists alone
did not [confirmed 2026-11-09]. In the save file the profile mission states are one byte per record at `0x2C3B1 +
record`; a save with Road at 2 loads normally (the map then draws Road as available).
Hyrule Field (record 1) gates Cryonis the same way [confirmed: Cryonis flag off + record 1 at 2 removed Cryonis], but a
save with record 1 at 2 makes Continue start a new game (the forced opening), so it can't be held the same way.
Remote Bombs and Cryonis behave the same way with The Battle of Hyrule Field (record 1): their flags only matter
inside that mission [confirmed 2026-10-28]. Ruled out for Magnesis/Stasis: the rune upgrade counters (profile
`+0x7A1..+0x7A4` zeroed, no change) and story flag 0x15 (zeroed, no change; it makes the world map replay a
cutscene and gives Road to the Ancient Lab its first-time intro text).

### Where a rune or rod is required [game data, all 233 missions, 2026-11-23]
**Archive.** `data/LinkData2.bin` is indexed by `data/LinkInfo2.bin`: 7857 entries of 40 bytes (u64 offset, size, stored
size, compressed flag, hash). Compressed entries: u32 chunk size, chunk count, total, chunk sizes, then zlib chunks on
128-byte boundaries (each with a 4-byte length). 2266 entries are stored raw, the mission scenarios among them (a scan
for zlib headers misses them). Entry numbers below are LinkInfo2 indices.

**Mission order in per-mission tables:** story records 1-28, then challenges 100-266 without the six records whose stage
byte is 0 (193, 194, 235, 239, 243, 248), then 300-307, 320-330, 350-374: 233 in all. Stage id = byte +59 of the mission
parameter table (400 rows x 104).

**Texts.** Objectives 0x94a094 (300 rows, stride 12), messages 0x9dcb94 (2000 rows, stride 16). Per mission, 20 objective
rows (6 u16: objective id, name ids; 299 = none) and 128 message rows (99 = none). Name ids: 300+ = places (0x83f714),
601+ = things (Magnesis 675, Stasis 676, Remote Bomb 677, Cryonis 678, rods 680-682, weak-point smash 708, perfect
dodge 709, special attack 710, rune counter 711, fire/ice/lightning 712-714). Ids 0/5 ("Use a Fire Rod") only appear as
blank rows. Named in objectives: Urbosa and When Courage Fails (Remote Bombs), EX Battle Research: Skills (weak-point hit
and smash, perfect dodge, special attack), EX Battle Research: Items (fire, rune counter, Remote Bomb), EX The Budget
Battle (ice, weak-point smash, special attack). Named in messages only: the four Mastering challenges ("Use Cryonis and
defeat ...") and Fleeing the Weather ("Use Remote Bombs to topple trees"; guides describe no such step).
Explosive-Handle With Care names bomb barrels, not a rune. EX The Yiga Clan's Retreat gives Kohga the Slate mid-mission.

**Mission scenarios** (raw, entry 689 + 8 * mission index): +0 units (120 x 13 i32), +1 (26 x 10), +4 (64 x 2), +5 objects
(100 x 10), **+6 gimmick states (100 x 3 i32: gimmick number, state, value; -2147483648 = none)**, +7 the script.
States seen: 0/1 off/on, 2 removed, 3 whole (the script or an attack breaks it), **5 whole, must be broken**.

**Stage layouts** (DJBO, entry 7811 + stage - 1): header u16 version, n nodes, n2, m instances; nodes from 0x20 (96 bytes;
u16 kind at +86, flags at +88); instances are the last 64 * m bytes (scale, rotation, position, then u16 gimmick number,
u16, u16 node, **u16 collectible number**, hash). Kinds: 10 updraft, **14 bombable rock or cracked wall**, 25 toppling tree
(When Courage Fails), **36 treasure chest** (counts match every mission; collectible number = chest slot), 38 + 43
monster lookout + skull chest, **58 rock over a Korok** (collectible number = Korok table row).
- Kind 14: Revali 2, exactly on the updrafts at (46078, 57238) and (88996, 65397), both state 5 with the updrafts off:
  the mission can't be finished without Remote Bombs. Air and Lightning 2, on both updrafts, state 2 (removed): no bombs.
  Calamity Strikes and The Future of Hyrule: the same 4 cracked walls, side rooms only.
- No other mission has a kind 14 or 25 object in state 3/5 in its way (Yunobo's Training has the trees, unused).

**Koroks** (entry 3878, 600 rows x 20; row = 20 * mission + slot + 1, challenges 401-412): u32 x, u32 z, u16 group, u16
stage (challenge record from 401), u16 angle, 2 grid bytes, kind, level, u16 in use. Kinds: 2 crate, 10 stump, 11
pinwheel, 12 flower, 13 still balloon, 14 light, **15 moving target (Stasis)**, **0 under a bomb rock**. The in-use
column equals the seed slots found live, for all 20 missions.
**Chests** (0x7f9314, 10 rows per block x 16): weapon id, amount, stage, slot, map square, item, **u16 +12 = buried
(Magnesis)**, set on 11 chests: exactly those the Zelda Dungeon wiki lists as Magnesis. Contents match that wiki's list in
order for every block, so the wiki's order is the slot order.
Cracked walls hide Korok 5 and chest 7 of Calamity Strikes, chests 7 and 8 of The Future of Hyrule, and the seed of Defend
Hyrule Castle (within 1000 units of a wall; the next nearest item is over 1900 away).
Tables: data.MISSION_RUNES / RUNE_CHALLENGES / ROD_CHALLENGES, data_koroks.KOROK_RUNES, data_chests.CHEST_RUNES.
Guides agree: Game8 and GameFAQs (Revali, Urbosa, When Courage Fails), Zelda Dungeon (per-chest and per-seed lists).

Full data: `tools/rune_audit/` (koroks.json, chests.json with positions and contents, mission_gimmicks.json = every mission's
gimmick states, stage_objects.json), written by `build_research.py`, which also checks the world's tables against the game.

Every Korok seed, by its check number (= slot order):

| Mission or challenge | Seeds |
|---|---|
| The Battle of Hyrule Field | 1 crate, 2 still balloon, 3 flower, 4 flower, 5 flower, 6 stump, 7 pinwheel |
| Road to the Ancient Lab | 1 stump, 2 light, 3 still balloon, 4 flower, 5 flower, 6 pinwheel |
| Mipha, the Zora Princess | 1 still balloon, 2 flower, 3 pinwheel, 4 pinwheel |
| Daruk, the Goron Hero | 1 stump, 2 pinwheel, 3 flower, 4 pinwheel, 5 stump, 6 pinwheel, 7 light, 8 light |
| Revali, the Rito Warrior | 1 stump, 2 pinwheel, 3 stump, 4 light, 5 flower, 6 pinwheel, 7 moving target **(Stasis)**, 8 under a bomb rock **(Remote Bombs)** |
| Urbosa, the Gerudo Chief | 1 flower, 2 pinwheel, 3 light, 4 light, 5 crate, 6 pinwheel, 7 moving target **(Stasis)**, 8 pinwheel, 9 under a bomb rock **(Remote Bombs)** |
| The Yiga Clan Attacks! | 1 flower, 2 stump, 3 still balloon, 4 flower, 5 light, 6 pinwheel, 7 flower, 8 stump |
| Freeing Korok Forest | 1 crate, 2 flower, 3 pinwheel, 4 flower, 5 pinwheel, 6 flower, 7 pinwheel, 8 still balloon, 9 flower, 10 flower |
| The Road Home, Besieged | 1 pinwheel, 2 flower, 3 under a bomb rock **(Remote Bombs)** |
| Akkala Tower | 1 flower, 2 pinwheel, 3 light, 4 stump, 5 pinwheel |
| Destroy the Yiga Clan! | 1 flower, 2 moving target **(Stasis)**, 3 pinwheel, 4 crate, 5 light, 6 crate, 7 pinwheel, 8 light |
| When Courage Fails | 1 moving target **(Stasis)**, 2 flower, 3 light, 4 pinwheel, 5 crate |
| Calamity Strikes | 1 stump, 2 crate, 3 pinwheel, 4 crate, 5 pinwheel **(Remote Bombs)**, 6 light, 7 pinwheel |
| Water and Fire | 1 flower, 2 moving target **(Stasis)**, 3 crate |
| Air and Lightning | 1 flower, 2 flower, 3 stump, 4 moving target **(Stasis)**, 5 under a bomb rock **(Remote Bombs)** |
| Relentless as a Waterfall | 1 pinwheel, 2 crate, 3 light, 4 stump, 5 flower, 6 pinwheel |
| Each Step Like Thunder | 1 pinwheel, 2 flower, 3 flower, 4 stump |
| The Great Plateau | 1 pinwheel, 2 flower, 3 stump, 4 pinwheel, 5 flower, 6 crate, 7 under a bomb rock **(Remote Bombs)** |
| All Hyrule, United | 1 pinwheel, 2 stump, 3 flower, 4 crate, 5 pinwheel, 6 moving target **(Stasis)** |
| The Future of Hyrule | 1 stump, 2 pinwheel, 3 flower |
| Innkeeper's Request | 1 pinwheel |
| Mipha's Training | 1 flower |
| Anti-Ice Training: II | 1 pinwheel |
| Defend Zora's Domain | 1 pinwheel |
| Elemental Uproar | 1 stump, 2 flower |
| Polishing His Technique | 1 pinwheel |
| Winged Escort | 1 stump |
| Cross the Hebra Mountains | 1 crate |
| Hunting Partners | 1 flower |
| Hair-Width Trial: Expert+ | 1 still balloon |
| Defend Hyrule Castle | 1 pinwheel **(Remote Bombs)** |

Chests that need a rune (the other 167 need none), x and z in stage units:

| Mission | Chest | Rune | Why | Position |
|---|---|---|---|---|
| Road to the Ancient Lab | #2 | Magnesis | buried | 83813, 69440 |
| Road to the Ancient Lab | #6 | Magnesis | buried | 68039, 59988 |
| Revali, the Rito Warrior | #3 | Magnesis | buried | 61527, 67261 |
| Urbosa, the Gerudo Chief | #9 | Magnesis | buried | 75439, 47857 |
| The Yiga Clan Attacks! | #8 | Magnesis | buried | 44204, 73950 |
| The Road Home, Besieged | #9 | Magnesis | buried | 86409, 57537 |
| When Courage Fails | #8 | Magnesis | buried | 90095, 86456 |
| Calamity Strikes | #7 | Remote Bombs | behind a cracked wall | 72827, 57517 |
| Air and Lightning | #9 | Magnesis | buried | 68448, 35010 |
| The Great Plateau | #10 | Magnesis | buried | 71221, 106683 |
| The Future of Hyrule | #7 | Remote Bombs | behind a cracked wall | 72838, 57514 |
| The Future of Hyrule | #8 | Remote Bombs | behind a cracked wall | 71892, 54398 |
| EX Battle of Goponga Village | #5 | Magnesis | buried | 70201, 57411 |
| EX Battle for Kakariko Village | #6 | Magnesis | buried | 37285, 84217 |

How it was found (for the next hunt): index the archive properly first (LinkInfo2; the zlib scan missed 2266 entries), look
for tables whose in-use column equals a mask already known from live play (seed slots, chest counts), then place objects by
position. Dead ends: the 360-byte tables at 0x69ba14 (attack data), the 0x17c tables (area map, run-length), DJBO alone
for Koroks (only the rock ones are placed there), ALGB (AI graphs), the guides' mission texts for forced obstacles (Revali's
rocks are in no text, wiki objective list or message).

### The story flag check and the rune mod [confirmed on Eden, 2026-11-14]
- `isStoryFlagSet(id)` = text `0x757E50` (main NSO, v1.4.1 build E5F275B5...): returns "the flag's linked mission record
  is cleared (profile state 3) OR the flag byte is set". Flag table: param holder `[main+0x2780A38]+0x10` list, entry
  `0xE4`, 8-byte rows, u16 linked record at `+0` (0 = none). Flag byte = Table A, id = save offset - 0x13.
- Runes: id 6 Remote Bombs, 7 Cryonis (both linked to record 1, Hyrule Field), 8 Magnesis, 9 Stasis (record 2, Road).
  This is why clears give runes. Found with Eden's GDB stub (read watchpoints work there; Ryujinx's don't).
- 25 calls in the whole game. 22 pass a constant 6-9 (`mov w0,#n`): per-rune switch 0xFD310, "any rune" chain
  0xD8683C, HUD groups 0xD89CA4/0xD8AA04/0xDB2998, and single Bombs checks 0xF83D8/0xFCC34 that gate the whole rune
  menu. One more path picks the id from a rodata table at VA 0x1EFAAC0 = (6, 8, 9, 7). Story scripts pass the id in a
  register (0x11B400), so they keep the real flags.
- Unused flags (empty table row, no linked record, 0 in the 100% save): ids 96-99 (save 0x73-0x76), 111-124.
- Rune mod (tools/selftest/make_rune_patch.py -> IPS32, offsets = VA + 0x100): the constant sites and the table point
  at ids 96 Bombs, 97 Cryonis, 98 Magnesis, 99 Stasis; the two menu-gate sites at id 111 (Slate). Tested live: real
  flags all 1 + mod flags 0 -> no rune menu; mod flags set mid-battle -> menu appears at once; Bombs 0, others 1,
  Slate 1 -> menu with Stasis/Cryonis/Magnesis and an empty Bombs slot. Hyrule Field's moblins [confirmed
  2026-11-15, user playing a new seed with no runes]: the mission's script still reads the real flags 0x19-0x1C, so
  its last wave spawns while the rune menu stays empty.
- Install: the client writes the patch as `<build id>.ips` into Eden `load/01002B00111A2000/AoC Archipelago/exefs/` and
  Ryujinx `mods/contents/01002b00111a2000/AoC Archipelago/exefs/` while no emulator runs (client/rune_mod.py). It
  sees the mod is live by reading text 0xF83D8 (`e00d8052` patched, `c0008052` vanilla).

### Frame timing and game speed (the frame-rate part of the game mod) [confirmed on Eden, 2026-11-15]
- Frame-rate block main+0x26A2280: u32 fps, u32 steps, u32 fps, float cap (vanilla 30, 2, 30, 30.0). The float caps
  how many frames are drawn; each drawn frame advances game time by `steps` ticks of 1/60 s. So vanilla is 30 frames x
  2 = real time, and the old 60 FPS cheats (60/1) run in slow motion whenever the PC can't reach 60.
- The display's present interval is the graphics object's u32 `+0x2AA4` (vanilla 2), reached from
  `[main+0x276FD98]+0x1898` or `[main+0x2784100]+0x2F0` and passed every frame to nvnWindowSetPresentInterval. It is
  copied once at start-up, so above 30 the client sets it to 1 (0 for unlimited). This is what broke the 1.3.0-era
  60 FPS cheats on v1.4.1: they changed the block but not the present interval.
- Per-frame counter main+0x277DBA8 (frames drawn); mission clock at flow `+0x128` (60/s, frozen in cutscenes and the
  pause menu).
- 178 reads of `steps` in 83 functions; 96 are `ldr s,[x,#0x284]` (x = page main+0x26A2000, so main+0x26A2284) then `ucvtf` (step count to float, then times a
  speed: movement, timers, animation). The mod points those at a float frame step at main+0x26A2290 (unused data,
  set to 2.0 = vanilla) and removes the `ucvtf`. The 52 integer users (counters, compares) keep `steps`.
- About 28 sites read the cap float as the frame length (1/fps). Pointing them at another float hung loads (the frame
  limiter is among them), so the client keeps the cap at min(mode cap, reached fps x 1.06 + 2) instead.
- The client's pacer (client/framerate.py), per drawn frame: integer steps from the real time owed, the float step
  from the frame length plus a correction from its own ledger, the cap as above. Speed measured 1.00 at 30, 60, 120
  and unlimited (about 44-57 frames/s on the test PC). Cutscenes and menus (clock frozen > 0.3 s) and the world map
  (it animates per drawn frame, not by the step) get the vanilla block and present interval 2.
- The game rewrites the block itself (menus, loads), so the client compares with memory every frame rather than with
  what it last wrote.
- Video cutscenes [dump + rodata strings, 2026-11-18]: pre-rendered cutscenes are WebM files in RomFS `movie/`
  (Movie001-093.webm, Stage_Intro_S%03d.webm), `movie_logo/`, DLC `movie_dlc2/`; played with nn::movie (Extractor,
  Decoder, Buffer symbols in rodata). Name formats in rodata: `/movie/Movie%03d.webm`, `/movie/Stage_Intro_S%03d.webm`,
  `/movie_dlc2/Movie%03d.webm`, `/movie_logo/Movie%03d.webm`. Other cutscenes are in-engine. Goal (user): the chosen
  FPS everywhere but these videos; next: the code that formats those names -> a "movie playing" state to detect.
- Frozen-clock moments [measured on Eden 2026-11-18, recorder fpsrec.py + user]: a Divine Beast's Y attack and
  special attack stop the mission clock for ~4 s (the game's request word `[[main+0x2780A70]]+0x1D58` stays 0), so the
  pacer took them for cutscenes and dropped to 30. With /fps_cutscenes on, the step ledger paces them: 64-88 FPS and
  the user saw the attacks at normal speed [confirmed in game] - those animations follow the steps, not drawn frames.
  Minimap pings blink fast above 30 (per-drawn-frame, like parts of the world map).
- Pacer handle after a reload: "game state manager not set up" (mission start) left the pacer's own LiveGame reading
  frozen values (no error), so it stayed at 30 for the rest of the session. Fixed: Pacer.reattach() when the client's
  hook reconnects.
- UI animation timing [static + live, 2026-11-18]: above 30 FPS the pause menu and the minimap pings ran fast even
  with game time frozen; a held 60 FPS with 1 or 2 steps per frame ran equally fast (user), so the UI ignores steps.
  The UI is Koei's "kids" screen layouts (script names kids::placeable::screenlayout::PlayAnimationLoop/OneTime/
  IsAnimationFrameEnd, registered at text 0x927380.. -> functions 0x16471b0 / 0x1646f10 / 0x1647450). Animation
  player object: +0x28 flags (bit 0/1 playing, bit 2 hold), +0x2C current frame (float), +0x30 hold value, +0x34/+0x38
  start/end frame, +0x3C speed. The only per-frame advance is text 0x18cd7c0: frames = dt / (1/60) (rodata
  0x1EF90F8), frame += speed * frames for each player in obj+0x270 (count obj+0x260). dt comes in s0 from its callers
  (0x11642d8, 0x115f968, 0x1165188 via vtables; 0xa660c0 from obj+0x58) and is 1/30 per drawn frame at any rate.
  Game mod (0.9.90): 0x18cd7fc/0x18cd800 load the divisor from main+0x26A2294 (no other reader; init 1/60); the client
  writes 1 / (30 * frame step) there with every frame step (live_hook.set_frame_step). In the pause menu the gameplay
  frame counter (main+0x277DBA8) stops; the "AllRender" profiling counter main+0x27843F0 keeps counting drawn frames
  (siblings 0x27842E0 RenderGraphGPU, 0x2784368 RenderGraphCPU, 0x2784478 TaskGraphCPU, 0x2784500 RenderGraphGPU
  CommandNum; objects 0x88 apart from 0x27842C0, name pointer at +0x78), so the pacer measures frame length there.
  Found with tools/selftest/ratescan.py (values whose rate doubles at 60 with game time frozen) and xref.py.
  In game (2026-11-18): scaling made most layout animations HALF speed at 60 (their dt already follows the frame
  time); the client keeps the slot at 1/60 (vanilla). The UI parts still fast above 30 (minimap pings, cursor, 118
  values in the world-map scan) use other code paths [open].
- UI timing resolved [stub read-watch + write-watch on Eden, 2026-11-19]: with the client's pacer the layout dt is
  already real time - a read-watch on the divisor slot (main+0x26A2294) at a held 60 FPS saw every call from 0xa6624c
  (callers 0x8a0e80..0x8a0ec0) with s0 = 1/60, in play and in the pause menu (dt = frame step / 60). So the divisor
  stays 1/60 everywhere (the client no longer scales it; scaling halved the hero-portrait arrow). The early "pause
  menu fast" result came from holds that left the float step at 2.0.
- Minimap objective ping [write-watch 2026-11-19]: the ping's animation frame is set at 0xf6cb8c from an int counter
  / period at [[main+0x2780aa8]+0x1b4] / +0x1b8 (60); the minimap update adds a constant 2 per drawn frame at
  0xf89f04 (`add w8, w8, #2`). Game mod: that add goes through a cave (0x1B42894) adding the frame's integer steps
  (main+0x26A2284) instead. Found by: heap signature search for the 0..60 float, write-watch (writer 0x18d31e4, a
  layout property setter fed by 0x18d2550 <- 0x18ce830 <- 0xf6cbe0), then the counter. Guest module base differs
  from the client's MODULE_BASE view (stub saw 0x80635000 this boot): match pc/lr page offsets against text.bin.
- Forced opening / The Battle of Hyrule Field as a normal mission [static + confirmed on Eden 2026-11-19]:
  - The game plays the New Game opening when Hyrule Field's mission state (record 1: profile +0x877, also read as
    [save]+0x757 off the summary base) is not 3. Two predicates answer "Hyrule Field not cleared" (text 0xA405F0 with
    w0 == 1, and 0xA40860; both end `orr w0, w9, w8; ret` at 0xA406D0 / 0xA40930), called from the title/boot flow
    (0xC5C428, 0xC5C74C, 0xC5C7B4, 0xC5DCB0, 0xC5DFF0, 0xC5FB88, 0xB757D4, 0xF8A8C0; 0x88389C.. for the second). At
    0xC5D444 the start sequence is picked: state 2 -> 0x18 (the opening), else 1 (Continue to the map).
  - Game mod (0.9.90): both `orr` -> `mov w0, wzr` and 0xC5D458 `b.ne` -> `b`. With Hyrule Field at state 2 the title
    menu shows Continue, which loads the world map; patching only the six title calls or only 0xC5D458 still went to
    the New Game settings screen.
  - The mission itself needs a clear time in some difficulty slot: with all six slots 0 it hangs on its loading
    screen when started from the map - also in the vanilla game (state 3, no patch). With a time in slot 5 (no
    difficulty uses it) it loads; at state 2 it plays its first-play version (the full opening, then the battle as
    Link Lv.1), at state 3 the replay version (your party, "COMPLETE" on its panel).
  - Map display lists ([P+0x5A8]+0x14C/+0x81C) at 0 and its unlock row requiring The Future of Hyrule did not hide a
    state-3 Hyrule Field from Chapters; profile state 1 (locked) in the starter save does, and the client's
    set_mission_states opens it (it shows after a menu round trip, like other live unlocks).
  - LiveGame.save_ok required a cleared mission to identify Eden's memory layout: a fresh shuffled-Field save has none,
    so it now requires the mission state lists to look sane with one mission open or cleared.
- Cutscene kinds [measured on Eden 2026-11-19, tools/selftest/staterec.py + timedshots.py, Mipha's mission]:
  - A mission's opening scene (Divine Beast battle intro): flow state word (flow+0xB0, u32) gains 0x08000000
    (0x08200400 vs 0x00200400 in play; also the holder byte `[main+0x2780A70]+0x6EA` = 1); clock readable and 0,
    gameplay frame counter running. Follows game time: 9.40 s / 279 frames at forced 30/2, 9.41 s / 540 frames at
    forced 60/1 - fine above 30.
  - Story cutscenes (in-engine, e.g. King Dorephan's audience): flow state 0x00000C00 (gameplay: 0x00000400 in that
    mission), low byte 0 so the clock reads (0, stopped); the gameplay frame counter main+0x277DBA8 STOPS, the render
    counter main+0x27843F0 keeps counting. They advance per drawn frame: timed screenshots after the same button press
    at forced 60/1 were ~2x further along than at 30/2 (subtitles as markers). Not the integer steps, the float frame
    step, the cap float or the block's fps fields (all were "right" at forced 60/1). Several u32 counters there add a
    fixed 2 per drawn frame (57.6/s at 30, 115/s at 60). The client now gives these the game's own 30 (framerate.py:
    frame counter stalled while the clock reads = story scene), also with /fps_cutscenes on [unit-tested; live check
    pending].
  - Divine Beast Y / special attacks: state unchanged (0x00200400), clock stops, frame counter runs: game time, fine.
  - Pause menu: state low byte 0x60 (e.g. 0x00200460, 0x60042000 seen as bytes), clock unreadable.
  - Loading / story text screens: state 0x00000C00 / 0x00000D00 with the block at 60,2,34 written by the game.
- World-map scroll speed MEASURED [2026-11-19, tools/selftest/scrollshot.py: screenshots + phase correlation, forced
  block 30/2/2.0 vs 60/1/1.0, client closed]: holding the stick scrolls linearly, ~510 screenshot px/s at 30 (0.4 s
  -> 203 px, 0.8 s -> 407 px; ~17 px per drawn frame) and twice as far at 60 (0.6 s: 305 vs ~593 px). So the map
  scroll advances a fixed amount per drawn frame: it uses neither the step count, the mod's float frame step nor the
  cap float (all were "right" at forced 60). A short tap moves a fixed nudge (+40.3 in one copy at both rates).
  Finding its code: the scroll moves hundreds of per-icon screen positions (deltas of 103.5, 41.6, 20.8 ... per push
  in different units, tools/selftest/scrollmaster.py); no lone master value identified yet, and writes to copies are
  kept (recomputed only on input). Next idea: the stick read - floats +-1.0 in an input history block (0x2290213000..,
  entries 0xE00 apart, no pointers to it found) - and the code that turns it into map movement.
- World-map scroll [2026-11-19, tools/selftest/cursorhunt.py]: the cursor stays centred and the map scrolls under it
  (it moves the cursor only at the map's edges); ~683 float copies of the scroll offset (screen px, e.g. -1987.8 ->
  -2365.8 for a 0.25 s push) live in the map layout's per-icon data; a write to one copy is kept (they only recompute
  on input), so the source wasn't isolated by writes. Stick values appear as floats +-1.0 in a block near
  0x2290213000 with no pointers to it (input history buffer). Open.
- Eden's GDB stub (use_gdbstub, port 6543): attaches and continues, but the connection drops after a while and the
  game is left halted (stuck at "Launching", or a freeze mid-play). Not usable for watchpoints; config restored.
- The game's own frame-rate request [static, 2026-11-19]: `[[main+0x2780A70]]+0x1D58` = interval << 4 | countdown.
  Text 0xfc3c50 counts the low 4 bits down once per frame; at 0, and in the battle setup at 0x8a3590, the block
  becomes fps = 60 / interval, steps = interval, fps, cap = 60 / interval (so interval 2 = the vanilla 30/2, 1 = 60/1).
  It changes the frame rate only, never the game speed. The client rewrites the block every frame anyway.
- Open: flurry rushes act oddly above 30 (the stall was seen with Link only; Sidon's at unlimited was normal). No
  recording yet: the 2026-11-18 slowmo_rec.log has no request at all. Needs a flurry rush done by hand while
  tools/selftest/slowmo_rec.py records.
- The world map has a battle clock and gameplay frame counter of its own (both run at 60/s there). Until 2026-11-19
  the pacer only checked "in a mission" when fps_map or fps_cutscenes was on, so with defaults it paced the map too
  (block 60/1 on the map); it now always checks, and fps_map off keeps the game's own 30.
- A mission's last ~10 s after the win (clock stopped, player still in control), Divine Beast and special attacks:
  the clock stops but the gameplay frame counter keeps counting, and they follow game time, so the pacer paces them by
  its step ledger by default (2026-11-19; before, only with fps_cutscenes on). Story cutscenes stop the frame counter
  too and keep the game's own 30 (they advance per drawn frame). REVERTED 2026-11-21: in-engine story cutscenes in
  the user's test run ran at double speed above 30 - some keep the frame counter running, so they look like this case;
  clock stopped + frames counted now always gets the game's own 30 (attacks and mission ends included).
- The pause menu with fps_cutscenes on: the menu is cheap to draw, so above 60 its loop spun far faster than frames
  were shown (unlimited: ~363 updates/s, 60 shown, 2026-11-19) and whole-step animations (the pause map's ping) ran
  ~6x. The pacer caps the pause menu at 60 (block 60/1, present 1): ping 59 units/s there, vanilla 60.
- World-map zoom (right stick, [P+0x5A8]+0x130, 0.45..1.0): same speed at 30 and at 60 with step 1.0 (traced
  2026-11-19) - it already follows the frame step.
- In-engine story cutscenes: kids timelines ("kids::timeline::*", "mud::from_kidshost::UpdateTimelineList" in
  rodata); the per-frame advance is not found yet (needs a replayable cutscene to watch).
- The remaining frame-rate item: computing the frame step inside the game (an injected code module) so it works
  without the client - deferred by the user until the FPS bugs are done.

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
- The same table on disk: LinkData2 entry 4192 (101 rows x 64, row = node + 1), condition type at +0x2B. Runes and rods are in
  exactly five nodes: 22 An Apple a Day (Fire Rod), 26 Bombs Away, 27 Magnetic Mayhem, 28 Go with the Flow, 29 Nice and Icy;
  the other conditions are missions (0, 32, 33) and lab weapons (4, 6, 10, 12) [checked against data_lab, 2026-11-23].
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

### Code caves and Ryujinx [confirmed on Ryujinx 1.3.3 and Eden, 2026-11-20]
- The main NSO's text segment ends at 0x1B55930; rodata starts at 0x1B56000. Ryujinx copies only the segment's real
  length into memory (an IPS record past it is logged as applied but never lands), so the page padding after the text
  reads as zeros there. Eden maps the whole page as patched. The 0.9.91/0.9.92 mod kept its caves in that padding:
  on Ryujinx the first one run (the minimap ping, already on the title screen) executed zeros and the emulator died
  (log: guest PC = text 0x1B559E0, LR 0xF89CF8; memory read 00.. from 0x1B55930 while the branch at 0xF89F04 was
  patched). Instant DeathLink and the world-map scroll cave would have crashed the same way.
- The text segment has no free run of zeros or NOPs; the large blocks with no visible reference are switch cases,
  and the two real unreferenced functions are the exported nninitStartup and nnMain. What it does have is ~15900
  three-word alignment gaps (zeros after a ret / b / br, before the next 16-byte aligned function). The caves now
  live there: two instructions per gap, a branch to the next gap (tools/selftest/make_rune_patch.py `chain`, gaps
  from 0x1B40000 not targeted by any branch or ADR). Chains: DeathLink 0x1B40054.., map scroll 0x1B41A64.., ping
  0x1B42894... The client recognises the DeathLink hook by its branch word (rune_mod.DEATHLINK_HOOK_CODE).
- Seen working on Ryujinx after the move: boots to the map, map scene / tab / redraw, frame pacing (25 FPS there,
  real speed 60 ticks/s, pings 59-60), instant DeathLink (defeat menu).

### Performance: where the frame time goes [Eden, Revali's mission, unlimited FPS, 2026-11-20]
- Eden tops out at ~46-50 FPS in missions on the dev PC whatever the GPU settings (4x/0.75x, Accurate/Normal),
  Ryujinx ~25: the emulated CPU is the wall. No host thread is pinned at 100% (three at 70-84%): the frame is a
  chain across threads. Handheld mode (F10) gives only ~8% (47 -> 51).
- Sampling profiler (scratchpad eden_profile.py: GDB stub, halt every 60 ms, each thread's pc + frame-pointer chain,
  250 samples): one thread does nearly all the game-code work - the RENDER thread, per-draw material/shader-constant
  setup. Hot chain: 0x12A7BB0 (render pass per mesh; strings RefractionPrePass, SSSTransmit, Refraction, IndexedRim,
  LightMap) -> 0x12B0BB0 (sets ~100 named shader parameters: vTsbViewPort, nAttCurvType, nIESIndex, vTessFactors,
  fHeightScale, PatternMap ...) -> 0x12B20E0 (SoftBody, IndexedRamp; 17% self) -> 0x17DF330 / 0x17E0A50 /
  0x19DA1A0 / 0x1228CF0 (command writing). 0x12ABC30 = GBuffer / RenderStateControl / PB2GRASS2 materials. The cost
  scales with draw calls (meshes x passes), not resolution.
- Docked/handheld: nn::oe::GetOperationMode (PLT 0x1B54720, called at 0x8CF0FC/0x8CF260) -> byte main+0x278377F
  (1 docked); GetPerformanceMode -> main+0x278377E (1 boost). Readers: 0x8C3528, 0x8C373C, 0xB0E784, 0xB0E888 (77F);
  0x1A5710, 0xA8DD4C, 0xAE8248 (cached in obj+0x45C, re-applied on change), 0xB07344, 0xB073CC (77E). Data diff
  docked vs handheld: only render height main+0x2780B78 (810 docked = 1440x810, 540 handheld), the mode bytes
  0x278377C..F, and two indices at main+0x275A344/0x275A350 (13->17, 14->18).
- Render preset table: 0xB071A8 picks index (byte 77E ? 1 : 3) + (byte 77D == 0) from
  [[[main+0x2780A38]+0x10][0x12F]]+0x30 (0x40-byte entries, 10 slots, 5 used): +0..+0x24 ten scale floats, +0x28..+0x38
  five uint distances (preset 1 docked: 50000 50000 5000 10000 1000000; 3 handheld: 8000 25000 3000 6000 30000;
  4: 5000 25000 2000 4000 5000), +0x3C detail byte (140/80), +0x3D flag bits. Writing it live in a mission changed
  nothing measurable (A/B x5: 56.5 vs 55.8): read at load, or not on the render thread's path. Next: write it before
  a mission loads; attribute render time per pass (shadow, refraction pre-pass, SSS ...) to find one to skip.
- Interpolation (logic at a lower rate, extra drawn frames) would not raise the frame rate: of the busy thread's
  game-code samples 112/132 are rendering, and every other thread together ran game code in ~60 of 250 samples
  (logic is cheap). Each drawn frame costs a full render-thread pass whatever the logic rate.
- Eden settings benchmark (scratchpad bench_eden.py: fixed 25 s of mission game time at unlimited, baseline 46.3-46.6
  over four runs): CPU accuracy Unsafe 51.4-52.4 (+11%, game speed exact, client fine); reactive flushing off, async
  presentation, skip CPU inner invalidation, fast CPU time 1/2, GPU accuracy Normal: no gain (+-1). Recommended in
  the docs: Eden with CPU accuracy Unsafe.
