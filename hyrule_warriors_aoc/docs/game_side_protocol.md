# Game-side protocol (version 1, extended for 0.2.0)

The Archipelago client listens on `127.0.0.1:38291`. A component running next to the game connects to it and exchanges
newline-delimited JSON objects (UTF-8, one object per line). Only one game connection is active at a time; a new
connection replaces the old one. Unknown message types must be ignored by both sides.

## Client -> game

| `type` | Fields | Meaning |
| --- | --- | --- |
| `hello` | `version`, `game` | Sent immediately on connect. |
| `state` | `unlocked_characters`, `unlocked_weapons`, `upgrades` (item name -> copies), `cleared_missions`, `available_missions`, `mission_slots` (story slot -> mission placed there), `completed` (kind -> names), `side_missions_completed`, `side_missions_required` (slot -> count), `goal_complete` | Full authoritative state. Sent on connect, and after every change. The game side should make its save match this. |
| `death_link` | `source`, `cause` | Another player died and DeathLink is on: **kill the player** (fail the mission). Only sent when `death_link` is enabled; the game must not echo it back as `player_died`. |
| `notice` | `kind`, `text`, `item`, `player` | An on-screen message. `kind` is `received`, `sent`, `hint`, `goal`, `info` or `death`. `text` is a ready one-liner of plain ASCII, at most 60 characters, so it is safe in the game's font; `item` and `player` are the parts if the hook lays it out itself. Show each for a few seconds in the game's own message style, one at a time and queued. Bursts are already collapsed by the client into a single summary. |
| `title_info` | `connected`, `slot`, `seed`, `server`, `world_version`, `checks`, `total_checks`, `goal_complete`, `lines` | What the title screen shows: slot name, seed, connection status and progress. `lines` is the same as ready text lines, one per row. Sent on connect, after every change and when the multiworld connection drops (`connected: false`, show "Not connected"). |
| `items_received` | `items` (list of item names) | Newly granted items, in order. Names beginning `Character: ` / `Weapon: ` are already reflected in `state`; upgrades (`Heart Container: <Character>`, `Combo Upgrade: ...`, `Special Gauge Upgrade: ...`, `Enhanced Ability: ...`, `Progressive Weapon Capacity`, `Progressive Seal Slot`, `Weapon Fusion`) are also summarised in `state`; anything else is filler (`Character XP Gift`, `Weapon XP Gift`, `Extra Weapon`, `Rupee Pouch`, `Material Bundle`, `Hearty Meal`) and must be applied by the game side exactly once per message. |

## Game -> client

| `type` | Fields | Meaning |
| --- | --- | --- |
| `mission_cleared` | `mission` | A main story mission was completed for the first time. |
| `weapon_obtained` | `weapon` | A tracked weapon was obtained through normal play. Do **not** send this for weapons granted by the client. |
| `challenge_cleared` | `challenge` | A challenge mission was completed. Send for every challenge, checked or not: they count toward side-mission story gates. |
| `quest_completed` | `quest` | A side quest was completed. Same rule as challenges. |
| `korok_found` | `korok` | A tracked Korok seed (`Korok: <mission or challenge> #n`). |
| `player_died` | | The player died or failed a mission through normal play. The client sends a DeathLink if enabled. Do not send it for deaths caused by a received `death_link`. |
| `request_state` | | Ask for a fresh `state` message. |

Mission and weapon names are exactly those in `data.py`. Duplicate reports are harmless: the client ignores anything it
has already recorded.

## What the game side must enforce

0. With a shuffled mission order, story slot `S` must launch `mission_slots[S]`.
1. Only missions in `available_missions` may be entered (or already-cleared ones replayed).
2. Only characters in `unlocked_characters` may be selected.
3. Only weapons in `unlocked_weapons` may be equipped.
