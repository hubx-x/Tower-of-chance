from concurrent.futures import ThreadPoolExecutor
import http.client
import json
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote
from uuid import uuid4

from client import database, leaderboard, scores


class LeaderboardTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.score_path = Path(self.folder.name) / "scores.json"
        self.patch = patch.object(scores, "_scores_path", return_value=self.score_path)
        self.patch.start()
        self.server = leaderboard.start_server(0)

    def tearDown(self):
        self.server.server_close()
        self.patch.stop()
        self.folder.cleanup()

    def request(self, path, method="GET", payload=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            body = json.dumps(payload).encode("utf-8") if payload is not None else None
            headers = {"Content-Type": "application/json"} if body else {}
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, {key.title(): value for key, value in response.getheaders()}, response.read()
        finally:
            connection.close()

    def submit(self, player="Player", score=100, **metadata):
        status, _headers, body = self.request("/scores", "POST", {"player": player, "score": score, **metadata})
        return status, json.loads(body)

    def test_home_is_jinja_html_with_saved_scores_escaped(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"TOWERS OF CHANCE", body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        name = "<img src=x onerror=x>"
        self.assertEqual(self.submit(name, 543)[0], 201)
        populated = self.request("/")[2]
        self.assertIn(b"&lt;img", populated)
        self.assertNotIn(name.encode("utf-8"), populated)
        self.assertIn(b"543", populated)
        self.assertEqual(self.request("/index.html")[0], 200)

    def test_minimal_post_and_live_compatibility_api(self):
        self.assertEqual(json.loads(self.request("/api/scores")[2]), {"scores": []})
        status, record = self.submit("  First   Player  ", 100)
        self.assertEqual(status, 201)
        self.assertEqual(record["player"], "First Player")
        self.assertEqual(record["level"], 1)
        self.assertEqual(record["difficulty"], "normal")
        self.assertFalse(record["won"])
        self.assertIn("date", record)
        self.assertEqual(self.submit("Second", 500, level=3, difficulty="hard", won=True)[0], 201)
        records = json.loads(self.request("/api/scores")[2])["scores"]
        self.assertEqual([record["score"] for record in records], [500, 100])
        self.assertEqual(records[0]["name"], "Second")
        self.assertEqual(set(records[0]), {"name", "score", "level", "difficulty", "won", "date"})

    def test_top_scores_order_limit_and_validation(self):
        for score in (100, 400, 200):
            self.assertEqual(self.submit(score=score)[0], 201)
        records = json.loads(self.request("/scores/top?limit=2")[2])
        self.assertEqual([record["score"] for record in records], [400, 200])
        for limit in ("0", "101", "abc"):
            with self.subTest(limit=limit):
                self.assertEqual(self.request("/scores/top?limit=" + limit)[0], 422)

    def test_player_stats_and_parameterized_names(self):
        name = "O'Neil / ?"
        self.submit(name, 100, won=True)
        self.submit(name, 300)
        self.submit("Other", 999)
        status, _headers, body = self.request("/players/" + quote(name, safe="") + "/stats")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {
            "player": name, "games_played": 2, "best_score": 300,
            "average_score": 200.0, "total_score": 400, "wins": 1,
        })
        self.assertEqual(self.request("/players/Missing/stats")[0], 404)

    def test_invalid_submissions_do_not_write(self):
        cases = (
            {"player": "", "score": 10}, {"player": "   ", "score": 10},
            {"player": "X" * 25, "score": 10}, {"player": 4, "score": 10},
            {"player": "X", "score": -1}, {"player": "X", "score": 1_000_000_001},
            {"player": "X", "score": True}, {"player": "X", "score": 1.2},
            {"player": "X", "score": "10"}, {"player": "X", "score": 10, "level": 4},
            {"player": "X", "score": 10, "difficulty": "impossible"},
            {"player": "X", "score": 10, "won": "true"},
            {"player": "X", "score": 10, "run_id": "not-a-uuid"},
            {"player": "X", "score": 10, "unexpected": "field"},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertEqual(self.request("/scores", "POST", payload)[0], 422)
        self.assertEqual(json.loads(self.request("/scores/top")[2]), [])

    def test_sqlite_persists_after_server_restart(self):
        self.submit("Persistent", 777)
        self.server.server_close()
        self.assertTrue(database.database_path().read_bytes().startswith(b"SQLite format 3"))
        self.server = leaderboard.start_server(0)
        records = json.loads(self.request("/scores/top")[2])
        self.assertEqual(records[0]["player"], "Persistent")
        self.assertEqual(records[0]["score"], 777)

    def test_run_id_retries_are_idempotent_and_conflicts_rejected(self):
        run_id = str(uuid4())
        first_status, first = self.submit(run_id=run_id)
        retry_status, retry = self.submit(run_id=run_id)
        self.assertEqual((first_status, retry_status), (201, 200))
        self.assertEqual(first, retry)
        self.assertEqual(self.submit(score=200, run_id=run_id)[0], 409)
        self.assertEqual(len(json.loads(self.request("/scores/top")[2])), 1)

    def test_simultaneous_retries_create_one_score(self):
        run_id = str(uuid4())
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.submit(run_id=run_id)[0], range(4)))
        self.assertEqual(sorted(results), [200, 200, 200, 201])
        self.assertEqual(len(json.loads(self.request("/scores/top")[2])), 1)

    def test_legacy_json_migrates_once(self):
        self.server.server_close()
        database.database_path().unlink()
        legacy = {"name": "Legacy", "score": 432, "level": 2,
                  "difficulty": "easy", "won": False, "date": "2026-10-15T10:00:00+00:00"}
        self.score_path.write_text(json.dumps([legacy, {"invalid": True}]), encoding="utf-8")
        self.server = leaderboard.start_server(0)
        self.assertEqual(len(json.loads(self.request("/scores/top")[2])), 1)
        self.server.server_close()
        self.server = leaderboard.start_server(0)
        records = json.loads(self.request("/scores/top")[2])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["player"], "Legacy")
        self.assertTrue(self.score_path.exists())

    def test_static_rules_and_openapi_documentation(self):
        for path, content in (("/static/style.css", b"--gold"), ("/static/rules.html", b"Towers"), ("/docs", b"swagger-ui")):
            with self.subTest(path=path):
                status, _headers, body = self.request(path)
                self.assertEqual(status, 200)
                self.assertIn(content, body)
        schema = json.loads(self.request("/openapi.json")[2])
        self.assertIn("post", schema["paths"]["/scores"])
        self.assertIn("/scores/top", schema["paths"])
        self.assertIn("/players/{name}/stats", schema["paths"])

    def test_application_files_and_database_are_not_served(self):
        for path in ("/client/scores.py", "/scores.db", "/scores.json", "/../README.md", "/%2e%2e/README.md", "/static/../client/scores.py"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request("/api/scores", "POST")[0], 405)

    def test_occupied_port_falls_back_to_our_server(self):
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            requested_port = occupied.getsockname()[1]
            fallback = leaderboard.start_server(requested_port)
            try:
                self.assertEqual(fallback.server_address[0], "127.0.0.1")
                self.assertNotEqual(fallback.server_address[1], requested_port)
                connection = http.client.HTTPConnection(*fallback.server_address, timeout=3)
                try:
                    connection.request("GET", "/scores/top")
                    self.assertEqual(connection.getresponse().status, 200)
                finally:
                    connection.close()
                self.assertEqual(fallback.url, f"http://127.0.0.1:{fallback.server_address[1]}/")
            finally:
                fallback.server_close()

    def test_pythonw_without_standard_streams_and_repeated_cleanup(self):
        with patch.object(sys, "stdout", None), patch.object(sys, "stderr", None):
            background = leaderboard.start_server(0)
            background.shutdown()
            background.shutdown()
            background.server_close()
            background.server_close()
        self.assertFalse(background.thread.is_alive())

    def test_invalid_ports_are_rejected(self):
        for port in (-1, 65536, "8000", True):
            with self.subTest(port=port), self.assertRaises(ValueError):
                leaderboard.start_server(port)

    def test_database_startup_failure_is_reported_as_oserror(self):
        with patch.object(database, "initialize_database", side_effect=sqlite3.DatabaseError("corrupt database")):
            with self.assertRaisesRegex(OSError, "database could not be opened"):
                leaderboard.start_server(0)


if __name__ == "__main__":
    unittest.main()
