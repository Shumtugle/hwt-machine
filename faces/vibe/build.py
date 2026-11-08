"""Vibe: black and scarlet, glass cards, the date in words, time with seconds,
battery, weather, pulse and steps, and a cream mark running around the frame.

Usage: python3 faces/vibe/build.py [locale ... | all] [--switchable ru,en,fi] [--out DIR]
Writes one package per locale, one whose language is picked on the watch,
and PNG previews of both screen modes.
"""
import argparse
import io
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw  # noqa: E402

from machine import codes, container, draw, effects, layout, simulate  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_TEXT = os.path.join(ROOT, 'fonts', 'Oswald.ttf')
SYMBOLS = draw.Symbols(os.path.join(ROOT, 'fonts', 'Symbols.ttf'), os.path.join(ROOT, 'fonts', 'symbols.codepoints'))

TITLE = 'Vibe'
CHOICE_FUNCTIONS = [codes.FUNCTION_DATE, codes.FUNCTION_WEEKDAY, codes.FUNCTION_SUN]  # one per language slot
AUTHOR = 'vibe'
SCREEN = 'HWHD13'
FORMAT_VERSION = '2.5.1'
W, H = 408, 480

# palette
CREAM = (236, 224, 200, 255)        # text and light symbols, a soft cream
SCARLET = (255, 40, 60, 255)        # accents
SCARLET_SOFT = (255, 104, 112, 255)
SECONDS = (198, 34, 50, 255)        # seconds digits, a step quieter than the accents
DIM = (150, 140, 120, 255)          # always-on screen
GLOW = (168, 8, 28)                 # centre of the background glow
TICK = (50, 10, 15, 255)
TICK_MAJOR = (80, 15, 23, 255)

WEATHER = ['cloud_off', 'sunny', 'clear_night', 'cloud', 'partly_cloudy_day', 'rainy',
           'thunderstorm', 'weather_snowy', 'air', 'mist', 'foggy']

CARD_DATE, R_DATE = (24, 24, 384, 124), 24
CARD_TIME, R_TIME = (16, 134, 392, 298), 24
TILES, R_TILE = [(24, 308, 201, 378), (207, 308, 384, 378), (24, 386, 201, 452), (207, 386, 384, 452)], 18


def style(size, weight, color, tracking=0, sample=''):
    return draw.Style(FONT_TEXT, size, weight, color, tracking, sample)


# ---------------------------------------------------------------- the dial of the glass widget
# A square of six hundred units: a fine ring, bars at the quarters, dots at the other
# hours, and two bar hands of the widget's own widths.

HAND_HOUR_INK = (201, 191, 175, 255)
HAND_MINUTE_INK = (236, 228, 214, 255)


def dial_marks(d, ss=6):
    u = d * ss / 600.0
    im = Image.new('RGBA', (d * ss, d * ss), (0, 0, 0, 0))
    g = ImageDraw.Draw(im)
    c = d * ss / 2.0
    r = 268.5 * u
    g.ellipse([c - r, c - r, c + r, c + r], outline=CREAM[:3] + (102,), width=max(1, int(round(3 * u * 1.4))))
    for i in range(12):
        a = math.radians(i * 30)
        sn, cs = math.sin(a), math.cos(a)
        if i % 3 == 0:
            w = 15 * u
            g.line([(c + 221.5 * u * sn, c - 221.5 * u * cs), (c + 242.5 * u * sn, c - 242.5 * u * cs)],
                   fill=CREAM, width=int(round(w)))
            for rr in (221.5, 242.5):
                x, y = c + rr * u * sn, c - rr * u * cs
                g.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=CREAM)
        else:
            x, y, rr = c + 234 * u * sn, c - 234 * u * cs, 9.5 * u
            g.ellipse([x - rr, y - rr, x + rr, y + rr], fill=CREAM)
    return im.resize((d, d), Image.LANCZOS)


