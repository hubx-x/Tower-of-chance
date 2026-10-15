"""Small, local JSON checkpoints for an unfinished game."""

from dataclasses import asdict
import json
import math
import random

from client import scores
from game.model import EFFECTS, MAPS, TOWER_TYPES, Enemy, Game, Impact, Projectile, Tower


VERSION = 1
MAX_SAVE_BYTES = 5_000_000
_COUNTERS = ("level", "wave", "completed_waves", "lives", "coins", "score", "kills",
             "spawned_count", "wave_enemy_count", "_spawn_remaining")
_MULTIPLIERS = ("damage_multiplier", "speed_multiplier", "range_multiplier")


def _progress_path():
    return scores._scores_path().with_name("progress.json")


def _number(value, minimum=-1_000_000_000, maximum=1_000_000_000):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError("Invalid number")
    return value


def _integer(value, minimum=0, maximum=1_000_000_000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid integer")
    return value


def _items(value):
    if not isinstance(value, list) or len(value) > 10_000:
        raise ValueError("Invalid collection")
    return value


def _fields(value, names):
    if not isinstance(value, dict) or set(value) != set(names):
        raise ValueError("Invalid fields")
    return value


def _kind(value):
    if not isinstance(value, str) or value not in TOWER_TYPES:
        raise ValueError("Invalid tower type")
    return value


def _tuples(value):
    return tuple(_tuples(item) for item in value) if isinstance(value, list) else value


def _encode_game(game):
    # A projectile can still be flying towards an enemy that was killed or escaped.
    # Keep a separate object pool so those targets and shared identities survive.
    enemies = list(game.enemies)
    identities = {id(enemy): index for index, enemy in enumerate(enemies)}
    projectiles = []
    for projectile in game.projectiles:
        target_id = identities.get(id(projectile.target))
        if target_id is None:
            target_id = len(enemies)
            identities[id(projectile.target)] = target_id
            enemies.append(projectile.target)
        item = asdict(projectile)
        item["target"] = target_id
        projectiles.append(item)
    return {
        "difficulty": game.difficulty, "map_name": game.map_name, "state": game.state,
        **{key: getattr(game, key) for key in _COUNTERS + _MULTIPLIERS},
        "_spawn_timer": game._spawn_timer, "message": game.message,
        "towers": [asdict(tower) for tower in game.towers],
        "enemy_pool": [asdict(enemy) for enemy in enemies],
        "active_enemies": list(range(len(game.enemies))),
        "projectiles": projectiles,
        "impacts": [asdict(impact) for impact in game.impacts],
        "effects": [EFFECTS.index(effect) for effect in game.effects],
        "rng": game.rng.getstate(),
    }


def _decode_game(data):
    keys = ("difficulty", "map_name", "state", *_COUNTERS, *_MULTIPLIERS,
            "_spawn_timer", "message", "towers", "enemy_pool", "active_enemies",
            "projectiles", "impacts", "effects", "rng")
    _fields(data, keys)
    if data["state"] not in ("build", "wave", "choice"):
        raise ValueError("Only unfinished games can be resumed")
    if not isinstance(data["difficulty"], str) or data["difficulty"] not in ("easy", "normal", "hard"):
        raise ValueError("Invalid difficulty")
    if not isinstance(data["map_name"], str) or data["map_name"] not in MAPS:
        raise ValueError("Invalid map")
    game = Game(data["difficulty"], map_name=data["map_name"])
    game.state = data["state"]
    for key in _COUNTERS:
        setattr(game, key, _integer(data[key]))
    _integer(game.level, 1, 3)
    _integer(game.wave, 1, 3)
    _integer(game.lives, 1, 20)
    if game.completed_waves != game.total_wave - 1:
        raise ValueError("Invalid wave progress")
    for key in ("spawned_count", "wave_enemy_count", "_spawn_remaining"):
        _integer(getattr(game, key), 0, 100)
    if game._spawn_remaining > game.wave_enemy_count:
        raise ValueError("Invalid remaining spawn count")
    for key in _MULTIPLIERS:
        setattr(game, key, _number(data[key], 0.01, 100))
    game._spawn_timer = _number(data["_spawn_timer"], -10_000, 1)
    if game._spawn_remaining and game._spawn_timer < 0:
        raise ValueError("Invalid spawn timer")
    if not isinstance(data["message"], str) or len(data["message"]) > 2000:
        raise ValueError("Invalid message")
    game.message = data["message"]
    for item in _items(data["towers"]):
        _fields(item, Tower.__dataclass_fields__)
        path = item["path"]
        if path is not None and path not in ("damage", "speed", "range"):
            raise ValueError("Invalid upgrade path")
        game.towers.append(Tower(
            _number(item["x"]), _number(item["y"]), path,
            _integer(item["level"], 1, 4), _number(item["cooldown"], 0, 100),
            _kind(item["kind"]), _number(item["angle"]), _integer(item["invested"]),
        ))
    pool = []
    for item in _items(data["enemy_pool"]):
        _fields(item, Enemy.__dataclass_fields__)
        values = {key: _number(value) for key, value in item.items()}
        for key in ("progress", "freeze_timer", "burn_timer", "burn_dps"):
            _number(values[key], 0)
        _number(values["max_hp"], 0.01)
        _number(values["speed"], 0.01)
        pool.append(Enemy(**values))
    active = _items(data["active_enemies"])
    for index in active:
        _integer(index, 0, len(pool) - 1)
    if len(set(active)) != len(active):
        raise ValueError("Duplicate active enemies")
    game.enemies = [pool[index] for index in active]
    for item in _items(data["projectiles"]):
        _fields(item, Projectile.__dataclass_fields__)
        values = {key: _number(value) for key, value in item.items() if key not in ("target", "kind")}
        for key in ("damage", "freeze", "burn_dps", "burn_duration", "speed", "time"):
            _number(values[key], 0)
        values["target"] = pool[_integer(item["target"], 0, len(pool) - 1)]
        values["kind"] = _kind(item["kind"])
        game.projectiles.append(Projectile(**values))
    for item in _items(data["impacts"]):
        _fields(item, Impact.__dataclass_fields__)
        values = {key: _number(value) for key, value in item.items() if key != "kind"}
        _number(values["time"], 0)
        _number(values["duration"], 0.01)
        game.impacts.append(Impact(kind=_kind(item["kind"]), **values))
    game.effects = [EFFECTS[_integer(index, 0, len(EFFECTS) - 1)] for index in _items(data["effects"])]
    if (game.state == "choice" and len(game.effects) != 3) or (game.state != "choice" and game.effects):
        raise ValueError("Invalid chance cards")
    # random.Random validates the state structure and rejects incompatible versions.
    game.rng = random.Random()
    game.rng.setstate(_tuples(data["rng"]))
    return game


def load_progress():
    """Return {name, auto_wave, game}, or None when no valid checkpoint exists."""
    try:
        path = _progress_path()
        if path.stat().st_size > MAX_SAVE_BYTES:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        _fields(data, ("version", "name", "auto_wave", "game"))
        if type(data["version"]) is not int or data["version"] != VERSION:
            return None
        if not isinstance(data["name"], str) or not data["name"].strip() or len(data["name"]) > 24:
            return None
        if type(data["auto_wave"]) is not bool:
            return None
        return {"name": data["name"], "auto_wave": data["auto_wave"], "game": _decode_game(data["game"])}
    except (OSError, ValueError, TypeError, KeyError, IndexError, OverflowError, RecursionError):
        return None


def save_progress(name, game, auto_wave):
    """Atomically replace the checkpoint; failed writes leave the old one intact."""
    temporary = None
    try:
        if not isinstance(name, str) or not name.strip() or type(auto_wave) is not bool:
            return False
        data = {"version": VERSION, "name": " ".join(name.split())[:24],
                "auto_wave": auto_wave, "game": _encode_game(game)}
        _decode_game(data["game"])
        content = json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2)
        if len(content.encode("utf-8")) > MAX_SAVE_BYTES:
            return False
        path = _progress_path()
        temporary = path.with_suffix(".tmp")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
        return True
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, RecursionError):
        return False
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def clear_progress():
    """Remove the checkpoint, including when it is already absent."""
    try:
        _progress_path().unlink(missing_ok=True)
        return True
    except OSError:
        return False
