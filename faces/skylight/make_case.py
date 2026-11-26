"""Draws the pictures of Skylight: a face seen through a window between two shutters.

The hour and the minute stand very tall in a lens-shaped window. Behind them is the sky:
deep at night, lighter towards midday, back to indigo in the evening; only its middle
changes with the hour, the rim of the window keeps one colour. The shutters above and
below catch that light on their inner edges and cast a soft shadow onto the figures. The
seconds are cut out of the top of the last figure, where every one of the ten figures has
ink, so they always show the sky through it.

    python3 make_case.py OUT_DIR

Writes: case.png, the still sky with the shutters on it, except across the two bands
where the shutters reach over the figures; band-0.png ... band-2.png, the shutters in those
bands, laid over the figures (three equal pictures, carried by the hour's tens); sky-0.png ...
sky-23.png, the light in the middle of the window for each hour (equal hours share a
picture); fig-N.png, the figures; colon-N.png, the colon (three equal pictures, carried by
the hour's tens); sec-0.png ... sec-59.png, the seconds cut out of the sky.
"""
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H, SS = 408, 480, 4
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, '..', '..', 'fonts', 'Oswald.ttf')

FIG = (255, 244, 226)
# the window: its sky is an ellipse of light round the middle of the screen
CX, CY, RX, RY = W * 0.5, H * 0.5, W * 0.75, H * 0.6
RIM = ((0.42, (18, 26, 61)), (0.74, (7, 10, 24)), (1.0, (0, 0, 0)))
# the middle of the sky through the day: (from hour, core colour)
SKY = ((0, (20, 26, 66)), (5, (26, 36, 86)), (7, (44, 71, 144)), (10, (47, 99, 176)),
       (16, (42, 85, 159)), (18, (40, 63, 134)), (20, (29, 42, 92)), (22, (24, 32, 76)))
# the figures: cells, each picture FIG_W x FIG_H with the ink filling it, its top at TOP
CELLS = (31, 113, 219, 301)
FIG_W, FIG_H, TOP = 76, 250, 115
COLON = 204
# the seconds: centre of the zone every figure inks, inside the last cell
SEC_CX, SEC_CY, SEC_SIZE = 301 + 45, TOP + 21.5, 22
SEC_BOX = (322, 120, 370, 154)
# the shutter edges: quadratic curves from side to side through a control point
TOP_EDGE = (128, 108)
BOTTOM_EDGE = (348, 372)
SHUTTER_TOP = ((13, 17, 32), (27, 34, 56))
SHUTTER_BOTTOM = ((27, 34, 56), (11, 14, 26))
# the rows where the shutters, their light and their shadow reach over the figures
BANDS = ((96, 158), (326, 378))


def font(size, weight):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_axes([weight])
    return f


def mix(a, b, t):
    return tuple(int(round(p + (q - p) * t)) for p, q in zip(a, b))


def flatten(im, tol):
    """Pixels that stay within tol of the start of their run take its colour, so smooth
    light is stored in runs."""
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


def reach(x, y):
    return math.hypot((x - CX) / RX, (y - CY) / RY)


def rim(t):
    """The sky from the edge of the middle outwards; the same at every hour."""
    (a, ca), (b, cb), (c, cc) = RIM
    if t <= b:
        return mix(ca, cb, (t - a) / (b - a))
    return mix(cb, cc, min(1.0, (t - b) / (c - b)))


def edge_y(edge, x):
    """Height of a shutter edge at x."""
    side, ctrl = edge
    t = x / float(W)
    return (1 - t) ** 2 * side + 2 * t * (1 - t) * ctrl + t ** 2 * side


def case():
    """The still sky: the rim colours everywhere outside the middle, black under the shutters."""
    im = Image.new('RGB', (W, H), (0, 0, 0))
    px = im.load()
    for y in range(H):
        for x in range(W):
            if edge_y(TOP_EDGE, x) - 12 <= y <= edge_y(BOTTOM_EDGE, x) + 12:
                t = reach(x, y)
                px[x, y] = rim(max(t, RIM[0][0]))
    return flatten(im, 2)


def core_at(hour):
    for (h0, c0), (h1, c1) in zip(SKY, SKY[1:] + ((24, SKY[0][1]),)):
        if h0 <= hour < h1:
            return c0
    return SKY[-1][1]


# the box of the light in the middle: everything inside reach 0.42 of the ellipse
MID = (int(CX - RX * 0.42), int(CY - RY * 0.42), int(math.ceil(CX + RX * 0.42)), int(math.ceil(CY + RY * 0.42)))


def sky(core):
    """The middle of the sky for one hour: from the core at the centre to the rim colour at
    reach 0.42, where it meets the still sky without an edge."""
    l, t, r, b = MID
    im = Image.new('RGBA', (r - l, b - t), (0, 0, 0, 0))
    px = im.load()
    for y in range(t, b):
        for x in range(l, r):
            d = reach(x, y)
            if d < RIM[0][0]:
                px[x - l, y - t] = mix(core, RIM[0][1], d / RIM[0][0]) + (255,)
    return flatten(im, 2)


def figure(ch):
    """One digit, its ink stretched to fill FIG_W x FIG_H."""
    f = font(200 * SS, 640)
    probe = Image.new('L', (300 * SS, 300 * SS), 0)
    ImageDraw.Draw(probe).text((20 * SS, 20 * SS), ch, font=f, fill=255)
    ink = probe.crop(probe.getbbox()).resize((FIG_W, FIG_H), Image.LANCZOS)
    out = Image.new('RGBA', (FIG_W, FIG_H), FIG + (255,))
    out.putalpha(ink)
    return out


