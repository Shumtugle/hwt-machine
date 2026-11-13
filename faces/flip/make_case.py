"""Draws the pictures of Flip: the case and the weather.

Two dark flip cards on black, each split at its middle with a hinge at each side, the
lower half a shade deeper than the upper, a faint sheen across the top and a hairline
round the edge. Under them a dark bar for the date and the temperature, and below it
the small marks of the readings. The weather is a picture of its own in the middle,
over the foot of the cards and the top of the bar: a glossy sun, clouds, rain, snow,
a storm, mist, wind, a moon, one picture for each state the watch reports.

    python3 make_case.py case.png

writes case.png and, next to it, sky-0.png ... sky-10.png in the watch's order of
weather states.
"""
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H, SS = 408, 480, 4
CARDS = [(22, 50, 198, 230), (210, 50, 386, 230)]
BAR = (22, 262, 386, 352)
ROUND = 16
SPLIT = 2
FAINT = (168, 162, 154)
SKY = 132                     # the side of a weather picture


def S(v):
    return [int(round(a * SS)) for a in v]


def vertical(size, stops):
    """A vertical gradient through (fraction, colour) stops."""
    w, h = size
    im = Image.new('RGB', (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        f = y / float(max(1, h - 1))
        for (fa, ca), (fb, cb) in zip(stops, stops[1:]):
            if fa <= f <= fb:
                k = (f - fa) / (fb - fa) if fb > fa else 0
                d.line([(0, y), (w, y)], fill=tuple(int(ca[i] + (cb[i] - ca[i]) * k) for i in range(3)))
                break
    return im


def shaped(big, box, radius, stops):
    """A rounded box filled with a vertical gradient, with a soft shadow below it."""
    shape = Image.new('L', big.size, 0)
    ImageDraw.Draw(shape).rounded_rectangle(S(box), radius=radius * SS, fill=255)
    sh = Image.new('L', big.size, 0)
    sh.paste(shape.filter(ImageFilter.GaussianBlur(6 * SS)), (0, 4 * SS))
    big.paste((0, 0, 0), (0, 0), sh)
    x0, y0, x1, y1 = S(box)
    fill = Image.new('RGB', big.size)
    fill.paste(vertical((x1 - x0, y1 - y0), stops), (x0, y0))
    big.paste(fill, (0, 0), shape)
    return shape


def card(big, box):
    x0, y0, x1, y1 = box
    mid = (y0 + y1) / 2.0
    shape = shaped(big, box, ROUND, [(0.0, (52, 48, 44)), (0.49, (33, 31, 28)), (0.51, (21, 19, 17)), (1.0, (31, 29, 26))])
    sheen = Image.new('L', big.size, 0)
    ImageDraw.Draw(sheen).rectangle(S((x0, y0, x1, y0 + (mid - y0) * 0.35)), fill=12)
    big.paste((255, 255, 255), (0, 0), ImageChops.multiply(sheen, shape))
    d = ImageDraw.Draw(big, 'RGBA')
    d.rounded_rectangle(S((x0 + 0.5, y0 + 0.5, x1 - 0.5, y1 - 0.5)), radius=ROUND * SS, outline=(255, 255, 255, 38), width=SS)
    d.rectangle(S((x0, mid - SPLIT / 2.0, x1, mid + SPLIT / 2.0)), fill=(10, 9, 8, 255))
    for hx in (x0, x1):
        d.rounded_rectangle(S((hx - 3, mid - 7, hx + 3, mid + 7)), radius=2 * SS, fill=(90, 84, 76, 255))
        d.rounded_rectangle(S((hx - 2, mid - 6, hx + 0.5, mid + 1)), radius=1 * SS, fill=(124, 117, 106, 255))


def bar(big):
    shaped(big, BAR, 14, [(0.0, (40, 38, 36)), (0.12, (24, 23, 22)), (1.0, (12, 12, 12))])
    d = ImageDraw.Draw(big, 'RGBA')
    x0, y0, x1, y1 = BAR
    d.rounded_rectangle(S((x0 + 0.5, y0 + 0.5, x1 - 0.5, y1 - 0.5)), radius=14 * SS, outline=(255, 255, 255, 30), width=SS)


def moon_mark(big, cx, cy, r, colour):
    m = Image.new('L', big.size, 0)
    d = ImageDraw.Draw(m)
    d.ellipse(S((cx - r, cy - r, cx + r, cy + r)), fill=255)
    d.ellipse(S((cx - r + r * 0.55, cy - r - r * 0.25, cx + r + r * 0.55, cy + r - r * 0.25)), fill=0)
    big.paste(colour, (0, 0), m)


def bolt_mark(big, cx, cy, h, colour):
    s = h / 20.0
    pts = [(1, -10), (-6, 2), (-1, 2), (-3, 10), (6, -3), (1, -3), (3, -10)]
    ImageDraw.Draw(big).polygon([P(cx + x * s, cy + y * s) for x, y in pts], fill=colour)


# ---------------------------------------------------------------- the weather pictures

def P(x, y):
    return (int(x * SS), int(y * SS))


def glow(layer, box, colour, alpha, blur):
    g = Image.new('L', layer.size, 0)
    ImageDraw.Draw(g).ellipse([int(v * SS) for v in box], fill=alpha)
    g = g.filter(ImageFilter.GaussianBlur(blur * SS))
    c = Image.new('RGBA', layer.size, colour + (0,))
    c.putalpha(g)
    layer.alpha_composite(c)


def orb(layer, cx, cy, r, centre, edge, shine=True):
    """A glossy ball: lighter towards the upper left, a sheen on top."""
    d = ImageDraw.Draw(layer)
    for k in range(40, 0, -1):
        t = k / 40.0
        rr = r * t
        off = (1 - t) * r * 0.28
        col = tuple(int(centre[i] + (edge[i] - centre[i]) * t) for i in range(3)) + (255,)
        d.ellipse([P(cx - rr - off, cy - rr - off), P(cx + rr - off, cy + rr - off)], fill=col)
    if shine:
        sh = Image.new('L', layer.size, 0)
        ImageDraw.Draw(sh).ellipse([P(cx - r * 0.62, cy - r * 0.86), P(cx + r * 0.38, cy - r * 0.18)], fill=120)
        sh = sh.filter(ImageFilter.GaussianBlur(r * 0.12 * SS))
        white = Image.new('RGBA', layer.size, (255, 255, 255, 0))
        white.putalpha(sh)
        layer.alpha_composite(white)


def sun(layer, cx, cy, r):
    glow(layer, (cx - r * 1.25, cy - r * 1.25, cx + r * 1.25, cy + r * 1.25), (255, 176, 40), 150, r * 0.3)
    d = ImageDraw.Draw(layer)
    for i in range(12):
        a = math.radians(i * 30 + 15)
        tip, base, w = r * 1.42, r * 0.95, 0.17
        d.polygon([P(cx + math.cos(a) * tip, cy + math.sin(a) * tip),
                   P(cx + math.cos(a + w) * base, cy + math.sin(a + w) * base),
                   P(cx + math.cos(a - w) * base, cy + math.sin(a - w) * base)], fill=(255, 190, 52, 230))
    orb(layer, cx, cy, r, (255, 246, 170), (246, 150, 20))


def moon(layer, cx, cy, r):
    glow(layer, (cx - r * 1.2, cy - r * 1.2, cx + r * 1.2, cy + r * 1.2), (190, 205, 255), 90, r * 0.32)
    disc = Image.new('RGBA', layer.size, (0, 0, 0, 0))
    orb(disc, cx, cy, r, (255, 252, 230), (214, 206, 170))
    cut = Image.new('L', layer.size, 255)
    ImageDraw.Draw(cut).ellipse([P(cx - r * 0.45, cy - r * 1.25), P(cx + r * 1.55, cy + r * 0.75)], fill=0)
    disc.putalpha(ImageChops.multiply(disc.getchannel('A'), cut))
    layer.alpha_composite(disc)


def cloud(layer, cx, cy, s, top=(252, 252, 254), bottom=(176, 184, 198)):
    """A cloud of overlapping puffs on a flat base, lit from above, with a soft shadow."""
    puffs = [(-0.55, 0.12, 0.42), (-0.12, -0.2, 0.55), (0.42, -0.02, 0.45), (0.1, 0.2, 0.42), (-0.35, 0.28, 0.32),
             (0.55, 0.26, 0.32)]
    m = Image.new('L', layer.size, 0)
    d = ImageDraw.Draw(m)
    for px, py, pr in puffs:
        x, y, r = cx + px * s, cy + py * s, pr * s
        d.ellipse([P(x - r, y - r), P(x + r, y + r)], fill=255)
    d.rounded_rectangle([P(cx - 0.85 * s, cy + 0.12 * s), P(cx + 0.85 * s, cy + 0.58 * s)], radius=int(0.23 * s * SS), fill=255)
    sh = Image.new('L', layer.size, 0)
    sh.paste(m.filter(ImageFilter.GaussianBlur(3 * SS)), P(2, 5))
    shade = Image.new('RGBA', layer.size, (0, 0, 0, 0))
    shade.putalpha(sh.point(lambda a: a * 2 // 3))
    layer.alpha_composite(shade)
    y0, y1 = int((cy - 0.78 * s) * SS), int((cy + 0.6 * s) * SS)
    body = Image.new('RGBA', layer.size, (0, 0, 0, 0))
    mid = tuple((top[i] + bottom[i]) // 2 for i in range(3))
    body.paste(vertical((layer.size[0], y1 - y0), [(0.0, top), (0.55, mid), (1.0, bottom)]).convert('RGBA'), (0, y0))
    body.putalpha(m)
    layer.alpha_composite(body)


def drops(layer, cx, cy, s, n=3):
    d = ImageDraw.Draw(layer)
    for i in range(n):
        x, y, r = cx + (i - (n - 1) / 2.0) * s * 0.42, cy + (i % 2) * s * 0.18, s * 0.1
        d.polygon([P(x, y - r * 2.1), P(x - r, y), P(x + r, y)], fill=(80, 156, 255, 255))
        d.ellipse([P(x - r, y - r), P(x + r, y + r)], fill=(60, 132, 240, 255))
        d.ellipse([P(x - r * 0.45, y - r * 0.7), P(x - r * 0.05, y - r * 0.2)], fill=(200, 228, 255, 255))


def flakes(layer, cx, cy, s, n=3):
    d = ImageDraw.Draw(layer)
    for i in range(n):
        x, y, r = cx + (i - (n - 1) / 2.0) * s * 0.42, cy + (i % 2) * s * 0.18, s * 0.13
        for k in range(3):
            a = math.radians(k * 60)
            d.line([P(x - math.cos(a) * r, y - math.sin(a) * r), P(x + math.cos(a) * r, y + math.sin(a) * r)],
                   fill=(240, 248, 255, 255), width=int(s * 0.045 * SS))


def bolt(layer, cx, cy, s):
    pts = [(0.05, -0.5), (-0.28, 0.08), (-0.04, 0.08), (-0.16, 0.5), (0.3, -0.12), (0.06, -0.12), (0.18, -0.5)]
    glow(layer, (cx - s * 0.4, cy - s * 0.5, cx + s * 0.4, cy + s * 0.5), (255, 220, 80), 120, s * 0.12)
    ImageDraw.Draw(layer).polygon([P(cx + x * s, cy + y * s) for x, y in pts], fill=(255, 214, 64, 255))


def bands(layer, cx, cy, s, colour, n=3, curl=False):
    d = ImageDraw.Draw(layer)
    for i in range(n):
        y = cy + (i - (n - 1) / 2.0) * s * 0.26
        w = s * (0.9 - 0.15 * (i % 2))
        x0 = cx - w / 2 + (i % 2) * s * 0.12
        d.rounded_rectangle([P(x0, y - s * 0.045), P(x0 + w, y + s * 0.045)], radius=int(s * 0.045 * SS), fill=colour)
        if curl:
            d.arc([P(x0 + w - s * 0.12, y - s * 0.2), P(x0 + w + s * 0.12, y + s * 0.045)], 270, 90, fill=colour,
                  width=int(s * 0.07 * SS))


def sky(state):
    """One weather picture, SKY px square, in the watch's order of states."""
    layer = Image.new('RGBA', (SKY * SS, SKY * SS), (0, 0, 0, 0))
    c = SKY / 2.0
    if state == 0:                                   # unknown
        cloud(layer, c, c + 6, 46, (150, 150, 156), (96, 98, 106))
    elif state == 1:                                 # sunny
        sun(layer, c, c, 34)
    elif state == 2:                                 # clear night
        moon(layer, c, c, 32)
    elif state == 3:                                 # cloudy
        cloud(layer, c + 12, c - 4, 34, (214, 218, 226), (140, 148, 162))
        cloud(layer, c - 6, c + 8, 46)
    elif state == 4:                                 # partly cloudy
        sun(layer, c - 14, c - 14, 26)
        cloud(layer, c + 6, c + 12, 42)
    elif state == 5:                                 # rain
        cloud(layer, c, c - 10, 46, (226, 230, 238), (150, 158, 174))
        drops(layer, c, c + 34, 46)
    elif state == 6:                                 # thunderstorm
        cloud(layer, c, c - 10, 46, (150, 154, 168), (82, 86, 100))
        bolt(layer, c + 2, c + 32, 40)
    elif state == 7:                                 # snow
        cloud(layer, c, c - 10, 46)
        flakes(layer, c, c + 34, 46)
    elif state == 8:                                 # wind
        bands(layer, c, c, 70, (226, 232, 242, 255), 3, curl=True)
    elif state == 9:                                 # haze: a sun behind veils
        sun(layer, c, c - 8, 28)
        veil = Image.new('RGBA', layer.size, (0, 0, 0, 0))
        bands(veil, c, c + 16, 74, (214, 206, 190, 200), 3)
        layer.alpha_composite(veil)
    else:                                            # fog
        cloud(layer, c, c - 12, 40, (200, 204, 212), (140, 146, 158))
        bands(layer, c, c + 26, 76, (190, 194, 202, 235), 3)
    return layer.resize((SKY, SKY), Image.LANCZOS)


def main(out):
    big = Image.new('RGB', (W * SS, H * SS), (0, 0, 0))
    for box in CARDS:
        card(big, box)
    bar(big)
    moon_mark(big, 180, 404, 8, FAINT)
    bolt_mark(big, 312, 404, 18, FAINT)
    big.resize((W, H), Image.LANCZOS).save(out)
    folder = os.path.dirname(os.path.abspath(out))
    for state in range(11):
        sky(state).save(os.path.join(folder, 'sky-%d.png' % state))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'case.png')
