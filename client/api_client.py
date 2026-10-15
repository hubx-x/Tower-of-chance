"""The game's small HTTP connection to the local leaderboard server.

Requests time out after three seconds. The app submits once on the result screen
and keeps running if the server is unavailable. This module writes no local data.
"""

from datetime import datetime, timezone
from http.client import HTTPException
import json
from urllib.error import URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from client.scores import _clean_score


SERVER_URL = "http://127.0.0.1:8000/"
REQUEST_TIMEOUT = 3
MAX_RESPONSE_BYTES = 1_000_000


class ScoreClient:
    def __init__(self, base_url=SERVER_URL):
        self.base_url = base_url.rstrip("/") + "/" if isinstance(base_url, str) else ""

    def _request(self, method, path, payload=None):
        try:
            parsed = urlsplit(self.base_url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                return None
            if parsed.query or parsed.fragment:
                return None
            body = None if payload is None else json.dumps(
                payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            headers = {"Accept": "application/json"}
            if body is not None:
                headers["Content-Type"] = "application/json; charset=utf-8"
            request = Request(self.base_url + path, data=body, headers=headers, method=method)
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    return None
                return response.status, json.loads(raw.decode("utf-8"))
        except (OSError, URLError, HTTPException, ValueError, TypeError,
                UnicodeError, OverflowError, RecursionError):
            return None

    def submit_score(self, name, score, level, difficulty, won, run_id):
        """Return True for a created score or an already accepted run ID."""
        record = _clean_score({
            "name": name, "score": score, "level": level,
            "difficulty": difficulty, "won": won,
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        if record is None:
            return False
        if run_id is not None and (not isinstance(run_id, str) or not run_id or len(run_id) > 64):
            return False
        payload = {"player": record["name"], "score": record["score"],
                   "level": record["level"], "difficulty": record["difficulty"],
                   "won": record["won"]}
        if run_id is not None:
            payload["run_id"] = run_id
        result = self._request("POST", "scores", payload)
        return bool(result and result[0] in (200, 201) and isinstance(result[1], dict))

    def fetch_scores(self):
        """Return records in the game's existing format, or [] when offline."""
        result = self._request("GET", "api/scores")
        if not result or result[0] != 200 or not isinstance(result[1], dict):
            return []
        records = result[1].get("scores")
        if not isinstance(records, list):
            return []
        cleaned = [record for item in records if (record := _clean_score(item))]
        return sorted(cleaned, key=lambda item: item["score"], reverse=True)[:30]

    def player_stats(self, name):
        """Return the server's player statistics, or None when unavailable."""
        if not isinstance(name, str) or not name.strip():
            return None
        name = " ".join(name.split())[:24]
        result = self._request("GET", f"players/{quote(name, safe='')}/stats")
        if result and result[0] == 200 and isinstance(result[1], dict):
            return result[1]
        return None
