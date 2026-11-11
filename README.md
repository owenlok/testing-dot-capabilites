# Cache Quest 🗝️

A tiny, offline mystery game you play in your terminal.

Explore an abandoned research station, collect three signal fragments, solve a
lock puzzle, and recover the missing beacon. Each mission seed determines the
fragment locations and vault code, so you can replay or share the same challenge.
There is no timer, account, network connection, or runtime dependency.

**Status: complete, playable MVP.** Requires Python 3.11 or newer.

## Quick start

From the project root:

```sh
python -m cache_quest
```

On systems where Python is named `python3`, use that instead. A mission starts
immediately. Type `help` for commands or `hint` for a nudge.

```sh
python -m cache_quest --seed 42
python -m cache_quest --load mission.json
python -m cache_quest --save-dir /path/to/my-saves
```

No installation is needed. Optionally, install the project with `python -m pip
install .` to get the `cache-quest` command. If you downloaded the release archive,
you can also run its standalone `cache-quest.pyz` with Python, from any folder:

```sh
python cache-quest.pyz --seed 42
```

## Your mission

Five connected rooms make up the station: the Control Room, Lab, Hallway,
Maintenance, and Archive Vault.

1. Explore with `look` and `move`. Take useful objects when you find them.
2. Use the access card on the vault reader in the Hallway.
3. Inspect the Lab terminal and maintenance log. Combine their clues to get the
   three-digit code, then use it on the Hallway keypad. Keep any leading zeroes.
4. Find the amber, cyan, and violet signal fragments. All are reachable before
   opening the vault.
5. Inside the vault, use the fragments on the beacon, then take the beacon to win.

Wrong codes do not lock you out. Hints describe the next useful step without
revealing the code. After winning, you can still save, explore, or start again.

## Commands

| Command | What it does |
| --- | --- |
| `new [--seed N]` | Start a new mission; an optional seed reproduces a challenge |
| `look` | Describe the current room, exits, and visible objects |
| `move <direction>` | Move north, south, east, or west; n/s/e/w also work |
| `inspect <object>` | Examine a nearby object or something you carry |
| `take <object>` | Add a nearby collectible to your inventory |
| `inventory` | Show carried objects |
| `use <object> [on <target>]` | Apply an item to a device or puzzle |
| `use <three-digit code> on keypad` | Enter the vault code in the Hallway |
| `use fragments on beacon` | Assemble all three collected fragments in the vault |
| `hint` | Get a contextual, spoiler-light hint |
| `save [filename]` | Save the current mission; default is `mission.json` |
| `load [filename]` | Restore a saved mission |
| `help` | Show command help |
| `quit` | Exit the game |

Commands and object names are case-insensitive. Multiword object names do not
need quotes. Seeds must be signed 64-bit integers, including zero and negatives.
When no seed is supplied, the chosen seed is displayed so you can reuse it.
Different seeds can occasionally produce the same fragment arrangement.

`new` and a successful `load` replace current progress. **There is no autosave:**
use `save` before restarting or quitting. Ctrl+C and end-of-input exit cleanly.

## Example session

This opening sequence is reproducible with seed 42:

```text
$ python -m cache_quest --seed 42
CACHE QUEST
An emergency signal flickers inside an abandoned station.

> take access card
Added access card to your inventory.

> move north
You enter the Lab.

> inspect terminal
The terminal displays a partial access code: 2 _ 0. These are the first and third digits. The maintenance log records the missing digit.

> take cyan fragment
Added cyan fragment to your inventory.

> hint
Bring your access card to the hallway and use it on the vault.

> save checkpoint
Game saved to saves/checkpoint.json.

> quit
Mission paused. Unsaved progress is not kept. See you soon.
```

Room descriptions and prompts are abbreviated above.

## Local saves

Saves are plain, versioned JSON files under `./saves`, relative to the folder
where you launch the game. The folder is created on the first save. Change it
with the startup option `--save-dir`.

- Use simple names such as `mission`, `checkpoint.json`, or `"my mission.json"`.
- Names start with an ASCII letter or digit and allow letters, digits, spaces,
  underscores, and hyphens. The basename is limited to 80 characters.
- `.json` is appended when omitted. Quote filenames containing spaces.
- Paths, hidden files, and symbolic-link save files or directories are rejected.
- Saving the same name replaces that save atomically. Use different names to
  keep multiple checkpoints.
- Loading validates the schema, types, item ownership, and mission progress.
  Corrupted, oversized, incompatible, and impossible saves produce an error
  without replacing the current game.
- The world and code are regenerated from the stored seed. Saves contain only
  mission state, never executable code. Save schema version 1 is supported.

Keep your original saves if you edit JSON manually; invalid edits will not load.
The game makes no network calls or telemetry requests.

## Development and tests

All tests use Python's standard library; no pytest install is required:

```sh
python -m unittest discover -v
python -m compileall -q cache_quest tests
```

The suite covers movement and locked exits, inventory and visibility, puzzle
ordering, repeated and invalid actions, leading-zero codes, deterministic world
generation, complete missions across 250 seeds, CLI parsing and entry points,
interrupted input, save/load round trips, corrupted saves, unsafe filenames,
symbolic links, invalid state, and atomic-save failures.

### Project structure

```text
cache_quest/
  __init__.py       Version information
  __main__.py       python -m cache_quest entry point
  cli.py            Command parsing and terminal loop
  game.py           State, actions, inventory, and win conditions
  world.py          Five-room world and seeded fragment/code generation
  puzzles.py        Code validation and contextual hints
  persistence.py    Validated JSON loading and atomic saving
tests/
  test_cli.py
  test_game.py
  test_world.py
  test_persistence.py
pyproject.toml      Optional packaging and console entry point
```

The game rules do not depend on terminal input or file access. `Game.new(seed)`
creates a mission; action methods return player-facing text or raise `GameError`.
The CLI turns expected failures into readable messages. Persistence rebuilds
world data from the seed and rejects invalid state before applying it.

## MVP checklist

- [x] Five-room world map and object descriptions
- [x] Complete command loop and clear help
- [x] Inventory, inspection, and item use
- [x] Reproducible, solvable seeded missions
- [x] Three-digit vault puzzle using clues in multiple rooms
- [x] Contextual hints and a clear beacon-recovery ending
- [x] Safe local JSON saves and resumable progress
- [x] Automated gameplay, parsing, world, and persistence tests

## Future ideas

The original stretch goals remain optional: timed missions or flashlight power,
an exploration map, more puzzle types and endings, user-defined levels, and a
debug view. They are not part of the current game.

This project practices Python modules, dataclasses, dictionaries, state machines,
input parsing, seeded randomness, file I/O, exceptions, and unit testing.