def bar_hand(d, width, tip, tail, round_, ink, ss=6):
    """A rounded bar pointing up; returns (image, pivot x, pivot y)."""
    u = d / 600.0
    w = int(math.ceil(width * u)) + 2
    h = int(math.ceil((tip + tail) * u)) + 2
    im = Image.new('RGBA', (w * ss, h * ss), (0, 0, 0, 0))
    r = min(round_, width / 2.0) * u * ss
    x0 = (w * ss - width * u * ss) / 2.0
    ImageDraw.Draw(im).rounded_rectangle([x0, ss, x0 + width * u * ss, ss + (tip + tail) * u * ss], radius=r, fill=ink)
    return im.resize((w, h), Image.LANCZOS), w // 2, int(round(1 + tip * u))


def load_locale(locale):
    with open(os.path.join(HERE, 'locale', locale + '.json'), encoding='utf-8') as fh:
        return json.load(fh)


def build(locales, dial=False):
    """One locale: words drawn straight into the date card. Several: the words become
    choices the wearer switches in the face editor; the first one is the default."""
    langs = [load_locale(l) for l in locales]
    names = langs[0]
    words = [w for n in langs for w in n['weekdays'] + n['months']]
    suffixes = [n.get('day_suffix', '') for n in langs]
    face = layout.Face(W, H)
    aod_bg = face.add(Image.new('RGBA', (W, H), (0, 0, 0, 255)), 'aod_bg')

    # --- background: glow, glass cards, dim ticks
    ring = draw.Ring(W, H)
    bg = draw.glow(W, H, GLOW)
    for box, rad in [(CARD_DATE, R_DATE), (CARD_TIME, R_TIME)] + [(t, R_TILE) for t in TILES]:
        if not ring.clear(box, rad):
            raise ValueError('card %s runs into the ticks' % (box,))
        draw.glass(bg, box, radius=rad)
    bg.alpha_composite(ring.draw_ticks(range(60), lambda i: TICK_MAJOR if ring.ticks[i][2] else TICK))
    mark_items = effects.running_mark(face, bg, ring, radius=4.2, color=CREAM)

    # --- date card: day number, weekday above month beside it
    x0, y0, x1, y1 = CARD_DATE
    cy = (y0 + y1) / 2.0
    s_day = style(64 if dial else 74, 600, CREAM, sample=''.join(suffixes))
    day_digits, day_cell = s_day.digits()
    dots = [s_day.render(sfx) if sfx else None for sfx in suffixes]
    day_right = x0 + (10 if dial else 14) + 2 * day_cell
    col = day_right + max([d.width for d in dots if d] or [0]) + 12
    words_right = x1 - 16
    if dial:
        dial_d = (y1 - y0) - 14
        dial_cx, dial_cy = x1 - 10 - dial_d // 2, int(round(cy))
        words_right = dial_cx - dial_d // 2 - 10
    weekdays = [w for n in langs for w in n['weekdays']]
    months = [m for n in langs for m in n['months']]
    s_week = draw.fit_style(FONT_TEXT, weekdays, words_right - col, 32, 500, CREAM)
    s_month = draw.fit_style(FONT_TEXT, months, words_right - col, s_week.size, 500, SCARLET_SOFT)
    size = min(s_week.size, s_month.size)
    s_week = style(size, 500, CREAM, 1, ''.join(words))
    s_month = style(size, 500, SCARLET_SOFT, 1, ''.join(words))
    day_y = s_day.top_for_digits_centred_on(cy)
    d_top, d_bot = day_y + s_day.digit_ink[0], day_y + s_day.digit_ink[1]
    week_y = d_top - s_week.cap_ink[0]
    month_y = d_bot - s_month.cap_ink[1]
    date_items = [
        layout.number(face.add_set(day_digits, 'day'), day_right, day_y, codes.ALIGN_RIGHT, codes.DAY_OF_MONTH),
    ]
    slots, choices = [], []
    if len(langs) == 1:
        week_refs = face.add_set([s_week.render(t) for t in names['weekdays']], 'week')
        month_refs = face.add_set([s_month.render(t) for t in names['months']], 'month')
        date_items += [
            layout.image_list([week_refs[0]] + week_refs, col, week_y, codes.WEEKDAY),
            layout.image_list([month_refs[0]] + month_refs, col, month_y, codes.MONTH),
        ]
        if dots[0]:
            bg.alpha_composite(dots[0], (day_right, day_y))
    else:
        zone = (day_right, y0 + 6, words_right + 4, y1 - 6)
        zx, zy = zone[0], zone[1]
        zw, zh = zone[2] - zone[0], zone[3] - zone[1]
        frame = Image.new('RGBA', (zw, zh), (0, 0, 0, 0))
        ImageDraw.Draw(frame).rounded_rectangle([1, 1, zw - 2, zh - 2], radius=12, outline=SCARLET, width=2)
        frame_ref = face.add(frame, 'choice_frame')
        for i, (n, d) in enumerate(zip(langs, dots)):
            week_refs = face.add_set([s_week.render(t) for t in n['weekdays']], ('week', i))
            month_refs = face.add_set([s_month.render(t) for t in n['months']], ('month', i))
            items = [
                layout.slot_image_list([week_refs[0]] + week_refs, col - zx, week_y - zy, codes.WEEKDAY),
                layout.slot_image_list([month_refs[0]] + month_refs, col - zx, month_y - zy, codes.MONTH),
            ]
            thumb = Image.new('RGBA', (zw, zh), (0, 0, 0, 0))
            thumb.alpha_composite(s_week.render(n['weekdays'][6]), (col - zx, week_y - zy))
            thumb.alpha_composite(s_month.render(n['months'][10]), (col - zx, month_y - zy))
            if d:
                items.append(layout.slot_image(face.add(d, ('dot', i)), 0, day_y - zy))
                thumb.alpha_composite(d, (0, day_y - zy))
            slots.append(layout.slot(i, items, face.add(thumb, ('thumb', i)), frame_ref, CHOICE_FUNCTIONS[i % len(CHOICE_FUNCTIONS)]))
        choices.append((zone, list(range(len(langs))), 0))

    # --- time card: HH:MM as large as fits, seconds smaller and quieter on the same baseline
    x0, y0, x1, y1 = CARD_TIME
    colon_w, gap = 26, 10
    for size in range(124, 90, -2):
        s_time = style(size, 600, CREAM)
        s_sec = style(int(size * 0.32), 500, SECONDS)
        t_digits, t_cell = s_time.digits(extra_pad=2)
        sec_digits, sec_cell = s_sec.digits(extra_pad=1)
        total = 4 * t_cell + colon_w + gap + 2 * sec_cell
        if total <= x1 - x0 - 24:
            break
    t_refs = face.add_set(t_digits, 'time')
    sec_refs = face.add_set(sec_digits, 'sec')
    tx = (W - total) // 2
    ty = s_time.top_for_digits_centred_on((y0 + y1) / 2.0)
    t_top, t_bot = ty + s_time.digit_ink[0], ty + s_time.digit_ink[1]
    xs = [tx, tx + t_cell, tx + 2 * t_cell + colon_w, tx + 3 * t_cell + colon_w]
    sx = xs[3] + t_cell + gap
    sy = t_bot - s_sec.digit_ink[1]
    draw.colon(bg, tx + 2 * t_cell + colon_w / 2.0, t_top, t_bot, 5.5, SCARLET)
    dial_items = []
    if dial:
        bg.alpha_composite(dial_marks(dial_d), (dial_cx - dial_d // 2, dial_cy - dial_d // 2))
        h_img, hpx, hpy = bar_hand(dial_d, 43, 150, 16, 21.5, HAND_HOUR_INK)
        m_img, mpx, mpy = bar_hand(dial_d, 27, 215, 16, 10, HAND_MINUTE_INK)
        pin = draw.dot(max(7, int(dial_d * 0.075)), SCARLET)
        dial_items = [
            layout.hand(face.add(h_img, 'hand_h'), dial_cx, dial_cy, hpx, hpy, codes.HAND_HOUR),
            layout.hand(face.add(m_img, 'hand_m'), dial_cx, dial_cy, mpx, mpy, codes.HAND_MINUTE),
            layout.image(face.add(pin, 'pin'), dial_cx - pin.width // 2, dial_cy - pin.height // 2),
        ]
    time_items = mark_items + dial_items + [
        layout.image_list(t_refs[0:3], xs[0], ty, codes.HOUR_TENS),
        layout.image_list(t_refs, xs[1], ty, codes.HOUR_UNITS),
        layout.image_list(t_refs[0:6], xs[2], ty, codes.MINUTE_TENS),
        layout.image_list(t_refs, xs[3], ty, codes.MINUTE_UNITS),
        layout.image_list(sec_refs[0:6], sx, sy, codes.SECOND_TENS),
        layout.image_list(sec_refs, sx + sec_cell, sy, codes.SECOND_UNITS),
    ]

    # --- tiles: symbol on the left, value on the right, one centre line
    s_val = style(32, 500, CREAM, sample='%°')
    v_refs = face.add_set(s_val.digits()[0], 'val')
    minus_ref = face.add(s_val.render('-'), 'minus')
    zones = []

    def mid(box):
        return (box[1] + box[3]) / 2.0

    def symbol_at(box, im):
        return box[0] + 16, int(round(mid(box) - im.height / 2.0))

    b = TILES[0]
    bat = [draw.battery(i, CREAM, SCARLET) for i in range(11)]
    vy = s_val.top_for_digits_centred_on(mid(b))
    pct = s_val.render('%')
    bg.alpha_composite(pct, (b[2] - 16 - pct.width, vy))
    zones.append((codes.OPEN_SETTINGS, b, [
        layout.image_list(face.add_set(bat, 'battery'), *symbol_at(b, bat[10]), codes.BATTERY_LEVEL),
        layout.number(v_refs, b[2] - 18 - pct.width, vy, codes.ALIGN_RIGHT, codes.BATTERY_PERCENT),
    ]))

    b = TILES[1]
    wx = SYMBOLS.same_box(WEATHER, 38, CREAM)
    vy = s_val.top_for_digits_centred_on(mid(b))
    deg = s_val.render('°')
    bg.alpha_composite(deg, (b[2] - 14 - deg.width, vy))
    zones.append((codes.OPEN_WEATHER, b, [
        layout.image_list(face.add_set(wx, 'weather'), *symbol_at(b, wx[0]), codes.WEATHER_ICON),
        layout.number(v_refs, b[2] - 16 - deg.width, vy, codes.ALIGN_RIGHT, codes.TEMPERATURE, minus=minus_ref),
    ]))

    b = TILES[2]
    heart = SYMBOLS.get('favorite', 34, SCARLET)
    bg.alpha_composite(heart, symbol_at(b, heart))
    zones.append((codes.OPEN_HEART_RATE, b, [layout.number(
        v_refs, b[2] - 16, s_val.top_for_digits_centred_on(mid(b)), codes.ALIGN_RIGHT, codes.HEART_RATE)]))

    b = TILES[3]
    steps = SYMBOLS.get('footprint', 32, SCARLET_SOFT)
    bg.alpha_composite(steps, symbol_at(b, steps))
    zones.append((codes.OPEN_STEPS, b, [layout.number(
        v_refs, b[2] - 16, s_val.top_for_digits_centred_on(mid(b)), codes.ALIGN_RIGHT, codes.STEPS)]))

    # --- always-on screen: black, thin time without seconds, quiet date
    a_time = style(118, 300, DIM)
    a_day = style(54, 400, DIM, sample=suffixes[0])
    a_word = style(26, 400, DIM, 1, ''.join(words))
    at_digits, at_cell = a_time.digits(extra_pad=2)
    at_refs = face.add_set(at_digits, 'aod_time')
    acolon = Image.new('RGBA', (colon_w, a_time.height), (0, 0, 0, 0))
    draw.colon(acolon, colon_w / 2.0, a_time.digit_ink[0], a_time.digit_ink[1], 4, (150, 20, 34, 255))
    ax = (W - (4 * at_cell + colon_w)) // 2
    aty = a_time.top_for_digits_centred_on(240)
    time_items += [
        layout.image_list(at_refs[0:3], ax, aty, codes.HOUR_TENS, aod=1),
        layout.image_list(at_refs, ax + at_cell, aty, codes.HOUR_UNITS, aod=1),
        layout.image(face.add(acolon, 'aod_colon'), ax + 2 * at_cell, aty, aod=1),
        layout.image_list(at_refs[0:6], ax + 2 * at_cell + colon_w, aty, codes.MINUTE_TENS, aod=1),
        layout.image_list(at_refs, ax + 3 * at_cell + colon_w, aty, codes.MINUTE_UNITS, aod=1),
    ]
    ad_digits, ad_cell = a_day.digits()
    aw = face.add_set([a_word.render(t) for t in names['weekdays']], 'aod_week')
    am = face.add_set([a_word.render(t) for t in names['months']], 'aod_month')
    ady = a_day.top_for_digits_centred_on(100)
    a_top, a_bot = ady + a_day.digit_ink[0], ady + a_day.digit_ink[1]
    a_right = 40 + 2 * ad_cell
    a_dot = a_day.render(suffixes[0]) if suffixes[0] else None
    acol = a_right + (a_dot.width if a_dot else 0) + 12
    date_items += [
        layout.number(face.add_set(ad_digits, 'aod_day'), a_right, ady, codes.ALIGN_RIGHT, codes.DAY_OF_MONTH, aod=1),
        layout.image_list([aw[0]] + aw, acol, a_top - a_word.cap_ink[0], codes.WEEKDAY, aod=1),
        layout.image_list([am[0]] + am, acol, a_bot - a_word.cap_ink[1], codes.MONTH, aod=1),
    ]
    if a_dot:
        date_items.append(layout.image(face.add(a_dot, 'aod_dot'), a_right, ady, aod=1))

    face.set_reserved(layout.BACKGROUND, bg)
    background = [layout.image(layout.BACKGROUND, 0, 0), layout.image(aod_bg, 0, 0, aod=1)]
    return face, layout.layout(TITLE, background, zones, date_items, time_items, slots, choices)


def jpeg(im, size):
    buf = io.BytesIO()
    im.convert('RGB').resize(size, Image.LANCZOS).save(buf, 'JPEG', quality=92)
    return buf.getvalue()


def package(locales, out_dir, name, dial=False):
    face, lay = build(locales, dial)
    blank = Image.new('RGBA', (W, H))
    face.set_reserved(layout.THUMB, blank.resize((240, 282)))
    face.set_reserved(layout.PREVIEW, blank)
    # previews come from the simulator reading the packed binary, then go back inside it
    first = container.pack(lay, face.images)
    normal = simulate.render(first)
    aod = simulate.render(first, aod=True)
    face.set_reserved(layout.THUMB, normal.resize((240, 282), Image.LANCZOS))
    face.set_reserved(layout.PREVIEW, normal)
    binary = container.pack(lay, face.images)
    previews = {
        'cover.jpg': jpeg(normal, (816, 960)),
        'icon_small.jpg': jpeg(normal, (332, 390)),
        'aod.jpg': jpeg(aod, (816, 960)),
    }
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, name)
    container.write_package(base + '.hwt', binary, TITLE, AUTHOR, SCREEN, FORMAT_VERSION, previews)
    normal.convert('RGB').save(base + '.png')
    aod.convert('RGB').save(base + '-aod.png')
    return base + '.hwt', len(binary), len(face.images)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('locales', nargs='*', default=['all'],
                    help='locales to build one face each, or "all"')
    ap.add_argument('--switchable', default='',
                    help='also build one face with these locales as editor choices')
    ap.add_argument('--dial', action='store_true', help='the glass widget\'s dial in the date card')
    ap.add_argument('--out', default=os.path.join(ROOT, 'dist'))
    a = ap.parse_args()
    available = sorted(n[:-5] for n in os.listdir(os.path.join(HERE, 'locale')) if n.endswith('.json'))
    wanted = available if a.locales == ['all'] else a.locales
    stem = 'vibe-dial' if a.dial else 'vibe'
    jobs = [([loc], '%s-%s' % (stem, loc)) for loc in wanted]
    if a.switchable:
        jobs.append((a.switchable.split(','), stem))
    for locales, name in jobs:
        path, size, count = package(locales, a.out, name, a.dial)
        print('%s  %d bytes  %d images  %s' % (os.path.relpath(path, ROOT), size, count, '+'.join(locales)))


if __name__ == '__main__':
    main()
