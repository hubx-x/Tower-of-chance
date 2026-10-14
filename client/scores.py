import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _scores_path():
    folder = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    if not folder:
        folder = Path.home() / "AppData" / "Local" if os.name == "nt" else Path.home() / ".local" / "share"
    return Path(folder) / "TowersOfChance" / "scores.json"


def _clean_score(item):
    if not isinstance(item, dict):
        return None
    name = item.get("name")
    score = item.get("score")
    level = item.get("level")
    difficulty = item.get("difficulty")
    won = item.get("won")
    date = item.get("date")
    if not isinstance(name, str) or not name.strip():
        return None
    if type(score) is not int or not 0 <= score <= 1_000_000_000:
        return None
    if type(level) is not int or not 1 <= level <= 3:
        return None
    if difficulty not in ("easy", "normal", "hard") or type(won) is not bool:
        return None
    if not isinstance(date, str) or len(date) > 40:
        return None
    try:
        datetime.fromisoformat(date)
    except ValueError:
        return None
    return {"name": " ".join(name.split())[:24], "score": score, "level": level,
            "difficulty": difficulty, "won": won, "date": date}


def load_scores():
    try:
        path = _scores_path()
        if path.stat().st_size > 1_000_000:
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return []
    if not isinstance(data, list):
        return []
    scores = [score for item in data if (score := _clean_score(item))]
    return sorted(scores, key=lambda item: item["score"], reverse=True)[:30]


def save_score(name, score, level, difficulty, won):
    record = _clean_score({"name": name, "score": score, "level": level,
                           "difficulty": difficulty, "won": won,
                           "date": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    if record is None:
        return False
    path = _scores_path()
    temporary = path.with_suffix(".tmp")
    try:
        scores = sorted(load_scores() + [record], key=lambda item: item["score"], reverse=True)[:30]
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    except (OSError, ValueError):
        return False
    return True
