import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from client import progress
from game.model import EFFECTS, Enemy, Game, Impact, Projectile, Tower


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.folder.cleanup)
        self.scores_path = Path(self.folder.name) / "TowersOfChance" / "scores.json"
        self.path_patch = patch("client.scores._scores_path", return_value=self.scores_path)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.path = self.scores_path.with_name("progress.json")

    def game(self, state):
        game = Game("hard", random.Random(137), "desert")
        game.state = state
        game.level, game.wave, game.completed_waves = 2, 2, 4
        game.lives, game.coins, game.score, game.kills = 13, 241, 670, 27
        game.damage_multiplier = 1.56
        game.speed_multiplier = 0.99
        game.range_multiplier = 1.25
        game.towers = [
            Tower(130, 310, "damage", 4, 0.32, "fire", 1.12, 480),
            Tower(280, 310, "speed", 3, 0.08, "ice", -0.19, 180),
        ]
        game.impacts = [Impact(110, 220, "fire", 0.19, 0.3)]
        game.message = "A saved game."
        if state == "choice":
            game.effects = game.rng.sample(EFFECTS, 3)
        if state == "wave":
            first = Enemy(80, 18.7, 21, 68, 120, 220, 0.13, 1.7, 2.2)
            second = Enemy(20, 21, 21, 68, 60, 220)
            removed = Enemy(55, -0.3, 21, 68, 95, 220)
            game.enemies = [first, second]
            game.projectiles = [
                Projectile(135, 288, first, "fire", 12, 0, 10, 2, 280, 1.6, 120, 220, 0.4),
                Projectile(280, 290, first, "ice", 2.7, 0.95, 0, 0, 330, 2.4, 120, 220, 0.8),
                Projectile(150, 270, removed, "fire", 10, target_x=95, target_y=220),
                Projectile(160, 280, removed, "fire", 10, target_x=95, target_y=220),
            ]
            game.spawned_count = 3
            game.wave_enemy_count = 10
            game._spawn_remaining = 7
            game._spawn_timer = 0.43
        return game

    def test_round_trip_build_wave_and_choice(self):
        for state in ("build", "wave", "choice"):
            with self.subTest(state=state):
                game = self.game(state)
                self.assertTrue(progress.save_progress("Player One", game, True))
                checkpoint = progress.load_progress()
                self.assertEqual(checkpoint["name"], "Player One")
                self.assertIs(checkpoint["auto_wave"], True)
                self.assertEqual(progress._encode_game(game), progress._encode_game(checkpoint["game"]))
                self.assertEqual(checkpoint["game"].rng.random(), game.rng.random())
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["version"], 1)

    def test_projectile_targets_preserve_identity_and_removed_targets(self):
        self.assertTrue(progress.save_progress("Player", self.game("wave"), False))
        restored = progress.load_progress()["game"]
        self.assertIs(restored.projectiles[0].target, restored.enemies[0])
        self.assertIs(restored.projectiles[1].target, restored.enemies[0])
        self.assertIs(restored.projectiles[2].target, restored.projectiles[3].target)
        self.assertNotIn(restored.projectiles[2].target, restored.enemies)

    def test_resumed_simulation_matches_without_saving(self):
        original = self.game("wave")
        self.assertTrue(progress.save_progress("Player", original, False))
        restored = progress.load_progress()["game"]
        for _ in range(800):
            original.update(0.05)
            restored.update(0.05)
            self.assertEqual(progress._encode_game(original), progress._encode_game(restored))
        self.assertIn(original.state, ("build", "choice"))

    def test_missing_truncated_or_incompatible_checkpoint_is_ignored(self):
        self.assertIsNone(progress.load_progress())
        self.path.parent.mkdir(parents=True)
        for content in ('{"version":', '[]', '{}', '{"version": 99}', 'null', '\ufeff{}'):
            with self.subTest(content=content):
                self.path.write_text(content, encoding="utf-8")
                self.assertIsNone(progress.load_progress())

    def test_invalid_checkpoint_fields_are_ignored(self):
        self.assertTrue(progress.save_progress("Player", self.game("wave"), False))
        good = self.path.read_text(encoding="utf-8")
        edits = (
            lambda d: d.update(version=True),
            lambda d: d.update(auto_wave="yes"),
            lambda d: d["game"].update(state="win"),
            lambda d: d["game"].update(level=4),
            lambda d: d["game"].update(speed_multiplier=0),
            lambda d: d["game"].update(rng=[3, [1, 2], None]),
            lambda d: d["game"].update(active_enemies=[0, 0]),
            lambda d: d["game"]["projectiles"][0].update(target=100),
            lambda d: d["game"]["towers"][0].update(kind="unknown"),
            lambda d: d["game"]["enemy_pool"][0].update(hp=float("nan")),
            lambda d: d["game"]["impacts"][0].update(duration=0),
        )
        for edit in edits:
            data = json.loads(good)
            edit(data)
            self.path.write_text(json.dumps(data), encoding="utf-8")
            self.assertIsNone(progress.load_progress(), repr(data))

    def test_write_and_replace_failure_preserve_previous_checkpoint(self):
        game = self.game("build")
        self.assertTrue(progress.save_progress("Original", game, False))
        original_content = self.path.read_bytes()
        game.coins += 50
        for operation in ("write_text", "replace"):
            with self.subTest(operation=operation), patch.object(Path, operation, side_effect=OSError("Disk unavailable")):
                self.assertFalse(progress.save_progress("Changed", game, True))
            self.assertEqual(self.path.read_bytes(), original_content)
            self.assertEqual(progress.load_progress()["name"], "Original")
        self.assertFalse(self.path.with_suffix(".tmp").exists())

    def test_invalid_or_finished_game_does_not_overwrite_checkpoint(self):
        game = self.game("build")
        self.assertTrue(progress.save_progress("Original", game, False))
        original_content = self.path.read_bytes()
        game.state = "win"
        self.assertFalse(progress.save_progress("Finished", game, False))
        self.assertFalse(progress.save_progress("", self.game("build"), False))
        self.assertEqual(self.path.read_bytes(), original_content)

    def test_clear_progress(self):
        self.assertTrue(progress.clear_progress())
        self.assertTrue(progress.save_progress("Player", self.game("build"), False))
        self.assertTrue(progress.clear_progress())
        self.assertIsNone(progress.load_progress())
        with patch.object(Path, "unlink", side_effect=OSError("Read-only")):
            self.assertFalse(progress.clear_progress())


if __name__ == "__main__":
    unittest.main()
