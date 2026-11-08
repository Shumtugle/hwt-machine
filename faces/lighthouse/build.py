"""Lighthouse: a painted night sea with a lighthouse on a cliff; the time in a warm
serif across the sky, the seconds quiet beneath it, a golden wave with a small boat on
it, and the battery, the weather, the pulse and the steps on the dark water below.

Usage: python3 faces/lighthouse/build.py [locale ... | all] [--switchable ru,en,fi] [--out DIR]
"""
import argparse
import io
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from PIL import Image, ImageChops, ImageDraw, ImageFilter  # noqa: E402

from machine import codes, container, draw, layout, simulate  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_SERIF = os.path.join(ROOT, 'fonts', 'Cormorant.ttf')
SYMBOLS = draw.Symbols(os.path.join(ROOT, 'fonts', 'Symbols.ttf'), os.path.join(ROOT, 'fonts', 'symbols.codepoints'))
ART = os.path.join(HERE, 'art', 'night.jpg')

TITLE = 'Lighthouse'
AUTHOR = 'lighthouse'
NAME = 'lighthouse'
SCREEN = 'HWHD13'
FORMAT_VERSION = '2.5.1'
CHOICE_FUNCTIONS = [codes.FUNCTION_DATE, codes.FUNCTION_WEEKDAY, codes.FUNCTION_SUN]
W, H = 408, 480
LNUM = ['lnum']

GOLD_TOP = (250, 232, 196)
GOLD_BOTTOM = (226, 188, 128)
CREAM = (236, 224, 200, 255)
QUIET = (150, 152, 166, 255)
DIM = (120, 116, 106, 255)
SHADOW = (4, 8, 22)

WEATHER = ['cloud_off', 'sunny', 'clear_night', 'cloud', 'partly_cloudy_day', 'rainy',
           'thunderstorm', 'weather_snowy', 'air', 'mist', 'foggy']


def gold(w, h):
    """Warm vertical gradient for the numerals, lighter at the top."""
    im = Image.new('RGBA', (w, h))
    px = []
    for y in range(h):
        t = y / float(max(1, h - 1))
        c = tuple(int(GOLD_TOP[i] * (1 - t) + GOLD_BOTTOM[i] * t) for i in range(3)) + (255,)
        px.extend([c] * w)
    im.putdata(px)
    return im


def serif(size, weight, color, tracking=0, sample='', fill=None):
    return draw.Style(FONT_SERIF, size, weight, color, tracking, sample, features=LNUM, fill=fill)


