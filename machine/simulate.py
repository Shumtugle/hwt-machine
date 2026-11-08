"""Draw a packed watch face the way the watch would, from the binary alone.

This reads the container independently of how it was written, so a preview made
here doubles as a check that the package decodes back into the intended screen.
Element kinds it cannot draw are skipped and reported.
"""
import datetime
import math

from PIL import Image

from . import codes
from .container import unpack


def sample_data(when=None, **values):
    """Data sources for a given moment, plus plausible sensor values."""
    t = when or datetime.datetime(2026, 11, 8, 19, 58, 36)
    d = {
        codes.HOUR_TENS: t.hour // 10, codes.HOUR_UNITS: t.hour % 10,
        codes.MINUTE_TENS: t.minute // 10, codes.MINUTE_UNITS: t.minute % 10,
        codes.SECOND_TENS: t.second // 10, codes.SECOND_UNITS: t.second % 10,
        codes.MONTH: t.month, codes.WEEKDAY: t.isoweekday(),
        codes.DAY_OF_MONTH: t.day, codes.DAY_TENS: t.day // 10, codes.DAY_UNITS: t.day % 10,
        codes.HOURS: t.hour, codes.MINUTES: t.minute, codes.SECONDS: t.second,
        codes.WEATHER_ICON: 4, codes.BATTERY_LEVEL: 8, codes.UNREAD_MESSAGES: 0,
        codes.STEPS: 7645, codes.HEART_RATE: 72, codes.TEMPERATURE: 3, codes.BATTERY_PERCENT: 80,
        codes.CALORIES: 328,
    }
    d['_time'] = t
    d.update(values)
    return d


def _get(node, f, default=None):
    for k, v in node:
        if k == f:
            # some writers store negative coordinates as unsigned 32-bit values
            if isinstance(v, int) and (1 << 31) <= v < (1 << 32):
                v -= 1 << 32
            return v
    return default


def _offset(body, field, origin):
    """Slot elements carry an offset from their zone; others have none."""
    off = _get(body, field)
    if isinstance(off, list) and origin is not None:
        return origin[0] + _get(off, 1, 0), origin[1] + _get(off, 2, 0)
    return 0, 0


def _put(screen, im, x, y):
    """alpha_composite that tolerates pictures hanging off the screen."""
    x, y = int(x), int(y)
    left, top = max(0, -x), max(0, -y)
    right = min(im.width, screen.width - x)
    bottom = min(im.height, screen.height - y)
    if right <= left or bottom <= top:
        return
    screen.alpha_composite(im.crop((left, top, right, bottom)), (x + left, y + top))


def _all(node, f):
    return [v for k, v in node if k == f]


def render(binary, aod=False, data=None, size=(408, 480)):
    data = data or sample_data()
    tree, imgs = unpack(binary)
    screen = Image.new('RGBA', size, (0, 0, 0, 255))
    flag = 1 if aod else 0
    skipped = set()

    blank = Image.new('RGBA', (1, 1), (0, 0, 0, 0))

    def img(ref):
        im = imgs[int(ref) - 1]
        return im if im is not None else blank

    def draw(el, origin=(0, 0)):
        kind = _get(el, 2)
        body = _get(el, codes.BODY_FIELD.get(kind, -1))
        if body is None:
            skipped.add(kind)
            return
        if kind == codes.IMAGE:
            if _get(body, 5, 0) != flag:
                return
            p = _get(body, 2)
            ox, oy = _offset(body, 4, origin)
            _put(screen, img(_get(body, 1)), _get(p, 1, 0) + ox, _get(p, 2, 0) + oy)
        elif kind == codes.IMAGE_LIST:
            if _get(body, 6, 0) != flag:
                return
            refs = _all(body, 1)
            idx = data.get(_get(body, 3))
            if idx is not None and 0 <= idx < len(refs):
                p = _get(body, 2)
                ox, oy = _offset(body, 5, origin)
                _put(screen, img(refs[idx]), _get(p, 1, 0) + ox, _get(p, 2, 0) + oy)
        elif kind == codes.NUMBER:
            if _get(body, 13, 0) != flag:
                return
            refs = _all(body, 1)
            v = data.get(_get(body, 5))
            if v is None:
                return
            parts = [img(refs[int(c)]) for c in str(abs(v))]
            minus = _get(body, 6, '')
            if v < 0 and minus:
                parts.insert(0, img(minus))
            width = sum(p.width for p in parts)
            p = _get(body, 3)
            ox, oy = _offset(body, 10, origin)
            x, y = _get(p, 1, 0) + ox, _get(p, 2, 0) + oy
            align = _get(body, 4, 0)
            if align == codes.ALIGN_RIGHT:
                x -= width
            elif align == codes.ALIGN_CENTER:
                x -= width // 2
            for part in parts:
                _put(screen, part, x, y)
                x += part.width
        elif kind == codes.HAND:
            if _get(body, 9, 0) != flag:
                return
            t = data['_time']
            angle = {
                codes.HAND_HOUR: ((t.hour % 12) + t.minute / 60.0) * 30.0,
                codes.HAND_MINUTE: (t.minute + t.second / 60.0) * 6.0,
                codes.HAND_SECOND: t.second * 6.0,
            }.get(_get(body, 6))
            if angle is None:
                return
            r = _get(body, 2)
            cx = _get(r, 1, 0) + _get(r, 3, 0) / 2.0
            cy = _get(r, 2, 0) + _get(r, 4, 0) / 2.0
            pv = _get(body, 3)
            px, py = _get(pv, 1, 0), _get(pv, 2, 0)
            im = img(_get(body, 1))
            half = int(math.ceil(max(px, im.width - px, py, im.height - py))) + 1
            canvas = Image.new('RGBA', (2 * half, 2 * half), (0, 0, 0, 0))
            canvas.alpha_composite(im, (half - px, half - py))
            rot = canvas.rotate(-angle, resample=Image.BICUBIC)
            _put(screen, rot, int(round(cx - half)), int(round(cy - half)))
        else:
            skipped.add(kind)

    for k, group in tree:
        if k != 1 or not isinstance(group, list):
            continue
        slots = {_get(s, 1): s for f, s in group if f == 7 and isinstance(s, list)}
        for f, item in group:
            if f == 5:
                draw(item)
            elif f == 8 and isinstance(item, list):
                if _get(item, 2) == 1:
                    # choice zone: draw the slot picked by default, relative to the zone
                    chosen = slots.get(_get(item, 4, 0))
                    r = _get(item, 5, [])
                    if chosen:
                        for g, sub in chosen:
                            if g == 2:
                                draw(sub, (_get(r, 1, 0), _get(r, 2, 0)))
                    continue
                for g, sub in item:
                    if g == 6:
                        draw(sub)
    render.skipped = sorted(skipped)
    return screen
