"""Draws the pictures of Triptych: the case, the lamps of the seconds and the message lamp.

Three windows meet in a black case. Above, a dial of deep pyramids lit from the upper
left runs on under the bezel and ends in an arch turned down, with a polished lip and
applied cream indices; a small ruby lens below the hands lights while messages wait.
In the middle, red lamps sit in sunken dark windows. Below, a crystal display runs on
under the bezel too, its arch rising to meet the dial's. Ten slim glass lamps ride the
crystal's lip and light one a second; after them the tens of seconds already passed.

    python3 make_case.py case.png

writes case.png and, next to it, lamps-0.png ... lamps-9.png, tens-0.png ... tens-5.png,
lamp-0.png and lamp-1.png.
"""
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H, SS = 408, 480, 3
CREAM, CREAM_DIM = (236, 227, 210), (185, 174, 154)
LED, LED_HOT = (255, 58, 34), (255, 196, 170)
PANEL = (33, 196, 375, 316)
WINDOWS = [(28, 230, 116, 282), (132, 230, 276, 282), (292, 230, 380, 282)]   # behind pulse, steps, charge
HUB = (204, 103)                                                               # the hand axis
LAMP = (204, 150)                                                              # the message lamp


def S(pts):
    return [(x * SS, y * SS) for x, y in pts]


def canvas(c=(0, 0, 0, 0), mode='RGBA'):
    return Image.new(mode, (W * SS, H * SS), c)


def vgrad(top, bottom, y0=0, y1=H):
    im = Image.new('RGB', (W * SS, H * SS))
    d = ImageDraw.Draw(im)
    for y in range(H * SS):
        k = min(1.0, max(0.0, (y / SS - y0) / float(y1 - y0)))
        d.line([(0, y), (W * SS, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * k) for i in range(3)))
    return im


def mask(draw_fn):
    m = canvas(0, 'L')
    draw_fn(ImageDraw.Draw(m))
    return m


def shadow(big, m, blur, dx=0, dy=0, alpha=1.0, color=(0, 0, 0)):
    sh = ImageChops.offset(m, int(dx * SS), int(dy * SS)).filter(ImageFilter.GaussianBlur(blur * SS))
    if alpha != 1.0:
        sh = sh.point(lambda a: int(a * alpha))
    big.paste(Image.new('RGB', big.size, color), (0, 0), sh)


def seen(x, y, m):
    """Inside the visible screen, m px in from its edge."""
    i, r = 11 + m, 82 - m
    if not (i <= x <= W - 1 - i and i <= y <= H - 1 - i):
        return False
    for cx, cy in ((i + r, i + r), (W - 1 - i - r, i + r), (i + r, H - 1 - i - r), (W - 1 - i - r, H - 1 - i - r)):
        if ((x < cx) if cx < W / 2 else (x > cx)) and ((y < cy) if cy < H / 2 else (y > cy)) and math.hypot(x - cx, y - cy) > r:
            return False
    return True


def dial_y(x):
    """The dial's lower edge: the crystal's arch turned over."""
    return 150 + 36 * math.sin(math.pi * (x + 4) / 416.0)


def crystal_y(x):
    return 356 - 36 * math.sin(math.pi * (x + 4) / 416.0)


XS = [-4 + 416 * i / 96.0 for i in range(97)]


# ---------------------------------------------------------------- the dial

