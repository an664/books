#!/usr/bin/env python3
"""Генерирует обложку для «Неспящие. Книга первая: Мёртвый час».

Замёрзший дождь (капли висят, как бисер), коридор в дожде — след идущего
человека — и фигура в конце коридора, у фонаря. Сверху название.
"""
import math
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1600, 2560
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"

GLOW = (800, 1830)          # фонарь в конце коридора
VANISH_Y = 1835             # где коридор упирается в фигуру


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_col(c1, c2, t):
    return tuple(int(round(lerp(c1[i], c2[i], t))) for i in range(len(c1)))


def background():
    img = Image.new("RGB", (W, H))
    px = img.load()
    top, mid, bot = (6, 9, 19), (15, 22, 40), (5, 7, 12)
    for y in range(H):
        t = y / (H - 1)
        if t < 0.62:
            c = lerp_col(top, mid, t / 0.62)
        else:
            c = lerp_col(mid, bot, (t - 0.62) / 0.38)
        for x in range(W):
            px[x, y] = c
    return img


def glow_layer():
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    gx, gy = GLOW
    for r, a in [(900, 18), (650, 26), (450, 38), (280, 55), (160, 80), (80, 120)]:
        d.ellipse((gx - r, gy - r * 0.8, gx + r, gy + r * 0.8), fill=(255, 150, 70, a))
    return layer.filter(ImageFilter.GaussianBlur(120))


def corridor_halfwidth(y):
    """Полуширина коридора в дожде на высоте y (перспектива к фонарю)."""
    if y < VANISH_Y - 40:
        return 0
    t = (y - VANISH_Y) / (H - VANISH_Y)
    t = max(0.0, min(1.0, t))
    return lerp(26, 210, t ** 0.9)


def in_corridor(x, y):
    hw = corridor_halfwidth(y)
    return hw > 0 and abs(x - GLOW[0]) < hw


def rain_layer(seed=1942):
    rnd = random.Random(seed)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    gx, gy = GLOW
    n = 6200
    for _ in range(n):
        x = rnd.uniform(0, W)
        y = rnd.uniform(0, H)
        depth = rnd.random() ** 1.6            # 0 — далеко, 1 — близко
        r = lerp(1.2, 6.5, depth)
        if in_corridor(x, y):
            continue
        # возле краёв коридора капли реже — будто их разбили
        hw = corridor_halfwidth(y)
        if hw > 0 and abs(x - gx) < hw + 24 and rnd.random() < 0.7:
            continue
        dist = math.hypot((x - gx) / 1.0, (y - gy) / 0.8)
        warm = max(0.0, 1.0 - dist / 900.0) ** 1.4
        col = lerp_col((178, 202, 255), (255, 186, 118), warm)
        # капли под заголовком приглушаем, чтобы текст читался
        fade = 1.0
        if y < 1150:
            fade = lerp(0.35, 1.0, y / 1150)
        alpha = int(lerp(55, 205, depth) * fade)
        # капля чуть вытянута вниз — висит, не долетев
        d.ellipse((x - r * 0.7, y - r * 1.05, x + r * 0.7, y + r * 1.05), fill=col + (alpha,))
        d.polygon([(x - r * 0.42, y - r * 0.6), (x + r * 0.42, y - r * 0.6), (x, y - r * 1.9)],
                  fill=col + (int(alpha * 0.85),))
        # блик
        hr = max(0.6, r * 0.24)
        hx, hy = x - r * 0.26, y - r * 0.3
        d.ellipse((hx - hr, hy - hr, hx + hr, hy + hr),
                  fill=(255, 255, 255, min(255, alpha + 30)))
    return layer


