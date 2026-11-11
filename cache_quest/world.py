"""Station layout and reproducible, self-contained mission generation."""

from dataclasses import dataclass
import random

ROOM_IDS = ("control_room", "lab", "hallway", "maintenance", "archive_vault")
FRAGMENT_IDS = ("amber fragment", "cyan fragment", "violet fragment")
START_ROOM = "control_room"


@dataclass(frozen=True)
class Room:
    id: str
    name: str
    description: str
    exits: dict[str, str]
    fixtures: tuple[str, ...]


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    description: str


@dataclass
class World:
    seed: int
    rooms: dict[str, Room]
    items: dict[str, Item]
    initial_locations: dict[str, str]
    code: str


def build_world(seed: int | None = None) -> World:
    """Build a solvable mission without modifying Python's global RNG.

    Explicit seeds must be signed 64-bit integers (not booleans). Retaining
    the chosen seed lets a randomly generated mission be reconstructed later.
    """
    if seed is None:
        seed = random.SystemRandom().randrange(2**63)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Seed must be an integer, not a boolean.")
    if not -(2**63) <= seed < 2**63:
        raise ValueError("Seed must be a signed 64-bit integer.")
    rng = random.Random(seed)
    fragment_rooms = list(ROOM_IDS[:-1])
    rng.shuffle(fragment_rooms)
    code = f"{rng.randrange(1000):03d}"

    rooms = {
        "control_room": Room(
            "control_room", "Control Room",
            "Dusty monitors hum beneath a fading emergency light. An abandoned "
            "station map points toward the lab and the central hallway.",
            {"north": "lab", "east": "hallway"}, (),
        ),
        "lab": Room(
            "lab", "Lab",
            "Silent workbenches surround a flickering terminal. A service door "
            "leads east to maintenance.",
            {"south": "control_room", "east": "maintenance"}, ("terminal",),
        ),
        "hallway": Room(
            "hallway", "Hallway",
            "Cable bundles run toward the Archive Vault to the east. A card "
            "reader and keypad guard its heavy door.",
            {"west": "control_room", "north": "maintenance", "east": "archive_vault"},
            ("keypad", "vault"),
        ),
        "maintenance": Room(
            "maintenance", "Maintenance",
            "Spare circuits litter the benches. A maintenance log lies open "
            "beside the station's backup power supply.",
            {"west": "lab", "south": "hallway"}, ("maintenance log",),
        ),
        "archive_vault": Room(
            "archive_vault", "Archive Vault",
            "Insulated shelves protect the station's last beacon. Three empty "
            "signal sockets wait in its casing.",
            {"west": "hallway"}, (),
        ),
    }
    descriptions = {
        "access card": "A station access card marked ARCHIVE. Use it on the vault "
        "in the hallway to activate the keypad.",
        "beacon": "The missing emergency beacon has three signal sockets: amber, "
        "cyan, and violet. Fit all three fragments before taking it home.",
        "terminal": f"The terminal displays a partial access code: {code[0]} _ {code[2]}. "
        "These are the first and third digits. The maintenance log records the missing digit.",
        "maintenance log": f"The log reads: 'Middle code digit: {code[1]}. Read the "
        "terminal from left to right, placing this digit in its blank. Use the "
        "resulting three-digit code on the hallway keypad.'",
        "keypad": "A three-digit keypad beside the vault door. Activate it with "
        "the access card on the vault, then use the code here. The lab terminal "
        "and maintenance log hold the clues.",
        "vault": "The Archive Vault door has a card reader and a numeric lock. "
        "Use the access card on the vault, then enter the code on the keypad.",
        "amber fragment": "An amber signal fragment, shaped to fit the beacon's amber socket.",
        "cyan fragment": "A cyan signal fragment, shaped to fit the beacon's cyan socket.",
        "violet fragment": "A violet signal fragment, shaped to fit the beacon's violet socket.",
    }
    items = {name: Item(name, name, description) for name, description in descriptions.items()}
    locations = {"access card": START_ROOM, "beacon": "archive_vault"}
    locations.update(zip(FRAGMENT_IDS, fragment_rooms))
    return World(seed, rooms, items, locations, code)
