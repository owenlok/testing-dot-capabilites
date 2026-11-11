"""Exercise real player actions, including complete missions across seeds."""

from collections import deque
from copy import deepcopy
import re
import unittest

from cache_quest.game import Game, GameError
from cache_quest.world import FRAGMENT_IDS


def travel(game, destination):
    """Reach a room through real move actions, never by changing state."""
    pending = deque([(game.room_id, [])])
    visited = set()
    while pending:
        room_id, path = pending.popleft()
        if room_id == destination:
            for direction in path:
                game.move(direction)
            return
        if room_id in visited:
            continue
        visited.add(room_id)
        for direction, next_room in game.world.rooms[room_id].exits.items():
            if next_room != "archive_vault" or game.vault_unlocked:
                pending.append((next_room, [*path, direction]))
    raise AssertionError(f"Cannot reach {destination}")


def unlock(game):
    travel(game, "control_room")
    if "access card" not in game.inventory:
        game.take("access card")
    travel(game, "lab")
    outer = re.search(r"(\d) _ (\d)", game.inspect("terminal"))
    travel(game, "maintenance")
    middle = re.search(r"Middle code digit: (\d)", game.inspect("maintenance log"))
    code = outer[1] + middle[1] + outer[2]
    travel(game, "hallway")
    game.use("access card", "vault")
    game.use(code, "keypad")


def complete(game):
    for fragment in FRAGMENT_IDS:
        if fragment not in game.inventory:
            travel(game, game.item_locations[fragment])
            game.take(fragment)
    unlock(game)
    travel(game, "archive_vault")
    game.use("fragments", "beacon")
    return game.take("beacon")


class GameTests(unittest.TestCase):
    def setUp(self):
        self.game = Game.new(42)

    def assert_unchanged_error(self, action):
        before = deepcopy(self.game)
        with self.assertRaises(GameError):
            action()
        self.assertEqual(self.game, before)

    def test_start_and_navigation(self):
        self.assertIn("Control Room", self.game.look())
        self.assertIn("access card", self.game.look())
        self.assertIn("Lab", self.game.move("N"))
        self.assertEqual(self.game.room_id, "lab")
        self.game.move("south")
        self.assert_unchanged_error(lambda: self.game.move("west"))
        self.game.move("east")
        self.assertIn("locked", self.game.look())
        self.assert_unchanged_error(lambda: self.game.move("east"))

    def test_inventory_and_visibility(self):
        self.assertIn("empty", self.game.inventory_text())
        self.assert_unchanged_error(lambda: self.game.take("terminal"))
        self.assert_unchanged_error(lambda: self.game.inspect("terminal"))
        self.game.take(" ACCESS   CARD ")
        self.assertNotIn("access card", self.game.item_locations)
        self.assertIn("access card", self.game.inventory_text())
        self.game.move("north")
        self.assertIn("ARCHIVE", self.game.inspect("Access Card"))
        self.assert_unchanged_error(lambda: self.game.take("access card"))
        self.assert_unchanged_error(lambda: self.game.take("terminal"))
        self.assert_unchanged_error(lambda: self.game.take("imaginary object"))

    def test_card_and_code_require_correct_location_and_order(self):
        self.assert_unchanged_error(lambda: self.game.use("access card", "vault"))
        self.game.take("access card")
        self.assert_unchanged_error(lambda: self.game.use("access card", "vault"))
        self.assert_unchanged_error(lambda: self.game.use(self.game.world.code, "keypad"))
        self.game.move("east")
        self.assert_unchanged_error(lambda: self.game.use(self.game.world.code, "keypad"))
        self.assert_unchanged_error(lambda: self.game.use("access card", "beacon"))
        self.assertIn("accepted", self.game.use("access card", "vault"))
        self.assertIn("already", self.game.use("access card", "vault"))
        wrong = f"{(int(self.game.world.code) + 1) % 1000:03d}"
        self.assert_unchanged_error(lambda: self.game.use(wrong, "keypad"))
        self.assert_unchanged_error(lambda: self.game.use(self.game.world.code, "beacon"))
        self.game.use("code " + self.game.world.code, "keypad")
        self.assertTrue(self.game.vault_unlocked)
        self.assertIn("already", self.game.use(self.game.world.code, "keypad"))
        self.assertIn("GRANTED", self.game.inspect("keypad"))
        self.assertIn("open", self.game.inspect("vault"))

    def test_beacon_requires_all_fragments_and_repair(self):
        unlock(self.game)
        self.game.move("east")
        self.assert_unchanged_error(lambda: self.game.take("beacon"))
        self.assert_unchanged_error(lambda: self.game.use("fragments", "beacon"))
        self.assertFalse(self.game.won)
        for fragment in FRAGMENT_IDS:
            travel(self.game, self.game.item_locations[fragment])
            self.game.take(fragment)
        self.assert_unchanged_error(lambda: self.game.use("fragments", "beacon"))
        travel(self.game, "archive_vault")
        self.assert_unchanged_error(lambda: self.game.use("fragments", "keypad"))
        self.game.use("signal fragments", "beacon")
        self.assertTrue(self.game.beacon_repaired)
        self.assertFalse(self.game.won)
        self.assertIn("repaired", self.game.inspect("beacon"))
        self.assertIn("already repaired", self.game.use("fragments", "beacon"))
        self.assertIn("RECOVERED", self.game.take("beacon"))
        self.assertTrue(self.game.won)
        self.assertIn("recovered", self.game.inspect("beacon"))
        self.assertNotIn("Take", self.game.inspect("beacon"))
        self.assertIn("complete", self.game.hint())
        self.assert_unchanged_error(lambda: self.game.take("beacon"))

    def test_all_seeded_missions_solvable_from_visible_clues(self):
        for seed in range(250):
            with self.subTest(seed=seed):
                game = Game.new(seed)
                self.assertIn("RECOVERED", complete(game))
                self.assertTrue(game.won)
                self.assertEqual(game.inventory, {"access card", "beacon", *FRAGMENT_IDS})
                self.assertEqual(game.item_locations, {})

    def test_leading_zero_code_preserved(self):
        game = next(Game.new(seed) for seed in range(1000) if Game.new(seed).world.code.startswith("0"))
        unlock(game)
        self.assertTrue(game.vault_unlocked)

    def test_inspect_keypad_stages(self):
        self.game.take("access card")
        self.game.move("east")
        self.assertIn("dark", self.game.inspect("keypad"))
        self.game.use("access card")
        self.assertIn("glows", self.game.inspect("keypad"))

    def test_unused_objects_and_non_ascii_codes(self):
        for item in ("unknown", "1234", "１２３", "١٢٣", "12²"):
            self.assert_unchanged_error(lambda item=item: self.game.use(item, "keypad"))
        complete(self.game)
        self.assert_unchanged_error(lambda: self.game.use("beacon", "keypad"))


if __name__ == "__main__":
    unittest.main()
