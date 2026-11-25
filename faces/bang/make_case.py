"""Draws the pictures of Bang: the first second of everything, every minute.

A fireball fills the middle of the screen, white at its heart, through gold, orange and red
to violet and the dark; rays and sparks run out of it to the edges. The hour and the minute
stand black against the fire, rimmed with heat. With every minute a shock wave leaves the
fire at the second 0 and reaches the edge of the screen at the second 59. Over the fire the
weekday bends along an arc, the day stands in gold and the month under it.

    python3 make_case.py OUT_DIR

Writes bang.png and aod.png; the figures h1-*, h2-*, m1-*, m2-*; wave-0.png ... wave-59.png;
and, for every language, weekday-<lang>-0..7, day-<lang>-0..31 and month-<lang>-0..12
(the pictures 0 are never shown). Nothing here is committed: run it before a build.
"""
import json
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, SS = 408, 480, 4
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
FONT = os.path.join(ROOT, 'fonts', 'Oswald.ttf')
LANGS = ('ru', 'en', 'fi')

CX, CY = 204, 254             # the heart of the fire, on the middle of the time
RX, RY = 190, 96              # its reach across and down
CREAM, GOLD = (246, 236, 214), (255, 196, 80)

# the four figures and the colon between them
CELLS = [32, 110, 222, 300]
CELL_W, TOP, TALL = 76, 192, 124
COLON = 204

# the strips that carry the date: left edge and width, centred on the axis
WEEKDAY_STRIP, DAY_STRIP, MONTH_STRIP = (44, 320), (124, 160), (34, 340)

# the ramp of the fire, from the dark to its heart
RAMP = [(0.00, (0, 0, 0)), (0.10, (14, 4, 30)), (0.22, (52, 8, 64)), (0.38, (132, 16, 40)),
        (0.52, (214, 52, 18)), (0.66, (250, 128, 24)), (0.80, (255, 204, 96)),
        (0.92, (255, 240, 196)), (1.00, (255, 255, 246))]


def font(size, weight):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_axes([weight])
    return f


def ramp(v):
    v = np.clip(v, 0, 1)
    out = np.zeros(v.shape + (3,))
    for (a, ca), (b, cb) in zip(RAMP, RAMP[1:]):
        m = (v >= a) & (v <= b)
        t = ((v - a) / (b - a))[m][:, None]
        out[m] = np.array(ca) * (1 - t) + np.array(cb) * t
    return out


def fire():
    """The heat of every pixel, 0 to 1: a flat bright core, rays and a faint haze."""
    rnd = np.random.default_rng(7)
    y, x = np.mgrid[0:H, 0:W].astype(float)
    dx, dy = (x - CX) / RX, (y - CY) / RY
    r = np.hypot(dx, dy)
    a = np.arctan2(y - CY, x - CX)
    core = np.clip(1.25 - 0.55 * r ** 2.2, 0, 1)
    rays = np.zeros_like(r)
    for _ in range(46):
        th, wd, amp = rnd.uniform(-math.pi, math.pi), rnd.uniform(0.006, 0.03), rnd.uniform(0.15, 0.55)
        d = np.angle(np.exp(1j * (a - th)))
        rays += amp * np.exp(-(d / wd) ** 2)
    rays *= np.exp(-np.clip(r - 0.7, 0, None) * 1.1)
    haze = 0.16 * np.exp(-((r - 1.4) / 0.9) ** 2)
    return np.clip(core + rays * np.clip(r - 0.35, 0, 1) + haze, 0, 1)


def sparks(im):
    """Debris thrown along the rays: small, hot, thinning out towards the edge."""
    rnd = random.Random(11)
    d = ImageDraw.Draw(im)
    for _ in range(260):
        t = rnd.random() ** 0.6
        ang = rnd.uniform(0, 2 * math.pi)
        x = CX + math.cos(ang) * RX * (0.75 + 1.6 * t)
        y = CY + math.sin(ang) * RY * (0.75 + 2.4 * t)
        if not (14 < x < W - 14 and 14 < y < H - 14):
            continue
        s = 1.4 if rnd.random() < 0.15 else 0.8
        c = GOLD if rnd.random() < 0.6 else CREAM
        k = 1 - 0.6 * t
        d.ellipse([(x - s) * SS, (y - s) * SS, (x + s) * SS, (y + s) * SS],
                  fill=tuple(int(v * k) for v in c))


def flatten(im, tol):
    """Pixels within tol of the start of their run take its colour: the picture is stored
    run by run, and this nearly halves its weight with no difference on the watch."""
    px = im.load()
    w, h = im.size
    for y in range(h):
        x = 0
        while x < w:
            c = px[x, y]
            j = x + 1
            while j < w and max(abs(p - q) for p, q in zip(px[j, y], c)) <= tol:
                j += 1
            for k in range(x + 1, j):
                px[k, y] = c
            x = j
    return im


def colon(d, colour):
    for cy in (TOP + TALL * 0.32, TOP + TALL * 0.72):
        d.rounded_rectangle([(COLON - 6) * SS, (cy - 8) * SS, (COLON + 6) * SS, (cy + 8) * SS],
                            radius=3 * SS, fill=colour)


def background():
    rgb = ramp(fire())
    im = Image.fromarray(rgb.astype('uint8')).resize((W * SS, H * SS), Image.BICUBIC)
    sparks(im)
    colon(ImageDraw.Draw(im), (0, 0, 0))
    return flatten(im.resize((W, H), Image.LANCZOS), 6)


