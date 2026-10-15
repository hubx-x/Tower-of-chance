import json
from http.client import BadStatusLine
from unittest import TestCase, main
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from client.api_client import MAX_RESPONSE_BYTES, ScoreClient


class ApiClientTests(TestCase):
    def setUp(self):
        self.client = ScoreClient()
        self.run_id = "da49e575-6cc7-47a7-a4c1-d3461d131171"
        self.record = {"name": "Player", "score": 420, "level": 2,
                       "difficulty": "normal", "won": False,
                       "date": "2026-10-15T17:00:00+00:00"}

    def response(self, status, data):
        response = MagicMock()
        response.status = status
        response.read.return_value = json.dumps(data, ensure_ascii=False).encode("utf-8")
        response.__enter__.return_value = response
        return response

    def submit(self, **changes):
        args = {"name": "Player", "score": 420, "level": 2,
                "difficulty": "normal", "won": False, "run_id": self.run_id}
        args.update(changes)
        return self.client.submit_score(**args)

    def test_submission_posts_exact_payload_with_three_second_timeout(self):
        response = self.response(201, {"id": 1, "player": "Spēlētājs", "score": 420})
        with patch("client.api_client.urlopen", return_value=response) as open_request:
            self.assertTrue(self.submit(name="  Spēlētājs  "))
        request = open_request.call_args.args[0]
        self.assertEqual(open_request.call_args.kwargs, {"timeout": 3})
        self.assertEqual(request.full_url, "http://127.0.0.1:8000/scores")
        self.assertEqual(request.get_method(), "POST")
        self.assertIn("application/json", request.get_header("Content-type"))
        self.assertEqual(json.loads(request.data.decode("utf-8")), {
            "player": "Spēlētājs", "score": 420, "level": 2,
            "difficulty": "normal", "won": False, "run_id": self.run_id,
        })
        response.read.assert_called_once_with(MAX_RESPONSE_BYTES + 1)

    def test_existing_run_is_success_and_conflicting_run_is_failure(self):
        with patch("client.api_client.urlopen", return_value=self.response(200, {"id": 1})):
            self.assertTrue(self.submit())
        conflict = HTTPError("http://127.0.0.1:8000/scores", 409, "Conflict", {}, None)
        with patch("client.api_client.urlopen", side_effect=conflict):
            self.assertFalse(self.submit())

    def test_invalid_score_input_is_rejected_without_request(self):
        for changes in ({"name": " "}, {"score": -1}, {"score": True},
                        {"score": "420"}, {"level": 4}, {"difficulty": "unknown"},
                        {"won": "yes"}, {"run_id": []}, {"run_id": ""}):
            with self.subTest(changes=changes), patch("client.api_client.urlopen") as open_request:
                self.assertFalse(self.submit(**changes))
                open_request.assert_not_called()

    def test_offline_timeouts_and_bad_http_do_not_escape_client(self):
        failures = (URLError("Server unavailable"), TimeoutError("Timed out"),
                    OSError("Connection refused"), BadStatusLine("not HTTP"),
                    HTTPError("http://127.0.0.1:8000/scores", 500, "Failed", {}, None))
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), patch("client.api_client.urlopen", side_effect=failure):
                self.assertFalse(self.submit())
                self.assertEqual(self.client.fetch_scores(), [])
                self.assertIsNone(self.client.player_stats("Player"))

    def test_malformed_responses_do_not_escape_client(self):
        for raw in (b"not JSON", b"\xff", b"[", b"x" * (MAX_RESPONSE_BYTES + 1)):
            response = self.response(200, {})
            response.read.return_value = raw
            with self.subTest(prefix=raw[:10]), patch("client.api_client.urlopen", return_value=response):
                self.assertFalse(self.submit())
                self.assertEqual(self.client.fetch_scores(), [])
                self.assertIsNone(self.client.player_stats("Player"))
        for value in (None, [], "unexpected"):
            with self.subTest(value=value), patch("client.api_client.urlopen", return_value=self.response(200, value)):
                self.assertFalse(self.submit())
                self.assertEqual(self.client.fetch_scores(), [])
                self.assertIsNone(self.client.player_stats("Player"))

    def test_fetch_scores_cleans_records_and_uses_actual_server_url(self):
        self.client = ScoreClient("http://127.0.0.1:54321")
        better = dict(self.record, name="Winner", score=600, won=True)
        data = {"scores": [None, self.record, {"name": "Broken"}, better]}
        with patch("client.api_client.urlopen", return_value=self.response(200, data)) as open_request:
            self.assertEqual(self.client.fetch_scores(), [better, self.record])
        self.assertEqual(open_request.call_args.args[0].full_url, "http://127.0.0.1:54321/api/scores")
        self.assertEqual(open_request.call_args.args[0].get_method(), "GET")
        self.assertEqual(open_request.call_args.kwargs, {"timeout": 3})
        for data in ({}, {"scores": None}, {"scores": {}}, {"scores": "bad"}):
            with patch("client.api_client.urlopen", return_value=self.response(200, data)):
                self.assertEqual(self.client.fetch_scores(), [])

    def test_stats_escape_player_name_and_handle_missing_player(self):
        stats = {"player": "A/B ?", "games_played": 2, "best_score": 420,
                 "average_score": 300, "total_score": 600, "wins": 1}
        with patch("client.api_client.urlopen", return_value=self.response(200, stats)) as open_request:
            self.assertEqual(self.client.player_stats("A/B ?"), stats)
        self.assertEqual(open_request.call_args.args[0].full_url,
                         "http://127.0.0.1:8000/players/A%2FB%20%3F/stats")
        absent = HTTPError("http://127.0.0.1:8000/players/Missing/stats", 404, "Not found", {}, None)
        with patch("client.api_client.urlopen", side_effect=absent):
            self.assertIsNone(self.client.player_stats("Missing"))

    def test_invalid_server_configuration_is_treated_as_unavailable(self):
        for address in (None, "", "not-a-url", "file:///scores", "http://127.0.0.1:8000/?bad=1"):
            client = ScoreClient(address)
            with self.subTest(address=address), patch("client.api_client.urlopen") as open_request:
                self.assertFalse(client.submit_score("Player", 420, 2, "normal", False, self.run_id))
                self.assertEqual(client.fetch_scores(), [])
                self.assertIsNone(client.player_stats("Player"))
                open_request.assert_not_called()


if __name__ == "__main__":
    main()
