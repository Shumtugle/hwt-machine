"""Drawing helpers: text with shared baselines, symbols, glass cards, a tick ring.

Vertical placement always uses the visible ink of glyphs, never font metrics, so
digits, capitals and symbols line up the way the eye expects.
"""
import math

from PIL import Image, ImageChops, ImageDraw, ImageFont


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
    d.rounded_rectangle([ss, ss, body_w, h * ss - ss], radius=5 * ss, outline=color, width=2 * ss)
    d.rounded_rectangle([body_w + ss, h * ss // 2 - 4 * ss, w * ss - ss, h * ss // 2 + 4 * ss],
                        radius=2 * ss, fill=color)
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
