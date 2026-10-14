import math

import pygame


# --- Krasa ---
PALETTE = {
    "k": (25, 32, 38), "s": (48, 57, 59), "b": (91, 105, 102),
    "c": (139, 153, 140), "m": (183, 191, 176), "g": (190, 129, 52),
    "y": (255, 214, 93), "w": (233, 250, 244), "r": (169, 49, 43),
    "o": (246, 110, 37), "f": (255, 171, 47), "i": (43, 153, 203),
    "a": (94, 219, 245), "v": (72, 91, 62), "n": (117, 143, 80),
}
PATH_COLORS = {"damage": (244, 117, 108), "speed": (128, 223, 166), "range": (126, 184, 248)}

BASES = {
    "basic": (
        "....................", "....................", "....................",
        "....................", ".......kkkkkk.......", "......kggggggk......",
        ".....kgmmmmmmgk.....", "....kgbbccccbbgk....", "....kgbbccccbbgk....",
        "....kgbbbccbbbgk....", "....kgbbbbbbbbgk....", ".....kgssssssgk.....",
        ".....kkggggggkk.....", "....kcccccccccck....", "...kccbbbccbbbcck...",
        "...kcbbbbccbbbbck...", "..kbbbbbbbbbbbbbbk..", "..kssssssssssssssk..",
        "...kkkkkkkkkkkkkk...", "....................",
    ),
    "ice": (
        "....................", "....................", "....................",
        ".........k..........", "........kak.........", ".......kawik........",
        ".....k.kawik.k......", "....kakawwwikak.....", "...kawikawwikawik...",
        "...kawikawwikawik...", "...kawikawwikawik...", "....kawwwwwwwik.....",
        ".....kiiaaaiik......", "....kkkiiiikkkk.....", "...kccbbbbbbbbcck...",
        "...kcbbccaaccbbck...", "..kbbbbaaaaabbbbbk..", "..kssssssssssssssk..",
        "...kkkkkkkkkkkkkk...", "....................",
    ),
    "fire": (
        "....................", "....................", ".........o..........",
        "........orf.........", "........ofyo........", ".....o..ofyfo.......",
        ".....foofyyfoo......", "....offfyyyfffo.....", "....ofyyywyyffo.....",
        ".....ofyywyffo......", "......ofyyyfo.......", ".....kggggggggk.....",
        "....kgyyyyyyyygk....", "....kgrrrrrrrrgk....", ".....kgrrrrrrgk.....",
        "....kgggrrrrgggk....", "...kgcgggrrgggcgk...", "...kgssssssssssgk...",
        "....kkkkkkkkkkkk....", "....................",
    ),
    "machine": (
        "....................", "....................", "....................",
        "....................", ".......kkkkkk.......", "......knnnnnnk......",
        ".....knccccccnk.....", "....knvvmmmmvvnk....", "....knvvmmmmvvnk....",
        "....knvvmmmmvvnk....", "....knvvvvvvvvnk....", ".....knvvvvvvnk.....",
        "....kkknnnnnnkkk....", "...kskbbbbbbbbksk...", "..ksmkbnnnnnnbkmsk..",
        "..ksmkbvvvvvvbkmsk..", "..ksmkbbbbbbbbkmsk..", "..kssksssssssskssk..",
        "...kkkkkkkkkkkkkk...", "....................",
    ),
}


def make_sprite(rows, palette=PALETTE, scale=3):
    sprite = pygame.Surface((len(rows[0]), len(rows)), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, color in enumerate(row):
            if color != ".":
                sprite.set_at((x, y), palette[color])
    return pygame.transform.scale(sprite, (sprite.get_width() * scale, sprite.get_height() * scale))


class TowerArt:
    def __init__(self):
        self.sprites = {}
        for kind in BASES:
            for level in range(1, 5):
                for direction in range(8):
                    self.sprites[kind, level, direction] = self._tower(kind, level, direction)
        rows = (
            "...kkkk...", "..krrrrk..", ".krmrrmrk.", ".krrrrrrk.",
            ".krwwwwrk.", "..krrrrk..", ".kkrrrrkk.", "ksskkkkssk",
            ".kk....kk.", "..........",
        )
        self.enemies = []
        for body in ((202, 84, 70), (179, 126, 213), (219, 145, 65)):
            palette = dict(PALETTE, r=body)
            self.enemies.append(make_sprite(rows, palette))

    def _tower(self, kind, level, direction):
        sprite = make_sprite(BASES[kind], scale=1)
        tier = level - 1
        if tier:
            armor = PALETTE["g" if level == 4 else "m"]
            pygame.draw.rect(sprite, armor, (5, 14, 2, 3))
            pygame.draw.rect(sprite, armor, (13, 14, 2, 3))
        if kind == "ice" and tier:
            for x in (5, 14):
                pygame.draw.line(sprite, PALETTE["i"], (x, 7 - tier), (x, 12), 3)
                pygame.draw.line(sprite, PALETTE["a"], (x, 7 - tier), (x, 11), 1)
            if level >= 3:
                pygame.draw.line(sprite, PALETTE["a"], (9, 2), (9, 10), 3)
                pygame.draw.line(sprite, PALETTE["w"], (9, 2), (9, 8), 1)
        elif kind == "fire" and tier:
            for x in (6, 13):
                pygame.draw.line(sprite, PALETTE["o"], (x, 8), (x, 5 - tier), 3)
                pygame.draw.line(sprite, PALETTE["y"], (x, 8), (x, 6 - tier), 1)
            if level == 4:
                pygame.draw.rect(sprite, PALETTE["y"], (7, 12, 6, 1))
        if kind in ("basic", "machine"):
            angle = direction * math.pi / 4
            dx, dy = math.cos(angle), math.sin(angle)
            offsets = (-2, 2) if kind == "machine" else (0,)
            for offset in offsets:
                start = (round(10 - dy * offset), round(9 + dx * offset))
                end = (round(start[0] + dx * (7 + (level >= 3))), round(start[1] + dy * (7 + (level >= 3))))
                pygame.draw.line(sprite, PALETTE["k"], start, end, 5 if kind == "basic" else 3)
                pygame.draw.line(sprite, PALETTE["g" if kind == "basic" else "b"], start, end, 3 if kind == "basic" else 1)
                pygame.draw.rect(sprite, PALETTE["k"], (end[0] - 1, end[1] - 1, 3, 3))
            pygame.draw.rect(sprite, PALETTE["y" if level == 4 else "m"], (9, 8, 3, 3))
        if level == 4:
            pygame.draw.line(sprite, PALETTE["y"], (5, 17), (14, 17), 1)
        return pygame.transform.scale(sprite, (60, 60))

    def draw(self, surface, x, y, kind="basic", level=1, path=None, angle=-0.5):
        kind = kind if kind in BASES else "basic"
        level = max(1, min(4, level))
        direction = round(angle / (math.pi / 4)) % 8
        surface.blit(self.sprites[kind, level, direction], (round(x - 30), round(y - 30)))
        if path in PATH_COLORS:
            pygame.draw.rect(surface, PALETTE["k"], (round(x + 15), round(y + 13), 9, 9))
            pygame.draw.rect(surface, PATH_COLORS[path], (round(x + 18), round(y + 16), 3, 3))
        for i in range(level):
            pygame.draw.rect(surface, PALETTE["y"], (round(x - level * 4 + i * 8 + 2), round(y + 31), 4, 3))

    def enemy(self, surface, x, y, variant=0):
        surface.blit(self.enemies[variant % len(self.enemies)], (round(x - 15), round(y - 15)))
