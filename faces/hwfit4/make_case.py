"""Draws the pictures of hwfit4: the reference face for this screen, in two colourings.

A deep ground lit from the middle, a frame of sixty dots round the visible edge with the
quarters written in, and a small tablet carrying the second along it. The hour and the
minute stand tall in the middle: in the cool colouring (s) every number on the face is
set in a rounded condensed face, each figure at its own width in the middle of its cell;
in the warm one (r) the numbers keep the face of the words, and the figures of the time
are stretched to one width. On every tenth second the tablet strikes: it swells and
glows, and in the cool colouring also takes the colour of the heart below; on the next
second it is still a little large, then it is itself again.

    python3 make_case.py OUT_DIR

Writes, for each colouring (plain names for s, an "r-" prefix for r): case.png, the
background with the colon; h1-N.png, h2-N.png, m1-N.png, m2-N.png, the figures;
tab-0.png ... tab-59.png, the second's tablet. Run it into the face's own folder before a
build; the pictures are not committed.
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, SS = 408, 480, 4
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, '..', '..', 'fonts', 'Oswald.ttf')
ROUNDED = os.path.join(HERE, '..', '..', 'fonts', 'SairaExtraCondensed-ExtraBold.ttf')

# strike: "pulse" swells the tablet; "both" swells it and gives it the colour of the heart.
# figures: "rounded" sets every number in the rounded face; "stretched" keeps the face of the words
PALETTES = {
    '': dict(core=(15, 53, 87), mid=(10, 32, 56), deep=(4, 11, 22),
             halo=(40, 130, 220), halo_out=(15, 70, 140), fig=(238, 246, 255),
             quarter=(207, 227, 241), dot=(95, 127, 153),
             tab=(207, 227, 241), ink=(10, 32, 56), tab_glow=(60, 150, 240),
             hit=(200, 54, 47), hit_ink=(255, 244, 240), hit_glow=(230, 60, 50), strike='both',
             figures='rounded'),
    'r-': dict(core=(74, 10, 12), mid=(37, 4, 10), deep=(11, 1, 2),
                    halo=(200, 28, 28), halo_out=(120, 10, 10), fig=(240, 230, 206),
                    quarter=(205, 191, 160), dot=(140, 135, 127),
                    tab=(205, 191, 160), ink=(37, 4, 10), tab_glow=(200, 28, 28),
                    hit=(210, 70, 58), hit_ink=(255, 244, 224), hit_glow=(255, 60, 40), strike='pulse',
                    figures='stretched'),
}

# the still halo of the ground, behind the time
HALO = (12, 120, 396, 352)
# the four figures: cells, each picture CELL_W wide and TALL + 8 high, the ink stretched to
# INK_W x TALL and starting 4 px down; the colon between them
CELLS = {'h1': 32, 'h2': 110, 'm1': 222, 'm2': 300}
COUNTS = {'h1': 3, 'h2': 10, 'm1': 6, 'm2': 10}
CELL_W, INK_W, TALL, TOP, COLON = 76, 70, 124, 178, 204
# the tablet on the strike, on the second after, at rest: scale and how far in from the edge
STRIKE = {0: (1.45, 12), 1: (1.15, 10)}
REST = (1.0, 9)


def font(size, weight):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_axes([weight])
    return f



def edge(angle, inset):
    """Where a ray from the centre at angle meets the rounded visible edge, inset px inside."""
    i, r = 11 + inset, 82 - inset
    dx, dy = math.sin(math.radians(angle)), -math.cos(math.radians(angle))
    t = 0.0
    while True:
        x, y = W / 2 + dx * t, H / 2 + dy * t
        inside = i <= x <= W - 1 - i and i <= y <= H - 1 - i
        for kx, ky in ((i + r, i + r), (W - 1 - i - r, i + r), (i + r, H - 1 - i - r), (W - 1 - i - r, H - 1 - i - r)):
            if ((x < kx) if kx < W / 2 else (x > kx)) and ((y < ky) if ky < H / 2 else (y > ky)) and math.hypot(x - kx, y - ky) > r:
                inside = False
        if not inside:
            return x, y
        t += 0.25



def centred_text(d, x, y, s, f, fill):
    w = d.textlength(s, font=f)
    box = f.getbbox(s)
    d.text((x - w / 2, y - (box[1] + box[3]) / 2), s, font=f, fill=fill)



def mix(a, b, t):
    return tuple(int(round(p + (q - p) * t)) for p, q in zip(a, b))



def flatten(im, tol):
    """Pixels that stay within tol of the start of their run take its colour, so smooth
    light is stored in runs; at small tol the steps cannot be seen on the watch."""
    px = im.load()
    w, h = im.size
    for y in range(h):
        x = 0
        while x < w:
            c = px[x, y]
            j = x + 1
            while j < w and max(abs(a - b) for a, b in zip(px[j, y], c)) <= tol:
                j += 1
            if j - x >= 4:
                for k in range(x + 1, j):
                    px[k, y] = c
            x = j
    return im



def ground(p):
    """Light from the middle of the screen, dying into black at the edges, with the still
    halo behind the time."""
    im = Image.new('RGB', (W, H))
    px = im.load()
    cx, cy, rx, ry = W * 0.5, H * 0.54, W * 0.72, H * 0.58
    stops = ((0.0, p['core']), (0.42, p['mid']), (0.74, p['deep']), (1.0, (0, 0, 0)))
    for y in range(H):
        for x in range(W):
            t = min(1.0, math.hypot((x - cx) / rx, (y - cy) / ry))
            for (a, ca), (b, cb) in zip(stops, stops[1:]):
                if t <= b:
                    px[x, y] = mix(ca, cb, (t - a) / (b - a))
                    break
    im = im.convert('RGBA')
    l, t, r, b = HALO
    w, h = r - l, b - t
    hl = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    hp = hl.load()
    for y in range(h):
        for x in range(w):
            d = math.hypot((x - w / 2) / (w / 2), (y - h / 2) / (h / 2))
            if d >= 1:
                continue
            if d < 0.6:
                c, a = mix(p['halo'], p['halo_out'], d / 0.6), 0.55 + (0.22 - 0.55) * d / 0.6
            else:
                c, a = p['halo_out'], 0.22 * (1 - (d - 0.6) / 0.4)
            hp[x, y] = c + (int(round(255 * a * 0.45)),)
    im.alpha_composite(hl, (l, t))
    return flatten(im.convert("RGB"), 3)




def numbers(p, size):
    """The face of the small numbers on the frame and the tablet."""
    if p['figures'] == 'rounded':
        return ImageFont.truetype(ROUNDED, int(round(size * 1.17 * SS)))
    return font(int(round(size * SS)), 600)


def case(p, plain):
    im = plain.convert('RGBA')
    big = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    f = numbers(p, 15)
    for i in range(60):
        x, y = edge(i * 6, 7)
        if i % 15 == 0:
            centred_text(d, x * SS, y * SS, '%02d' % i, f, p['quarter'] + (255,))
        else:
            r = 1.5 * SS
            d.ellipse([x * SS - r, y * SS - r, x * SS + r, y * SS + r], fill=p['dot'] + (255,))
    for fy in (0.32, 0.72):
        cy = TOP + TALL * fy
        d.rounded_rectangle([(COLON - 6) * SS, (cy - 8) * SS, (COLON + 6) * SS, (cy + 8) * SS],
                            radius=2 * SS, fill=p['fig'] + (255,))
    im.alpha_composite(big.resize((W, H), Image.LANCZOS))
    return im.convert('RGB')


def figure(ch, colour, kind):
    """One digit TALL high: stretched to fill its cell, or at its own width in the middle of it."""
    if kind == 'stretched':
        f = font(160 * SS // 2, 640)
    else:
        f = ImageFont.truetype(ROUNDED, 160 * SS // 2)
    probe = Image.new('L', (200 * SS, 200 * SS), 0)
    ImageDraw.Draw(probe).text((10 * SS, 10 * SS), ch, font=f, fill=255)
    ink = probe.crop(probe.getbbox())
    if kind == 'stretched':
        w = INK_W * SS
    else:
        # the height of a zero sets the scale for every figure, so all keep their proportions
        zero = Image.new('L', (200 * SS, 200 * SS), 0)
        ImageDraw.Draw(zero).text((10 * SS, 10 * SS), '0', font=f, fill=255)
        scale = TALL * SS / float(zero.getbbox()[3] - zero.getbbox()[1])
        w = min(CELL_W * SS, int(round(ink.width * scale)))
    ink = ink.resize((w, TALL * SS), Image.LANCZOS)
    big = Image.new('L', (CELL_W * SS, (TALL + 8) * SS), 0)
    big.paste(ink, ((CELL_W * SS - w) // 2, 4 * SS))
    out = Image.new('RGBA', big.size, colour + (255,))
    out.putalpha(big)
    return out.resize((CELL_W, TALL + 8), Image.LANCZOS)


def tablet(p, second):
    """The second's tablet at its place on the frame, on an otherwise empty screen."""
    u = second % 10
    k, inset = STRIKE.get(u, REST)
    struck = u == 0
    hit = struck and p['strike'] == 'both'
    fill, text = (p['hit'], p['hit_ink']) if hit else (p['tab'], p['ink'])
    halo_colour = p['hit_glow'] if hit else p['tab_glow']
    halo_alpha = 230 if struck else (170 if u == 1 else 130)
    big = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0))
    x, y = edge(second * 6, inset)
    f = numbers(p, 15 * k)
    s = '%02d' % second
    w = ImageDraw.Draw(big).textlength(s, font=f) / SS
    hh, pad = 9.5 * k, 6 * k
    box = [(x - w / 2 - pad) * SS, (y - hh) * SS, (x + w / 2 + pad) * SS, (y + hh) * SS]
    halo = Image.new('RGBA', big.size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).rounded_rectangle(box, radius=hh * SS, fill=halo_colour + (halo_alpha,))
    blur = 5 if struck else (3.5 if u == 1 else 2.5)
    big.alpha_composite(halo.filter(ImageFilter.GaussianBlur(blur * SS)))
    if struck:
        big.alpha_composite(halo.filter(ImageFilter.GaussianBlur(2 * SS)))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle(box, radius=hh * SS, fill=fill + (255,))
    centred_text(d, x * SS, y * SS, s, f, text + (255,))
    return big.resize((W, H), Image.LANCZOS)


def main(out):
    for prefix, p in PALETTES.items():
        case(p, ground(p)).save(os.path.join(out, prefix + 'case.png'))
        for name, count in COUNTS.items():
            for v in range(count):
                figure(str(v), p['fig'], p['figures']).save(os.path.join(out, '%s%s-%d.png' % (prefix, name, v)))
        for s in range(60):
            tablet(p, s).save(os.path.join(out, '%stab-%d.png' % (prefix, s)))


if __name__ == '__main__':
    main(sys.argv[1])
