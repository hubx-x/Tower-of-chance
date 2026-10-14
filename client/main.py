import math
import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from client.scores import load_scores, save_score
from client.art import TowerArt
from client.effects import draw_projectile, draw_impact, draw_status
from game.model import Game, MAPS, ROAD_WIDTH, TOWER_TYPES


SIZE = (1180, 780)
# --- Krasa ---
INK = (22, 28, 33)
PANEL = (33, 43, 43)
TEXT = (241, 232, 198)
MUTED = (185, 199, 176)
GOLD = (240, 190, 79)
GREEN = (123, 188, 113)
RED = (223, 112, 88)
PATH_COLORS = {None: GOLD, "damage": RED, "speed": GREEN, "range": (127, 174, 231)}
TOWER_COLORS = {"basic": GOLD, "ice": (128, 213, 240), "fire": RED, "machine": GREEN}
# --- Vilnu pauze ---
AUTO_DELAY = 3.0
NAME_BOX = pygame.Rect(90, 273, 430, 48)
MAP_DESCRIPTIONS = {
    "meadow": "A winding trail through green fields.",
    "desert": "Long bends across the desert sands.",
    "tundra": "A zigzag road through the frozen valley.",
}


class App:
    def __init__(self):
        pygame.init()
        info = pygame.display.Info()
        scale = min(1, (info.current_w - 60) / SIZE[0], (info.current_h - 100) / SIZE[1])
        window_size = (int(SIZE[0] * scale), int(SIZE[1] * scale))
        self.window = pygame.display.set_mode(window_size, pygame.RESIZABLE)
        pygame.display.set_caption("Towers of Chance")
        self.screen = pygame.Surface(SIZE)
        self.clock = pygame.time.Clock()
        font = Path(__file__).resolve().parents[1] / "assets" / "VT323-Regular.ttf"
        self.fonts = {
            size: (pygame.font.Font(str(font), size + 6) if size >= 36
                   else pygame.font.SysFont("arial", 18 if size == 16 else max(20, size),
                                            bold=size == 16))
            for size in (16, 18, 20, 24, 28, 36, 54, 68)
        }
        self.art = TowerArt()
        self.page = "menu"
        self.name = ""
        self.difficulty = "normal"
        self.map_name = "meadow"
        self.build_kind = "basic"
        self.typing = False
        self.game = None
        self.selected = None
        self.building = False
        self.merging = False
        self.paused = False
        self.auto_wave = False
        self.auto_timer = AUTO_DELAY
        self.fx_time = 0
        self.saved = False
        self.save_ok = True
        self.scores = load_scores()
        self.buttons = []
        self.mouse = (0, 0)
        self.running = True
        self.draw()

    def text(self, value, pos, size=20, color=TEXT, center=False, width=None):
        value = str(value)
        if width and self.fonts[size].size(value)[0] > width:
            while value and self.fonts[size].size(value + "...")[0] > width:
                value = value[:-1]
            value += "..."
        image = self.fonts[size].render(value, size < 36, color)
        rect = image.get_rect(center=pos) if center else image.get_rect(topleft=pos)
        self.screen.blit(image, rect)

    def wrapped(self, value, pos, width, size=18, color=MUTED):
        words = value.split()
        line = ""
        y = pos[1]
        for word in words:
            next_line = (line + " " + word).strip()
            if self.fonts[size].size(next_line)[0] > width and line:
                self.text(line, (pos[0], y), size, color)
                y += size + 8
                line = word
            else:
                line = next_line
        if line:
            self.text(line, (pos[0], y), size, color)
        return y + size + 8

    def button(self, rect, label, action, active=False, enabled=True, color=GOLD):
        rect = pygame.Rect(rect)
        hover = rect.collidepoint(self.mouse)
        fill = color if active else ((48, 62, 61) if hover and enabled else (35, 47, 47))
        pygame.draw.rect(self.screen, INK, rect.move(3, 4))
        pygame.draw.rect(self.screen, fill, rect)
        if enabled:
            border = color if active or hover else (85, 105, 82)
            pygame.draw.rect(self.screen, border, rect, 2)
            self.buttons.append((rect, action))
        label_color = INK if active else (TEXT if enabled else (131, 144, 129))
        if isinstance(label, tuple):
            self.text(label[0], (rect.centerx, rect.centery - 11), 18, label_color, True)
            self.text(label[1], (rect.centerx, rect.centery + 12), 18, label_color, True)
        else:
            self.text(label, rect.center, 18, label_color, True)

    def start_game(self):
        self.name = " ".join(self.name.split()) or "Player"
        self.game = Game(self.difficulty, map_name=self.map_name)
        self.page = "game"
        self.selected = None
        self.building = True
        self.build_kind = "basic"
        self.merging = False
        self.paused = False
        self.auto_timer = AUTO_DELAY
        self.fx_time = 0
        self.saved = False
        self.typing = False

    def menu(self):
        self.page = "menu"
        self.paused = False
        self.scores = load_scores()

    def set_difficulty(self, value):
        self.difficulty = value

    def set_map(self, value):
        self.map_name = value

    def choose_tower(self, kind):
        self.building = not (self.building and self.build_kind == kind)
        self.build_kind = kind
        self.selected = None
        self.merging = False
        self.game.message = TOWER_TYPES[kind]["description"]

    def toggle_auto(self):
        self.auto_wave = not self.auto_wave
        self.auto_timer = AUTO_DELAY

    def sell_selected(self):
        if self.game.sell_tower(self.selected):
            self.cancel()

    def start_wave(self):
        if self.game.start_wave():
            self.auto_timer = AUTO_DELAY
            self.building = False
            self.merging = False

    def choose_effect(self, index):
        self.game.choose_effect(index)
        self.auto_timer = AUTO_DELAY
        self.cancel()

    def show_page(self, page):
        self.page = page
        self.typing = False

    def cancel(self):
        self.building = False
        self.merging = False
        self.selected = None

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            w, h = self.window.get_size()
            self.mouse = (int(event.pos[0] * SIZE[0] / w), int(event.pos[1] * SIZE[1] / h))
            self.draw()
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.TEXTINPUT and self.typing and self.page == "menu":
            self.name = (self.name + "".join(c for c in event.text if c.isprintable()))[:24]
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.menu()
            elif self.page == "menu":
                if self.typing and event.key == pygame.K_BACKSPACE:
                    self.name = self.name[:-1]
                elif event.key == pygame.K_RETURN:
                    self.start_game()
            elif self.page == "game" and self.game.state not in ("win", "lose"):
                if event.key == pygame.K_p:
                    self.paused = not self.paused
                elif not self.paused and event.key == pygame.K_SPACE:
                    self.start_wave()
                elif not self.paused and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    if self.game.state == "choice":
                        self.choose_effect(event.key - pygame.K_1)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3:
                self.cancel()
                return
            if event.button != 1:
                return
            self.typing = self.page == "menu" and NAME_BOX.collidepoint(self.mouse)
            for rect, action in self.buttons:
                if rect.collidepoint(self.mouse):
                    action()
                    return
            if self.page != "game" or self.paused or self.game.state in ("choice", "win", "lose"):
                return
            if self.mouse[0] >= 860 or not 130 <= self.mouse[1] <= 710:
                return
            tower = next((t for t in self.game.towers
                          if pygame.Rect(t.x - 30, t.y - 36, 60, 70).collidepoint(self.mouse)), None)
            if tower and self.merging:
                if self.game.merge_towers(self.selected, tower):
                    self.merging = False
                return
            if tower:
                self.selected = tower
                self.building = False
            elif self.building:
                self.game.place_tower(*self.mouse, self.build_kind)
            else:
                self.selected = None
                self.merging = False

    def tower(self, x, y, level=1, path=None, angle=-0.5, kind="basic"):
        self.art.draw(self.screen, x, y, kind, level, path, angle)

    def terrain(self):
        map_name = self.game.map_name if self.page == "game" else self.map_name
        path = MAPS[map_name]["path"]
        palettes = {
            "meadow": ((66, 103, 62), (63, 99, 58), (90, 131, 68),
                       (46, 65, 38), (159, 124, 77), (191, 155, 102)),
            "desert": ((174, 141, 85), (180, 147, 88), (207, 171, 105),
                       (106, 85, 55), (124, 91, 58), (151, 115, 71)),
            "tundra": ((159, 190, 190), (151, 180, 181), (210, 228, 221),
                       (77, 96, 110), (105, 130, 141), (128, 154, 165)),
        }
        grass, alternate, detail, edge, road, center = palettes[map_name]
        for row, y in enumerate(range(130, 710, 20)):
            for col, x in enumerate(range(20, 860, 20)):
                pygame.draw.rect(self.screen, grass if (row + col) % 2 else alternate,
                                 (x, y, 20, 20))
                if (col * 7 + row * 13) % 11 == 0:
                    pygame.draw.rect(self.screen, detail, (x + 5, y + 7, 3, 6))
                    pygame.draw.rect(self.screen, detail, (x + 8, y + 10, 3, 3))
        for width, color in ((ROAD_WIDTH + 12, edge), (ROAD_WIDTH, road),
                             (ROAD_WIDTH - 12, center)):
            pygame.draw.lines(self.screen, color, False, path, width)
            for x, y in path:
                pygame.draw.rect(self.screen, color,
                                 (x - width // 2, y - width // 2, width, width))
        for start, end in zip(path, path[1:]):
            length = int(math.dist(start, end))
            for step in range(15, length, 30):
                x = int(start[0] + (end[0] - start[0]) * step / length)
                y = int(start[1] + (end[1] - start[1]) * step / length)
                pygame.draw.rect(self.screen, road, (x - 6, y - 5, 9, 3))
        x, y = path[0]
        pygame.draw.polygon(self.screen, RED, [(x - 6, y - 9), (x + 9, y), (x - 6, y + 9)])
        x, y = path[-1]
        pygame.draw.rect(self.screen, (33, 48, 36), (x - 27, y - 35, 54, 60))
        pygame.draw.rect(self.screen, (179, 168, 122), (x - 21, y - 26, 42, 48))
        pygame.draw.rect(self.screen, (219, 206, 152), (x - 21, y - 26, 42, 12))
        pygame.draw.rect(self.screen, (81, 72, 50), (x - 9, y - 2, 15, 24))
        for offset in (-18, -5, 8):
            pygame.draw.rect(self.screen, (219, 206, 152), (x + offset, y - 35, 9, 12))

    def draw_menu(self):
        self.terrain()
        for x, y, kind, level in ((575, 310, "basic", 3), (680, 475, "ice", 3),
                                 (570, 615, "fire", 4), (735, 605, "machine", 4)):
            self.tower(x, y, level, kind=kind)
        shade = pygame.Surface(SIZE, pygame.SRCALPHA)
        shade.fill((12, 21, 22, 130))
        self.screen.blit(shade, (0, 0))
        pygame.draw.rect(self.screen, INK, (60, 65, 505, 650))
        pygame.draw.rect(self.screen, (82, 105, 74), (60, 65, 505, 650), 3)
        self.text("2D TOWER DEFENSE", (90, 88), 16, GREEN)
        self.text("TOWERS", (86, 120), 54)
        self.text("OF CHANCE", (88, 177), 54, GOLD)
        self.text("PLAYER NAME", (90, 245), 16, MUTED)
        pygame.draw.rect(self.screen, PANEL, NAME_BOX)
        pygame.draw.rect(self.screen, GOLD if self.typing else (85, 105, 82), NAME_BOX, 2)
        self.text(self.name or "Click to enter your name", (105, 283), 20,
                  TEXT if self.name else MUTED, width=400)
        self.text("DIFFICULTY", (90, 340), 16, MUTED)
        for i, value in enumerate(("easy", "normal", "hard")):
            self.button((90 + i * 147, 369, 136, 43), value.title(),
                        lambda d=value: self.set_difficulty(d), self.difficulty == value)
        self.text("MAP", (90, 430), 16, MUTED)
        for i, (key, info) in enumerate(MAPS.items()):
            self.button((90 + i * 147, 456, 136, 44), info["name"],
                        lambda m=key: self.set_map(m), self.map_name == key)
        self.text(MAP_DESCRIPTIONS[self.map_name], (90, 517), 18, MUTED)
        self.button((90, 565, 430, 50), "PLAY  /  ENTER", self.start_game, True)
        self.button((90, 629, 209, 43), "Records", lambda: self.show_page("records"))
        self.button((311, 629, 209, 43), "How to play", lambda: self.show_page("help"))
        self.text("3 levels  /  9 waves  /  4 tower types", (90, 687), 16, MUTED)
        self.text("YOUR DEFENSE", (735, 285), 16, GOLD)
        self.wrapped("Pick a map, build your towers and clear nine waves. Every tower has three upgrade paths.",
                     (735, 322), 355, 24, TEXT)
        name = " ".join(self.name.split()).casefold()
        best = max((r["score"] for r in self.scores
                    if r["difficulty"] == self.difficulty and r["name"].casefold() == name),
                   default=0)
        self.text(f"Personal best: {best}", (735, 548), 20, GREEN)
        self.button((735, 610, 355, 43), f"Auto wave: {'ON' if self.auto_wave else 'OFF'}",
                    self.toggle_auto, self.auto_wave, color=GREEN)

    def draw_game(self):
        game = self.game
        self.text("TOWERS OF CHANCE", (25, 24), 28, GOLD)
        self.text(f"{self.name} / {game.difficulty.title()} / {MAPS[game.map_name]['name']}",
                  (25, 65), 18, MUTED, width=385)
        base_color = GREEN if game.lives > 10 else (GOLD if game.lives > 5 else RED)
        for x, label, value, color in ((430, "BASE", f"{game.lives}/20", base_color), (560, "COINS", game.coins, GOLD), (700, "SCORE", game.score, GREEN)):
            self.text(label, (x, 28), 16, MUTED)
            self.text(value, (x, 53), 28, color)
        pygame.draw.rect(self.screen, PANEL, (430, 96, 102, 5))
        pygame.draw.rect(self.screen, base_color, (430, 96, int(102 * game.lives / 20), 5))
        self.terrain()
        self.screen.set_clip(pygame.Rect(20, 130, 840, 580))
        if self.selected in game.towers:
            radius = int(game.tower_stats(self.selected)["range"])
            overlay = pygame.Surface((840, 580), pygame.SRCALPHA)
            center = (int(self.selected.x - 20), int(self.selected.y - 130))
            pygame.draw.circle(overlay, (*PATH_COLORS[self.selected.path], 25), center, radius)
            pygame.draw.circle(overlay, (*PATH_COLORS[self.selected.path], 90), center, radius, 1)
            self.screen.blit(overlay, (20, 130))
        for tower in game.towers:
            self.tower(tower.x, tower.y, tower.level, tower.path, tower.angle, tower.kind)
            if tower is self.selected:
                pygame.draw.rect(self.screen, TEXT, (tower.x - 32, tower.y - 34, 64, 70), 1)
            if (self.merging and self.selected in game.towers and tower is not self.selected
                    and tower.level == 3 and tower.path == self.selected.path
                    and tower.kind == self.selected.kind):
                pygame.draw.rect(self.screen, GOLD, (tower.x - 32, tower.y - 34, 64, 70), 2)
        for enemy in game.enemies:
            pos = (round(enemy.x), round(enemy.y))
            bob = 3 if not enemy.freeze_timer and int(enemy.progress / 12) % 2 else 0
            self.art.enemy(self.screen, pos[0], pos[1] - bob, game.level - 1)
            draw_status(self.screen, enemy, self.fx_time)
            health = max(0, enemy.hp) / enemy.max_hp
            color = GREEN if health > 0.5 else (GOLD if health > 0.25 else RED)
            pygame.draw.rect(self.screen, INK, (pos[0] - 17, pos[1] - 33, 34, 6))
            pygame.draw.rect(self.screen, color, (pos[0] - 16, pos[1] - 32, int(32 * health), 4))
        for projectile in game.projectiles:
            draw_projectile(self.screen, projectile)
        for impact in game.impacts:
            draw_impact(self.screen, impact)
        if self.building and game.state in ("build", "wave") and 20 < self.mouse[0] < 860 and 130 < self.mouse[1] < 710:
            old_message = game.message
            valid = game.can_place(*self.mouse) and game.coins >= TOWER_TYPES[self.build_kind]["cost"]
            game.message = old_message
            self.tower(*self.mouse, kind=self.build_kind)
            pygame.draw.rect(self.screen, GREEN if valid else RED,
                             (self.mouse[0] - 32, self.mouse[1] - 34, 64, 70), 2)
            pygame.draw.line(self.screen, GREEN if valid else RED, (self.mouse[0] - 7, self.mouse[1]), (self.mouse[0] + 7, self.mouse[1]), 2)
        self.screen.set_clip(None)
        self.draw_sidebar()
        self.wrapped(game.message, (25, 725), 820, 18)
        if game.state == "choice":
            self.draw_choices()
        elif game.state in ("win", "lose"):
            self.draw_result()
        if self.paused:
            self.veil()
            self.text("PAUSED", (590, 306), 54, GOLD, True)
            self.text("Take your time. The base can wait.", (590, 376), 20, TEXT, True)
            self.button((430, 421, 320, 50), "Resume  /  P", lambda: setattr(self, "paused", False), True)
            self.button((430, 487, 320, 46), "Main menu", self.menu)

    def draw_sidebar(self):
        game = self.game
        pygame.draw.rect(self.screen, PANEL, (880, 0, 300, 780))
        self.text(f"LEVEL {game.level} / 3", (902, 25), 24, GOLD)
        self.text(f"Wave {game.total_wave} / 9", (902, 64), 20)
        for i in range(9):
            pygame.draw.rect(self.screen, GREEN if i < game.completed_waves else (63, 80, 73),
                             (902 + i * 28, 101, 21, 6))
        count, hp, _ = game.wave_stats()
        status = f"{game.remaining_enemies} enemies remaining" if game.state == "wave" else f"Next: {count} enemies, {hp:g} HP"
        self.text(status, (902, 127), 18, MUTED)
        usable = game.state in ("build", "wave") and not self.paused
        for i, (kind, info) in enumerate(TOWER_TYPES.items()):
            self.button((902 + (i % 2) * 134, 173 + (i // 2) * 62, 122, 52),
                        (info["name"], f"{info['cost']} coins"),
                        lambda k=kind: self.choose_tower(k),
                        self.building and self.build_kind == kind,
                        usable and game.coins >= info["cost"], TOWER_COLORS[kind])
        tower = self.selected
        if tower in game.towers:
            info = TOWER_TYPES[tower.kind]
            self.text(f"{info['name'].upper()} / LV {tower.level}", (902, 318), 20,
                      TOWER_COLORS[tower.kind])
            self.text(f"{tower.path.title()} path" if tower.path else "Choose an upgrade below",
                      (902, 353), 18, TEXT)
            stats = game.tower_stats(tower)
            self.text(f"Dmg {stats['damage']:g}", (902, 386), 18, MUTED)
            self.text(f"Range {stats['range']:.0f}", (1036, 386), 18, MUTED)
            self.text(f"Rate {1 / stats['delay']:.1f}/s", (902, 414), 18, MUTED)
            if tower.kind == "ice":
                self.text(f"Freeze {stats['freeze']:.1f}s", (1036, 414), 18, TOWER_COLORS["ice"])
            elif tower.kind == "fire":
                self.text(f"Burn {stats['burn_dps']:.1f}/s", (1036, 414), 18, TOWER_COLORS["fire"])
            cost = game.upgrade_cost(tower)
            if tower.path is None:
                for i, path in enumerate(("damage", "speed", "range")):
                    self.button((902, 449 + i * 42, 256, 36), f"{path.title()} +  /  {cost} coins",
                                lambda p=path: game.upgrade_tower(tower, p),
                                enabled=usable and game.coins >= cost, color=PATH_COLORS[path])
            elif tower.level < 3:
                self.button((902, 449, 256, 44), f"Upgrade to LV {tower.level + 1} / {cost}",
                            lambda: game.upgrade_tower(tower), enabled=usable and game.coins >= cost)
            elif tower.level == 3:
                label = "Click a matching tower" if self.merging else "Merge into LV 4"
                self.button((902, 449, 256, 44), label,
                            lambda: setattr(self, "merging", not self.merging),
                            active=self.merging, enabled=usable)
                self.wrapped("Pick a LV 3 tower of the same type and path.",
                             (902, 508), 250, 18)
            else:
                self.text("MAX LEVEL", (902, 460), 20, GREEN)
            self.button((902, 579, 256, 34), f"Sell / {game.sell_value(tower)} coins",
                        self.sell_selected, enabled=usable, color=RED)
        else:
            info = TOWER_TYPES[self.build_kind]
            self.text(info["name"].upper(), (902, 321), 24, TOWER_COLORS[self.build_kind])
            self.wrapped(info["description"], (902, 361), 250, 18, TEXT)
            self.text("UPGRADES", (902, 455), 16, GOLD)
            self.wrapped("Click a tower on the map to improve its damage, speed or range. All four types can reach level 4.",
                         (902, 489), 250, 18)
        self.button((902, 625, 256, 32), f"Auto wave: {'ON' if self.auto_wave else 'OFF'}",
                    self.toggle_auto, self.auto_wave, not self.paused and game.state not in ("win", "lose"), GREEN)
        start_label = "Start wave / SPACE"
        if self.auto_wave and game.state == "build" and game.towers:
            start_label = f"Start now / {math.ceil(self.auto_timer)}s"
        elif game.state == "wave":
            start_label = "Wave in progress"
        self.button((902, 666, 256, 43), start_label, self.start_wave,
                    game.state == "build", game.state == "build" and not self.paused)
        self.button((902, 716, 122, 38), "Pause / P", lambda: setattr(self, "paused", True),
                    enabled=game.state not in ("win", "lose") and not self.paused)
        self.button((1036, 716, 122, 38), "Menu / ESC", self.menu, enabled=not self.paused)

    def veil(self):
        shade = pygame.Surface(SIZE, pygame.SRCALPHA)
        shade.fill((10, 18, 20, 225))
        self.screen.blit(shade, (0, 0))
        self.buttons = []

    def draw_choices(self):
        self.veil()
        self.text("A TURN OF CHANCE", (590, 188), 36, GOLD, True)
        self.text("Wave cleared. Choose exactly one effect for this run.", (590, 247), 20, TEXT, True)
        for i, effect in enumerate(self.game.effects):
            x = 115 + i * 323
            rect = pygame.Rect(x, 305, 300, 285)
            pygame.draw.rect(self.screen, PANEL, rect)
            pygame.draw.rect(self.screen, (85, 105, 82), rect, 3)
            self.text(f"0{i + 1}", (x + 23, 325), 36, GREEN)
            self.text(effect.title, (x + 23, 389), 24, GOLD)
            self.wrapped(effect.description, (x + 23, 435), 255, 18, TEXT)
            self.button((x + 23, 524, 254, 43), f"Choose  /  {i + 1}", lambda index=i: self.choose_effect(index))
        self.text("Effects stack and also apply to towers you build later.", (590, 636), 18, MUTED, True)

    def draw_result(self):
        self.veil()
        won = self.game.state == "win"
        color = GOLD if won else RED
        self.text("VICTORY" if won else "BASE LOST", (590, 208), 68, color, True)
        self.text("All nine waves cleared. You beat the odds." if won else "A new plan. A new chance. Try again.", (590, 299), 20, TEXT, True)
        for x, label, value in ((390, "FINAL SCORE", self.game.score), (590, "WAVES CLEARED", f"{self.game.completed_waves}/9"), (790, "BASE LIVES", self.game.lives)):
            self.text(label, (x, 369), 16, MUTED, True)
            self.text(value, (x, 416), 36, GREEN, True)
        self.text("Record saved locally." if self.save_ok else "Could not save the record. Check folder permissions.", (590, 476), 18, MUTED if self.save_ok else RED, True)
        self.button((355, 531, 220, 50), "Play again", self.start_game, True)
        self.button((605, 531, 220, 50), "Main menu", self.menu)

    def draw_records(self):
        self.text("LOCAL RECORDS", (90, 60), 36, GOLD)
        self.text("Your best runs, saved on this computer.", (90, 117), 20, MUTED)
        for i, difficulty in enumerate(("easy", "normal", "hard")):
            self.button((90 + i * 147, 167, 136, 43), difficulty.title(), lambda d=difficulty: self.set_difficulty(d), self.difficulty == difficulty)
        for x, label in ((90, "RANK"), (192, "PLAYER"), (560, "SCORE"), (705, "LEVEL"), (843, "RESULT")):
            self.text(label, (x, 246), 16, MUTED)
        records = [r for r in self.scores if r["difficulty"] == self.difficulty][:10]
        for i, row in enumerate(records):
            y = 289 + i * 34
            pygame.draw.line(self.screen, (41, 56, 51), (90, y + 30), (1080, y + 30))
            for x, value in ((90, f"{i + 1:02}"), (192, row["name"]), (560, row["score"]), (705, row["level"]), (843, "Victory" if row["won"] else "Defeat")):
                self.text(value, (x, y), 18, GREEN if row["won"] else TEXT,
                          width=340 if x == 192 else None)
        if not records:
            self.text("Finish a game to set the first record.", (90, 301), 20, MUTED)
        self.button((90, 692, 240, 45), "Back to menu", self.menu)

    def draw_help(self):
        self.text("HOW TO PLAY", (90, 55), 36, GOLD)
        rows = (
            ("DEFEND", "Pick a map and survive 9 waves. Each escaping enemy takes one of your 20 base lives."),
            ("FOUR TOWERS", "Basic: 50 coins. Ice freezes, Fire burns, Machine gun fires rapidly. Pick one, then click empty ground."),
            ("UPGRADE", "Click any placed tower. Choose damage, speed or range, then upgrade that path to level 3."),
            ("MERGE", "Merge two level 3 towers of the same type and path to create one level 4 tower."),
            ("CHANCE CARDS", "Easy/Normal: waves 1, 4, 7. Hard: 1, 6. Pick one of three cards; it lasts the whole game."),
            ("AUTO & SELL", "Auto wave waits 3 seconds, then starts the next wave. Sell returns half the tower's purchase and upgrade costs."),
        )
        y = 125
        for title, description in rows:
            self.text(title, (90, y), 18, GREEN)
            y = self.wrapped(description, (90, y + 29), 985, 18, TEXT) + 16
        self.text("Left click: select   /   Right click: cancel   /   SPACE: wave   /   P: pause   /   ESC: menu",
                  (90, 655), 18, MUTED)
        self.button((90, 699, 240, 45), "Back to menu", self.menu)

    def draw(self):
        self.screen.fill(INK)
        self.buttons = []
        if self.page == "menu":
            self.draw_menu()
        elif self.page == "game":
            self.draw_game()
        elif self.page == "records":
            self.draw_records()
        else:
            self.draw_help()
        self.window.blit(pygame.transform.smoothscale(self.screen, self.window.get_size()), (0, 0))
        pygame.display.flip()

    def update(self, dt):
        if self.page != "game" or self.paused:
            return
        dt = max(0, min(0.25, dt))
        self.fx_time += dt
        previous = self.game.state
        self.game.update(dt)
        if self.game.state == "build" and self.auto_wave and self.game.towers:
            if previous != "build":
                self.auto_timer = AUTO_DELAY
            else:
                self.auto_timer -= dt
                if self.auto_timer <= 0:
                    self.start_wave()
        else:
            self.auto_timer = AUTO_DELAY
        if self.game.state in ("win", "lose") and not self.saved:
            self.save_ok = save_score(self.name, self.game.score, self.game.level,
                                      self.game.difficulty, self.game.state == "win")
            self.saved = True
            self.scores = load_scores()

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000
            x, y = pygame.mouse.get_pos()
            w, h = self.window.get_size()
            self.mouse = (int(x * SIZE[0] / w), int(y * SIZE[1] / h))
            for event in pygame.event.get():
                self.handle(event)
            self.update(dt)
            self.draw()
        pygame.quit()


if __name__ == "__main__":
    App().run()
