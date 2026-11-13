"""Draws case.png for Triptych: three windows in a black case.

Above, a chamfered dial cut in small pyramids lit from the upper left, rising out of
the black with no frame; in the middle, smoked glass for red lamps, also frameless;
below, a crystal display with an arched top that runs on under the case at the sides
and the bottom, where the watch's own bezel frames it.

    python3 make_case.py case.png
"""
import math
import sys

from PIL import Image, ImageDraw, ImageFilter

W, H, SS = 408, 480, 3
DIAL, CHAMFER = (40, 22, 368, 204), 44
PANEL, PANEL_RADIUS = (33, 216, 375, 300), 20
CREAM, CREAM_DIM = (236, 227, 210), (185, 174, 154)


def scaled(pts):
    return [(x * SS, y * SS) for x, y in pts]


def octagon(x0, y0, x1, y1, c):
    return [(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c),
            (x1 - c, y1), (x0 + c, y1), (x0, y1 - c), (x0, y0 + c)]


def vgrad(top, bottom):
    im = Image.new('RGB', (W * SS, H * SS))
    d = ImageDraw.Draw(im)
    for y in range(H * SS):
        k = y / (H * SS - 1)
        d.line([(0, y), (W * SS, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * k) for i in range(3)))
    return im


def polygon_mask(pts):
    m = Image.new('L', (W * SS, H * SS), 0)
    ImageDraw.Draw(m).polygon(scaled(pts), fill=255)
    return m


def rounded_mask(box, radius):
    m = Image.new('L', (W * SS, H * SS), 0)
    ImageDraw.Draw(m).rounded_rectangle([v * SS for v in box], radius=radius * SS, fill=255)
    return m


def dial(big):
    face = Image.new('RGB', big.size, (18, 18, 18))
    fd = ImageDraw.Draw(face)
    cell = 13 * SS
    for gy in range(DIAL[1] * SS, DIAL[3] * SS + cell, cell):
        for gx in range(DIAL[0] * SS, DIAL[2] * SS + cell, cell):
            a, b, c, e = gx, gy, gx + cell, gy + cell
            m = (a + cell / 2, b + cell / 2)
            fd.polygon([(a, b), (c, b), m], fill=(74, 72, 68))     # facing the light
            fd.polygon([(a, b), (a, e), m], fill=(50, 49, 46))
            fd.polygon([(c, b), (c, e), m], fill=(28, 27, 26))
            fd.polygon([(a, e), (c, e), m], fill=(12, 12, 12))     # away from it
    # darker towards the edge, as under a domed glass
    inner = polygon_mask(octagon(DIAL[0] + 34, DIAL[1] + 30, DIAL[2] - 34, DIAL[3] - 30, CHAMFER))
    inner = inner.filter(ImageFilter.GaussianBlur(26 * SS))
    face = Image.composite(face, Image.new('RGB', big.size, (6, 6, 6)), Image.eval(inner, lambda v: 110 + v * 145 // 255))
    # no frame: the pattern rises out of the case
    soft = polygon_mask(octagon(DIAL[0] + 6, DIAL[1] + 6, DIAL[2] - 6, DIAL[3] - 6, CHAMFER - 2))
    big.paste(face, (0, 0), soft.filter(ImageFilter.GaussianBlur(16 * SS)))

    # indices where rays from the centre meet the octagon, so each stands at its true angle
    edge = octagon(*DIAL, CHAMFER)
    cx, cy = (DIAL[0] + DIAL[2]) / 2, (DIAL[1] + DIAL[3]) / 2
    d = ImageDraw.Draw(big)
    for i in range(60):
        th = math.radians(i * 6)
        dx, dy = math.sin(th), -math.cos(th)
        r = None
        for j in range(len(edge)):
            (x1, y1), (x2, y2) = edge[j], edge[(j + 1) % len(edge)]
            ex, ey = x2 - x1, y2 - y1
            den = dx * ey - dy * ex
            if abs(den) < 1e-9:
                continue
            t = ((x1 - cx) * ey - (y1 - cy) * ex) / den
            u = ((x1 - cx) * dy - (y1 - cy) * dx) / den
            if t > 0 and 0 <= u <= 1 and (r is None or t < r):
                r = t
        if i % 5 == 0:
            r0, r1, w, col = r - 8, r - 26, 6, CREAM
        else:
            r0, r1, w, col = r - 7, r - 11, 1.4, CREAM_DIM
        d.line([((cx + dx * r0) * SS, (cy + dy * r0) * SS), ((cx + dx * r1) * SS, (cy + dy * r1) * SS)],
               fill=col, width=int(w * SS))


def panel(big):
    x0, y0, x1, y1 = PANEL
    soft = rounded_mask((x0 + 4, y0 + 4, x1 - 4, y1 - 4), PANEL_RADIUS)
    big.paste(vgrad((16, 6, 6), (30, 10, 9)), (0, 0), soft.filter(ImageFilter.GaussianBlur(10 * SS)))


def crystal(big):
    arch = [(-4, 346)] + [(-4 + 416 * i / 48, 346 - 36 * math.sin(math.pi * i / 48)) for i in range(1, 48)] + [(412, 346)]
    shape = arch + [(412, 484), (-4, 484)]
    lip = [(x, y - 3) for x, y in arch] + list(reversed(arch))
    big.paste(vgrad((88, 88, 90), (28, 28, 30)), (0, 0), polygon_mask(lip))
    glass = vgrad((176, 182, 158), (146, 154, 130))
    lit = Image.new('L', big.size, 0)
    ImageDraw.Draw(lit).ellipse([120 * SS, 330 * SS, 290 * SS, 420 * SS], fill=70)
    glass = Image.composite(Image.new('RGB', big.size, (196, 202, 178)), glass, lit.filter(ImageFilter.GaussianBlur(40 * SS)))
    inside = polygon_mask(shape)
    big.paste(glass, (0, 0), inside)
    # the shadow the arched lip casts on the reflector
    sh = Image.new('L', big.size, 0)
    ImageDraw.Draw(sh).line(scaled(arch), fill=120, width=7 * SS)
    sh = Image.composite(sh.filter(ImageFilter.GaussianBlur(3 * SS)), Image.new('L', big.size, 0), inside)
    return Image.composite(Image.new('RGB', big.size, (40, 44, 34)), big, sh)


def main(out):
    big = vgrad((10, 10, 10), (0, 0, 0))
    dial(big)
    panel(big)
    big = crystal(big)
    big.resize((W, H), Image.LANCZOS).save(out)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'case.png')