def pyramids():
    """Square pyramids in rows, each face shaded by how it turns to a light from the upper left."""
    face = Image.new('RGB', (W * SS, H * SS), (10, 10, 10))
    fd = ImageDraw.Draw(face)
    cell = 15 * SS
    tones = {'up': (112, 109, 103), 'left': (74, 72, 68), 'right': (30, 29, 28), 'down': (9, 9, 9)}
    for gy in range(-cell // 2, 240 * SS, cell):
        for gx in range(-cell, W * SS + cell, cell):
            a, b, c, e = gx, gy, gx + cell, gy + cell
            m = (a + cell / 2.0, b + cell / 2.0)
            fd.polygon([(a, b), (c, b), m], fill=tones['up'])
            fd.polygon([(a, b), (a, e), m], fill=tones['left'])
            fd.polygon([(c, b), (c, e), m], fill=tones['right'])
            fd.polygon([(a, e), (c, e), m], fill=tones['down'])
            # the lit ridges catch a thin line of light, the valleys stay black
            fd.line([(a, b), m], fill=(150, 146, 138), width=max(1, SS // 2))
            fd.line([(a, e), (c, e)], fill=(4, 4, 4), width=SS)
    # light falls off towards the bezel, as under a domed glass
    fall = mask(lambda d: d.ellipse(S([(40, -40), (368, 190)]), fill=255)).filter(ImageFilter.GaussianBlur(46 * SS))
    dark = Image.new('RGB', face.size, (4, 4, 4))
    return Image.composite(face, dark, fall.point(lambda v: 90 + v * 165 // 255))


def lip(big, ys, below, highlight_first=True):
    """A polished metal lip along a curve: bands from bright to dark, 4 px wide."""
    d = ImageDraw.Draw(big)
    tones = [(214, 214, 218), (150, 150, 156), (92, 92, 98), (48, 48, 52), (26, 26, 28)]
    if not highlight_first:
        tones = list(reversed(tones))
    for i, t in enumerate(tones):
        off = (i * 0.8) if below else -(i * 0.8)
        d.line(S([(x, y + off) for x, y in ys]), fill=t, width=max(1, int(1.0 * SS)))


def index_bar(big, x0, y0, x1, y1, w, color):
    """An applied index: a bar with a lit face and a shaded face, casting a shadow down and right."""
    ang = math.atan2(y1 - y0, x1 - x0)
    nx, ny = -math.sin(ang), math.cos(ang)

    def quad(o0, o1, grow=0.0):
        return S([(x0 - math.cos(ang) * grow + nx * o0, y0 - math.sin(ang) * grow + ny * o0),
                  (x1 + math.cos(ang) * grow + nx * o0, y1 + math.sin(ang) * grow + ny * o0),
                  (x1 + math.cos(ang) * grow + nx * o1, y1 + math.sin(ang) * grow + ny * o1),
                  (x0 - math.cos(ang) * grow + nx * o1, y0 - math.sin(ang) * grow + ny * o1)])
    sh = mask(lambda d: d.polygon(quad(-w / 2, w / 2, 0.5), fill=255))
    shadow(big, sh, 1.4, 1.6, 2.2, 0.85)
    d = ImageDraw.Draw(big)
    d.polygon(quad(-w / 2, w / 2), fill=color)
    # the face turned to the upper left is lighter, the other darker
    lit_side = 1 if (nx * -0.7 + ny * -0.7) > 0 else -1
    lighter = tuple(min(255, int(c * 1.08) + 8) for c in color)
    darker = tuple(int(c * 0.72) for c in color)
    if w >= 3:
        d.polygon(quad(0, lit_side * w / 2), fill=lighter)
        d.polygon(quad(0, -lit_side * w / 2), fill=darker)
        d.line(S([(x0 + nx * lit_side * w / 2, y0 + ny * lit_side * w / 2),
                  (x1 + nx * lit_side * w / 2, y1 + ny * lit_side * w / 2)]), fill=(255, 250, 238), width=max(1, SS // 2))


def dial(big):
    arch = [(x, dial_y(x)) for x in XS]
    shape = mask(lambda d: d.polygon(S([(-4, -4), (412, -4)] + list(reversed(arch))), fill=255))
    big.paste(pyramids(), (0, 0), shape)
    # the dial stands proud of the band: its shadow on the band, then its lip
    under = mask(lambda d: d.polygon(S([(x, y) for x, y in arch] + [(412, 0), (-4, 0)]), fill=255))
    band_only = ImageChops.subtract(canvas(255, 'L'), under)
    sh = ImageChops.offset(under, 0, 5 * SS).filter(ImageFilter.GaussianBlur(4 * SS))
    big.paste(Image.new('RGB', big.size, (0, 0, 0)), (0, 0), ImageChops.multiply(sh, band_only))
    lip(big, arch, below=True)

    cx, cy = HUB
    for i in range(60):
        th = math.radians(i * 6)
        dx, dy = math.sin(th), -math.cos(th)
        r = 0.0
        while True:
            x, y = cx + dx * (r + 0.25), cy + dy * (r + 0.25)
            if not seen(x, y, 5) or y > dial_y(x) - 8:
                break
            r += 0.25
        if i % 5 == 0:
            index_bar(big, cx + dx * r, cy + dy * r, cx + dx * (r - 16), cy + dy * (r - 16), 5.2, CREAM)
        else:
            index_bar(big, cx + dx * r, cy + dy * r, cx + dx * (r - 5), cy + dy * (r - 5), 1.5, CREAM_DIM)


def ruby(big, lit=False):
    """The message lamp: a domed lens in a polished bezel."""
    x, y = LAMP
    d = ImageDraw.Draw(big)
    if not lit:
        shadow(big, mask(lambda m: m.ellipse(S([(x - 6.5, y - 6.5), (x + 6.5, y + 6.5)]), fill=255)), 1.2, 0.8, 1.6, 0.9)
        d.ellipse(S([(x - 6.5, y - 6.5), (x + 6.5, y + 6.5)]), fill=(120, 120, 124))
        d.ellipse(S([(x - 5.6, y - 5.6), (x + 5.6, y + 5.6)]), fill=(44, 44, 46))
    inner, outer = ((255, 120, 96), (170, 16, 8)) if lit else ((120, 18, 14), (34, 4, 3))
    for k in range(24, 0, -1):
        r = 4.6 * k / 24.0
        t = k / 24.0
        col = tuple(int(inner[j] + (outer[j] - inner[j]) * t) for j in range(3))
        d.ellipse(S([(x - r + 0.6 * (1 - t), y - r + 0.6 * (1 - t)), (x + r + 0.6 * (1 - t), y + r + 0.6 * (1 - t))]), fill=col)
    d.ellipse(S([(x - 2.6, y - 3.0), (x - 0.6, y - 1.4)]), fill=(255, 236, 228) if lit else (196, 150, 146))


# ---------------------------------------------------------------- the band

def band(big):
    soft = mask(lambda d: d.rounded_rectangle(S([(PANEL[0] + 4, PANEL[1] + 4), (PANEL[2] - 4, PANEL[3] - 4)]), radius=20 * SS, fill=255))
    big.paste(vgrad((16, 6, 6), (30, 10, 9)), (0, 0), soft.filter(ImageFilter.GaussianBlur(10 * SS)))
    for x0, y0, x1, y1 in WINDOWS:
        win = mask(lambda d: d.rounded_rectangle(S([(x0, y0), (x1, y1)]), radius=7 * SS, fill=255))
        # a sunken window: dark glass, a shadow cast in from its upper edge, a lit lower lip
        big.paste(Image.new('RGB', big.size, (12, 3, 3)), (0, 0), win)
        inner = ImageChops.subtract(win, ImageChops.offset(win, 0, 5 * SS))
        big.paste(Image.new('RGB', big.size, (0, 0, 0)), (0, 0), inner.filter(ImageFilter.GaussianBlur(3 * SS)))
        edge = ImageChops.subtract(win, ImageChops.offset(win, 0, -1 * SS))
        big.paste(Image.new('RGB', big.size, (74, 40, 36)), (0, 0), edge)
        rim = ImageChops.subtract(ImageChops.offset(win, 0, -1 * SS), win)
        big.paste(Image.new('RGB', big.size, (0, 0, 0)), (0, 0), rim)


# ---------------------------------------------------------------- the crystal

def crystal(big):
    arch = [(x, crystal_y(x)) for x in XS]
    inside = mask(lambda d: d.polygon(S(arch + [(412, 484), (-4, 484)]), fill=255))
    glass = vgrad((178, 184, 160), (150, 158, 134), 320, 480)
    lit = mask(lambda d: d.ellipse(S([(110, 340), (300, 440)]), fill=70)).filter(ImageFilter.GaussianBlur(40 * SS))
    glass = Image.composite(Image.new('RGB', big.size, (198, 204, 180)), glass, lit)
    # a faint reflection across the glass from the upper left
    sheen = mask(lambda d: d.polygon(S([(-10, 470), (60, 330), (130, 330), (40, 480)]), fill=28)).filter(ImageFilter.GaussianBlur(14 * SS))
    glass = Image.composite(Image.new('RGB', big.size, (236, 240, 226)), glass, sheen)
    big.paste(glass, (0, 0), inside)
    # the lip casts its shadow on the reflector behind the crystal
    sh = mask(lambda d: d.line(S([(x, y + 2) for x, y in arch]), fill=150, width=8 * SS))
    big.paste(Image.new('RGB', big.size, (44, 48, 38)), (0, 0), ImageChops.multiply(sh.filter(ImageFilter.GaussianBlur(3.5 * SS)), inside))
    lip(big, [(x, y - 0.5) for x, y in arch], below=False)


# ---------------------------------------------------------------- the seconds

N, GAP, HW, LIFT = 10, 0.30, 3.4, 8.0


def lamp_path(x0=30, x1=338):
    path = [(x0 + (x1 - x0) * i / 400.0, crystal_y(x0 + (x1 - x0) * i / 400.0) - 3.5) for i in range(401)]
    off = []
    for i, (x, y) in enumerate(path):
        xa, ya = path[max(0, i - 1)]
        xb, yb = path[min(len(path) - 1, i + 1)]
        tx, ty = xb - xa, yb - ya
        L = math.hypot(tx, ty)
        nx, ny = ty / L, -tx / L
        off.append((x + nx * LIFT, y + ny * LIFT, nx, ny))
    acc = [0.0]
    for a, b in zip(off, off[1:]):
        acc.append(acc[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))

    def at(s):
        for i in range(1, len(acc)):
            if acc[i] >= s:
                k = (s - acc[i - 1]) / (acc[i] - acc[i - 1])
                a, b = off[i - 1], off[i]
                return tuple(a[j] + (b[j] - a[j]) * k for j in range(4))
        return off[-1]
    return at, acc[-1]


AT, TOTAL = lamp_path()
SPAN = TOTAL / (N - GAP)


def tube(k, h, inset=0.0):
    """The outline of lamp k, h px either side of its axis, with rounded ends."""
    s, e = SPAN * k + inset, SPAN * (k + 1 - GAP) - inset
    pts = []
    steps = 16
    for i in range(steps + 1):
        A = AT(s + (e - s) * i / steps)
        pts.append((A[0] + A[2] * h, A[1] + A[3] * h))
    for i in range(steps + 1):
        A = AT(e - (e - s) * i / steps)
        pts.append((A[0] - A[2] * h, A[1] - A[3] * h))
    return S(pts)


def lamps_at_rest(big):
    d = ImageDraw.Draw(big)
    for k in range(N):
        d.polygon(tube(k, HW), fill=(26, 8, 7))
        d.polygon(tube(k, HW - 0.8, 0.8), fill=(46, 14, 11))
        d.polygon(tube(k, 0.6, 2.0), fill=(70, 30, 26))       # the cold filament


def lit(count):
    glow = canvas()
    gd = ImageDraw.Draw(glow)
    body = canvas()
    bd = ImageDraw.Draw(body)
    for k in range(count):
        gd.polygon(tube(k, HW), fill=LED + (255,))
        for h, col in ((HW, (196, 24, 14)), (HW * 0.72, (255, 64, 38)), (HW * 0.42, (255, 132, 104)), (HW * 0.16, LED_HOT)):
            bd.polygon(tube(k, h, (HW - h) * 0.6), fill=col + (255,))
    out = canvas()
    for blur, strength in ((6, 0.55), (2, 0.8)):
        g = glow.filter(ImageFilter.GaussianBlur(blur * SS))
        g.putalpha(g.getchannel('A').point(lambda a, s=strength: int(a * s)))
        out.alpha_composite(g)
    out.alpha_composite(body)
    return out.resize((W, H), Image.LANCZOS)


def tens(v):
    root = os.environ.get('HWT_ROOT') or os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    sys.path.insert(0, root)
    from machine import draw
    st = draw.Style(os.path.join(root, 'fonts', 'Oswald.ttf'), 20, 300, LED + (255,))
    im = st.render('%d0' % v)
    pad = 6
    out = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    out.alpha_composite(im, (pad, pad))
    halo = out.filter(ImageFilter.GaussianBlur(2.2))
    halo.putalpha(halo.getchannel('A').point(lambda a: int(a * 0.8)))
    halo.alpha_composite(out)
    return halo


def message_lamp():
    on = canvas()
    x, y = LAMP
    glow = canvas()
    ImageDraw.Draw(glow).ellipse(S([(x - 7, y - 7), (x + 7, y + 7)]), fill=LED + (255,))
    for blur, strength in ((7, 0.7), (2.5, 0.7)):
        g = glow.filter(ImageFilter.GaussianBlur(blur * SS))
        g.putalpha(g.getchannel('A').point(lambda a, s=strength: int(a * s)))
        on.alpha_composite(g)
    lens = Image.new('RGB', on.size, (0, 0, 0))
    ruby(lens, lit=True)
    lm = mask(lambda d: d.ellipse(S([(x - 4.7, y - 4.7), (x + 4.7, y + 4.7)]), fill=255))
    lens = lens.convert('RGBA')
    lens.putalpha(lm)
    on.alpha_composite(lens)
    return on.resize((W, H), Image.LANCZOS)


def main(out):
    big = vgrad((10, 10, 10), (0, 0, 0))
    band(big)
    dial(big)
    ruby(big)
    crystal(big)
    lamps_at_rest(big)
    big.resize((W, H), Image.LANCZOS).save(out)
    folder = os.path.dirname(os.path.abspath(out))
    frames = [lit(k) for k in range(N)]
    box = frames[-1].getchannel('A').getbbox()
    for k, im in enumerate(frames):
        im.crop(box).save(os.path.join(folder, 'lamps-%d.png' % k))
    ims = [tens(v) for v in range(6)]
    w, h = max(i.width for i in ims), max(i.height for i in ims)
    for v, im in enumerate(ims):
        c = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        c.alpha_composite(im, ((w - im.width) // 2, 0))
        c.save(os.path.join(folder, 'tens-%d.png' % v))
    on = message_lamp()
    lbox = on.getchannel('A').getbbox()
    Image.new('RGBA', (lbox[2] - lbox[0], lbox[3] - lbox[1]), (0, 0, 0, 0)).save(os.path.join(folder, 'lamp-0.png'))
    on.crop(lbox).save(os.path.join(folder, 'lamp-1.png'))
    end = AT(TOTAL)
    print('lamps', box[:2], 'tens', (w, h), 'end', (round(end[0]), round(end[1])), 'lamp', lbox[:2])


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'case.png')
