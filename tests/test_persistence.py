"""Save integrity, malformed input and safe-file behavior."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cache_quest.game import Game
from cache_quest.persistence import MAX_SAVE_BYTES, PersistenceError, load_game, save_game
from cache_quest.world import FRAGMENT_IDS


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = Game.new(seed=42)

    def payload(self):
        return json.loads(save_game(self.game, save_dir=self.root).read_text())

    def write(self, data):
        (self.root / "mission.json").write_text(json.dumps(data), encoding="utf-8")

    def collect(self, *names):
        for name in names:
            del self.game.item_locations[name]
            self.game.inventory.add(name)

    def test_round_trip_initial_and_partial(self):
        self.collect("access card")
        self.game.card_used = True
        self.game.room_id = "lab"
        path = save_game(self.game, "checkpoint", self.root)
        self.assertEqual(path.name, "checkpoint.json")
        restored = load_game("checkpoint", self.root)
        self.assertEqual(restored.room_id, self.game.room_id)
        self.assertEqual(restored.world.seed, 42)
        self.assertEqual(restored.world.code, self.game.world.code)
        self.assertEqual(restored.world.initial_locations, self.game.world.initial_locations)
        self.assertEqual(restored.item_locations, self.game.item_locations)
        self.assertEqual(restored.inventory, self.game.inventory)
        self.assertTrue(restored.card_used)
        self.assertIsNot(restored.world, self.game.world)

    def test_quoted_name_with_spaces(self):
        path = save_game(self.game, "my mission", self.root)
        self.assertEqual(path.name, "my mission.json")
        self.assertEqual(load_game("my mission.json", self.root).world.seed, 42)

    def test_round_trip_won(self):
        self.collect("access card", *FRAGMENT_IDS, "beacon")
        self.game.card_used = self.game.vault_unlocked = True
        self.game.beacon_repaired = self.game.won = True
        self.game.room_id = "archive_vault"
        save_game(self.game, save_dir=self.root)
        restored = load_game(save_dir=self.root)
        self.assertTrue(restored.won)
        self.assertEqual(restored.inventory, self.game.inventory)

    def test_schema_is_minimal(self):
        data = self.payload()
        self.assertEqual(set(data), {"version", "seed", "room_id", "inventory", "item_locations", "card_used", "vault_unlocked", "beacon_repaired", "won"})
        self.assertNotIn("code", data)

    def test_invalid_fields_and_types(self):
        original = self.payload()
        cases = [("version", 2), ("version", True), ("seed", True), ("seed", 2**63),
                 ("seed", -(2**63)-1), ("seed", "42"), ("seed", 1.5),
                 ("room_id", []), ("room_id", "moon"), ("inventory", {}),
                 ("inventory", [[]]), ("inventory", ["access card", "access card"]),
                 ("inventory", ["unknown"]), ("item_locations", []),
                 ("item_locations", {"access card": []}), ("card_used", 1),
                 ("won", "false"), ("beacon_repaired", None), ("vault_unlocked", 0)]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                self.write({**original, key: value})
                with self.assertRaises(PersistenceError):
                    load_game(save_dir=self.root)
        for data in ([], None, 1, {}, {**original, "code": "123"}, {k: v for k, v in original.items() if k != "won"}):
            with self.subTest(data=data):
                self.write(data)
                with self.assertRaises(PersistenceError):
                    load_game(save_dir=self.root)

    def test_signed_seed_boundaries(self):
        for seed in (-(2**63), 2**63-1):
            game = Game.new(seed=seed)
            save_game(game, save_dir=self.root)
            self.assertEqual(load_game(save_dir=self.root).world.seed, seed)

    def test_impossible_progress(self):
        original = self.payload()
        cases = [{"card_used": True}, {"vault_unlocked": True},
                 {"beacon_repaired": True}, {"won": True}, {"room_id": "archive_vault"},
                 {"inventory": ["access card"]}, {"item_locations": {}},
                 {"item_locations": {**original["item_locations"], "access card": "lab"}}]
        for change in cases:
            with self.subTest(change=change):
                self.write({**original, **change})
                with self.assertRaises(PersistenceError):
                    load_game(save_dir=self.root)

    def test_beacon_requires_repair_and_matching_win(self):
        data = self.payload()
        del data["item_locations"]["beacon"]
        data["inventory"] = ["beacon"]
        for won in (False, True):
            data["won"] = won
            self.write(data)
            with self.assertRaises(PersistenceError):
                load_game(save_dir=self.root)

    def test_corrupt_missing_duplicate_and_oversized(self):
        with self.assertRaises(PersistenceError):
            load_game(save_dir=self.root)
        for raw in (b"{", b"\xff", b'{"version":1,"version":1}', b"[" * 2000, b"9" * 5000,
                    b" " * (MAX_SAVE_BYTES + 1)):
            with self.subTest(length=len(raw)):
                (self.root / "mission.json").write_bytes(raw)
                with self.assertRaises(PersistenceError):
                    load_game(save_dir=self.root)

    def test_unsafe_names(self):
        for name in ("../outside.json", "/tmp/outside.json", "a/b", "a\\b", ".hidden", "", "foo.txt", "..", "a\x00", "x" * 81, None):
            for operation in (save_game, load_game):
                with self.subTest(name=name, operation=operation.__name__):
                    with self.assertRaises(PersistenceError):
                        if operation is save_game:
                            operation(self.game, name, self.root)
                        else:
                            operation(name, self.root)

    def test_symlink_targets_and_roots_rejected(self):
        actual = self.root / "actual.json"
        actual.write_text("unchanged")
        (self.root / "mission.json").symlink_to(actual)
        for operation in (lambda: save_game(self.game, save_dir=self.root), lambda: load_game(save_dir=self.root)):
            with self.assertRaises(PersistenceError):
                operation()
        self.assertEqual(actual.read_text(), "unchanged")
        link = self.root / "linked"
        link.symlink_to(self.root, target_is_directory=True)
        for operation in (lambda: save_game(self.game, save_dir=link), lambda: load_game(save_dir=link)):
            with self.assertRaises(PersistenceError):
                operation()

    def test_directory_instead_of_file(self):
        (self.root / "mission.json").mkdir()
        with self.assertRaises(PersistenceError):
            load_game(save_dir=self.root)

    def test_failed_atomic_replace_keeps_original_and_cleans_temporary(self):
        path = save_game(self.game, save_dir=self.root)
        before = path.read_bytes()
        self.collect("access card")
        with patch("cache_quest.persistence.os.replace", side_effect=OSError("private path")):
            with self.assertRaises(PersistenceError) as caught:
                save_game(self.game, save_dir=self.root)
        self.assertNotIn("private path", str(caught.exception))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_save_validates_before_overwriting(self):
        path = save_game(self.game, save_dir=self.root)
        before = path.read_bytes()
        self.game.won = True
        with self.assertRaises(PersistenceError):
            save_game(self.game, save_dir=self.root)
        self.assertEqual(path.read_bytes(), before)

    def test_nested_save_directory_created(self):
        directory = self.root / "nested" / "saves"
        self.assertTrue(save_game(self.game, save_dir=directory).is_file())
        self.assertEqual(load_game(save_dir=directory).world.seed, 42)


if __name__ == "__main__":
    unittest.main()
