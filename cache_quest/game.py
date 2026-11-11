"""Game rules and state, independent of terminal input and file access."""

from dataclasses import dataclass, field

from .puzzles import contextual_hint, valid_code
from .world import FRAGMENT_IDS, START_ROOM, World, build_world


class GameError(ValueError):
    """An action the player cannot currently perform."""


def normalize(text: str) -> str:
    """Accept case-insensitive object names and forgiving whitespace."""
    return " ".join(text.casefold().split())


@dataclass
class Game:
    world: World
    room_id: str
    inventory: set[str] = field(default_factory=set)
    item_locations: dict[str, str] = field(default_factory=dict)
    card_used: bool = False
    vault_unlocked: bool = False
    beacon_repaired: bool = False
    won: bool = False

    @classmethod
    def new(cls, seed: int | None = None) -> "Game":
        world = build_world(seed)
        return cls(world, START_ROOM, set(), dict(world.initial_locations))

    def look(self) -> str:
        room = self.world.rooms[self.room_id]
        exits = []
        for direction, destination in room.exits.items():
            label = self.world.rooms[destination].name
            if destination == "archive_vault" and not self.vault_unlocked:
                label += ", locked"
            exits.append(f"{direction} ({label})")
        visible = sorted(
            item for item, location in self.item_locations.items()
            if location == self.room_id
        )
        visible.extend(room.fixtures)
        return "\n".join([
            f"{room.name}: {room.description}",
            "Exits: " + ", ".join(exits),
            "You notice: " + (", ".join(visible) if visible else "nothing else"),
        ])

    def move(self, direction: str) -> str:
        direction = normalize(direction)
        direction = {"n": "north", "s": "south", "e": "east", "w": "west"}.get(
            direction, direction
        )
        destination = self.world.rooms[self.room_id].exits.get(direction)
        if destination is None:
            raise GameError("There is no exit that way. Type look to see the exits.")
        if destination == "archive_vault" and not self.vault_unlocked:
            raise GameError(
                "The Archive Vault is locked. Its access-card reader and keypad are here in the Hallway."
            )
        self.room_id = destination
        return f"You enter the {self.world.rooms[destination].name}.\n{self.look()}"

    def _visible(self, item: str) -> bool:
        return (
            item in self.inventory
            or self.item_locations.get(item) == self.room_id
            or item in self.world.rooms[self.room_id].fixtures
        )

    def inspect(self, item: str) -> str:
        item = normalize(item)
        if not self._visible(item):
            raise GameError("You cannot see that object here or in your inventory.")
        if item == "vault":
            if self.vault_unlocked:
                return "The Archive Vault door is open. Move east to enter."
            return "A sealed door with an access-card reader. A three-digit keypad sits beside it."
        if item == "keypad":
            if self.vault_unlocked:
                return "ACCESS GRANTED. The Archive Vault is unlocked."
            if self.card_used:
                return "The keypad glows. Enter three digits with: use <code> on keypad."
            return "The keypad is dark. Use an access card on the vault to activate it."
        if item == "beacon" and self.beacon_repaired:
            if self.won:
                return "The recovered beacon pulses with all three signals. Your rescue signal is on its way."
            return "The repaired beacon pulses with all three signals. Take it to complete the mission."
        return self.world.items[item].description

    def take(self, item: str) -> str:
        item = normalize(item)
        if item in self.inventory:
            raise GameError("You already have that object.")
        if item in self.world.rooms[self.room_id].fixtures:
            raise GameError("That stays in the station. Try inspecting it instead.")
        if self.item_locations.get(item) != self.room_id:
            raise GameError("There is no such object to take here.")
        if item == "beacon" and not self.beacon_repaired:
            raise GameError("The beacon is inert. Collect all three signal fragments and use fragments on beacon.")
        self.inventory.add(item)
        del self.item_locations[item]
        if item == "beacon":
            self.won = True
            return (
                "BEACON RECOVERED!\n"
                "Three signals become one. The station's emergency lights brighten as your rescue signal rises.\n"
                "You completed Cache Quest. Save this mission, explore, or start again with new --seed N."
            )
        return f"Added {item} to your inventory."

    def inventory_text(self) -> str:
        if not self.inventory:
            return "Your inventory is empty."
        return "Inventory:\n" + "\n".join(f"- {item}" for item in sorted(self.inventory))

    def use(self, item: str, target: str | None = None) -> str:
        item = normalize(item)
        target = normalize(target) if target is not None else None
        if item == "access card":
            if target not in (None, "vault", "keypad", "reader", "vault reader"):
                raise GameError("The access card fits the vault reader in the Hallway.")
            if item not in self.inventory:
                raise GameError("You need to take the access card first.")
            if self.room_id != "hallway":
                raise GameError("The vault reader is in the Hallway.")
            if self.card_used:
                return "The reader has already accepted your card."
            self.card_used = True
            return "Card accepted. The keypad lights up, waiting for a three-digit code."

        candidate = item.removeprefix("code ")
        if len(candidate) == 3 and candidate.isascii() and candidate.isdigit():
            if target not in (None, "keypad", "vault"):
                raise GameError("Enter the code on the vault keypad in the Hallway.")
            if self.room_id != "hallway":
                raise GameError("The vault keypad is in the Hallway.")
            if self.vault_unlocked:
                return "The Archive Vault is already unlocked."
            if not self.card_used:
                raise GameError("The keypad is dark. Use access card on vault first.")
            if not valid_code(candidate, self.world.code):
                raise GameError("The keypad flashes red. Check the terminal and maintenance log, then try again.")
            self.vault_unlocked = True
            return "ACCESS GRANTED. The Archive Vault unlocks. Move east to enter."

        if item in ("fragments", "signal fragments", *FRAGMENT_IDS):
            if target not in (None, "beacon"):
                raise GameError("The signal fragments belong in the beacon.")
            if self.room_id != "archive_vault":
                raise GameError("The beacon is inside the Archive Vault.")
            missing = [fragment for fragment in FRAGMENT_IDS if fragment not in self.inventory]
            if missing:
                raise GameError("You still need: " + ", ".join(missing) + ".")
            if self.beacon_repaired:
                return "The beacon is already repaired. " + (
                    "You have recovered it!" if self.won else "Take beacon to finish the mission."
                )
            self.beacon_repaired = True
            return "You assemble all three signal fragments in the beacon. It flickers to life! Take beacon to recover it."

        if item not in self.inventory:
            raise GameError("You do not carry that object. Type help for the use command syntax.")
        raise GameError("That object cannot be used that way.")

    def hint(self) -> str:
        return contextual_hint(
            self.room_id, self.inventory, self.card_used, self.vault_unlocked,
            self.beacon_repaired, self.won,
        )
