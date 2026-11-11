Cache Quest 🗝️
A tiny, offline mystery game you play in your terminal.

Explore an abandoned research station, collect three signal fragments, solve a lock puzzle, and recover the missing beacon before the station goes dark. Every new game rearranges the clues, so you can replay it with a different seed.
Project status: Idea / not yet implemented. This README is a specification for a project to build, not a claim that the game already runs.

The idea
Cache Quest is a beginner-to-intermediate Python project that turns a command-line interface into a text-adventure game. The player navigates connected rooms, examines objects, collects clues, solves a short puzzle, and saves progress to a local JSON file.

The challenge is to write clean game logic while keeping the interface simple and fun.
Planned features
- Room exploration: Move between five connected rooms and discover their descriptions.
- Seeded randomness: Shuffle clue locations with a reproducible random seed.
- Inventory: Pick up and inspect useful objects.
- Puzzle system: Unlock the Archive Vault using information found in the station.
- Hints: Request a clue without immediately revealing the solution.
- Local saves: Save and resume a game as a JSON file—no accounts or internet required.
- Clear ending: Win by assembling three signal fragments and retrieving the beacon.
Tech stack
Component	Choice
Language	Python 3.11+
Interface	Interactive terminal / REPL
Data storage	JSON files
Libraries	Python standard library (argparse, json, pathlib, random)
Tests (optional)	pytest


Getting started (once implemented)
1. Install Python 3.11 or newer.
2. Download or clone your own implementation of this project.
3. From the project root, start the game:
   python -m cache_quest
4. Type help to see the available commands.
No external packages should be required to play the finished game.
Example gameplay (illustrative)
$ python -m cache_quest

CACHE QUEST
An emergency signal flickers inside an abandoned station.

> new --seed 42
New mission started. You are in the Control Room.

> look
Control Room: Dusty monitors hum beside a locked cabinet.
Exits: north (Lab), east (Hallway)
You notice: an access card

> take access card
Added access card to your inventory.

> move north
You enter the Lab.

> inspect terminal
The terminal displays a partial access code: 7 _ 2.

> inventory
- access card

> hint
Look for a maintenance log before trying the vault keypad.

> save
Game saved to saves/mission.json.

> quit
Mission paused. See you soon.
The sample above shows intended behavior; it is not output from existing code.
Commands to implement
Command	Behavior
new [--seed N]	Start a new mission; optional seed controls clue placement
look	Describe the current room, exits, and visible objects
move <direction>	Travel through an available exit
inspect <object>	Read information about a visible object
take <object>	Add a collectable object to inventory
inventory	Show objects the player carries
use <object> [on <target>]	Apply an item to a door, device, or puzzle
hint	Show a contextual hint
save [filename]	Serialize the current mission to JSON
load [filename]	Restore a saved mission
help	List commands
quit	Exit the game


Proposed project structure
cache-quest/
├── README.md
├── cache_quest/
│   ├── __init__.py
│   ├── __main__.py      # Entry point: python -m cache_quest
│   ├── cli.py           # Input loop and command parsing
│   ├── game.py          # Game state, inventory, win conditions
│   ├── world.py         # Rooms, objects, seeded clue placement
│   ├── puzzles.py       # Vault puzzle and hint logic
│   └── persistence.py   # JSON save/load and validation
├── saves/               # Locally generated save files
└── tests/
    ├── test_game.py
    ├── test_world.py
    └── test_persistence.py
Only README.md is provided at this stage; the directories and Python files above are a suggested layout.
MVP build plan
- [ ] 1. World map: Define five rooms, their exits, and item descriptions.
- [ ] 2. Command loop: Support help, look, move, inspect, and quit.
- [ ] 3. Items: Implement take, inventory, and use.
- [ ] 4. Randomization: Place three signal fragments based on a seeded RNG without making a mission unsolvable.
- [ ] 5. Vault puzzle: Add a three-digit code derived from clues in multiple rooms.
- [ ] 6. Save/load: Validate data, handle corrupted saves gracefully, and avoid unsafe file paths.
- [ ] 7. Tests: Cover movement, inventory changes, puzzle completion, seeded repeatability, and save/load round-trips.
Definition of done
A player can start a mission, navigate all five rooms, find enough clues to open the Archive Vault, collect all three signal fragments, win, and resume that mission from a saved file. The same seed produces the same clue placement.
Stretch goals
- Timed missions or a limited flashlight battery
- ASCII room map that updates as you explore
- Multiple puzzle types and alternate endings
- User-defined levels loaded from JSON
- A --debug option to inspect the generated world while testing
Learning goals
This project practices Python modules, dictionaries and classes, state machines, input parsing, reproducible randomness, file I/O, exception handling, and unit testing.
