import math

import pygame


# --- Krasa ---
IRON = (35, 41, 47)
STEEL = (111, 122, 128)
ICE = (92, 218, 248)
FROST = (217, 250, 255)
FIRE = (250, 105, 35)
GOLD = (255, 212, 84)
COPPER = (184, 123, 61)
SMOKE = (148, 139, 123)
COLORS = {"basic": STEEL, "ice": ICE, "fire": FIRE, "machine": GOLD}

# --- Efekta izmers ---
PROJECTILE_SIZE = {"basic": 5, "ice": 6, "fire": 6, "machine": 3}
TRAIL_LENGTH = {"basic": 10, "ice": 13, "fire": 11, "machine": 8}
IMPACT_RADIUS = 21
STATUS_RADIUS = 20


def point(x, y):
    return round(x), round(y)


def glow(surface, x, y, color, radius):
    image = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
    center = (radius + 1, radius + 1)
    pygame.draw.circle(image, (*color, 32), center, radius)
    pygame.draw.circle(image, (*color, 55), center, max(1, radius - 3))
    surface.blit(image, (round(x - radius - 1), round(y - radius - 1)))


def draw_projectile(surface, projectile):
    x, y, kind = projectile.x, projectile.y, projectile.kind
    dx, dy = math.cos(projectile.angle), math.sin(projectile.angle)
    radius = PROJECTILE_SIZE[kind]
    color = COLORS[kind]
    for i in range(3, 0, -1):
        distance = TRAIL_LENGTH[kind] * i / 3
        position = point(x - dx * distance, y - dy * distance)
        trail_color = tuple(round(c * (0.72 - i * 0.1)) for c in color)
        pygame.draw.circle(surface, trail_color, position, 1 if i == 3 else 2)
    center = point(x, y)
    if kind == "basic":
        pygame.draw.circle(surface, IRON, center, radius + 1)
        pygame.draw.circle(surface, (67, 76, 83), center, radius - 1)
        pygame.draw.rect(surface, STEEL, (round(x - 3), round(y - 3), 3, 2))
    elif kind == "ice":
        vertices = (point(x + dx * 8, y + dy * 8), point(x - dy * 4, y + dx * 4),
                    point(x - dx * 6, y - dy * 6), point(x + dy * 4, y - dx * 4))
        glow(surface, x, y, ICE, 10)
        pygame.draw.polygon(surface, ICE, vertices)
        pygame.draw.polygon(surface, (36, 129, 177), vertices, 1)
        pygame.draw.line(surface, FROST, vertices[2], vertices[0], 2)
    elif kind == "fire":
        glow(surface, x, y, FIRE, 13)
        pygame.draw.circle(surface, (190, 63, 26), center, radius + 1)
        pygame.draw.circle(surface, FIRE, center, radius)
        pygame.draw.circle(surface, GOLD, point(x + dx, y + dy), radius - 2)
        pygame.draw.rect(surface, (255, 244, 165), (round(x - 1), round(y - 2), 3, 3))
    else:
        back, front = point(x - dx * 4, y - dy * 4), point(x + dx * 3, y + dy * 3)
        pygame.draw.line(surface, COPPER, back, front, radius + 2)
        pygame.draw.line(surface, GOLD, back, front, radius)
        pygame.draw.rect(surface, (255, 240, 166), (front[0] - 1, front[1] - 1, 2, 2))


def draw_impact(surface, impact):
    progress = max(0, min(1, 1 - impact.time / impact.duration))
    radius = 3 + IMPACT_RADIUS * progress
    color = COLORS[impact.kind]
    fade = 1 - progress * 0.55
    faded = tuple(round(c * fade) for c in color)
    for i in range(5):
        angle = i * math.tau / 5 + (0.35 if impact.kind == "ice" else 0)
        x = impact.x + math.cos(angle) * radius
        y = impact.y + math.sin(angle) * radius
        size = max(1, round(4 * (1 - progress)))
        if impact.kind == "ice":
            pygame.draw.line(surface, faded, point(x - size, y), point(x + size, y), 1)
            pygame.draw.line(surface, FROST, point(x, y - size), point(x, y + size), 1)
        elif impact.kind == "fire":
            pygame.draw.rect(surface, faded, (round(x), round(y - progress * 5), size, size))
        else:
            smoke_color = tuple(round(c * fade) for c in SMOKE)
            pygame.draw.circle(surface, smoke_color, point(x, y), size)
    if progress < 0.35:
        pygame.draw.circle(surface, FROST if impact.kind == "ice" else GOLD,
                           point(impact.x, impact.y), max(1, round(5 * (1 - progress * 2))))


def draw_status(surface, enemy, time):
    x, y = enemy.x, enemy.y
    if enemy.freeze_timer > 0:
        radius = STATUS_RADIUS
        image = pygame.Surface((radius * 2 + 1, radius * 2 + 1), pygame.SRCALPHA)
        shell = ((7, 7), (14, 3), (24, 4), (32, 10), (36, 22),
                 (29, 33), (17, 36), (5, 28), (3, 16))
        pygame.draw.polygon(image, (*ICE, 75), shell)
        pygame.draw.polygon(image, (*FROST, 200), shell, 1)
        pygame.draw.polygon(image, (*FROST, 85), ((7, 7), (20, 10), (12, 27), (5, 28)))
        pygame.draw.lines(image, (*FROST, 210), False, ((15, 7), (19, 15), (15, 21), (20, 29)), 1)
        pygame.draw.line(image, (*FROST, 180), (19, 15), (28, 17), 1)
        surface.blit(image, (round(x - radius), round(y - radius)))
        for i, (ox, oy) in enumerate(((-18, -10), (16, -13), (18, 9))):
            color = FROST if (int(time * 5) + i) % 3 else ICE
            pygame.draw.line(surface, color, point(x + ox - 2, y + oy), point(x + ox + 2, y + oy), 1)
            pygame.draw.line(surface, color, point(x + ox, y + oy - 2), point(x + ox, y + oy + 2), 1)
    if enemy.burn_timer > 0:
        image = pygame.Surface((44, 44), pygame.SRCALPHA)
        for i, ox in enumerate((-10, 0, 10)):
            height = 12 + round(3 * math.sin(time * 13 + i * 2))
            cx, base = 22 + ox, 34
            flame = ((cx - 5, base), (cx - 6, base - 7), (cx - 2, base - height),
                     (cx, base - height - 4), (cx + 2, base - 9), (cx + 5, base - 3))
            pygame.draw.polygon(image, (*FIRE, 200), flame)
            pygame.draw.polygon(image, (*GOLD, 220), ((cx - 2, base), (cx, base - height + 4), (cx + 2, base)))
        surface.blit(image, (round(x - 22), round(y - 22)))
        for i in range(3):
            rise = (time * 18 + i * 9) % 27
            pygame.draw.rect(surface, GOLD, (round(x - 13 + i * 12), round(y + 8 - rise), 2, 2))
