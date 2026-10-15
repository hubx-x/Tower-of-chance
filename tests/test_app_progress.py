"""Exercise checkpoint behavior through the Pygame app without opening a window."""

import os

# These must be selected before importing pygame or the application.
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pygame

from client import main, progress, scores
from game.model import Enemy


class AppProgressTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.folder.cleanup)
        self.score_path = Path(self.folder.name) / "TowersOfChance" / "scores.json"
        path_patch = patch("client.scores._scores_path", return_value=self.score_path)
        path_patch.start()
        self.addCleanup(path_patch.stop)
        self.server = Mock(url="http://127.0.0.1:8765/")
        server_patch = patch("client.main.start_server", return_value=self.server)
        self.start_server = server_patch.start()
        self.addCleanup(server_patch.stop)
        self.addCleanup(pygame.quit)

    def start_game(self, name="Player One"):
        app = main.App()
        app.name = name
        app.start_game()
        self.assertTrue(app.progress_ok)
        return app

    def test_new_game_and_periodic_autosave_persist_real_changes(self):
        app = main.App()
        app.name = "  Player   One  "
        app.difficulty = "hard"
        app.map_name = "desert"
        app.start_game()
        saved = progress.load_progress()
        self.assertEqual(saved["name"], "Player One")
        self.assertEqual(saved["game"].difficulty, "hard")
        self.assertEqual(saved["game"].map_name, "desert")
        self.assertEqual(saved["game"].coins, 130)
        self.assertTrue(app.game.place_tower(130, 310, "basic"))
        self.assertEqual(progress.load_progress()["game"].towers, [])
        for _ in range(8):
            app.update(0.25)
        saved_game = progress.load_progress()["game"]
        self.assertEqual(len(saved_game.towers), 1)
        self.assertEqual(saved_game.coins, 80)
        self.assertEqual(saved_game.towers[0].invested, 50)

    def test_mid_wave_quit_recreate_and_continue_restore_paused(self):
        app = self.start_game()
        self.assertTrue(app.game.place_tower(130, 310))
        app.toggle_auto()
        app.start_wave()
        self.assertEqual(progress.load_progress()["game"].state, "wave")
        app.update(0.25)
        self.assertTrue(app.game.enemies)
        expected = progress._encode_game(app.game)
        app.handle(pygame.event.Event(pygame.QUIT))
        self.assertFalse(app.running)

        restored = main.App()
        self.assertEqual(restored.page, "menu")
        self.assertIsNone(restored.game)
        self.assertEqual(restored.name, "Player One")
        restored.continue_game()
        self.assertEqual(restored.page, "game")
        self.assertTrue(restored.paused)
        self.assertTrue(restored.auto_wave)
        self.assertEqual(restored.auto_timer, main.AUTO_DELAY)
        self.assertEqual(progress._encode_game(restored.game), expected)
        restored.update(0.25)
        self.assertEqual(progress._encode_game(restored.game), expected)
        restored.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p))
        restored.update(0.25)
        self.assertFalse(restored.paused)
        self.assertGreater(restored.game.enemies[0].progress,
                           app.game.enemies[0].progress)

    def test_menu_name_edits_do_not_rename_saved_run(self):
        app = self.start_game("Original Player")
        self.assertTrue(app.game.place_tower(130, 310, "ice"))
        app.toggle_auto()
        app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertEqual(app.page, "menu")
        self.assertEqual(len(progress.load_progress()["game"].towers), 1)
        app.name = "Next Player"
        app.set_difficulty("easy")
        app.set_map("tundra")
        app.handle(pygame.event.Event(pygame.QUIT))
        saved = progress.load_progress()
        self.assertEqual(saved["name"], "Original Player")
        self.assertEqual(saved["game"].difficulty, "normal")
        self.assertEqual(saved["game"].map_name, "meadow")
        self.assertTrue(saved["auto_wave"])
        app.continue_game()
        self.assertEqual(app.name, "Original Player")
        self.assertEqual(app.difficulty, "normal")
        self.assertEqual(app.map_name, "meadow")

    def test_choice_transition_and_selected_effect_are_saved_immediately(self):
        app = self.start_game()
        app.start_wave()
        app.game._spawn_remaining = 0
        app.game.enemies = []
        app.update(0)
        self.assertEqual(app.game.state, "choice")
        saved_game = progress.load_progress()["game"]
        self.assertEqual(saved_game.state, "choice")
        self.assertEqual(saved_game.effects, app.game.effects)
        app.choose_effect(0)
        saved_game = progress.load_progress()["game"]
        self.assertEqual(saved_game.state, "build")
        self.assertEqual(saved_game.completed_waves, 1)
        self.assertEqual(saved_game.effects, [])
        self.assertEqual(saved_game.damage_multiplier, app.game.damage_multiplier)
        self.assertEqual(saved_game.speed_multiplier, app.game.speed_multiplier)
        self.assertEqual(saved_game.range_multiplier, app.game.range_multiplier)

    def assert_finished_once(self, app, won):
        self.assertTrue(app.saved)
        self.assertTrue(app.save_ok)
        self.assertTrue(app.progress_ok)
        self.assertIsNone(app.checkpoint)
        self.assertIsNone(progress.load_progress())
        self.assertFalse(self.score_path.with_name("progress.json").exists())
        records = scores.load_scores()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], app.run_name)
        self.assertEqual(records[0]["score"], app.game.score)
        self.assertEqual(records[0]["won"], won)
        app.update(0.25)
        app.menu()
        app.handle(pygame.event.Event(pygame.QUIT))
        self.assertEqual(scores.load_scores(), records)
        self.assertIsNone(progress.load_progress())

    def test_victory_saves_one_record_and_removes_checkpoint(self):
        app = self.start_game()
        app.game.level, app.game.wave, app.game.completed_waves = 3, 3, 8
        app.start_wave()
        app.game._spawn_remaining = 0
        app.game.enemies = []
        app.update(0)
        self.assertEqual(app.game.state, "win")
        self.assertEqual(app.game.completed_waves, 9)
        self.assert_finished_once(app, True)

    def test_loss_saves_one_record_and_removes_checkpoint(self):
        app = self.start_game()
        app.start_wave()
        app.game.lives = 1
        app.game._spawn_remaining = 0
        app.game.enemies = [Enemy(app.game.path_length - 1, 10, 10, 100)]
        app.update(0.25)
        self.assertEqual(app.game.state, "lose")
        self.assertEqual(app.game.lives, 0)
        self.assert_finished_once(app, False)

    def test_run_finally_saves_and_closes_server_after_loop_failure(self):
        app = self.start_game()
        self.assertTrue(app.game.place_tower(130, 310))
        app.clock = Mock()
        app.clock.tick.return_value = 16
        with patch("pygame.event.get", side_effect=RuntimeError("Unexpected event failure")):
            with self.assertRaisesRegex(RuntimeError, "Unexpected event failure"):
                app.run()
        saved = progress.load_progress()
        self.assertEqual(len(saved["game"].towers), 1)
        self.assertEqual(saved["game"].coins, 100)
        self.server.shutdown.assert_called_once_with()
        self.server.server_close.assert_called_once_with()
        self.assertFalse(pygame.get_init())


if __name__ == "__main__":
    unittest.main()
