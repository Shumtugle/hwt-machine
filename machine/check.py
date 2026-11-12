"""Look at a resolved face the way a reader would: what collides, what cannot be read,
what the rounded screen cuts off.

Every element gets a footprint: the union of every picture it can show, at every
place it can show it. Footprints are compared with each other, with the corners of
the screen, with the path of the second mark, and against the background under them.
"""
from PIL import Image, ImageChops, ImageDraw

from . import codes, simulate

INK = 40                 # alpha above which a pixel counts as drawn
OVERLAP_PIXELS = 4       # fewer shared pixels than this are antialiasing, not a collision
CORNER_RADIUS = 64       # estimated rounding of the visible screen; the tick ring follows it
CONTRAST_ERROR = 1.5     # below this a value disappears into its background
CONTRAST_WARNING = 3.0   # below this it is hard to read on a wrist outdoors


def _union_of(ims):
    w = max(i.width for i in ims)
    h = max(i.height for i in ims)
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    for i in ims:
        out.alpha_composite(i)
    return out


def footprint(pieces, size):
    """Everything the pieces can ever draw, composited."""
    canvas = Image.new('RGBA', size, (0, 0, 0, 0))
    for p in pieces:
        if p is None:
            continue
        if p.kind == 'image':
            simulate._put(canvas, p.im, p.x, p.y)
        elif p.kind == 'paint':
            p.fn(canvas)
        elif p.kind == 'list':
            simulate._put(canvas, _union_of(p.ims), p.x, p.y)
        elif p.kind == 'overlay':
            simulate._put(canvas, p.im, p.x, p.y)
        elif p.kind == 'hand':
            # a turning hand may be anywhere on its circle; its colour is the hand's
            col = p.ink[:3] + (255,)
            ImageDraw.Draw(canvas).ellipse([p.cx - p.reach, p.cy - p.reach, p.cx + p.reach, p.cy + p.reach], fill=col)
        elif p.kind == 'number':
            digit = _union_of(p.ims)
            cell = p.ims[0].width
            cells = max(1, p.width // max(1, cell))
            for n in range(1, cells + 1):
                w = n * cell
                x0 = {codes.ALIGN_LEFT: p.x, codes.ALIGN_RIGHT: p.x - w}.get(p.align, p.x - w // 2)
                for k in range(n):
                    simulate._put(canvas, digit, x0 + k * cell, p.y)
                if p.minus is not None:
                    simulate._put(canvas, p.minus, x0 - p.minus.width, p.y)
    return canvas


def mask(im):
    return im.getchannel('A').point(lambda a: 255 if a > INK else 0)


def _count(m):
    return m.histogram()[255]


def _luminance(rgb):
    def ch(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _mean(im, m):
    """Mean colour of im over the white pixels of m."""
    n = _count(m)
    if not n:
        return None
    rgb = im.convert('RGB')
    return tuple(sum(i * v for i, v in enumerate(rgb.getchannel(c).histogram(m))) / float(n) for c in range(3))


def _solid(fp):
    """Pixels where the element is fully itself, not an antialiased edge."""
    return fp.getchannel('A').point(lambda a: 255 if a > 200 else 0)


def _rounded_outside(size):
    w, h = size
    m = Image.new('L', size, 255)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=CORNER_RADIUS, fill=0)
    return m


def _describe(item):
    return '"%s" at %s' % (item['kind'], item['path'])


def inspect(items, plain_bg, mark_area, size, label=''):
    """items: [{'path', 'kind', 'pieces', 'tap_box'}]; plain_bg: the background without
    any element; mark_area: mask the second mark repaints, or None.
    Returns (errors, warnings)."""
    errors, warnings = [], []
    where = (' (%s)' % label) if label else ''
    outside = _rounded_outside(size)
    done = []
    for it in items:
        fp = footprint(it['pieces'], size)
        m = mask(fp)
        if not _count(m):
            continue
        box = list(m.getbbox())

        # the rounded corners of the screen
        cut = ImageChops.multiply(m, outside)
        if _count(cut) >= OVERLAP_PIXELS:
            warnings.append('%s%s: %d px of "%s" fall in a rounded corner of the screen around %s and may be cut '
                            'off; move it inwards' % (it['path'], where, _count(cut), it['kind'], list(cut.getbbox())))

        # the path of the second mark
        if mark_area is not None:
            hit = ImageChops.multiply(m, mark_area)
            if _count(hit) >= OVERLAP_PIXELS:
                errors.append('%s%s: "%s" sits on the path of the second mark around %s; the layer that hides the '
                              'other ten-second strips paints over it. Keep it clear of the path' % (
                                  it['path'], where, it['kind'], list(hit.getbbox())))

        # leaving the tap zone it belongs to
        tb = it.get('tap_box')
        if tb:
            zone = Image.new('L', size, 255)
            ImageDraw.Draw(zone).rectangle([tb[0], tb[1], tb[2] - 1, tb[3] - 1], fill=0)
            out = ImageChops.multiply(m, zone)
            if _count(out) >= OVERLAP_PIXELS:
                warnings.append('%s%s: "%s" reaches outside its tap zone %s (drawn at %s); a touch there '
                                'opens nothing' % (it['path'], where, it['kind'], list(tb), box))

        # other elements
        for other, om in done:
            hit = ImageChops.multiply(m, om)
            n = _count(hit)
            if n >= OVERLAP_PIXELS:
                errors.append('%s%s: %s overlaps %s by %d px around %s; move one of them' % (
                    it['path'], where, _describe(it), _describe(other), n, list(hit.getbbox())))
        done.append((it, m))

        # contrast against what is under it, part by part: a quiet part must not hide in a loud one
        worst = {}
        for p in it['pieces']:
            if p is None:
                continue
            pfp = footprint([p], size)
            solid = _solid(pfp)
            ink, under = _mean(pfp, solid), _mean(plain_bg, solid)
            if ink is None or under is None:
                continue
            role = getattr(p, 'role', None)
            c = contrast(ink, under)
            if role not in worst or c < worst[role][0]:
                worst[role] = (c, ink, under, it.get('quiet') or getattr(p, 'quiet', False))
        for role, (c, ink, under, quiet) in worst.items():
            what = '"%s"%s' % (it['kind'], (' (%s)' % role) if role else '')
            quiet = quiet or role == 'colon'   # an accent, not something to read
            fix = 'make it lighter or the background under it darker' if _luminance(ink) >= _luminance(under) \
                else 'make it darker or the background under it lighter'
            if c < CONTRAST_ERROR:
                errors.append('%s%s: %s has contrast %.1f:1 against the background under it and cannot be '
                              'seen; %s' % (it['path'], where, what, c, fix))
            elif c < CONTRAST_WARNING and not quiet:
                warnings.append('%s%s: %s has contrast %.1f:1 against the background under it, hard to read '
                                'outdoors; %s, or add "quiet": true if it is meant to recede' % (
                                    it['path'], where, what, c, fix))
    return errors, warnings
