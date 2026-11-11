"""Command parsing, recoverable errors, stream handling, and entry-point tests."""

from copy import deepcopy
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cache_quest.cli import CommandRunner, main, run_repl
from cache_quest.game import Game


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.runner = CommandRunner(Game.new(42), Path(self.tempdir.name) / "saves")

    def test_basics_case_and_whitespace(self):
        self.assertEqual(self.runner.execute("  "), "")
        self.assertIn("Control Room", self.runner.execute(" LOOK  "))
        self.assertIn("empty", self.runner.execute("inventory"))
        self.assertIn("access card", self.runner.execute("hint"))
        self.assertIn("Added", self.runner.execute(" TAKE   ACCESS CARD"))
        self.assertIn("ARCHIVE", self.runner.execute('inspect "access card"'))
        self.assertIn("Hallway", self.runner.execute("move e"))
        self.assertIn("accepted", self.runner.execute("use access card ON vault"))
        self.assertIn("GRANTED", self.runner.execute(f"use {self.runner.game.world.code} on keypad"))
        self.assertIn("Archive Vault", self.runner.execute("move east"))
        self.assertIn("Commands:", self.runner.execute("help"))

    def test_malformed_commands_never_reset_or_mutate(self):
        for line in ("look extra", "inventory extra", "hint extra", "help extra", "quit extra",
                     "move", "move north east", "take", "inspect", "use", "use on vault",
                     "use card on", "use card on vault on keypad", "new --seed",
                     "new --seed nope", "new --seed 9223372036854775808", "new extra",
                     "save one two", "load one two", 'take "unterminated', "unknown"):
            with self.subTest(line=line):
                before = deepcopy(self.runner.game)
                self.assertTrue(self.runner.execute(line))
                self.assertEqual(self.runner.game, before)
                self.assertTrue(self.runner.running)

    def test_save_load_and_failed_load(self):
        self.runner.execute("take access card")
        self.runner.execute("move east")
        self.runner.execute("use access card on vault")
        before = deepcopy(self.runner.game)
        self.assertIn("saved", self.runner.execute('save "my mission.json"'))
        self.runner.execute("new --seed -7")
        self.assertEqual(self.runner.game.world.seed, -7)
        self.assertIn("loaded", self.runner.execute('load "my mission.json"'))
        self.assertEqual(self.runner.game, before)
        self.assertNotIn("loaded", self.runner.execute("load missing.json"))
        self.assertEqual(self.runner.game, before)
        self.runner.execute("save")
        self.runner.execute("new --seed 42")
        self.runner.execute("load")
        self.assertEqual(self.runner.game, before)

    def test_new_with_seed_and_no_seed(self):
        self.runner.execute("take access card")
        self.assertIn("seed 42", self.runner.execute("new --seed 42"))
        self.assertEqual(self.runner.game, Game.new(42))
        self.assertIn("New mission", self.runner.execute("new"))
        self.assertIsInstance(self.runner.game.world.seed, int)

    def test_quit_eof_and_interrupt(self):
        output = io.StringIO()
        run_repl(self.runner, io.StringIO("look\nquit\ntake access card\n"), output)
        self.assertFalse(self.runner.running)
        self.assertNotIn("access card", self.runner.game.inventory)
        self.assertIn("paused", output.getvalue())
        for source in (io.StringIO(""), io.StringIO("\n")):
            output = io.StringIO()
            run_repl(CommandRunner(Game.new(42)), source, output)
            self.assertIn("paused", output.getvalue())
        source = io.StringIO()
        with patch.object(source, "readline", side_effect=KeyboardInterrupt):
            output = io.StringIO()
            run_repl(CommandRunner(Game.new(42)), source, output)
            self.assertIn("paused", output.getvalue())

    def test_main_seed_and_saved_resume(self):
        with patch("sys.stdin", io.StringIO("quit\n")), patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(main(["--seed", "0"]), 0)
            self.assertIn("Mission seed: 0", output.getvalue())
        self.runner.execute("save")
        with patch("sys.stdin", io.StringIO("quit\n")), patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(main(["--load", "mission.json", "--save-dir", str(self.runner.save_dir)]), 0)
            self.assertIn("Mission seed: 42", output.getvalue())

    def test_main_argument_failures(self):
        for args in (["--seed", "nope"], ["--seed", str(2**63)], ["--seed", "1", "--load", "mission.json"]):
            with self.subTest(args=args), patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit) as raised:
                main(args)
            self.assertEqual(raised.exception.code, 2)
        with patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["--load", "missing.json", "--save-dir", str(self.runner.save_dir)])
        self.assertEqual(raised.exception.code, 1)

    def test_module_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "-m", "cache_quest", "--seed", "42"],
            input="help\nquit\n", text=True, capture_output=True, timeout=10,
            cwd=Path(__file__).resolve().parents[1],
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CACHE QUEST", result.stdout)
        self.assertIn("Commands:", result.stdout)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
