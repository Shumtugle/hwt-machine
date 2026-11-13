"""Drawing helpers: text with shared baselines, symbols, glass cards, a tick ring.

Vertical placement always uses the visible ink of glyphs, never font metrics, so
digits, capitals and symbols line up the way the eye expects.
"""
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


def ink(im):
    """(top, bottom) rows of visible pixels."""
    box = im.getchannel('A').getbbox()
    return (box[1], box[3]) if box else (0, im.height)


def variable_font(path, size, shaping=False, **axes):
    """Open a font and set its variation axes by name (e.g. Weight=600). With shaping,
    OpenType features (such as lining figures) can be asked for when drawing."""
    f = ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM if shaping else ImageFont.Layout.BASIC)
    try:
        current = f.get_variation_axes()
    except OSError:
        return f
    vals = []
    for a in current:
        name = a['name'].decode() if isinstance(a['name'], bytes) else a['name']
        key = name.replace(' ', '')
        vals.append(axes.get(key, a['default']))
    f.set_variation_by_axes(vals)
    return f


class Style:
    """A text style. Every render of one style shares the same box, so glyphs keep a
    common baseline; ink positions of digits and capitals are measured once."""

    BASE_SAMPLE = '0123456789%-HIÄÅ'

    def __init__(self, font_path, size, weight, color, tracking=0, sample='', features=None, fill=None):
        """sample: every character the style will ever render, so the shared box
        has room for the tallest accent and the deepest descender. features: OpenType
        features such as 'lnum'. fill: a function (width, height) -> RGBA image used
        instead of the flat colour, e.g. a gradient."""
        self.size, self.weight, self.color, self.tracking = size, weight, color, tracking
        self.features = features
        self.fill = fill
        self.font = variable_font(font_path, size, shaping=bool(features), Weight=weight)
        kw = {'features': features} if features else {}
        box = self.font.getbbox(self.BASE_SAMPLE + ''.join(sorted(set(sample))), **kw)
        self.top, self.bottom = box[1], box[3]
        self.height = self.bottom - self.top
        self.digit_ink = ink(self.render('0123456789'))
        self.cap_ink = ink(self.render('HIT'))

    def _kw(self):
        return {'features': self.features} if self.features else {}

    def width(self, s):
        if not s:
            return 0
        return sum(self.font.getlength(c, **self._kw()) for c in s) + self.tracking * (len(s) - 1)

    def render(self, s, cell=None):
        """Render s; with cell set the result is exactly cell px wide, text centred."""
        w = int(math.ceil(self.width(s)))
        cw = cell if cell else max(1, w)
        im = Image.new('RGBA', (cw, self.height), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        x = (cw - w) / 2.0
        for c in s:
            d.text((x, -self.top), c, font=self.font, fill=self.color, **self._kw())
            x += self.font.getlength(c, **self._kw()) + self.tracking
        if self.fill:
            painted = self.fill(im.width, im.height)
            painted.putalpha(ImageChops.multiply(painted.getchannel('A'), im.getchannel('A')))
            im = painted
        return im

    def digits(self, extra_pad=0):
        """Ten digit images of one width, so numbers never jitter."""
        cell = int(math.ceil(max(self.font.getlength(str(i), **self._kw()) for i in range(10)))) + extra_pad
        return [self.render(str(i), cell) for i in range(10)], cell

    def top_for_digits_centred_on(self, cy):
        t, b = self.digit_ink
        return int(round(cy - (t + b) / 2.0))


def fit_style(font_path, texts, max_width, size, weight, color, tracking=1, min_size=16):
    """Largest style, starting from size, in which every text fits max_width."""
    sample = ''.join(texts)
    while size > min_size:
        st = Style(font_path, size, weight, color, tracking, sample)
        if max(st.width(t) for t in texts) <= max_width:
            return st
        size -= 1
    return Style(font_path, min_size, weight, color, tracking, sample)


class Symbols:
    """Symbols from a variable icon font addressed by name."""

    def __init__(self, font_path, codepoints_path):
        self.path = font_path
        self.cp = {}
        with open(codepoints_path, encoding='utf-8') as fh:
            for line in fh:
                name, code = line.split()
                self.cp[name] = chr(int(code, 16))

    def get(self, name, size, color, fill=1, weight=500):
        f = variable_font(self.path, size, Fill=fill, Grade=0, OpticalSize=min(48, max(20, size)), Weight=weight)
        im = Image.new('RGBA', (size * 2, size * 2), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((size // 2, size // 2), self.cp[name], font=f, fill=color)
        return im.crop(im.getchannel('A').getbbox())

    def same_box(self, names, size, color, fill=1):
        """Several symbols on one canvas size, each centred, so a list never jumps."""
        ims = [self.get(n, size, color, fill) for n in names]
        bw = max(i.width for i in ims)
        bh = max(i.height for i in ims)
        out = []
        for i in ims:
            c = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
            c.alpha_composite(i, ((bw - i.width) // 2, (bh - i.height) // 2))
            out.append(c)
        return out


def battery(level, color, low_color, w=40, h=22, ss=4):
    """level 0..10 -> outlined cell with proportional fill."""
    im = Image.new('RGBA', (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    body_w = (w - 4) * ss
    shell = low_color if level <= 1 else color   # under a fifth the whole cell warns
    d.rounded_rectangle([ss, ss, body_w, h * ss - ss], radius=5 * ss, outline=shell, width=2 * ss)
    d.rounded_rectangle([body_w + ss, h * ss // 2 - 4 * ss, w * ss - ss, h * ss // 2 + 4 * ss],
                        radius=2 * ss, fill=shell)
    inner = [4 * ss, 4 * ss, body_w - 3 * ss, h * ss - 4 * ss]
    if level > 0:
        span = inner[2] - inner[0]
        d.rounded_rectangle([inner[0], inner[1], inner[0] + span * level // 10, inner[3]], radius=2 * ss,
                            fill=low_color if level <= 2 else color)
    return im.resize((w, h), Image.LANCZOS)


def dot(diameter, color, ss=8):
    im = Image.new('RGBA', (diameter * ss, diameter * ss), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([ss // 2, ss // 2, diameter * ss - ss // 2, diameter * ss - ss // 2], fill=color)
    return im.resize((diameter, diameter), Image.LANCZOS)


def colon(img, cx, top, bottom, r, color, spread=0.22):
    """Two dots whose midpoint sits on the middle of the visible digits."""
    mid = (top + bottom) / 2.0
    off = (bottom - top) * spread
    d = ImageDraw.Draw(img)
    for cy in (mid - off, mid + off):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)


# ---------------------------------------------------------------- surfaces

def glow(width, height, color, centre=(0.5, 0.47), reach=(0.80, 0.66), power=1.5, edge=(6, 70)):
    """Radial glow that falls to pure black well before the screen edge."""
    cx, cy = width * centre[0], height * centre[1]
    rx, ry = width * reach[0], height * reach[1]
    e0, e1 = edge
    px = []
    for y in range(height):
        ey = min(y, height - 1 - y)
        for x in range(width):
            g = max(0.0, 1.0 - math.hypot((x - cx) / rx, (y - cy) / ry)) ** power
            e = min(1.0, max(0.0, (min(x, width - 1 - x, ey) - e0) / float(e1)))
            k = g * e * e * (3 - 2 * e)
            px.append((int(color[0] * k), int(color[1] * k), int(color[2] * k), 255))
    im = Image.new('RGBA', (width, height))
    im.putdata(px)
    return im


def glass(base, box, radius=22, fill_alpha=14, rim_alpha=46):
    """Frosted card: faint fill, hairline rim that fades towards the bottom."""
    x0, y0, x1, y1 = box
    layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=radius, fill=(255, 255, 255, fill_alpha))
    rim = Image.new('RGBA', base.size, (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle(box, radius=radius, outline=(255, 255, 255, rim_alpha), width=1)
    fade = Image.new('L', base.size, 0)
    fd = ImageDraw.Draw(fade)
    for y in range(y0, y1 + 1):
        t = (y - y0) / max(1, (y1 - y0))
        fd.line([(x0, y), (x1, y)], fill=int(255 * (1.0 - 0.75 * t)))
    rim.putalpha(ImageChops.multiply(rim.getchannel('A'), fade))
    base.alpha_composite(layer)
    base.alpha_composite(rim)



def well(base, box, radius=22, depth=150, shade=12, lip_alpha=40):
    """A dark well sunk into the background: the light under it dimmed by depth (0-255),
    a soft shadow cast inward from the upper edge, a hairline lip catching light along
    the lower edge and fading towards the top."""
    x0, y0, x1, y1 = box
    mask = Image.new('L', base.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)
    dark = Image.new('RGBA', base.size, (0, 0, 0, 0))
    dark.putalpha(mask.point(lambda v: v * depth // 255))
    base.alpha_composite(dark)
    if shade > 0:
        lower = Image.new('L', base.size, 0)
        lower.paste(mask.crop((0, 0, base.size[0], base.size[1] - shade)), (0, shade))
        band = ImageChops.subtract(mask, lower).filter(ImageFilter.GaussianBlur(shade / 2.0))
        shadow = Image.new('RGBA', base.size, (0, 0, 0, 0))
        shadow.putalpha(ImageChops.multiply(band, mask))
        base.alpha_composite(shadow)
    lip = Image.new('RGBA', base.size, (0, 0, 0, 0))
    ImageDraw.Draw(lip).rounded_rectangle(box, radius=radius, outline=(255, 255, 255, lip_alpha), width=1)
    fade = Image.new('L', base.size, 0)
    fd = ImageDraw.Draw(fade)
    for y in range(y0, y1 + 1):
        t = (y - y0) / max(1, (y1 - y0))
        fd.line([(x0, y), (x1, y)], fill=int(255 * (0.15 + 0.85 * t)))
    lip.putalpha(ImageChops.multiply(lip.getchannel('A'), fade))
    base.alpha_composite(lip)


class Ring:
    """60 ticks spaced evenly along a rounded rectangle just inside the screen edge,
    starting at top centre, clockwise; 15 seconds land exactly on the right middle."""

    def __init__(self, width, height, inset=3, radius=64, length=(5, 8), thickness=(1.8, 2.6)):
        self.width, self.height = width, height
        self.inset, self.radius = inset, radius
        self.length, self.thickness = length, thickness
        self.ticks = self._ticks()

    def _ticks(self):
        x0, y0 = self.inset, self.inset
        x1, y1 = self.width - 1 - self.inset, self.height - 1 - self.inset
        r = self.radius
        sw, sh = (x1 - x0) - 2 * r, (y1 - y0) - 2 * r
        arc = math.pi * r / 2
        segs = [
            ('line', sw / 2, ((x0 + r + sw / 2, y0), (1, 0), (0, 1))),
            ('arc', arc, ((x1 - r, y0 + r), -math.pi / 2)),
            ('line', sh, ((x1, y0 + r), (0, 1), (-1, 0))),
            ('arc', arc, ((x1 - r, y1 - r), 0.0)),
            ('line', sw, ((x1 - r, y1), (-1, 0), (0, -1))),
            ('arc', arc, ((x0 + r, y1 - r), math.pi / 2)),
            ('line', sh, ((x0, y1 - r), (0, -1), (1, 0))),
            ('arc', arc, ((x0 + r, y0 + r), math.pi)),
            ('line', sw / 2, ((x0 + r, y0), (1, 0), (0, 1))),
        ]
        total = sum(sg[1] for sg in segs)
        out = []
        for i in range(60):
            t = total * i / 60.0
            for kind, length, prm in segs:
                if t <= length + 1e-9:
                    break
                t -= length
            if kind == 'line':
                (sx, sy), (dx, dy), n = prm
                p = (sx + dx * t, sy + dy * t)
            else:
                (cx, cy), a0 = prm
                a = a0 + t / r
                p = (cx + r * math.cos(a), cy + r * math.sin(a))
                n = (-math.cos(a), -math.sin(a))
            out.append((p, n, i % 5 == 0))
        return out

    def clear(self, box, radius, margin=3):
        """True if a rounded box keeps clear of the ticks, corners included."""
        inset = self.inset + self.length[1] + margin
        r_in = self.radius - self.length[1] - margin
        lo_x, hi_x = inset + r_in, self.width - 1 - inset - r_in
        lo_y, hi_y = inset + r_in, self.height - 1 - inset - r_in
        x0, y0, x1, y1 = box
        for k in range(64):
            a = 2 * math.pi * k / 64
            for (cx, cy) in ((x0 + radius, y0 + radius), (x1 - radius, y0 + radius),
                             (x0 + radius, y1 - radius), (x1 - radius, y1 - radius)):
                px, py = cx + radius * math.cos(a), cy + radius * math.sin(a)
                qx, qy = min(max(px, lo_x), hi_x), min(max(py, lo_y), hi_y)
                if math.hypot(px - qx, py - qy) > r_in:
                    return False
        return True

    def draw_ticks(self, indices, color_of, ss=4):
        im = Image.new('RGBA', (self.width * ss, self.height * ss), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for i in indices:
            (px, py), (nx, ny), major = self.ticks[i]
            length = self.length[1] if major else self.length[0]
            width = self.thickness[1] if major else self.thickness[0]
            bx, by = px + nx * length, py + ny * length
            d.line([(px * ss, py * ss), (bx * ss, by * ss)], fill=color_of(i), width=max(1, int(width * ss)))
            for (cx, cy) in ((px, py), (bx, by)):
                rr = width * ss / 2
                d.ellipse([cx * ss - rr, cy * ss - rr, cx * ss + rr, cy * ss + rr], fill=color_of(i))
        return im.resize((self.width, self.height), Image.LANCZOS)

    def ball_centre(self, i):
        (px, py), (nx, ny), _ = self.ticks[i]
        k = self.length[1] / 2.0
        return px + nx * k, py + ny * k

    def draw_balls(self, indices, radius, color, ss=4):
        im = Image.new('RGBA', (self.width * ss, self.height * ss), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        r = radius * ss
        for i in indices:
            cx, cy = self.ball_centre(i)
            d.ellipse([cx * ss - r, cy * ss - r, cx * ss + r, cy * ss + r], fill=color)
        return im.resize((self.width, self.height), Image.LANCZOS)


class Track:
    """Sixty stations along any polyline, for a running mark that does not follow the
    screen's edge: a thread, a slot, a groove. Same interface as Ring for the mark."""

    def __init__(self, width, height, points):
        self.width, self.height = width, height
        self.points = points

    @classmethod
    def line(cls, width, height, start, end, steps=60, decade_gap=0.0):
        """Stations along a straight line. decade_gap adds room after every tenth
        station: the running mark needs its decades apart by more than its own reach,
        or the covering layer clips the mark near a decade's edge."""
        (x0, y0), (x1, y1) = start, end
        length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        breaks = (steps - 1) // 10
        step = (length - breaks * decade_gap) / float(steps - 1)
        pts = []
        for i in range(steps):
            t = (i * step + (i // 10) * decade_gap) / length
            pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        return cls(width, height, pts)

    def ball_centre(self, i):
        return self.points[i]

    def draw_balls(self, indices, radius, color, ss=4):
        im = Image.new('RGBA', (self.width * ss, self.height * ss), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        r = radius * ss
        for i in indices:
            cx, cy = self.points[i]
            d.ellipse([cx * ss - r, cy * ss - r, cx * ss + r, cy * ss + r], fill=color)
        return im.resize((self.width, self.height), Image.LANCZOS)


# ---------------------------------------------------------------- liquid-crystal digits

SEGMENTS_OF = {'0': 'abcdef', '1': 'bc', '2': 'abged', '3': 'abgcd', '4': 'fgbc', '5': 'afgcd',
               '6': 'afgedc', '7': 'abc', '8': 'abcdefg', '9': 'abcdfg', '-': 'g', ' ': ''}


class Segments:
    """Seven-segment digits with the unlit segments faintly visible, as on a crystal
    display. Offers what text styles offer to the face builder: digits in fixed cells,
    the rows of their ink, and pictures of short strings made of digits and '-'."""

    def __init__(self, size, color, ghost=None, aspect=0.5, thickness=0.13, shadow=None, ss=4):
        """shadow: (color, dx, dy, blur) cast by lit segments on the reflector behind them."""
        self.size, self.color, self.ghost, self.shadow = size, color, ghost, shadow
        self.ss = ss
        self.h = size
        self.w = max(4, int(round(size * aspect)))
        self.t = max(2.0, size * thickness)
        self.margin = 1 + (int(math.ceil(max(abs(shadow[1]), abs(shadow[2])) + 2 * shadow[3])) if shadow else 0)
        self.height = self.h + 2 * self.margin
        self.top = 0
        self.digit_ink = self.cap_ink = (self.margin, self.margin + self.h)

    def _polygons(self):
        W, H, T = self.w, self.h, self.t
        g = max(0.9, T * 0.22)
        h2 = T / 2.0

        def horiz(yc):
            x0, x1 = h2 + g, W - h2 - g
            return [(x0, yc), (x0 + h2, yc - h2), (x1 - h2, yc - h2), (x1, yc), (x1 - h2, yc + h2), (x0 + h2, yc + h2)]

        def vert(xc, y0, y1):
            y0, y1 = y0 + g, y1 - g
            return [(xc, y0), (xc + h2, y0 + h2), (xc + h2, y1 - h2), (xc, y1), (xc - h2, y1 - h2), (xc - h2, y0 + h2)]
        return {'a': horiz(h2), 'g': horiz(H / 2.0), 'd': horiz(H - h2),
                'f': vert(h2, h2, H / 2.0), 'b': vert(W - h2, h2, H / 2.0),
                'e': vert(h2, H / 2.0, H - h2), 'c': vert(W - h2, H / 2.0, H - h2)}

    def _cell(self, lit, pad, ghosts=True):
        ss = self.ss
        pad = max(pad, self.margin - 1) if self.shadow else pad
        cw = self.w + 2 * pad
        ox, oy = pad * ss, self.margin * ss
        polys = self._polygons()

        def layer(names, color, dx=0, dy=0):
            im = Image.new('RGBA', (cw * ss, self.height * ss), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            for name in names:
                d.polygon([(ox + (x + dx) * ss, oy + (y + dy) * ss) for x, y in polys[name]], fill=color)
            return im.resize((cw, self.height), Image.LANCZOS)
        out = Image.new('RGBA', (cw, self.height), (0, 0, 0, 0))
        if self.ghost is not None and ghosts:
            out.alpha_composite(layer([n for n in polys if n not in lit], self.ghost))
        if self.shadow and lit:
            col, dx, dy, blur = self.shadow
            sh = layer(lit, col, dx, dy)
            out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)) if blur else sh)
        if lit:
            out.alpha_composite(layer(lit, self.color))
        return out

    def digits(self, extra_pad=0):
        cells = [self._cell(SEGMENTS_OF[str(i)], extra_pad) for i in range(10)]
        return cells, cells[0].width

    def blank(self, extra_pad=0):
        return self._cell('', extra_pad)

    def width(self, s):
        return len(s) * self.w

    def render(self, s, cell=None):
        if any(c not in SEGMENTS_OF for c in s):
            raise ValueError('segment digits draw only 0-9 and -')
        parts = [self._cell(SEGMENTS_OF[c], 1, ghosts=False) for c in s]
        out = Image.new('RGBA', (sum(p.width for p in parts), self.height), (0, 0, 0, 0))
        x = 0
        for p in parts:
            out.alpha_composite(p, (x, 0))
            x += p.width
        return out


# ---------------------------------------------------------------- dials and hands

def lcd_window(size, box, radius, centre, edge, focus=(0.42, 0.38), reach=(0.62, 0.95), power=1.6,
               rim=7, rim_alpha=140, outline=None, ss=4):
    """A lit crystal window: light brightest at focus, fading to edge, a shadow along
    the inside of the rim as if the glass sat below the case, and the case's edge."""
    W, H = size
    l, t, r, b = [int(round(v)) for v in box]
    w, h = r - l, b - t
    field = Image.new('RGBA', (w, h))
    px = []
    for y in range(h):
        for x in range(w):
            k = min(1.0, math.hypot((x - w * focus[0]) / (w * reach[0]), (y - h * focus[1]) / (h * reach[1])))
            k = k ** power
            px.append(tuple(int(centre[i] * (1 - k) + edge[i] * k) for i in range(3)) + (255,))
    field.putdata(px)
    if rim:
        band = Image.new('L', (w, h), 0)
        ImageDraw.Draw(band).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, outline=255, width=rim)
        band = band.filter(ImageFilter.GaussianBlur(rim * 0.6))
        dark = Image.new('RGBA', (w, h), (0, 0, 0, 255))
        dark.putalpha(band.point(lambda v: v * rim_alpha // 255))
        field.alpha_composite(dark)
    mask = Image.new('L', (w * ss, h * ss), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], radius=radius * ss, fill=255)
    field.putalpha(mask.resize((w, h), Image.LANCZOS))
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    out.alpha_composite(field, (l, t))
    if outline:
        edge_im = Image.new('RGBA', (W * ss, H * ss), (0, 0, 0, 0))
        ImageDraw.Draw(edge_im).rounded_rectangle([l * ss, t * ss, r * ss, b * ss], radius=radius * ss,
                                                  outline=outline[0], width=max(1, int(round(outline[1] * ss))))
        out.alpha_composite(edge_im.resize((W, H), Image.LANCZOS))
    return out


def inside_rounded(x, y, box, radius):
    l, t, r, b = box
    if not (l <= x <= r and t <= y <= b):
        return False
    dx = max(l + radius - x, 0, x - (r - radius))
    dy = max(t + radius - y, 0, y - (b - radius))
    return dx * dx + dy * dy <= radius * radius


def edge_point(centre, angle, box, radius):
    """Where a ray from centre at angle (degrees clockwise from 12) leaves a rounded box."""
    cx, cy = centre
    sn, cs = math.sin(math.radians(angle)), -math.cos(math.radians(angle))
    lo, hi = 0.0, float(max(box[2] - box[0], box[3] - box[1]))
    for _ in range(40):
        mid = (lo + hi) / 2.0
        if inside_rounded(cx + sn * mid, cy + cs * mid, box, radius):
            lo = mid
        else:
            hi = mid
    return cx + sn * lo, cy + cs * lo, sn, cs


def band(size, inset, width, radius, ss=4):
    """A rounded band along the edges: 255 inside it, 0 elsewhere."""
    W, H = size
    m = Image.new('L', (W * ss, H * ss), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([inset * ss, inset * ss, (W - inset) * ss - 1, (H - inset) * ss - 1],
                        radius=radius * ss, fill=255)
    i2 = inset + width
    d.rounded_rectangle([i2 * ss, i2 * ss, (W - i2) * ss - 1, (H - i2) * ss - 1],
                        radius=max(radius - width, 0) * ss, fill=0)
    return m.resize((W, H), Image.LANCZOS)


def band_ticks(size, centre, inset, width, radius, minor, major, every=5, ss=4):
    """Sixty ticks across a rounded band, each on the ray from centre at 6 degrees a step,
    so a second hand from the same centre lands on them. minor/major: dicts with
    color, width and length (along the ray, from the outer edge)."""
    W, H = size
    outer = (inset, inset, W - inset, H - inset)
    i2 = inset + width
    inner = (i2, i2, W - i2, H - i2)
    im = Image.new('RGBA', (W * ss, H * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i in range(60):
        t = major if i % every == 0 else minor
        if not t:
            continue
        ox, oy, sn, cs = edge_point(centre, 6 * i, outer, radius)
        ix, iy, _, _ = edge_point(centre, 6 * i, inner, max(radius - width, 0))
        span = math.hypot(ox - ix, oy - iy)
        # stop short of the outer edge by half the tick's width, so its corners stay inside
        ox, oy = ox - sn * t['width'] / 2.0, oy - cs * t['width'] / 2.0
        ln = min(t.get('length', span), span) - t['width'] / 2.0
        x0, y0 = ox - sn * ln, oy - cs * ln
        d.line([x0 * ss, y0 * ss, ox * ss, oy * ss], fill=t['color'], width=max(1, int(round(t['width'] * ss))))
    return im.resize((W, H), Image.LANCZOS)


def dial(size, box, radius, frame=None, minute=None, hour=None, inset=6, centre=None, ss=4):
    """A rounded-rectangle dial: an outline and radial ticks that follow it.
    frame/minute/hour: dicts with color, width (and length for ticks), or None."""
    W, H = size
    im = Image.new('RGBA', (W * ss, H * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    l, t, r, b = box
    if centre is None:
        centre = ((l + r) / 2.0, (t + b) / 2.0)
    fw = frame['width'] if frame else 0
    if frame:
        d.rounded_rectangle([l * ss, t * ss, r * ss, b * ss], radius=radius * ss, outline=frame['color'],
                            width=max(1, int(round(fw * ss))))
    inner = (l + fw + inset, t + fw + inset, r - fw - inset, b - fw - inset)
    inner_r = max(0, radius - fw - inset)
    for i in range(60):
        spec = hour if (hour and i % 5 == 0) else minute
        if not spec:
            continue
        x, y, sn, cs = edge_point(centre, i * 6, inner, inner_r)
        ln = spec['length']
        d.line([(x * ss, y * ss), ((x - sn * ln) * ss, (y - cs * ln) * ss)], fill=spec['color'],
               width=max(1, int(round(spec['width'] * ss))))
    return im.resize((W, H), Image.LANCZOS)


def hand(length, tail, width, color, inner=None, ss=4, shade=None, ridge=None):
    """A rounded bar pointing to 12, optionally with a darker slit along it.
    shade: (color, blur) a soft shadow all round, which turns with the hand unchanged;
    ridge: a colour laid over one half of the bar along its length, so it reads as a
    blade with two faces. Returns (image, pivot x, pivot y)."""
    m = 2 + (int(math.ceil(2.5 * shade[1])) if shade else 0)
    w = int(math.ceil(width)) + 2 * m
    h = int(math.ceil(length + tail)) + 2 * m
    im = Image.new('RGBA', (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0 = (w - width) / 2.0
    py = m + length
    bar = [x0 * ss, m * ss, (x0 + width) * ss, (m + length + tail) * ss]
    if shade:
        sh = Image.new('RGBA', im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle(bar, radius=width / 2.0 * ss, fill=shade[0])
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(shade[1] * ss)))
        d = ImageDraw.Draw(im)
    d.rounded_rectangle(bar, radius=width / 2.0 * ss, fill=color)
    if ridge:
        face = Image.new('RGBA', im.size, (0, 0, 0, 0))
        ImageDraw.Draw(face).rounded_rectangle(bar, radius=width / 2.0 * ss, fill=ridge)
        half = Image.new('L', im.size, 0)
        ImageDraw.Draw(half).rectangle([0, 0, int((x0 + width / 2.0) * ss), im.height], fill=255)
        face.putalpha(ImageChops.multiply(face.getchannel('A'), half))
        im.alpha_composite(face)
        d = ImageDraw.Draw(im)
    if inner:
        iw = width - 2 * inner['inset']
        if iw > 0:
            ix = (w - iw) / 2.0
            y_tip = py - length * inner.get('to', 0.9)
            y_base = py - length * inner.get('from', 0.25)
            d.rounded_rectangle([ix * ss, y_tip * ss, (ix + iw) * ss, y_base * ss], radius=iw / 2.0 * ss,
                                fill=inner['color'])
    return im.resize((w, h), Image.LANCZOS), w / 2.0, py


def pin(rings, ss=8):
    """Concentric discs at the pivot, largest first: [(radius, color), ...]."""
    rmax = max(r for r, _ in rings)
    s = int(math.ceil(2 * rmax)) + 2
    im = Image.new('RGBA', (s * ss, s * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = s * ss / 2.0
    for r, col in rings:
        d.ellipse([c - r * ss, c - r * ss, c + r * ss, c + r * ss], fill=col)
    return im.resize((s, s), Image.LANCZOS)


# ---------------------------------------------------------------- hands of light

def laser(length, core, glow, width=2.0, ss=4):
    """A beam pointing to 12: a hot core, a halo and a wide faint haze, all fading
    in near the pivot. Returns (image, pivot x, pivot y)."""
    layers = ((26.0, 14.0, glow[:3] + (60,)), (9.0, 4.0, glow[:3] + (150,)), (width, 0.0, core))
    m = int(math.ceil(3 * max(b for _, b, _ in layers))) + 2
    w = int(math.ceil(max(lw for lw, _, _ in layers))) + 2 * m
    h = int(math.ceil(length)) + 2 * m
    cx, py = w / 2.0, m + length
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    for lw, blur, col in layers:
        im = Image.new('RGBA', (w * ss, h * ss), (0, 0, 0, 0))
        ImageDraw.Draw(im).line([(cx * ss, py * ss), (cx * ss, m * ss)], fill=col, width=max(1, int(lw * ss)))
        im = im.resize((w, h), Image.LANCZOS)
        if blur:
            im = im.filter(ImageFilter.GaussianBlur(blur))
        out.alpha_composite(im)
    return out, cx, py


def sweep(length, trail, color, edge, edge_width=2.0, start=0.0, ss=None):
    """A radar sweep pointing to 12: a bright leading edge and, behind it (anticlockwise,
    as the sweep turns clockwise), a sector that fades out over trail degrees.
    start leaves the middle empty: the sweep begins that far from the pivot.
    Returns (image, pivot x, pivot y)."""
    ss = ss or (3 if length < 120 else 2)
    m = 4
    trail = max(1.0, min(90.0, float(trail)))
    left = length * math.sin(math.radians(trail)) if trail < 90 else length
    w = int(math.ceil(left + edge_width)) + 2 * m
    h = int(math.ceil(length)) + 2 * m
    px, py = m + left, m + length
    W, H = w * ss, h * ss
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    pix = out.load()
    for y in range(H):
        dy = py * ss - y - 0.5
        for x in range(W):
            dx = x + 0.5 - px * ss
            r = math.hypot(dx, dy) / ss
            if r > length or r < max(0.5, start):
                continue
            a = math.degrees(math.atan2(-dx, dy))        # 0 at the leading edge, growing anticlockwise
            if 0 <= a <= trail:
                k = (1 - a / trail) ** 2
                pix[x, y] = color[:3] + (int(color[3] * k),)
    out = out.resize((w, h), Image.LANCZOS)
    line = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(line).line([(px * ss, (py - start) * ss), (px * ss, (py - length) * ss)], fill=edge,
                              width=max(1, int(round(edge_width * ss))))
    out.alpha_composite(line.resize((w, h), Image.LANCZOS))
    return out, px, py


def cone(length, spread, color, ss=2):
    """A searchlight wedge pointing to 12, brightest at the pivot and fading outwards.
    spread is the half-angle in degrees. Returns (image, pivot x, pivot y)."""
    half = length * math.tan(math.radians(spread))
    m = 8
    w = int(math.ceil(2 * half)) + 2 * m
    h = int(math.ceil(length)) + 2 * m
    cx, py = w / 2.0, m + length
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    steps = 48
    for i in range(steps, 0, -1):
        r = length * i / steps
        k = r * math.tan(math.radians(spread))
        layer = Image.new('RGBA', (w * ss, h * ss), (0, 0, 0, 0))
        ImageDraw.Draw(layer).polygon([(cx * ss, py * ss), ((cx - k) * ss, (py - r) * ss), ((cx + k) * ss, (py - r) * ss)],
                                      fill=color[:3] + (int(color[3] * (1 - i / float(steps)) ** 0.6 / 6),))
        out.alpha_composite(layer.resize((w, h), Image.LANCZOS))
    return out.filter(ImageFilter.GaussianBlur(3)), cx, py
