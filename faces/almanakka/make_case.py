"""Draws the pictures of Almanakka: a wall calendar on the wrist.

On black, a frame of sixty dots runs round the visible edge with the quarters written
in; a small amber tablet carrying the second steps along it. The hour and the minute
stand very tall, the figures stretched upward to fill the upper half. Under the date a
painted landscape changes with the month, twelve of them; the readings sit below.

    python3 make_case.py OUT_DIR PANELS_DIR

PANELS_DIR holds the twelve paintings, 01-*.png ... 12-*.png, one wide strip each.
Writes case.png and aod-colon.png; the figures h1-*, h2-*, m1-*, m2-* and their dim twins for the
always-on screen (a prefix); month-0.png ... month-12.png (0 is never shown); and
sec-0.png ... sec-59.png. The paintings are kept apart from this repository, so
the pictures are not committed: run this into the face's own folder before a build.
"""
import glob
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, SS = 408, 480, 4
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, '..', '..', 'fonts', 'Oswald.ttf')
CREAM, DIM = (250, 243, 223), (128, 122, 110)
DOT, AMBER, INK = (140, 135, 127), (255, 176, 32), (24, 14, 4)

# the four tall figures and the colon between them
CELLS = [39, 117, 215, 293]
CELL_W, TOP, TALL = 76, 44, 218
COLON = (195, 213)
# the painting
PIC = (33, 304, 342, 92)
# where in each painting the window sits, as a fraction of its width (0 left, 1 right)
FOCUS = [0.45, 0.5, 0.5, 0.62, 0.4, 0.58, 0.62, 0.5, 0.45, 0.38, 0.65, 0.62]


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


def colon(colour):
    big = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    for cy in (TOP + TALL * 0.34, TOP + TALL * 0.7):
        d.rounded_rectangle([COLON[0] * SS, (cy - 9) * SS, COLON[1] * SS, (cy + 9) * SS], radius=2 * SS, fill=colour + (255,))
    return big.resize((W, H), Image.LANCZOS)


def case():
    big = Image.new('RGB', (W * SS, H * SS), (0, 0, 0))
    d = ImageDraw.Draw(big)
    f = font(15 * SS, 600)
    for i in range(60):
        x, y = edge(i * 6, 7)
        if i % 15 == 0:
            centred_text(d, x * SS, y * SS, '%02d' % i, f, CREAM)
        else:
            r = 1.5 * SS
            d.ellipse([x * SS - r, y * SS - r, x * SS + r, y * SS + r], fill=DOT)
    big = big.resize((W, H), Image.LANCZOS).convert('RGBA')
    big.alpha_composite(colon(CREAM))
    return big.convert('RGB')


def figure(ch, colour):
    """One digit, drawn condensed and stretched upward to the full height of its cell."""
    f = font(160 * SS // 2, 640)
    probe = Image.new('L', (200 * SS, 200 * SS), 0)
    ImageDraw.Draw(probe).text((10 * SS, 10 * SS), ch, font=f, fill=255)
    ink = probe.crop(probe.getbbox())
    w = min(CELL_W - 4, round(ink.width / SS * 1.0))
    ink = ink.resize((w * SS, TALL * SS), Image.LANCZOS).resize((w, TALL), Image.LANCZOS)
    out = Image.new('RGBA', (CELL_W, TALL), (0, 0, 0, 0))
    paint = Image.new('RGBA', (w, TALL), colour + (255,))
    paint.putalpha(ink)
    out.alpha_composite(paint, ((CELL_W - w) // 2, 0))
    return out


def flatten(im, tol):
    """Pixels that stay within tol of the start of their run take its colour.
    Pictures are stored run by run, so this nearly halves a painting's weight;
    at tol 8 the difference cannot be seen on the watch."""
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


def paintings(panels):
    files = sorted(glob.glob(os.path.join(panels, '[01][0-9]-*.png')))
    assert len(files) == 12, files
    x0, y0, pw, ph = PIC
    out = []
    for k, f in enumerate(files):
        p = Image.open(f).convert('RGB')
        scale = ph / float(p.height)
        win = int(round(pw / scale))
        left = int(round(FOCUS[k] * p.width - win / 2))
        left = max(0, min(p.width - win, left))
        pic = p.crop((left, 0, left + win, p.height)).resize((pw, ph), Image.LANCZOS).convert('RGBA')
        m = Image.new('L', (pw * SS, ph * SS), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, pw * SS - 1, ph * SS - 1], radius=10 * SS, fill=255)
        pic.putalpha(m.resize((pw, ph), Image.LANCZOS))
        out.append(flatten(pic, 8))
    blank = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
    return [blank] + out           # the list starts at 0, which is never shown


def tablet(second):
    """The second's tablet at its place on the frame, on an otherwise empty screen."""
    big = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0))
    x, y = edge(second * 6, 9)     # a hair inside the dots, so the corners stay clear
    f = font(15 * SS, 650)
    s = '%02d' % second
    w = ImageDraw.Draw(big).textlength(s, font=f) / SS
    box = [(x - w / 2 - 6) * SS, (y - 9.5) * SS, (x + w / 2 + 6) * SS, (y + 9.5) * SS]
    glow = Image.new('RGBA', big.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle(box, radius=9.5 * SS, fill=AMBER + (110,))
    big.alpha_composite(glow.filter(ImageFilter.GaussianBlur(2 * SS)))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle(box, radius=9.5 * SS, fill=AMBER + (255,))
    centred_text(d, x * SS, y * SS, s, f, INK + (255,))
    return big.resize((W, H), Image.LANCZOS)


def main(out, panels):
    case().save(os.path.join(out, 'case.png'))
    colon(DIM).save(os.path.join(out, 'aod-colon.png'))
    for prefix, colour in (('', CREAM), ('a', DIM)):
        for name, count in (('h1', 3), ('h2', 10), ('m1', 6), ('m2', 10)):
            for v in range(count):
                figure(str(v), colour).save(os.path.join(out, '%s%s-%d.png' % (prefix, name, v)))
    for k, pic in enumerate(paintings(panels)):
        pic.save(os.path.join(out, 'month-%d.png' % k))
    for s in range(60):
        tablet(s).save(os.path.join(out, 'sec-%d.png' % s))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
