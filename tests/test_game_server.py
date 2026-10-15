"""Exercise the real game -> HTTP API -> SQLite path on temporary local data."""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import urlopen

import pygame

from client import database, leaderboard, main, progress
from client.api_client import ScoreClient
from game.model import Enemy


class GameServerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.folder.cleanup)
        self.score_path = Path(self.folder.name) / "TowersOfChance" / "scores.json"
        path_patch = patch("client.scores._scores_path", return_value=self.score_path)
        path_patch.start()
        self.addCleanup(path_patch.stop)
        self.servers = []
        self.addCleanup(self.close_servers)
        self.server = self.start_server()
        server_patch = patch("client.main.start_server", return_value=self.server)
        server_patch.start()
        self.addCleanup(server_patch.stop)
        self.addCleanup(pygame.quit)
        self.app = main.App()
        self.app.name = "Live / Player"
        self.app.start_game()
        self.assertIsInstance(self.app.score_client, ScoreClient)
        self.assertEqual(self.app.score_client.base_url, self.server.url)

    def start_server(self):
        server = leaderboard.start_server(0)
        self.servers.append(server)
        return server

    def close_servers(self):
        for server in self.servers:
            server.server_close()

    def get_json(self, path):
        with urlopen(self.server.url + path, timeout=3) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read().decode("utf-8"))

    def database_rows(self):
        with closing(sqlite3.connect(database.database_path())) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute("SELECT * FROM scores ORDER BY id")]

    def finish_loss(self, score):
        app = self.app
        app.start_wave()
        self.assertEqual(app.game.state, "wave")
        # Start from a real active wave with its final enemy about to escape.
        app.game.score, app.game.kills = score, score // 10
        app.game.lives = 1
        app.game._spawn_remaining = 0
        app.game.enemies = [Enemy(app.game.path_length - 1, 10, 10, 100)]
        app.update(0.25)
        self.assertEqual(app.game.state, "lose")
        self.assertEqual(app.game.lives, 0)
        app.draw()

    def test_game_result_reaches_api_stats_database_and_survives_restart(self):
        run_id = self.app.run_id
        self.finish_loss(420)
        self.assertTrue(self.app.saved)
        self.assertTrue(self.app.save_ok)
        self.assertIsNone(progress.load_progress())
        for _ in range(5):
            self.app.update(0.25)

        records = self.get_json("scores/top")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["player"], "Live / Player")
        self.assertEqual(records[0]["score"], 420)
        self.assertEqual(records[0]["run_id"], run_id)
        self.assertFalse(records[0]["won"])
        self.assertEqual(self.app.score_client.fetch_scores(), self.app.scores)
        self.assertEqual(self.app.scores[0]["name"], "Live / Player")
        expected_stats = {
            "player": "Live / Player", "games_played": 1, "best_score": 420,
            "average_score": 420.0, "total_score": 420, "wins": 0,
        }
        self.assertEqual(self.app.score_client.player_stats("Live / Player"), expected_stats)
        self.assertEqual(len(self.database_rows()), 1)
        self.assertEqual(self.database_rows()[0]["run_id"], run_id)

        # Retrying the accepted UUID is successful without making another row.
        self.assertTrue(self.app.score_client.submit_score(
            "Live / Player", 420, 1, "normal", False, run_id))
        self.assertEqual(len(self.database_rows()), 1)

        self.server.server_close()
        self.assertFalse(self.server.thread.is_alive())
        self.server = self.start_server()
        restarted_client = ScoreClient(self.server.url)
        self.assertEqual(self.get_json("scores/top"), records)
        self.assertEqual(restarted_client.fetch_scores(), self.app.scores)
        self.assertEqual(restarted_client.player_stats("Live / Player"), expected_stats)
        self.assertEqual(len(self.database_rows()), 1)

    def test_restart_key_sends_second_game_with_unique_uuid_and_no_duplicates(self):
        first_run = self.app.run_id
        self.finish_loss(120)
        self.assertTrue(self.app.save_ok)
        self.app.update(0.25)
        self.assertEqual(len(self.database_rows()), 1)

        self.app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
        self.assertEqual(self.app.game.state, "build")
        self.assertFalse(self.app.saved)
        second_run = self.app.run_id
        self.assertNotEqual(second_run, first_run)
        self.finish_loss(280)
        self.assertTrue(self.app.save_ok)
        for _ in range(5):
            self.app.update(0.25)

        rows = self.database_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["run_id"] for row in rows}, {first_run, second_run})
        self.assertEqual([row["score"] for row in rows], [120, 280])
        self.assertEqual([record["score"] for record in self.get_json("scores/top")], [280, 120])
        self.assertEqual(self.app.score_client.player_stats("Live / Player"), {
            "player": "Live / Player", "games_played": 2, "best_score": 280,
            "average_score": 200.0, "total_score": 400, "wins": 0,
        })

    def test_stopped_server_rejects_score_without_crashing_game(self):
        self.server.server_close()
        self.assertFalse(self.server.thread.is_alive())
        with patch.object(self.app.score_client, "submit_score",
                          wraps=self.app.score_client.submit_score) as submit:
            self.finish_loss(170)
            self.assertTrue(self.app.saved)
            self.assertFalse(self.app.save_ok)
            for _ in range(5):
                self.app.update(0.25)
            self.assertEqual(submit.call_count, 1)
        self.assertEqual(self.app.score_client.fetch_scores(), [])
        self.assertIsNone(self.app.score_client.player_stats("Live / Player"))
        self.assertEqual(self.database_rows(), [])
        self.app.menu()
        self.assertEqual(self.app.page, "menu")
        self.app.draw()


if __name__ == "__main__":
    unittest.main()