def ground_layer():
    """Мокрый асфальт: отражение фонаря на дне коридора."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    gx = GLOW[0]
    for i in range(14):
        y = VANISH_Y + 40 + i * i * 4.2
        if y > H:
            break
        hw = corridor_halfwidth(y) * 0.75
        a = int(70 * (1 - i / 14))
        d.ellipse((gx - hw, y - 3 - i * 0.6, gx + hw, y + 3 + i * 0.6), fill=(255, 170, 90, a))
    return layer.filter(ImageFilter.GaussianBlur(10))


def figure_layer():
    """Силуэт человека в пальто в конце коридора, спиной к нам."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, base = GLOW[0], VANISH_Y + 18
    s = 1.15
    col = (8, 10, 18, 255)
    # ноги
    d.polygon([(cx - 13 * s, base - 46 * s), (cx - 4 * s, base - 46 * s),
               (cx - 7 * s, base), (cx - 15 * s, base)], fill=col)
    d.polygon([(cx + 4 * s, base - 46 * s), (cx + 13 * s, base - 46 * s),
               (cx + 16 * s, base - 2 * s), (cx + 8 * s, base)], fill=col)
    # пальто
    d.polygon([(cx - 17 * s, base - 112 * s), (cx + 17 * s, base - 112 * s),
               (cx + 24 * s, base - 40 * s), (cx - 24 * s, base - 40 * s)], fill=col)
    # плечи
    d.ellipse((cx - 22 * s, base - 122 * s, cx + 22 * s, base - 100 * s), fill=col)
    # шея и голова
    d.rectangle((cx - 5 * s, base - 128 * s, cx + 5 * s, base - 116 * s), fill=col)
    d.ellipse((cx - 11 * s, base - 150 * s, cx + 11 * s, base - 124 * s), fill=col)
    # тень на земле
    d.ellipse((cx - 40 * s, base - 4 * s, cx + 40 * s, base + 8 * s), fill=(0, 0, 0, 120))
    return layer


def draw_spaced(draw, text, font, cy, fill, spacing):
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x = (W - total) / 2
    for ch, w in zip(text, widths):
        draw.text((x, cy), ch, font=font, fill=fill, anchor="lm")
        x += w + spacing


def dial(draw, cx, cy, r, col):
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=3)
    for i in range(12):
        a = math.radians(i * 30)
        r1 = r * (0.78 if i % 3 == 0 else 0.86)
        x1, y1 = cx + math.sin(a) * r1, cy - math.cos(a) * r1
        x2, y2 = cx + math.sin(a) * r * 0.95, cy - math.cos(a) * r * 0.95
        draw.line((x1, y1, x2, y2), fill=col, width=4 if i % 3 == 0 else 2)
    # стрелки: ровно три часа
    draw.line((cx, cy, cx, cy - r * 0.72), fill=col, width=4)        # минутная — на 12
    draw.line((cx, cy, cx + r * 0.5, cy), fill=col, width=6)         # часовая — на 3
    draw.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=col)


def text_layer():
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    gold = (214, 190, 140, 255)
    ivory = (238, 233, 220, 255)

    dial(d, W // 2, 190, 62, gold)

    f_series = ImageFont.truetype(SERIF, 62)
    draw_spaced(d, "НЕСПЯЩИЕ", f_series, 340, gold, 26)
    d.line((W / 2 - 230, 410, W / 2 + 230, 410), fill=gold, width=2)

    f_title1 = ImageFont.truetype(SERIF_BOLD, 196)
    f_title2 = ImageFont.truetype(SERIF_BOLD, 290)
    draw_spaced(d, "МЁРТВЫЙ", f_title1, 575, ivory, 10)
    draw_spaced(d, "ЧАС", f_title2, 835, ivory, 30)

    f_book = ImageFont.truetype(SERIF, 54)
    d.line((W / 2 - 230, 1010, W / 2 + 230, 1010), fill=gold, width=2)
    draw_spaced(d, "КНИГА ПЕРВАЯ", f_book, 1070, gold, 16)
    return layer


def main(out):
    img = background().convert("RGBA")
    img = Image.alpha_composite(img, glow_layer())
    img = Image.alpha_composite(img, ground_layer())
    rain = rain_layer()
    halo = rain.filter(ImageFilter.GaussianBlur(4))
    img = Image.alpha_composite(img, halo)
    img = Image.alpha_composite(img, rain)
    img = Image.alpha_composite(img, figure_layer())
    # лёгкая тень под текстом, чтобы читался на любом экране
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shade).rectangle((0, 0, W, 1180), fill=(0, 0, 0, 70))
    img = Image.alpha_composite(img, shade.filter(ImageFilter.GaussianBlur(80)))
    img = Image.alpha_composite(img, text_layer())
    img.convert("RGB").save(out, "JPEG", quality=90, optimize=True, progressive=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "cover.jpg")
