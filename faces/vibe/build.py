"""Vibe: black and scarlet, glass cards, the date in words, time with seconds,
battery, weather, pulse and steps, and a cream mark running around the frame.

Usage: python3 faces/vibe/build.py [locale ... | all] [--out DIR]
Writes one package per locale plus PNG previews of both screen modes.
"""
import argparse
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from PIL import Image  # noqa: E402

from machine import codes, container, draw, effects, layout, simulate  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_TEXT = os.path.join(ROOT, 'fonts', 'Oswald.ttf')
SYMBOLS = draw.Symbols(os.path.join(ROOT, 'fonts', 'Symbols.ttf'), os.path.join(ROOT, 'fonts', 'symbols.codepoints'))

TITLE = 'Vibe'
AUTHOR = 'vibe'
SCREEN = 'HWHD13'
FORMAT_VERSION = '2.5.1'
W, H = 408, 480

# palette
CREAM = (242, 227, 198, 255)        # text and light symbols
SCARLET = (255, 40, 60, 255)        # accents
SCARLET_SOFT = (255, 104, 112, 255)
SECONDS = (198, 34, 50, 255)        # seconds digits, a step quieter than the accents
DIM = (150, 140, 120, 255)          # always-on screen
GLOW = (168, 8, 28)                 # centre of the background glow
TICK = (70, 12, 20, 255)
TICK_MAJOR = (118, 20, 32, 255)

WEATHER = ['cloud_off', 'sunny', 'clear_night', 'cloud', 'partly_cloudy_day', 'rainy',
           'thunderstorm', 'weather_snowy', 'air', 'mist', 'foggy']

CARD_DATE, R_DATE = (24, 24, 384, 124), 24
CARD_TIME, R_TIME = (16, 134, 392, 298), 24
TILES, R_TILE = [(24, 308, 201, 378), (207, 308, 384, 378), (24, 386, 201, 452), (207, 386, 384, 452)], 18


def style(size, weight, color, tracking=0, sample=''):
    return draw.Style(FONT_TEXT, size, weight, color, tracking, sample)


def build(locale):
    names = json.load(open(os.path.join(HERE, 'locale', locale + '.json'), encoding='utf-8'))
    words = names['weekdays'] + names['months']
    suffix = names.get('day_suffix', '')
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
    s_day = style(74, 600, CREAM, sample=suffix)
    day_digits, day_cell = s_day.digits()
    dot = s_day.render(suffix) if suffix else None
    day_right = x0 + 14 + 2 * day_cell
    col = day_right + (dot.width if dot else 0) + 12
    s_week = draw.fit_style(FONT_TEXT, names['weekdays'], x1 - 16 - col, 32, 500, CREAM)
    s_month = draw.fit_style(FONT_TEXT, names['months'], x1 - 16 - col, s_week.size, 500, SCARLET_SOFT)
    size = min(s_week.size, s_month.size)
    s_week = style(size, 500, CREAM, 1, ''.join(words))
    s_month = style(size, 500, SCARLET_SOFT, 1, ''.join(words))
    day_y = s_day.top_for_digits_centred_on(cy)
    d_top, d_bot = day_y + s_day.digit_ink[0], day_y + s_day.digit_ink[1]
    if dot:
        bg.alpha_composite(dot, (day_right, day_y))
    week_refs = face.add_set([s_week.render(t) for t in names['weekdays']], 'week')
    month_refs = face.add_set([s_month.render(t) for t in names['months']], 'month')
    date_items = [
        layout.number(face.add_set(day_digits, 'day'), day_right, day_y, codes.ALIGN_RIGHT, codes.DAY_OF_MONTH),
        layout.image_list([week_refs[0]] + week_refs, col, d_top - s_week.cap_ink[0], codes.WEEKDAY),
        layout.image_list([month_refs[0]] + month_refs, col, d_bot - s_month.cap_ink[1], codes.MONTH),
    ]

    # --- time card: HH:MM as large as fits, seconds smaller and quieter on the same baseline
    x0, y0, x1, y1 = CARD_TIME
    colon_w, gap = 26, 10
    for size in range(124, 90, -2):
        s_time = style(size, 600, CREAM)
        s_sec = style(int(size * 0.42), 500, SECONDS)
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
    time_items = mark_items + [
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
    a_day = style(54, 400, DIM, sample=suffix)
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
    a_dot = a_day.render(suffix) if suffix else None
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
    return face, layout.layout(TITLE, background, zones, date_items, time_items)


def jpeg(im, size):
    buf = io.BytesIO()
    im.convert('RGB').resize(size, Image.LANCZOS).save(buf, 'JPEG', quality=92)
    return buf.getvalue()


def package(locale, out_dir):
    face, lay = build(locale)
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
    base = os.path.join(out_dir, 'vibe-%s' % locale)
    container.write_package(base + '.hwt', binary, TITLE, AUTHOR, SCREEN, FORMAT_VERSION, previews)
    normal.convert('RGB').save(base + '.png')
    aod.convert('RGB').save(base + '-aod.png')
    return base + '.hwt', len(binary), len(face.images)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('locales', nargs='*', default=['all'])
    ap.add_argument('--out', default=os.path.join(ROOT, 'dist'))
    a = ap.parse_args()
    available = sorted(n[:-5] for n in os.listdir(os.path.join(HERE, 'locale')) if n.endswith('.json'))
    wanted = available if a.locales == ['all'] else a.locales
    for loc in wanted:
        path, size, count = package(loc, a.out)
        print('%s  %d bytes  %d images' % (os.path.relpath(path, ROOT), size, count))


if __name__ == '__main__':
    main()
