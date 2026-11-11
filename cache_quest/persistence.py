"""Versioned, validated JSON saves with atomic replacement.

Names are 1–80 ASCII letters, digits, spaces, underscores or hyphens, beginning with
an alphanumeric character, optionally followed by .json. No paths are accepted.
The save directory is configurable by the caller, never by saved data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import TYPE_CHECKING

from .world import FRAGMENT_IDS, build_world

if TYPE_CHECKING:
    from .game import Game

MAX_SAVE_BYTES = 1024 * 1024
SAVE_VERSION = 1
_KEYS = {"version", "seed", "room_id", "inventory", "item_locations",
         "card_used", "vault_unlocked", "beacon_repaired", "won"}
_FLAGS = ("card_used", "vault_unlocked", "beacon_repaired", "won")


class PersistenceError(ValueError):
    """A save/load failure that is safe to display to the player."""


def _save_path(filename: str, save_dir: Path | str) -> Path:
    if not isinstance(filename, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9 _-]{0,79}(?:\.json)?", filename
    ):
        raise PersistenceError("Use a simple save name containing letters, numbers, spaces, _ or -, optionally ending in .json.")
    try:
        directory = Path(save_dir)
        if any(part.is_symlink() for part in (directory, *directory.parents)):
            raise PersistenceError("The save directory cannot be a symbolic link.")
        path = directory / (filename if filename.endswith(".json") else filename + ".json")
        if path.is_symlink():
            raise PersistenceError("Save files cannot be symbolic links.")
        return path
    except (OSError, TypeError, ValueError) as exc:
        if isinstance(exc, PersistenceError):
            raise
        raise PersistenceError("The save directory is unavailable.") from None


def _validate(data: object) -> Game:
    # Import lazily to keep the game's persistence commands free of import cycles.
    from .game import Game

    if not isinstance(data, dict) or set(data) != _KEYS:
        raise PersistenceError("The save has missing or unknown fields.")
    if type(data["version"]) is not int or data["version"] != SAVE_VERSION:
        raise PersistenceError("This save version is not supported.")
    seed = data["seed"]
    if type(seed) is not int or not -(2**63) <= seed < 2**63:
        raise PersistenceError("The save has an invalid mission seed.")
    world = build_world(seed)
    room = data["room_id"]
    inventory = data["inventory"]
    locations = data["item_locations"]
    if not isinstance(room, str) or room not in world.rooms:
        raise PersistenceError("The save has an unknown room.")
    if not isinstance(inventory, list) or any(type(item) is not str for item in inventory):
        raise PersistenceError("The save has an invalid inventory.")
    held = set(inventory)
    if len(held) != len(inventory):
        raise PersistenceError("The save contains duplicate inventory items.")
    if not isinstance(locations, dict) or any(
        type(item) is not str or type(location) is not str
        for item, location in locations.items()
    ):
        raise PersistenceError("The save has invalid item locations.")
    initial = world.initial_locations
    if held & locations.keys() or held | locations.keys() != set(initial):
        raise PersistenceError("The save has missing, unknown or duplicated items.")
    if any(location != initial[item] for item, location in locations.items()):
        raise PersistenceError("The save contains an impossible item location.")
    if any(type(data[flag]) is not bool for flag in _FLAGS):
        raise PersistenceError("The save has invalid progress flags.")
    card, unlocked, repaired, won = (data[flag] for flag in _FLAGS)
    if (card and "access card" not in held
            or unlocked and not card
            or room == "archive_vault" and not unlocked
            or repaired and (not unlocked or not set(FRAGMENT_IDS) <= held)
            or won != ("beacon" in held)
            or won and not repaired):
        raise PersistenceError("The save contains impossible mission progress.")
    return Game(world, room, held, dict(locations), card, unlocked, repaired, won)


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise PersistenceError("The save contains duplicate JSON fields.")
        result[key] = value
    return result


def save_game(game: Game, filename: str = "mission.json", save_dir: Path | str = "saves") -> Path:
    """Validate and atomically save a mission; return the saved path."""
    path = _save_path(filename, save_dir)
    try:
        data = {"version": SAVE_VERSION, "seed": game.world.seed,
                "room_id": game.room_id, "inventory": sorted(game.inventory),
                "item_locations": dict(game.item_locations),
                **{flag: getattr(game, flag) for flag in _FLAGS}}
        _validate(data)
        encoded = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")
    except (AttributeError, TypeError, ValueError) as exc:
        if isinstance(exc, PersistenceError):
            raise
        raise PersistenceError("The current mission cannot be saved.") from None
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Recheck after directory creation, before opening any output.
        _save_path(filename, save_dir)
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=".cache-quest-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        _save_path(filename, save_dir)
        os.replace(temporary, path)
        temporary = None
    except OSError:
        raise PersistenceError("Could not save the mission. Check the save directory and available space.") from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return path


def load_game(filename: str = "mission.json", save_dir: Path | str = "saves") -> Game:
    """Load a bounded regular JSON file, rebuilding immutable world data."""
    path = _save_path(filename, save_dir)
    try:
        # O_NOFOLLOW rejects a symlink even if it appears after _save_path.
        # O_NONBLOCK prevents a malicious FIFO from hanging the command loop.
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise PersistenceError("The save must be a regular file.")
            if info.st_size > MAX_SAVE_BYTES:
                raise PersistenceError("The save file is too large.")
            raw = stream.read(MAX_SAVE_BYTES + 1)
        if len(raw) > MAX_SAVE_BYTES:
            raise PersistenceError("The save file is too large.")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
        return _validate(data)
    except FileNotFoundError:
        raise PersistenceError("No saved mission with that name was found.") from None
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, PersistenceError):
            raise
        raise PersistenceError("The save file is corrupted or is not valid JSON.") from None
    except OSError:
        raise PersistenceError("Could not read the saved mission.") from None
