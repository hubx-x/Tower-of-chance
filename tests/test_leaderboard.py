import http.client
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from client import leaderboard, scores


class LeaderboardTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.score_path = Path(self.folder.name) / "scores.json"
        self.patch = patch.object(scores, "_scores_path", return_value=self.score_path)
        self.patch.start()
        self.server = leaderboard.start_server(0)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.patch.stop()
        self.folder.cleanup()

    def request(self, path, method="GET"):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_home_is_html_and_head_has_no_body(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"TOWERS OF CHANCE", body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        status, head_headers, head_body = self.request("/index.html", "HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(head_body, b"")
        self.assertEqual(int(head_headers["Content-Length"]), len(body))

    def test_scores_are_read_live_and_sorted(self):
        self.assertEqual(json.loads(self.request("/api/scores")[2]), {"scores": []})
        scores.save_score("First", 100, 1, "easy", False)
        scores.save_score("<script>alert(1)</script>", 500, 2, "hard", True)
        status, headers, body = self.request("/api/scores")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        records = json.loads(body)["scores"]
        self.assertEqual([record["score"] for record in records], [500, 100])
        self.assertTrue(records[0]["won"])
        self.assertTrue(records[0]["name"].startswith("<script>"))

    def test_corrupt_scores_do_not_break_server(self):
        self.score_path.write_text("not JSON", encoding="utf-8")
        self.assertEqual(json.loads(self.request("/api/scores")[2]), {"scores": []})

    def test_only_explicit_paths_are_available(self):
        for path in ("/client/scores.py", "/scores.json", "/../README.md", "/%2e%2e/README.md", "/web/index.html"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request("/api/scores", "POST")[0], 501)

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
                    connection.request("GET", "/api/scores")
                    self.assertEqual(connection.getresponse().status, 200)
                finally:
                    connection.close()
                self.assertEqual(fallback.url, f"http://127.0.0.1:{fallback.server_address[1]}/")
            finally:
                fallback.shutdown()
                fallback.server_close()

    def test_invalid_ports_are_rejected(self):
        for port in (-1, 65536, "8765", True):
            with self.subTest(port=port), self.assertRaises(ValueError):
                leaderboard.start_server(port)


if __name__ == "__main__":
    unittest.main()
