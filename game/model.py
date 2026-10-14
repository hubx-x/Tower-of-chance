from dataclasses import dataclass
import math
import random


PATH = (
    (40, 220), (210, 220), (210, 395), (490, 395), (490, 205),
    (770, 205), (770, 555), (430, 555), (430, 665), (820, 665),
)
ROAD_WIDTH = 42
TOWER_RADIUS = 26
TOWER_COST = 50
# --- Pardosanas cena ---
SELL_REFUND = 0.5
PATH_LENGTH = sum(math.dist(a, b) for a, b in zip(PATH, PATH[1:]))
MAPS = {
    "meadow": {"name": "Meadow", "path": PATH},
    "desert": {"name": "Desert", "path": (
        (40, 220), (340, 220), (340, 490), (140, 490), (140, 665),
        (610, 665), (610, 365), (800, 365), (800, 560), (720, 560),
        (720, 665), (820, 665),
    )},
    "tundra": {"name": "Tundra", "path": (
        (40, 220), (190, 220), (190, 580), (390, 580), (390, 180),
        (610, 180), (610, 460), (790, 460), (790, 665), (820, 665),
    )},
}
# --- Dmg / atrums / radius ---
TOWER_TYPES = {
    "basic": {"name": "Basic", "cost": 50, "description": "A balanced tower with reliable shots.",
              "damage": 4, "delay": 0.85, "range": 130},
    "ice": {"name": "Ice", "cost": 80, "description": "Briefly freezes enemies with each hit.",
            "damage": 2.2, "delay": 1.05, "range": 135},
    "fire": {"name": "Fire", "cost": 90, "description": "Burns enemies for damage over time.",
             "damage": 2.5, "delay": 0.95, "range": 130},
    "machine": {"name": "Machine gun", "cost": 100, "description": "Rapid shots at a shorter range.",
                "damage": 1.4, "delay": 0.16, "range": 115},
}
# --- Lodes atrums ---
PROJECTILE_SPEED = {"basic": 420, "ice": 330, "fire": 280, "machine": 700}
# --- Lodes laiks ---
PROJECTILE_TTL = 3.0
# --- Ledus / uguns ---
ICE_FREEZE = 0.7
FIRE_DURATION = 2.0
FIRE_BURN_SCALE = 1.2


def path_position(progress, path=PATH):
    progress = max(0, progress)
    for start, end in zip(path, path[1:]):
        length = math.dist(start, end)
        if progress <= length:
            fraction = progress / length
            return (
                start[0] + (end[0] - start[0]) * fraction,
                start[1] + (end[1] - start[1]) * fraction,
            )
        progress -= length
    return path[-1]


