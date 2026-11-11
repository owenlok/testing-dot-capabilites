"""World invariants, repeatability, and pure puzzle behavior."""

from dataclasses import FrozenInstanceError
import random
import unittest
from unittest.mock import patch

from cache_quest.puzzles import contextual_hint, valid_code
from cache_quest.world import FRAGMENT_IDS, ROOM_IDS, START_ROOM, build_world


class WorldTests(unittest.TestCase):
    def test_repeatable_world(self):
        for seed in (0, 42, -1, -(2**63), 2**63 - 1):
            with self.subTest(seed=seed):
                self.assertEqual(build_world(seed), build_world(seed))

    def test_variety(self):
        worlds = [build_world(seed) for seed in range(20)]
        self.assertGreater(len({world.code for world in worlds}), 1)
        self.assertGreater(len({tuple(world.initial_locations.items()) for world in worlds}), 1)

    def test_seed_validation(self):
        for seed in (True, False, 1.0, "42", [], 2**63, -(2**63) - 1):
            with self.subTest(seed=seed):
                with self.assertRaises(ValueError):
                    build_world(seed)

    def test_unspecified_seed_is_retained_and_reproducible(self):
        with patch("cache_quest.world.random.SystemRandom") as system_random:
            system_random.return_value.randrange.return_value = 12345
            world = build_world()
        self.assertEqual(world.seed, 12345)
        self.assertEqual(world, build_world(world.seed))

    def test_global_rng_is_not_modified(self):
        before = random.getstate()
        build_world(42)
        self.assertEqual(random.getstate(), before)

    def test_world_invariants_across_seeds(self):
        reverse = {"north": "south", "south": "north", "east": "west", "west": "east"}
        for seed in range(100):
            world = build_world(seed)
            with self.subTest(seed=seed):
                self.assertEqual(tuple(world.rooms), ROOM_IDS)
                self.assertTrue(valid_code(world.code, world.code))
                self.assertEqual(world.initial_locations["access card"], START_ROOM)
                self.assertEqual(world.initial_locations["beacon"], "archive_vault")
                locations = [world.initial_locations[key] for key in FRAGMENT_IDS]
                self.assertEqual(len(set(locations)), 3)
                self.assertTrue(set(locations) <= set(ROOM_IDS[:-1]))
                for room_id, room in world.rooms.items():
                    self.assertEqual(room.id, room_id)
                    for direction, destination in room.exits.items():
                        self.assertEqual(world.rooms[destination].exits[reverse[direction]], room_id)
                    for fixture in room.fixtures:
                        self.assertIn(fixture, world.items)
                        self.assertNotIn(fixture, world.initial_locations)
                for item_id, item in world.items.items():
                    self.assertEqual(item_id, item.id)
                    self.assertEqual(item_id, item.name.lower())
                    self.assertTrue(item.description)

    def test_graph_connected_without_vault(self):
        world = build_world(42)
        visited = {START_ROOM}
        pending = [START_ROOM]
        while pending:
            for destination in world.rooms[pending.pop()].exits.values():
                if destination not in visited and destination != "archive_vault":
                    visited.add(destination)
                    pending.append(destination)
        self.assertEqual(visited, set(ROOM_IDS[:-1]))

    def test_clues_encode_correct_digits(self):
        for seed in range(20):
            world = build_world(seed)
            self.assertIn(f"{world.code[0]} _ {world.code[2]}", world.items["terminal"].description)
            self.assertIn(f"Middle code digit: {world.code[1]}", world.items["maintenance log"].description)

    def test_fixtures_and_frozen_records(self):
        world = build_world(42)
        self.assertEqual(world.rooms["lab"].fixtures, ("terminal",))
        self.assertEqual(world.rooms["maintenance"].fixtures, ("maintenance log",))
        self.assertEqual(world.rooms["hallway"].fixtures, ("keypad", "vault"))
        with self.assertRaises(FrozenInstanceError):
            world.rooms[START_ROOM].name = "Changed"
        with self.assertRaises(FrozenInstanceError):
            world.items["access card"].name = "Changed"

    def test_worlds_do_not_share_mutable_maps(self):
        first, second = build_world(42), build_world(42)
        first.rooms[START_ROOM].exits.clear()
        first.initial_locations.clear()
        self.assertTrue(second.rooms[START_ROOM].exits)
        self.assertTrue(second.initial_locations)


class PuzzleTests(unittest.TestCase):
    def test_exact_code_only(self):
        self.assertTrue(valid_code("007", "007"))
        for candidate in ("7", "0007", "007 ", " 007", "007\n", "００７", "٠٠٧", "00²", "abc", "008", 7, None):
            with self.subTest(candidate=candidate):
                self.assertFalse(valid_code(candidate, "007"))
        self.assertFalse(valid_code("abc", "abc"))

    def hint(self, **changes):
        state = dict(room_id=START_ROOM, inventory=(), card_used=False,
                     vault_unlocked=False, beacon_repaired=False, won=False)
        state.update(changes)
        return contextual_hint(**state)

    def test_hints_follow_progress(self):
        self.assertIn("Control Room", self.hint())
        self.assertIn("hallway", self.hint(inventory=("access card",)))
        self.assertIn("on the vault", self.hint(room_id="hallway", inventory=("access card",)))
        self.assertIn("terminal", self.hint(card_used=True))
        self.assertIn("maintenance log", self.hint(card_used=True, room_id="lab"))
        self.assertIn("middle digit", self.hint(card_used=True, room_id="maintenance"))
        self.assertIn("missing signal fragments", self.hint(vault_unlocked=True))
        partial = self.hint(vault_unlocked=True, inventory=(FRAGMENT_IDS[0],))
        self.assertNotIn(FRAGMENT_IDS[0], partial)
        self.assertIn(FRAGMENT_IDS[1], partial)
        self.assertIn("Archive Vault", self.hint(vault_unlocked=True, inventory=FRAGMENT_IDS))
        self.assertIn("Use the fragments", self.hint(room_id="archive_vault", vault_unlocked=True, inventory=FRAGMENT_IDS))
        self.assertIn("Take the beacon", self.hint(room_id="archive_vault", beacon_repaired=True))
        self.assertIn("Return", self.hint(beacon_repaired=True))
        self.assertIn("Mission complete", self.hint(won=True))

    def test_hints_do_not_expose_numeric_codes_or_mutate_inventory(self):
        inventory = list(FRAGMENT_IDS)
        for room_id in ROOM_IDS:
            for card_used in (False, True):
                for vault_unlocked in (False, True):
                    hint = self.hint(room_id=room_id, inventory=inventory,
                                     card_used=card_used, vault_unlocked=vault_unlocked)
                    self.assertFalse(any(char.isdigit() for char in hint))
        self.assertEqual(inventory, list(FRAGMENT_IDS))


if __name__ == "__main__":
    unittest.main()