def figure(ch, fill, rim):
    """One digit, stretched to fill its cell, with a rim of heat."""
    f = font(160 * SS // 2, 640)
    probe = Image.new('L', (200 * SS, 200 * SS), 0)
    ImageDraw.Draw(probe).text((10 * SS, 10 * SS), ch, font=f, fill=255)
    ink = probe.crop(probe.getbbox())
    w = CELL_W - 6
    ink = ink.resize((w * SS, TALL * SS), Image.LANCZOS)
    big = Image.new('L', (CELL_W * SS, (TALL + 8) * SS), 0)
    big.paste(ink, ((CELL_W - w) * SS // 2, 4 * SS))
    out = Image.new('RGBA', big.size, (0, 0, 0, 0))
    if rim:
        halo = big.filter(ImageFilter.MaxFilter(2 * 3 + 1)).filter(ImageFilter.GaussianBlur(3 * SS))
        out.paste(Image.new('RGBA', big.size, rim + (255,)), (0, 0), halo.point(lambda v: v * 0.9))
    out.paste(Image.new('RGBA', big.size, fill + (255,)), (0, 0), big)
    return out.resize((CELL_W, TALL + 8), Image.LANCZOS)


def wave(second):
    """The shock wave at a second: a thin ring, out from the fire to the edge of the screen."""
    t = second / 59.0
    rx, ry = RX * (0.62 + 1.25 * t ** 0.85), RY * (0.62 + 2.6 * t ** 0.85)
    a = int(235 - 115 * t)
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for grow, alpha in ((2, a // 3), (0, a)):
        d.ellipse([CX - rx - grow, CY - ry - grow, CX + rx + grow, CY + ry + grow],
                  outline=(214, 236, 255, alpha), width=1 + 2 * (grow > 0))
    return lay


def arc_word(word, size, colour, radius, top, strip=WEEKDAY_STRIP):
    """A word set along an arc round the fire, its middle on the axis; returns a strip
    of the screen from y top, its left edge and width given by strip."""
    f = font(size * SS, 500)
    track = 2 * SS
    widths = [f.getlength(ch) + track for ch in word]
    total = sum(widths) - track
    R = radius * SS
    left, sw = strip
    big = Image.new('RGBA', (sw * SS, 90 * SS), (0, 0, 0, 0))
    cap = f.getbbox('H')
    pos = -total / 2
    for ch, w in zip(word, widths):
        mid = pos + (w - track) / 2
        ang = mid / R
        g = Image.new('RGBA', (int(size * 2.2 * SS), int(size * 2.2 * SS)), (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        gw = f.getlength(ch)
        gd.text((g.width / 2 - gw / 2, g.height / 2 - (cap[1] + cap[3]) / 2), ch, font=f, fill=colour + (255,))
        g = g.rotate(-math.degrees(ang), resample=Image.BICUBIC)
        x = (CX - left) * SS + R * math.sin(ang)
        y = (CY - top) * SS - R * math.cos(ang)
        big.alpha_composite(g, (int(x - g.width / 2), int(y - g.height / 2)))
        pos += w
    return big.resize((sw, 90), Image.LANCZOS)


def centred(text, size, weight, colour, height, strip, halo=None):
    """A line centred on the axis in a strip, with a hot halo when it stands black in the fire;
    over the dark it needs none, and a halo costs more than the letters."""
    f = font(size * SS, weight)
    left, sw = strip
    big = Image.new('RGBA', (sw * SS, height * SS), (0, 0, 0, 0))
    cap = f.getbbox('0')
    w = f.getlength(text)
    ImageDraw.Draw(big).text(((CX - left) * SS - w / 2, height * SS / 2 - (cap[1] + cap[3]) / 2), text, font=f,
                             fill=colour + (255,))
    if halo is None:
        return big.resize((sw, height), Image.LANCZOS)
    shadow = Image.new('RGBA', big.size, halo + (0,))
    shadow.putalpha(big.getchannel('A').filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(4 * SS)))
    shadow.alpha_composite(big)
    return shadow.resize((sw, height), Image.LANCZOS)


def main(out):
    background().save(os.path.join(out, 'bang.png'))
    aod = Image.new('RGB', (W * SS, H * SS), (0, 0, 0))
    aod.resize((W, H), Image.LANCZOS).save(os.path.join(out, 'aod.png'))
    for name, count in (('h1', 3), ('h2', 10), ('m1', 6), ('m2', 10)):
        for v in range(count):
            figure(str(v), (0, 0, 0), (255, 236, 190)).save(os.path.join(out, '%s-%d.png' % (name, v)))
    for s in range(60):
        wave(s).save(os.path.join(out, 'wave-%d.png' % s))
    blank = lambda strip, h: Image.new('RGBA', (strip[1], h), (0, 0, 0, 0))
    for lang in LANGS:
        loc = json.load(open(os.path.join(ROOT, 'machine', 'locales', lang + '.json'), encoding='utf-8'))
        words = [blank(WEEKDAY_STRIP, 90)] + [arc_word(w.upper(), 28, CREAM, 200, 30) for w in loc['weekdays']]
        for i, im in enumerate(words):
            im.save(os.path.join(out, 'weekday-%s-%d.png' % (lang, i)))
        sfx = loc.get('day_suffix', '')
        days = [blank(DAY_STRIP, 72)] + [centred('%d%s' % (d, sfx), 62, 600, GOLD, 72, DAY_STRIP) for d in range(1, 32)]
        for i, im in enumerate(days):
            im.save(os.path.join(out, 'day-%s-%d.png' % (lang, i)))
        months = [blank(MONTH_STRIP, 44)] + [centred(m.upper(), 32, 600, (0, 0, 0), 44, MONTH_STRIP) for m in loc['months']]
        for i, im in enumerate(months):
            im.save(os.path.join(out, 'month-%s-%d.png' % (lang, i)))


if __name__ == '__main__':
    main(sys.argv[1])