def distance_to_path(x, y, path=PATH):
    closest = float("inf")
    for start, end in zip(path, path[1:]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        fraction = ((x - start[0]) * dx + (y - start[1]) * dy) / (dx * dx + dy * dy)
        fraction = max(0, min(1, fraction))
        closest = min(closest, math.hypot(x - start[0] - dx * fraction, y - start[1] - dy * fraction))
    return closest


@dataclass
class Tower:
    x: float
    y: float
    path: str | None = None
    level: int = 1
    cooldown: float = 0
    kind: str = "basic"
    angle: float = -0.5
    invested: int = 0


@dataclass(eq=False)
class Enemy:
    progress: float
    hp: float
    max_hp: float
    speed: float
    x: float = PATH[0][0]
    y: float = PATH[0][1]
    freeze_timer: float = 0
    burn_timer: float = 0
    burn_dps: float = 0


@dataclass
class Projectile:
    x: float
    y: float
    target: Enemy
    kind: str
    damage: float
    freeze: float = 0
    burn_dps: float = 0
    burn_duration: float = 0
    speed: float = 420
    time: float = PROJECTILE_TTL
    target_x: float = 0
    target_y: float = 0
    angle: float = 0


@dataclass
class Impact:
    x: float
    y: float
    kind: str
    time: float = 0.3
    duration: float = 0.3


@dataclass(frozen=True)
class Effect:
    title: str
    description: str
    damage: float = 0
    speed: float = 0
    range: float = 0


EFFECTS = (
    Effect("Sharp shots", "All towers deal 20% more damage.", damage=0.20),
    Effect("Quick hands", "All towers attack 20% faster.", speed=0.20),
    Effect("Long sight", "All towers have 15% more range.", range=0.15),
    Effect("Heavy rounds", "Damage +30%, attack speed -10%.", damage=0.30, speed=-0.10),
    Effect("Rapid fire", "Attack speed +30%, damage -10%.", damage=-0.10, speed=0.30),
    Effect("Eagle eye", "Range +25%, attack speed -10%.", speed=-0.10, range=0.25),
    Effect("Close combat", "Damage +25%, range -10%.", damage=0.25, range=-0.10),
    Effect("Light rounds", "Attack speed +25%, range -10%.", speed=0.25, range=-0.10),
    Effect("Wide coverage", "Range +25%, damage -10%.", damage=-0.10, range=0.25),
    Effect("Worn barrels", "All towers deal 10% less damage.", damage=-0.10),
    Effect("Slow gears", "All towers attack 10% slower.", speed=-0.10),
    Effect("Thick fog", "All towers have 10% less range.", range=-0.10),
)


class Game:
    def __init__(self, difficulty="normal", rng=None, map_name="meadow"):
        if difficulty not in ("easy", "normal", "hard"):
            raise ValueError("Difficulty must be easy, normal or hard.")
        if map_name not in MAPS:
            raise ValueError("Map must be meadow, desert or tundra.")
        self.difficulty = difficulty
        self.map_name = map_name
        self.path = MAPS[map_name]["path"]
        self.path_length = sum(math.dist(a, b) for a, b in zip(self.path, self.path[1:]))
        self.rng = rng if rng is not None else random.Random()
        self.state = "build"
        self.level = 1
        self.wave = 1
        self.completed_waves = 0
        self.lives = 20
        self.coins = {"easy": 180, "normal": 150, "hard": 130}[difficulty]
        self.score = 0
        self.kills = 0
        self.towers = []
        self.enemies = []
        self.effects = []
        self.projectiles = []
        self.impacts = []
        self.message = "Place a tower, then start the first wave."
        self.damage_multiplier = 1.0
        self.speed_multiplier = 1.0
        self.range_multiplier = 1.0
        self.spawned_count = 0
        self.wave_enemy_count = 0
        self._spawn_remaining = 0
        self._spawn_timer = 0

    @property
    def total_wave(self):
        return (self.level - 1) * 3 + self.wave

    @property
    def remaining_enemies(self):
        return self._spawn_remaining + len(self.enemies)

    def path_position(self, progress):
        return path_position(progress, self.path)

    def distance_to_path(self, x, y):
        return distance_to_path(x, y, self.path)

    def can_place(self, x, y):
        if self.state in ("win", "lose"):
            self.message = "The game has ended."
            return False
        if not (60 <= x <= 820 and 150 <= y <= 690):
            self.message = "Place towers inside the map."
            return False
        if self.distance_to_path(x, y) < ROAD_WIDTH / 2 + TOWER_RADIUS + 4:
            self.message = "Towers must stay off the road."
            return False
        if any(math.hypot(t.x - x, t.y - y) < 2 * TOWER_RADIUS + 8 for t in self.towers):
            self.message = "Leave a little space between towers."
            return False
        return True

    def place_tower(self, x, y, kind="basic"):
        if kind not in TOWER_TYPES:
            self.message = "Choose a tower type first."
            return False
        if not self.can_place(x, y):
            return False
        cost = TOWER_TYPES[kind]["cost"]
        if self.coins < cost:
            self.message = f"A {TOWER_TYPES[kind]['name'].lower()} tower costs {cost} coins."
            return False
        self.towers.append(Tower(x, y, kind=kind, invested=cost))
        self.coins -= cost
        self.message = f"{TOWER_TYPES[kind]['name']} tower placed."
        return True

    def upgrade_cost(self, tower):
        return {1: 35, 2: 65}.get(tower.level, 0)

    def sell_value(self, tower):
        invested = tower.invested or TOWER_TYPES[tower.kind]["cost"]
        return int(invested * SELL_REFUND)

    def sell_tower(self, tower):
        if self.state in ("win", "lose"):
            self.message = "The game has ended."
            return False
        if not any(t is tower for t in self.towers):
            self.message = "Select a tower first."
            return False
        refund = self.sell_value(tower)
        self.towers.remove(tower)
        self.coins += refund
        self.message = f"Tower sold for {refund} coins."
        return True

    def upgrade_tower(self, tower, path=None):
        if self.state in ("win", "lose") or tower not in self.towers:
            self.message = "Select a tower first."
            return False
        if tower.level >= 3:
            self.message = "Merge two level 3 towers of the same type and upgrade path."
            return False
        chosen_path = tower.path if tower.path is not None else path
        if chosen_path not in ("damage", "speed", "range"):
            self.message = "Choose damage, speed or range."
            return False
        if tower.path is not None and path is not None and path != tower.path:
            self.message = "A tower keeps its chosen upgrade path."
            return False
        cost = self.upgrade_cost(tower)
        if self.coins < cost:
            self.message = f"This upgrade costs {cost} coins."
            return False
        tower.path = chosen_path
        tower.level += 1
        tower.invested = (tower.invested or TOWER_TYPES[tower.kind]["cost"]) + cost
        self.coins -= cost
        self.message = f"Tower upgraded to level {tower.level}."
        return True

    def merge_towers(self, first, second):
        if self.state in ("win", "lose"):
            self.message = "The game has ended."
            return False
        if first is second or first not in self.towers or second not in self.towers:
            self.message = "Choose two different towers."
            return False
        if first.level != 3 or second.level != 3 or first.path != second.path or first.kind != second.kind:
            self.message = "Both towers need level 3, the same type and the same upgrade path."
            return False
        first.level = 4
        first.cooldown = 0
        first.invested = (
            (first.invested or TOWER_TYPES[first.kind]["cost"])
            + (second.invested or TOWER_TYPES[second.kind]["cost"])
        )
        self.towers.remove(second)
        self.message = "Merged into a level 4 tower!"
        return True

    def tower_stats(self, tower):
        base = TOWER_TYPES[tower.kind]
        damage, delay, radius = base["damage"], base["delay"], base["range"]
        tier = tower.level - 1
        if tower.path == "damage":
            damage *= (1, 1.75, 2.75, 5.75)[tier]
            if tower.level == 4:
                radius *= 1.2
        elif tower.path == "speed":
            damage *= (1, 1.1, 1.2, 1.325)[tier]
            delay *= (1, 0.67, 0.435, 0.2)[tier]
        elif tower.path == "range":
            radius *= (1, 1.35, 1.73, 2.23)[tier]
            damage *= (1, 1.125, 1.25, 2.625)[tier]
        damage *= self.damage_multiplier
        freeze = ICE_FREEZE + tier * 0.25 if tower.kind == "ice" and tower.path == "damage" else ICE_FREEZE
        return {
            "damage": round(damage, 2),
            "delay": delay / self.speed_multiplier,
            "range": radius * self.range_multiplier,
            "freeze": freeze if tower.kind == "ice" else 0,
            "burn_dps": damage * FIRE_BURN_SCALE if tower.kind == "fire" else 0,
            "burn_duration": FIRE_DURATION if tower.kind == "fire" else 0,
        }

    def wave_stats(self):
        count = (5, 8, 12)[self.level - 1]
        hp = (10, 15, 20)[self.level - 1]
        speed = 66 + (self.level - 1) * 7 + (self.wave - 1) * 3
        count_scale, hp_scale, speed_scale = {
            "easy": (0.8, 0.8, 0.85),
            "normal": (1, 1, 1),
            "hard": (1.25, 1.4, 1.25),
        }[self.difficulty]
        return math.ceil(count * count_scale), hp * hp_scale, speed * speed_scale

    def start_wave(self):
        if self.state == "choice":
            self.message = "Choose one chance card before starting the next wave."
            return False
        if self.state != "build":
            self.message = "A wave is already running." if self.state == "wave" else "The game has ended."
            return False
        count, _, _ = self.wave_stats()
        self.wave_enemy_count = count
        self._spawn_remaining = count
        self.spawned_count = 0
        self._spawn_timer = 0
        self.state = "wave"
        self.message = f"Level {self.level}, wave {self.wave}. Defend the base!"
        return True

    def choose_effect(self, index):
        if self.state != "choice" or not isinstance(index, int) or not 0 <= index < len(self.effects):
            self.message = "Choose one of the three chance cards."
            return False
        effect = self.effects[index]
        self.damage_multiplier = max(0.55, min(3, self.damage_multiplier * (1 + effect.damage)))
        self.speed_multiplier = max(0.55, min(3, self.speed_multiplier * (1 + effect.speed)))
        self.range_multiplier = max(0.65, min(1.7, self.range_multiplier * (1 + effect.range)))
        self.effects = []
        self.state = "build"
        self.message = f"{effect.title} applied. Prepare for the next wave."
        return True

    def update(self, dt):
        dt = max(0, min(0.25, dt))
        for impact in self.impacts:
            impact.time -= dt
        self.impacts = [impact for impact in self.impacts if impact.time > 0]
        if self.state != "wave":
            return
        self._spawn_timer -= dt
        _, hp, speed = self.wave_stats()
        interval = {"easy": 0.95, "normal": 0.8, "hard": 0.62}[self.difficulty]
        while self._spawn_remaining and self._spawn_timer <= 0:
            self.enemies.append(Enemy(0, hp, hp, speed))
            self._spawn_remaining -= 1
            self.spawned_count += 1
            self._spawn_timer += interval
        for enemy in self.enemies[:]:
            burn_time = min(dt, enemy.burn_timer)
            enemy.hp -= enemy.burn_dps * burn_time
            enemy.burn_timer = max(0, enemy.burn_timer - dt)
            if enemy.burn_timer == 0:
                enemy.burn_dps = 0
            if enemy.hp <= 0:
                self._kill_enemy(enemy)
                continue
            move_time = max(0, dt - enemy.freeze_timer)
            enemy.freeze_timer = max(0, enemy.freeze_timer - dt)
            enemy.progress += enemy.speed * move_time
            enemy.x, enemy.y = self.path_position(enemy.progress)
            if enemy.progress >= self.path_length:
                self.enemies.remove(enemy)
                self.lives -= 1
                if self.lives <= 0:
                    self.lives = 0
                    self.state = "lose"
                    self.projectiles.clear()
                    self.message = "The base has fallen. Try another strategy!"
                    return
        self._update_projectiles(dt)
        for tower in self.towers:
            tower.cooldown -= dt
            if tower.cooldown > 0:
                continue
            stats = self.tower_stats(tower)
            while tower.cooldown <= 0:
                targets = [e for e in self.enemies if math.hypot(e.x - tower.x, e.y - tower.y) <= stats["range"]]
                if not targets:
                    tower.cooldown = 0
                    break
                target = max(targets, key=lambda enemy: enemy.progress)
                tower.cooldown += stats["delay"]
                tower.angle = math.atan2(target.y - tower.y, target.x - tower.x)
                if tower.kind in ("basic", "machine"):
                    x = tower.x + math.cos(tower.angle) * 21
                    y = tower.y - 3 + math.sin(tower.angle) * 21
                else:
                    x, y = tower.x, tower.y - 12
                self.projectiles.append(Projectile(
                    x, y, target, tower.kind, stats["damage"],
                    stats["freeze"], stats["burn_dps"], stats["burn_duration"],
                    PROJECTILE_SPEED[tower.kind], target_x=target.x, target_y=target.y,
                    angle=tower.angle,
                ))
        if self._spawn_remaining == 0 and not self.enemies:
            self._finish_wave()

    def _update_projectiles(self, dt):
        for projectile in self.projectiles[:]:
            projectile.time -= dt
            if projectile.time <= 0:
                self.projectiles.remove(projectile)
                continue
            target = projectile.target
            alive = target in self.enemies
            if alive:
                projectile.target_x, projectile.target_y = target.x, target.y
            dx, dy = projectile.target_x - projectile.x, projectile.target_y - projectile.y
            distance = math.hypot(dx, dy)
            projectile.angle = math.atan2(dy, dx)
            step = projectile.speed * dt
            if distance > step + 10:
                projectile.x += math.cos(projectile.angle) * step
                projectile.y += math.sin(projectile.angle) * step
                continue
            self.projectiles.remove(projectile)
            self.impacts.append(Impact(projectile.target_x, projectile.target_y, projectile.kind))
            if alive:
                target.hp -= projectile.damage
                target.freeze_timer = max(target.freeze_timer, projectile.freeze)
                target.burn_timer = max(target.burn_timer, projectile.burn_duration)
                target.burn_dps = max(target.burn_dps, projectile.burn_dps)
                if target.hp <= 0:
                    self._kill_enemy(target)

    def _kill_enemy(self, enemy):
        self.enemies.remove(enemy)
        self.kills += 1
        self.score += 10
        self.coins += 10

    def _finish_wave(self):
        self.projectiles.clear()
        self.completed_waves += 1
        self.score += 50
        self.coins += 30
        if self.wave == 3:
            self.score += 100
            self.coins += 40
            if self.level == 3:
                self.state = "win"
                self.message = "All nine waves cleared. The base is safe!"
                return
            self.level += 1
            self.wave = 1
        else:
            self.wave += 1
        chance_interval = 5 if self.difficulty == "hard" else 3
        if (self.completed_waves - 1) % chance_interval == 0:
            self.effects = self.rng.sample(EFFECTS, 3)
            self.state = "choice"
            self.message = "Wave cleared! Choose one chance card."
        else:
            self.state = "build"
            self.message = "Wave cleared! Prepare for the next wave."
