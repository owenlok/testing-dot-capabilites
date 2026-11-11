"""Terminal command parsing and the interactive input loop."""

import argparse
from pathlib import Path
import shlex
import sys
from typing import TextIO

from .game import Game, GameError
from .persistence import PersistenceError, load_game, save_game


HELP = """Commands:
  new [--seed N]                Start a new mission (replaces current progress)
  look                         Describe your room, exits, and objects
  move <north|south|east|west>   Travel through an exit (n/s/e/w also work)
  inspect <object>             Read a nearby or carried object
  take <object>                Collect a nearby object
  inventory                    Show what you carry
  use <object> [on <target>]    Apply an item, e.g. use access card on vault
  use <three-digit code> on keypad
  use fragments on beacon      Assemble the three signal fragments
  hint                         Get a contextual nudge without the solution
  save [filename]              Save under the saves folder (default mission.json)
  load [filename]              Resume a saved mission (replaces current progress)
  help                         Show this help
  quit                         Exit (save first to keep your progress)

Object names may contain spaces. Quote filenames that contain spaces.
There is no timer: take your time, explore, and follow the clues."""


def seed_value(value: str) -> int:
    try:
        seed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seed must be an integer") from exc
    if not -(2**63) <= seed < 2**63:
        raise argparse.ArgumentTypeError("seed must fit in a signed 64-bit integer")
    return seed


class CommandRunner:
    """Small REPL adapter; failed commands leave the current mission intact."""

    def __init__(self, game: Game, save_dir: str | Path = "saves") -> None:
        self.game = game
        self.save_dir = Path(save_dir)
        self.running = True

    def execute(self, line: str) -> str:
        try:
            parts = shlex.split(line)
        except ValueError as exc:
            return f"Could not read that command: {exc}."
        if not parts:
            return ""
        command, *args = parts
        command = command.casefold()
        try:
            if command == "new":
                seed = None
                if args:
                    if len(args) != 2 or args[0] != "--seed":
                        raise GameError("Usage: new [--seed N]")
                    try:
                        seed = seed_value(args[1])
                    except argparse.ArgumentTypeError as exc:
                        raise GameError(str(exc)) from exc
                game = Game.new(seed)
                self.game = game
                return f"New mission started (seed {game.world.seed}).\n{game.look()}"

            if command in ("look", "inventory", "hint", "help", "quit"):
                if args:
                    raise GameError(f"Usage: {command}")
                if command == "look":
                    return self.game.look()
                if command == "inventory":
                    return self.game.inventory_text()
                if command == "hint":
                    return self.game.hint()
                if command == "help":
                    return HELP
                self.running = False
                return "Mission paused. Unsaved progress is not kept. See you soon."

            if command in ("move", "inspect", "take"):
                if not args or (command == "move" and len(args) != 1):
                    raise GameError(f"Usage: {command} <{'direction' if command == 'move' else 'object'}>")
                return getattr(self.game, command)(" ".join(args))

            if command == "use":
                if not args:
                    raise GameError("Usage: use <object> [on <target>]")
                separators = [index for index, token in enumerate(args) if token.casefold() == "on"]
                if separators:
                    index = separators[0]
                    if len(separators) != 1 or index == 0 or index == len(args) - 1:
                        raise GameError("Usage: use <object> [on <target>]")
                    return self.game.use(" ".join(args[:index]), " ".join(args[index + 1:]))
                return self.game.use(" ".join(args))

            if command in ("save", "load"):
                if len(args) > 1:
                    raise GameError(f"Usage: {command} [filename] (quote filenames with spaces)")
                filename = args[0] if args else "mission.json"
                if command == "save":
                    path = save_game(self.game, filename, self.save_dir)
                    return f"Game saved to {path}."
                game = load_game(filename, self.save_dir)
                self.game = game
                return f"Mission loaded (seed {game.world.seed}).\n{game.look()}"
            return f"Unknown command: {command}. Type help to see the available commands."
        except (GameError, PersistenceError) as exc:
            return str(exc)


def run_repl(runner: CommandRunner, stdin: TextIO, stdout: TextIO) -> None:
    """Run with injectable streams so input/EOF behavior can be tested."""
    while runner.running:
        stdout.write("\n> ")
        stdout.flush()
        try:
            line = stdin.readline()
        except KeyboardInterrupt:
            stdout.write("\nMission paused. Unsaved progress is not kept. See you soon.\n")
            return
        if not line:
            stdout.write("\nMission paused. Unsaved progress is not kept. See you soon.\n")
            return
        response = runner.execute(line)
        if response:
            stdout.write(response + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cache Quest: an offline terminal mystery.")
    start = parser.add_mutually_exclusive_group()
    start.add_argument("--seed", type=seed_value, help="start a reproducible mission")
    start.add_argument("--load", metavar="FILENAME", help="resume a JSON save from the saves folder")
    parser.add_argument("--save-dir", type=Path, default=Path("saves"), help="save folder (default: ./saves)")
    args = parser.parse_args(argv)
    try:
        game = load_game(args.load, args.save_dir) if args.load is not None else Game.new(args.seed)
    except PersistenceError as exc:
        parser.exit(1, f"Could not start mission: {exc}\n")
    print("CACHE QUEST\nAn emergency signal flickers inside an abandoned station.")
    print(f"Mission seed: {game.world.seed}. Type help for commands.\n")
    print(game.look())
    run_repl(CommandRunner(game, args.save_dir), sys.stdin, sys.stdout)
    return 0
