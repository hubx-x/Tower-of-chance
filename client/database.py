"""SQLite storage owned by the leaderboard server, using one connection per call."""

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
import sqlite3

from client import scores


class RunConflict(ValueError):
    pass


def database_path():
    return scores._scores_path().with_name("scores.db")


def _legacy_records():
    """Read the previous local JSON format without calling the HTTP client."""
    try:
        path = scores._scores_path()
        if path.stat().st_size > 1_000_000:
            return []
        records = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return []
    if not isinstance(records, list):
        return []
    return [clean for record in records if (clean := scores._clean_score(record)) is not None]


def _initialize(connection):
    # A write transaction makes migration safe even during simultaneous requests.
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("""CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player TEXT NOT NULL,
            score INTEGER NOT NULL CHECK (score >= 0 AND score <= 1000000000),
            level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 3),
            difficulty TEXT NOT NULL CHECK (difficulty IN ('easy', 'normal', 'hard')),
            won INTEGER NOT NULL CHECK (won IN (0, 1)),
            date TEXT NOT NULL,
            run_id TEXT UNIQUE
        )""")
        connection.execute("CREATE INDEX IF NOT EXISTS scores_ranking ON scores(score DESC, id DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS scores_player ON scores(player)")
        connection.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        migrated = connection.execute("SELECT value FROM metadata WHERE key = ?", ("legacy_json_migrated",)).fetchone()
        if migrated is None:
            for record in _legacy_records():
                connection.execute(
                    "INSERT INTO scores(player, score, level, difficulty, won, date) VALUES (?, ?, ?, ?, ?, ?)",
                    (record["name"], record["score"], record["level"], record["difficulty"], int(record["won"]), record["date"]),
                )
            connection.execute("INSERT INTO metadata(key, value) VALUES (?, ?)", ("legacy_json_migrated", "1"))


@contextmanager
def _connection():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=5)) as connection:
        connection.row_factory = sqlite3.Row
        _initialize(connection)
        yield connection


def initialize_database():
    with _connection():
        pass
    return database_path()


def _record(row):
    record = dict(row)
    record["won"] = bool(record["won"])
    return record


def add_score(record):
    fields = ("player", "score", "level", "difficulty", "won", "run_id")
    with _connection() as connection:
        with connection:
            if record["run_id"] is not None:
                existing = connection.execute("SELECT * FROM scores WHERE run_id = ?", (record["run_id"],)).fetchone()
                if existing is not None:
                    existing = _record(existing)
                    if any(existing[field] != record[field] for field in fields):
                        raise RunConflict("This run ID already belongs to a different score.")
                    return existing, False
            date = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                cursor = connection.execute(
                    "INSERT INTO scores(player, score, level, difficulty, won, run_id, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    tuple(record[field] for field in fields) + (date,),
                )
            except sqlite3.IntegrityError:
                if record["run_id"] is None:
                    raise
                existing = connection.execute("SELECT * FROM scores WHERE run_id = ?", (record["run_id"],)).fetchone()
                if existing is None:
                    raise
                existing = _record(existing)
                if any(existing[field] != record[field] for field in fields):
                    raise RunConflict("This run ID already belongs to a different score.")
                return existing, False
            saved = connection.execute("SELECT * FROM scores WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return _record(saved), True


def top_scores(limit=30):
    with _connection() as connection:
        rows = connection.execute("SELECT * FROM scores ORDER BY score DESC, id DESC LIMIT ?", (limit,)).fetchall()
        return [_record(row) for row in rows]


def player_stats(player):
    with _connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS games_played, MAX(score) AS best_score, AVG(score) AS average_score, "
            "SUM(score) AS total_score, SUM(won) AS wins FROM scores WHERE player = ?", (player,),
        ).fetchone()
        if not row["games_played"]:
            return None
        stats = dict(row)
        stats["average_score"] = round(stats["average_score"], 2)
        return {"player": player, **stats}