def colon():
    big = Image.new('RGBA', (30 * SS, FIG_H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    for fy in (0.32, 0.68):
        cy = FIG_H * fy * SS
        d.rounded_rectangle([8 * SS, cy - 11 * SS, 22 * SS, cy + 11 * SS], radius=2 * SS, fill=FIG + (255,))
    return big.resize((30, FIG_H), Image.LANCZOS)


def seconds(still, s):
    """The second cut out of the sky: the still sky's own pixels, kept only where the
    numerals are, laid over the top of the last figure."""
    l, t, r, b = SEC_BOX
    f = font(SEC_SIZE * SS, 600)
    text = '%02d' % s
    mask = Image.new('L', ((r - l) * SS, (b - t) * SS), 0)
    d = ImageDraw.Draw(mask)
    w = d.textlength(text, font=f)
    bb = f.getbbox(text)
    d.text(((SEC_CX - l) * SS - w / 2, (SEC_CY - t) * SS - (bb[1] + bb[3]) / 2), text, font=f, fill=255)
    mask = mask.resize((r - l, b - t), Image.LANCZOS)
    out = still.crop(SEC_BOX).convert('RGBA')
    out.putalpha(mask)
    return out


def shutters():
    """Both shutters, their inner edges lit by the sky, their shadow falling into the window."""
    big = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0))
    top_mask = Image.new('L', big.size, 0)
    bottom_mask = Image.new('L', big.size, 0)
    steps = 64
    top = [(0, 0), (W * SS, 0)] + [((steps - i) * W * SS / steps, edge_y(TOP_EDGE, (steps - i) * W / steps) * SS)
                                   for i in range(steps + 1)]
    bottom = [(0, H * SS), (W * SS, H * SS)] + [((steps - i) * W * SS / steps,
                                                 edge_y(BOTTOM_EDGE, (steps - i) * W / steps) * SS)
                                                for i in range(steps + 1)]
    ImageDraw.Draw(top_mask).polygon(top, fill=255)
    ImageDraw.Draw(bottom_mask).polygon(bottom, fill=255)
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    # the shadow they cast into the window
    down = top_mask.transform(big.size, Image.AFFINE, (1, 0, 0, 0, 1, -5 * SS))
    up = bottom_mask.transform(big.size, Image.AFFINE, (1, 0, 0, 0, 1, 5 * SS))
    shade = ImageChops.lighter(down, up)
    shade = shade.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * 0.6))
    out.alpha_composite(Image.merge('RGBA', [Image.new('L', (W, H), 0)] * 3 + [shade]))
    # the shutters themselves, darker towards the outside
    for mask, (c0, c1), (y0, y1) in ((top_mask, SHUTTER_TOP, (0, TOP_EDGE[0])),
                                    (bottom_mask, SHUTTER_BOTTOM, (BOTTOM_EDGE[1] - 30, H))):
        grad = Image.new('RGBA', (W, H))
        gp = grad.load()
        for y in range(H):
            c = mix(c0, c1, min(1.0, max(0.0, (y - y0) / float(y1 - y0))))
            for x in range(W):
                gp[x, y] = c + (255,)
        m = mask.resize((W, H), Image.LANCZOS)
        grad.putalpha(m)
        out.alpha_composite(grad)
    # the lit inner edges: brightest in the middle, where the light is
    light = Image.new('RGBA', big.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(light)
    for edge in (TOP_EDGE, BOTTOM_EDGE):
        pts = [(i * W * SS / steps, edge_y(edge, i * W / steps) * SS) for i in range(steps + 1)]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            k = 1 - abs((x0 + x1) / 2 / (W * SS) - 0.5) * 2
            ld.line([(x0, y0), (x1, y1)], fill=(150, 175, 235, int(255 * k ** 1.5)), width=int(1.6 * SS))
    light = light.resize((W, H), Image.LANCZOS)
    out.alpha_composite(light.filter(ImageFilter.GaussianBlur(3)))
    out.alpha_composite(light)
    return flatten(out, 3)


def main(out):
    still = case()
    sh = shutters()
    # the background: the still sky with the shutters, but plain sky across the bands
    back = still.convert('RGBA')
    body = sh.copy()
    for t, b in BANDS:
        body.paste((0, 0, 0, 0), (0, t, W, b))
    back.alpha_composite(body)
    back.convert('RGB').save(os.path.join(out, 'case.png'))
    # the bands: the shutters only across their rows, everything else clear
    band = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for t, b in BANDS:
        band.paste(sh.crop((0, t, W, b)), (0, t))
    made = {}
    for h in range(24):
        c = core_at(h)
        if c not in made:
            made[c] = sky(c)
        made[c].save(os.path.join(out, 'sky-%d.png' % h))
    for v in range(10):
        figure(str(v)).save(os.path.join(out, 'fig-%d.png' % v))
    c = colon()
    for v in range(3):
        c.save(os.path.join(out, 'colon-%d.png' % v))
        band.save(os.path.join(out, 'band-%d.png' % v))
    for s in range(60):
        seconds(still, s).save(os.path.join(out, 'sec-%d.png' % s))


if __name__ == '__main__':
    main(sys.argv[1])