def with_shade(im, radius=5, strength=170):
    """The same glyphs over a soft dark halo, so they read against the stars."""
    pad = radius * 2
    out = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    a = Image.new('L', out.size, 0)
    a.paste(im.getchannel('A'), (pad, pad))
    a = a.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: min(255, v * strength // 100))
    shade = Image.new('RGBA', out.size, SHADOW + (255,))
    shade.putalpha(a)
    out.alpha_composite(shade)
    out.alpha_composite(im, (pad, pad))
    return out, pad


def load_locale(locale):
    with open(os.path.join(HERE, 'locale', locale + '.json'), encoding='utf-8') as fh:
        return json.load(fh)


def night():
    """The painting, darkened towards the screen's edges."""
    art = Image.open(ART).convert('RGB').resize((W, H), Image.LANCZOS).convert('RGBA')
    shade = Image.new('L', (W, H), 0)
    px = []
    for y in range(H):
        for x in range(W):
            e = min(x, W - 1 - x, y, H - 1 - y)
            k = min(1.0, max(0.0, (e - 2) / 34.0))
            px.append(int(255 * (1 - k * k * (3 - 2 * k)) * 0.85))
    shade.putdata(px)
    black = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    black.putalpha(shade)
    art.alpha_composite(black)
    # a cleaner night above the time and a calm dark band below the wave for the readings
    veil = Image.new('L', (W, H), 0)
    vp = []
    for y in range(H):
        top = max(0.0, 1.0 - y / 120.0) ** 1.6 * 0.55
        bottom = min(1.0, max(0.0, (y - 336) / 64.0)) * 0.82
        vp.extend([int(255 * max(top, bottom))] * W)
    veil.putdata(vp)
    ink = Image.new('RGBA', (W, H), (3, 6, 18, 255))
    ink.putalpha(veil)
    art.alpha_composite(ink)
    return art


WAVE_BASE, WAVE_AMP, WAVE_LEN, WAVE_PHASE = 382, 9.0, 250.0, 0.9
BOAT_X = 286


def wave_y(x):
    return WAVE_BASE + WAVE_AMP * math.sin(2 * math.pi * x / WAVE_LEN + WAVE_PHASE)


def sea_line(ss=4):
    """A golden wave across the water with a dotted wake under it and a small sailboat
    riding the crest, all in the numerals' warm gold."""
    im = Image.new('RGBA', (W * ss, H * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    xs = [x / 2.0 for x in range(-10, 2 * W + 10)]
    pts = [(x * ss, wave_y(x) * ss) for x in xs]
    d.line(pts, fill=GOLD_BOTTOM + (235,), width=int(1.6 * ss))
    for i in range(0, W + 6, 6):
        x = float(i)
        y = wave_y(x - 14) + 7
        fade = min(1.0, max(0.0, (x - 20) / 120.0)) * min(1.0, max(0.0, (W - 20 - x) / 120.0))
        r = 1.0 * ss
        d.ellipse([x * ss - r, y * ss - r, x * ss + r, y * ss + r], fill=GOLD_TOP + (int(170 * fade),))
    # the boat: hull on the wave, a mainsail and a jib, a pennant
    bx = BOAT_X
    by = wave_y(bx) - 1
    tilt = math.atan(WAVE_AMP * 2 * math.pi / WAVE_LEN * math.cos(2 * math.pi * bx / WAVE_LEN + WAVE_PHASE))

    def rot(x, y):
        c, s_ = math.cos(tilt), math.sin(tilt)
        return ((bx + x * c - y * s_) * ss, (by + x * s_ + y * c) * ss)

    gold = GOLD_TOP + (255,)
    d.polygon([rot(-15, -3), rot(15, -3), rot(10, 3), rot(-11, 3)], fill=GOLD_BOTTOM + (255,))
    d.polygon([rot(-1, -5), rot(-1, -36), rot(13, -6)], fill=gold)
    d.polygon([rot(-3, -6), rot(-3, -30), rot(-14, -7)], fill=GOLD_TOP + (215,))
    d.line([rot(-1, -3), rot(-1, -40)], fill=gold, width=int(1.2 * ss))
    d.polygon([rot(-1, -40), rot(5, -38), rot(-1, -36)], fill=gold)
    out = im.resize((W, H), Image.LANCZOS)
    glow = out.filter(ImageFilter.GaussianBlur(3))
    glow.putalpha(glow.getchannel('A').point(lambda a: a * 3 // 4))
    res = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    res.alpha_composite(glow)
    res.alpha_composite(out)
    return res


def build(locales):
    langs = [load_locale(l) for l in locales]
    names = langs[0]
    face = layout.Face(W, H)
    aod_bg = face.add(Image.new('RGBA', (W, H), (0, 0, 0, 255)), 'aod_bg')
    bg = night()
    bg.alpha_composite(sea_line())

    # --- time: warm serif numerals with a dark halo, as large as fits the sky
    for size in range(200, 80, -2):
        s_time = serif(size, 500, CREAM, fill=gold)
        digits, cell = s_time.digits(extra_pad=2)
        colon = s_time.render(':')
        ink_h = s_time.digit_ink[1] - s_time.digit_ink[0]
        total = 4 * cell + colon.width + 8
        if total <= W - 70 and ink_h <= 112:
            break
    shaded = [with_shade(d) for d in digits]
    pad = shaded[0][1]
    t_refs = face.add_set([s for s, _ in shaded], 'time')
    tx = (W - total) // 2
    tcy = 150
    ty = s_time.top_for_digits_centred_on(tcy)
    xs = [tx, tx + cell, tx + 2 * cell + colon.width + 8, tx + 3 * cell + colon.width + 8]
    c_im, c_pad = with_shade(colon)
    bg.alpha_composite(c_im, (tx + 2 * cell + 4 - c_pad, ty - c_pad))

    # --- seconds: small, grey, beneath
    s_sec = serif(34, 500, QUIET)
    sec_digits, sec_cell = s_sec.digits(extra_pad=1)
    sec_shaded = [with_shade(d, 3, 140) for d in sec_digits]
    sp = sec_shaded[0][1]
    sec_refs = face.add_set([s for s, _ in sec_shaded], 'sec')
    sy = s_sec.top_for_digits_centred_on(ty + s_time.digit_ink[1] + 34)
    sx = W // 2 - sec_cell
    time_items = [
        layout.image_list(t_refs[0:3], xs[0] - pad, ty - pad, codes.HOUR_TENS),
        layout.image_list(t_refs, xs[1] - pad, ty - pad, codes.HOUR_UNITS),
        layout.image_list(t_refs[0:6], xs[2] - pad, ty - pad, codes.MINUTE_TENS),
        layout.image_list(t_refs, xs[3] - pad, ty - pad, codes.MINUTE_UNITS),
        layout.image_list(sec_refs[0:6], sx - sp, sy - sp, codes.SECOND_TENS),
        layout.image_list(sec_refs, sx + sec_cell - sp, sy - sp, codes.SECOND_UNITS),
    ]

    # --- date line: weekday · day month, each language centred on its own
    line_cy, gap = 58, 10

    def date_line(n):
        sfx = n.get('day_suffix', '')
        own = ''.join(n['weekdays'] + n['months']) + sfx + '•'
        for sz in range(28, 14, -1):
            st = serif(sz, 600, CREAM, 3, own)
            dg, dcell = st.digits()
            weeks = [st.width(w) for w in n['weekdays']]
            months = [st.width(m) for m in n['months']]
            dot = st.render(sfx) if sfx else None
            sep = st.render('•')
            week_box = int(math.ceil(max(weeks)))
            fixed = week_box + gap + sep.width + gap + 2 * dcell + (dot.width if dot else 0) + gap
            typical = fixed + sum(months) / len(months)
            x0 = int(round((W - typical) / 2.0))
            if x0 >= 44 and x0 + fixed + max(months) <= W - 44:
                break
        L = {'st': st, 'digits': dg, 'cell': dcell, 'dot': dot, 'sep': sep, 'x0': x0, 'week_box': week_box,
             'y': st.top_for_digits_centred_on(line_cy)}
        L['sep_x'] = x0 + week_box + gap
        L['day_right'] = L['sep_x'] + sep.width + gap + 2 * dcell
        L['month_x'] = L['day_right'] + (dot.width if dot else 0) + gap
        L['right'] = int(L['month_x'] + max(months))
        return L

    def right_in_box(st, text, box):
        im = Image.new('RGBA', (box, st.height), (0, 0, 0, 0))
        t = st.render(text)
        im.alpha_composite(t, (box - t.width, 0))
        return im

    lines = [date_line(n) for n in langs]
    date_items, slots, choices = [], [], []
    if len(langs) == 1:
        L = lines[0]
        st, ly = L['st'], L['y']
        wr = face.add_set([right_in_box(st, t, L['week_box']) for t in names['weekdays']], 'week')
        mr = face.add_set([st.render(t) for t in names['months']], 'month')
        date_items += [
            layout.image_list([wr[0]] + wr, L['x0'], ly, codes.WEEKDAY),
            layout.number(face.add_set(L['digits'], 'day'), L['day_right'], ly, codes.ALIGN_RIGHT, codes.DAY_OF_MONTH),
            layout.image_list([mr[0]] + mr, L['month_x'], ly, codes.MONTH),
        ]
        bg.alpha_composite(L['sep'], (L['sep_x'], ly))
        if L['dot']:
            bg.alpha_composite(L['dot'], (L['day_right'], ly))
    else:
        zone = (min(L['x0'] for L in lines) - 8, min(L['y'] for L in lines) - 6,
                max(L['right'] for L in lines) + 8, max(L['y'] + L['st'].height for L in lines) + 6)
        zx, zy = zone[0], zone[1]
        zw, zh = zone[2] - zx, zone[3] - zy
        frame = Image.new('RGBA', (zw, zh), (0, 0, 0, 0))
        ImageDraw.Draw(frame).rounded_rectangle([1, 1, zw - 2, zh - 2], radius=10, outline=GOLD_BOTTOM + (255,), width=2)
        frame_ref = face.add(frame, 'choice_frame')
        for i, (n, L) in enumerate(zip(langs, lines)):
            st, ly = L['st'], L['y']
            wr = face.add_set([right_in_box(st, t, L['week_box']) for t in n['weekdays']], ('week', i))
            mr = face.add_set([st.render(t) for t in n['months']], ('month', i))
            items = [
                layout.slot_image_list([wr[0]] + wr, L['x0'] - zx, ly - zy, codes.WEEKDAY),
                layout.slot_image(face.add(L['sep'], ('sep', i)), L['sep_x'] - zx, ly - zy),
                layout.slot_number(face.add_set(L['digits'], ('day', i)), L['day_right'] - zx, ly - zy,
                                   codes.ALIGN_RIGHT, codes.DAY_OF_MONTH),
                layout.slot_image_list([mr[0]] + mr, L['month_x'] - zx, ly - zy, codes.MONTH),
            ]
            thumb = Image.new('RGBA', (zw, zh), (0, 0, 0, 0))
            thumb.alpha_composite(right_in_box(st, n['weekdays'][6], L['week_box']), (L['x0'] - zx, ly - zy))
            thumb.alpha_composite(L['sep'], (L['sep_x'] - zx, ly - zy))
            thumb.alpha_composite(st.render(n['months'][10]), (L['month_x'] - zx, ly - zy))
            if L['dot']:
                items.append(layout.slot_image(face.add(L['dot'], ('dot', i)), L['day_right'] - zx, ly - zy))
                thumb.alpha_composite(L['dot'], (L['day_right'] - zx, ly - zy))
            slots.append(layout.slot(i, items, face.add(thumb, ('thumb', i)), frame_ref,
                                     CHOICE_FUNCTIONS[i % len(CHOICE_FUNCTIONS)]))
        choices.append((zone, list(range(len(langs))), 0))

    # --- along the water: battery, weather, pulse, steps; small symbol, then the value
    s_val = serif(23, 600, CREAM, sample='%°')
    # number digits sit edge to edge, so they carry no halo; the sea under them is dark
    v_digits, v_cell = s_val.digits()
    vp = 0
    v_refs = face.add_set(v_digits, 'val')
    minus_ref = face.add(s_val.render('-'), 'minus')
    row_cy = 432
    vy = s_val.top_for_digits_centred_on(row_cy)
    pct, deg = s_val.render('%'), s_val.render('°')
    sym = 20
    zones = []
    bat = [draw.battery(i, CREAM, (230, 120, 70, 255), w=24, h=13) for i in range(11)]
    sky = SYMBOLS.same_box(WEATHER, 22, CREAM, fill=1)
    heart = SYMBOLS.get('favorite', 17, CREAM)
    steps = SYMBOLS.get('footprint', 17, CREAM)
    minus_w = s_val.render('-').width
    # each item gets the room its widest value needs; the row is centred on that
    spec = [(bat[0].width, 3, pct, 0), (sky[0].width, 2, deg, minus_w), (heart.width, 3, None, 0),
            (steps.width, 5, None, 0)]
    widths = [iw + 5 + lead + n * v_cell + (u.width if u else 0) for iw, n, u, lead in spec]
    gap_row = 20
    x = (W - (sum(widths) + gap_row * (len(widths) - 1))) // 2
    cols = []
    for (iw, n, u, lead), wdt in zip(spec, widths):
        cols.append((x, n, u, lead))
        x += wdt + gap_row
    targets = [codes.OPEN_SETTINGS, codes.OPEN_WEATHER, codes.OPEN_HEART_RATE, codes.OPEN_STEPS]
    for k, ((x0, digits_n, unit, lead), target) in enumerate(zip(cols, targets)):
        if k == 0:
            icon_w = bat[0].width
            items = [layout.image_list(face.add_set(bat, 'battery'), x0, int(round(row_cy - bat[0].height / 2.0)),
                                       codes.BATTERY_LEVEL)]
        elif k == 1:
            icon_w = sky[0].width
            items = [layout.image_list(face.add_set(sky, 'sky'), x0, int(round(row_cy - sky[0].height / 2.0)),
                                       codes.WEATHER_ICON)]
        else:
            ic = heart if k == 2 else steps
            icon_w = ic.width
            sh, spd = with_shade(ic, 3, 140)
            bg.alpha_composite(sh, (x0 - spd, int(round(row_cy - ic.height / 2.0)) - spd))
            items = []
        right = x0 + icon_w + 5 + lead + digits_n * v_cell
        source = [codes.BATTERY_PERCENT, codes.TEMPERATURE, codes.HEART_RATE, codes.STEPS][k]
        items.append(layout.number(v_refs, right + vp, vy - vp, codes.ALIGN_RIGHT, source,
                                   minus=minus_ref if k == 1 else ''))
        if unit is not None:
            u, upd = with_shade(unit, 3, 150)
            bg.alpha_composite(u, (right - upd, vy - upd))
        zones.append((target, (x0 - 6, row_cy - 20, right + (unit.width if unit else 0) + 4, row_cy + 20), items))

    # --- always-on: the time alone, thin and dim
    a_time = serif(s_time.size, 400, DIM)
    ad, _ = a_time.digits(extra_pad=2)
    a_refs = face.add_set(ad, 'aod_time')
    a_colon = face.add(a_time.render(':'), 'aod_colon')
    time_items += [
        layout.image_list(a_refs[0:3], xs[0], ty + 40, codes.HOUR_TENS, aod=1),
        layout.image_list(a_refs, xs[1], ty + 40, codes.HOUR_UNITS, aod=1),
        layout.image(a_colon, tx + 2 * cell + 4, ty + 40, aod=1),
        layout.image_list(a_refs[0:6], xs[2], ty + 40, codes.MINUTE_TENS, aod=1),
        layout.image_list(a_refs, xs[3], ty + 40, codes.MINUTE_UNITS, aod=1),
    ]

    face.set_reserved(layout.BACKGROUND, bg)
    background = [layout.image(layout.BACKGROUND, 0, 0), layout.image(aod_bg, 0, 0, aod=1)]
    return face, layout.layout(TITLE, background, zones, date_items, time_items, slots, choices)


def jpeg(im, size):
    buf = io.BytesIO()
    im.convert('RGB').resize(size, Image.LANCZOS).save(buf, 'JPEG', quality=92)
    return buf.getvalue()


def package(locales, out_dir, name):
    face, lay = build(locales)
    blank = Image.new('RGBA', (W, H))
    face.set_reserved(layout.THUMB, blank.resize((240, 282)))
    face.set_reserved(layout.PREVIEW, blank)
    first = container.pack(lay, face.images)
    normal = simulate.render(first)
    aod = simulate.render(first, aod=True)
    face.set_reserved(layout.THUMB, normal.resize((240, 282), Image.LANCZOS))
    face.set_reserved(layout.PREVIEW, normal)
    binary = container.pack(lay, face.images)
    previews = {'cover.jpg': jpeg(normal, (816, 960)), 'icon_small.jpg': jpeg(normal, (332, 390)),
                'aod.jpg': jpeg(aod, (816, 960))}
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, name)
    container.write_package(base + '.hwt', binary, TITLE, AUTHOR, SCREEN, FORMAT_VERSION, previews)
    normal.convert('RGB').save(base + '.png')
    aod.convert('RGB').save(base + '-aod.png')
    return base + '.hwt', len(binary), len(face.images)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('locales', nargs='*', default=['all'])
    ap.add_argument('--switchable', default='')
    ap.add_argument('--out', default=os.path.join(ROOT, 'dist'))
    a = ap.parse_args()
    available = sorted(n[:-5] for n in os.listdir(os.path.join(HERE, 'locale')) if n.endswith('.json'))
    wanted = available if a.locales == ['all'] else a.locales
    jobs = [([loc], '%s-%s' % (NAME, loc)) for loc in wanted]
    if a.switchable:
        jobs.append((a.switchable.split(','), NAME))
    for locales, name in jobs:
        path, size, count = package(locales, a.out, name)
        print('%s  %d bytes  %d images  %s' % (os.path.relpath(path, ROOT), size, count, '+'.join(locales)))


if __name__ == '__main__':
    main()
