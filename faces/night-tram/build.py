"""Night Tram: ink background, cream numerals, amber lights. A lamp runs along the
copper frame with the seconds, and six stops along the bottom light up as the day's
step goal is walked.

Usage: python3 faces/night-tram/build.py [locale ... | all] [--switchable ru,en,fi] [--out DIR]
"""
import argparse
import io
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

from machine import codes, container, draw, effects, layout, simulate  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_TEXT = os.path.join(ROOT, 'fonts', 'Oswald.ttf')
SYMBOLS = draw.Symbols(os.path.join(ROOT, 'fonts', 'Symbols.ttf'), os.path.join(ROOT, 'fonts', 'symbols.codepoints'))

TITLE = 'Night Tram'
AUTHOR = 'night-tram'
NAME = 'night-tram'
SCREEN = 'HWHD13'
FORMAT_VERSION = '2.5.1'
CHOICE_TARGET = 1
W, H = 408, 480
SS = 4

# palette
INK = (12, 19, 21)
INK_EDGE = (4, 7, 8)
CREAM = (243, 230, 204, 255)
CREAM_TICK = (243, 230, 204, 120)
CREAM_TICK_MAJOR = (243, 230, 204, 200)
AMBER = (255, 138, 30, 255)
AMBER_LAMP = (255, 176, 82, 255)
COPPER = (150, 78, 40, 210)
MINT = (126, 170, 152, 150)
DIM = (150, 140, 120, 255)
STOP_IDLE = (64, 66, 62, 255)

WEATHER = ['cloud_off', 'sunny', 'clear_night', 'cloud', 'partly_cloudy_day', 'rainy',
           'thunderstorm', 'weather_snowy', 'air', 'mist', 'foggy']

FRAME_INSET, FRAME_RADIUS = 7, 70
COLUMNS = [84, 204, 324]
STOPS_Y, STOPS_X = 446, [94 + 44 * i for i in range(6)]


def style(size, weight, color, tracking=0, sample=''):
    return draw.Style(FONT_TEXT, size, weight, color, tracking, sample)


def load_locale(locale):
    with open(os.path.join(HERE, 'locale', locale + '.json'), encoding='utf-8') as fh:
        return json.load(fh)


def canvas():
    return Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0))


def down(im):
    return im.resize((W, H), Image.LANCZOS)


# ---------------------------------------------------------------- background pieces

def ink_background():
    """Ink with a faint lift in the middle, darkening towards the edges."""
    px = []
    for y in range(H):
        for x in range(W):
            d = min(1.0, math.hypot((x - W / 2) / (W * 0.62), (y - H * 0.45) / (H * 0.62)))
            k = d * d
            px.append(tuple(int(INK[i] * (1 - k) + INK_EDGE[i] * k) for i in range(3)) + (255,))
    im = Image.new('RGBA', (W, H))
    im.putdata(px)
    return im


def copper_frame():
    im = canvas()
    i, r = FRAME_INSET * SS, FRAME_RADIUS * SS
    ImageDraw.Draw(im).rounded_rectangle([i, i, W * SS - 1 - i, H * SS - 1 - i], radius=r, outline=COPPER,
                                         width=int(1.4 * SS))
    return down(im)


def night_arc():
    """A thin horizon above the time with a crescent and a few stars."""
    im = canvas()
    d = ImageDraw.Draw(im)
    R, top = 700, 98
    cx, cy = W / 2, top + R
    half = math.degrees(math.asin(140 / float(R)))
    d.arc([(cx - R) * SS, (cy - R) * SS, (cx + R) * SS, (cy + R) * SS], 270 - half, 270 + half,
          fill=MINT, width=int(1.3 * SS))
    # crescent: a disc with an offset disc taken out of it
    mx, my, mr = W / 2, 80, 8.5
    moon = Image.new('L', im.size, 0)
    md = ImageDraw.Draw(moon)
    md.ellipse([(mx - mr) * SS, (my - mr) * SS, (mx + mr) * SS, (my + mr) * SS], fill=255)
    md.ellipse([(mx - mr + 5.5) * SS, (my - mr - 3.5) * SS, (mx + mr + 5.5) * SS, (my + mr - 3.5) * SS], fill=0)
    cream = Image.new('RGBA', im.size, CREAM)
    im.paste(cream, (0, 0), moon)

    def star(x, y, r):
        pts = []
        for k in range(8):
            a = math.pi / 4 * k
            rr = r if k % 2 == 0 else r * 0.28
            pts.append(((x + rr * math.sin(a)) * SS, (y - rr * math.cos(a)) * SS))
        d.polygon(pts, fill=CREAM)

    star(152, 82, 4.5)
    star(262, 82, 4.0)
    for x, y in ((122, 90), (290, 90), (176, 88), (238, 88)):
        d.ellipse([(x - 1.1) * SS, (y - 1.1) * SS, (x + 1.1) * SS, (y + 1.1) * SS], fill=CREAM_TICK_MAJOR)
    return down(im)


def battery_cells(level, w=46, h=24):
    """Outlined battery with four cells, lit by tenths of charge."""
    im = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bw = (w - 5) * SS
    d.rounded_rectangle([SS, SS, bw, h * SS - SS], radius=4 * SS, outline=CREAM, width=int(1.8 * SS))
    d.rounded_rectangle([bw + SS, h * SS // 2 - 4 * SS, w * SS - SS, h * SS // 2 + 4 * SS], radius=1.5 * SS, fill=CREAM)
    lit = int(round(level * 4 / 10.0))
    inner_x0, inner_x1 = 5 * SS, bw - 4 * SS
    cell = (inner_x1 - inner_x0 - 3 * 2 * SS) / 4.0
    for k in range(lit):
        x = inner_x0 + k * (cell + 2 * SS)
        d.rectangle([x, 5 * SS, x + cell, h * SS - 5 * SS], fill=CREAM if level > 2 else AMBER)
    return im.resize((w, h), Image.LANCZOS)


def stops(lit):
    """The route: idle grey, or amber with cream-lit stops."""
    im = canvas()
    d = ImageDraw.Draw(im)
    y = STOPS_Y * SS
    line = AMBER if lit else STOP_IDLE
    d.line([(STOPS_X[0] * SS, y), (STOPS_X[-1] * SS, y)], fill=line, width=int(1.6 * SS))
    for x in STOPS_X:
        r = 6.5 * SS
        if lit:
            d.ellipse([x * SS - r, y - r, x * SS + r, y + r], fill=CREAM, outline=AMBER, width=int(1.6 * SS))
        else:
            d.ellipse([x * SS - r, y - r, x * SS + r, y + r], fill=(18, 24, 25, 255), outline=STOP_IDLE,
                      width=int(1.6 * SS))
    out = down(im)
    if lit:
        halo = out.copy().filter(ImageFilter.GaussianBlur(4))
        halo.putalpha(halo.getchannel('A').point(lambda a: a * 3 // 5))
        glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        glow.alpha_composite(halo)
        glow.alpha_composite(out)
        out = glow
    return out


# ---------------------------------------------------------------- face

def build(locales):
    langs = [load_locale(l) for l in locales]
    names = langs[0]
    words = ''.join(w for n in langs for w in n['weekdays'] + n['months'])
    suffixes = [n.get('day_suffix', '') for n in langs]
    face = layout.Face(W, H)
    aod_bg = face.add(Image.new('RGBA', (W, H), (0, 0, 0, 255)), 'aod_bg')

    bg = ink_background()
    bg.alpha_composite(copper_frame())
    ticks = draw.Ring(W, H, inset=13, radius=FRAME_RADIUS - 6, length=(5, 8), thickness=(1.4, 2.0))
    bg.alpha_composite(ticks.draw_ticks(range(60), lambda i: CREAM_TICK_MAJOR if ticks.ticks[i][2] else CREAM_TICK))
    bg.alpha_composite(night_arc())

    # --- date line: lamp, weekday, separator, day, month
    lamp_d, gap = 11, 10
    for date_size in range(32, 16, -1):
        s_date = style(date_size, 500, CREAM, 2, words + ''.join(suffixes) + '·')
        day_digits, day_cell = s_date.digits()
        week_w = max(s_date.width(w) for n in langs for w in n['weekdays'])
        month_w = max(s_date.width(m) for n in langs for m in n['months'])
        dots = [s_date.render(sfx) if sfx else None for sfx in suffixes]
        dot_w = max([d.width for d in dots if d] or [0])
        sep = s_date.render('·')
        week_box = int(math.ceil(week_w))
        block = lamp_d + 14 + week_box + gap + sep.width + gap + 2 * day_cell + dot_w + gap + int(month_w)
        if block <= W - 84:
            break
    bx = (W - block) // 2
    line_cy = 56
    ly = s_date.top_for_digits_centred_on(line_cy)
    lamp_x = bx
    week_x = lamp_x + lamp_d + 14
    sep_x = week_x + week_box + gap
    day_right = sep_x + sep.width + gap + 2 * day_cell
    month_x = day_right + dot_w + gap
    lamp = draw.dot(lamp_d, AMBER)
    bg.alpha_composite(lamp, (lamp_x, int(line_cy - lamp_d / 2.0)))
    bg.alpha_composite(sep, (sep_x, ly))

    def right_aligned(text, st):
        im = Image.new('RGBA', (week_box, st.height), (0, 0, 0, 0))
        t = st.render(text)
        im.alpha_composite(t, (week_box - t.width, 0))
        return im

    date_items = [layout.number(face.add_set(day_digits, 'day'), day_right, ly, codes.ALIGN_RIGHT, codes.DAY_OF_MONTH)]
    slots, choices = [], []
    if len(langs) == 1:
        wr = face.add_set([right_aligned(t, s_date) for t in names['weekdays']], 'week')
        mr = face.add_set([s_date.render(t) for t in names['months']], 'month')
        date_items += [layout.image_list([wr[0]] + wr, week_x, ly, codes.WEEKDAY),
                       layout.image_list([mr[0]] + mr, month_x, ly, codes.MONTH)]
        if dots[0]:
            bg.alpha_composite(dots[0], (day_right, ly))
    else:
        zone = (week_x - 6, ly - 6, month_x + int(month_w) + 6, ly + s_date.height + 6)
        zx, zy = zone[0], zone[1]
        zw, zh = zone[2] - zx, zone[3] - zy
        frame = Image.new('RGBA', (zw, zh), (0, 0, 0, 0))
        ImageDraw.Draw(frame).rounded_rectangle([1, 1, zw - 2, zh - 2], radius=10, outline=AMBER, width=2)
        frame_ref = face.add(frame, 'choice_frame')
        for i, (n, d) in enumerate(zip(langs, dots)):
            wr = face.add_set([right_aligned(t, s_date) for t in n['weekdays']], ('week', i))
            mr = face.add_set([s_date.render(t) for t in n['months']], ('month', i))
            items = [layout.slot_image_list([wr[0]] + wr, week_x - zx, ly - zy, codes.WEEKDAY),
                     layout.slot_image_list([mr[0]] + mr, month_x - zx, ly - zy, codes.MONTH)]
            thumb = Image.new('RGBA', (zw, zh), (0, 0, 0, 0))
            thumb.alpha_composite(right_aligned(n['weekdays'][6], s_date), (week_x - zx, ly - zy))
            thumb.alpha_composite(s_date.render(n['months'][10]), (month_x - zx, ly - zy))
            if d:
                items.append(layout.slot_image(face.add(d, ('dot', i)), day_right - zx, ly - zy))
            slots.append(layout.slot(i, items, face.add(thumb, ('thumb', i)), frame_ref, CHOICE_TARGET))
        choices.append((zone, list(range(len(langs))), 0))

    # --- time: as large as fits between the horizon and the seconds rule
    for size in range(190, 120, -2):
        s_time = style(size, 600, CREAM)
        t_digits, t_cell = s_time.digits(extra_pad=1)
        colon_w = int(size * 0.17)
        total = 4 * t_cell + colon_w
        ink_h = s_time.digit_ink[1] - s_time.digit_ink[0]
        if total <= W - 56 and ink_h <= 150:
            break
    t_refs = face.add_set(t_digits, 'time')
    tx = (W - total) // 2
    tcy = 196
    ty = s_time.top_for_digits_centred_on(tcy)
    t_top, t_bot = ty + s_time.digit_ink[0], ty + s_time.digit_ink[1]
    ink_h = t_bot - t_top
    sq = max(10, int(size * 0.085))
    cxm = tx + 2 * t_cell + colon_w / 2.0
    dd = ImageDraw.Draw(bg)
    for fy in (-0.2, 0.2):
        cy = (t_top + t_bot) / 2.0 + fy * ink_h
        dd.rounded_rectangle([cxm - sq / 2, cy - sq / 2, cxm + sq / 2, cy + sq / 2], radius=sq * 0.28, fill=CREAM)

    # --- seconds between two rules
    s_sec = style(30, 500, AMBER)
    sec_digits, sec_cell = s_sec.digits(extra_pad=1)
    sec_refs = face.add_set(sec_digits, 'sec')
    rule_y = t_bot + 26
    sy = s_sec.top_for_digits_centred_on(rule_y)
    sx = W // 2 - sec_cell
    rules = canvas()
    rd = ImageDraw.Draw(rules)
    for x0, x1 in ((76, sx - 12), (sx + 2 * sec_cell + 12, 332)):
        rd.line([(x0 * SS, rule_y * SS), (x1 * SS, rule_y * SS)], fill=MINT, width=int(1.2 * SS))
    bg.alpha_composite(down(rules))

    lamp_ring = draw.Ring(W, H, inset=FRAME_INSET, radius=FRAME_RADIUS, length=(0, 0))
    mark_items = effects.running_mark(face, bg, lamp_ring,
                                      painter=effects.glowing(lamp_ring, 3.6, AMBER_LAMP, halo=11, halo_alpha=170))
    time_items = mark_items + [
        layout.image_list(t_refs[0:3], tx, ty, codes.HOUR_TENS),
        layout.image_list(t_refs, tx + t_cell, ty, codes.HOUR_UNITS),
        layout.image_list(t_refs[0:6], tx + 2 * t_cell + colon_w, ty, codes.MINUTE_TENS),
        layout.image_list(t_refs, tx + 3 * t_cell + colon_w, ty, codes.MINUTE_UNITS),
        layout.image_list(sec_refs[0:6], sx, sy, codes.SECOND_TENS),
        layout.image_list(sec_refs, sx + sec_cell, sy, codes.SECOND_UNITS),
    ]

    # --- three columns: battery, weather, steps; symbol over value
    row_top = rule_y + 20
    icon_cy = row_top + 16
    val_cy = row_top + 52
    s_val = style(30, 500, CREAM, sample='%°')
    v_refs = face.add_set(s_val.digits()[0], 'val')
    v_cell = s_val.digits()[1]
    minus_ref = face.add(s_val.render('-'), 'minus')
    vy = s_val.top_for_digits_centred_on(val_cy)
    divs = canvas()
    dv = ImageDraw.Draw(divs)
    for x in ((COLUMNS[0] + COLUMNS[1]) / 2.0, (COLUMNS[1] + COLUMNS[2]) / 2.0):
        dv.line([(x * SS, (row_top - 2) * SS), (x * SS, (val_cy + 22) * SS)], fill=MINT, width=int(1.2 * SS))
    bg.alpha_composite(down(divs))

    def centred_right_edge(cx, digits, tail=0):
        return int(round(cx - (digits * v_cell + tail) / 2.0 + digits * v_cell))

    zones = []
    col_w = (COLUMNS[1] - COLUMNS[0])
    # battery
    cx = COLUMNS[0]
    cells = [battery_cells(i) for i in range(11)]
    pct = s_val.render('%')
    xr = centred_right_edge(cx, 2, pct.width)
    bg.alpha_composite(pct, (xr, vy))
    track_box = (cx - 34, val_cy + 26, cx + 34, val_cy + 30)
    tdraw = ImageDraw.Draw(bg)
    tdraw.rounded_rectangle(track_box, radius=2, fill=(40, 46, 46, 255))
    bar = Image.new('RGBA', (track_box[2] - track_box[0], track_box[3] - track_box[1]), (0, 0, 0, 0))
    ImageDraw.Draw(bar).rounded_rectangle([0, 0, bar.width - 1, bar.height - 1], radius=2, fill=AMBER)
    zones.append((codes.OPEN_SETTINGS, (cx - col_w // 2 + 4, row_top - 6, cx + col_w // 2 - 4, val_cy + 34), [
        layout.image_list(face.add_set(cells, 'battery'), cx - cells[0].width // 2,
                          int(round(icon_cy - cells[0].height / 2.0)), codes.BATTERY_LEVEL),
        layout.number(v_refs, xr, vy, codes.ALIGN_RIGHT, codes.BATTERY_PERCENT),
        layout.progress(face.add(bar, 'battery_bar'), track_box, codes.PROGRESS_BATTERY),
    ]))
    # weather
    cx = COLUMNS[1]
    boxed = SYMBOLS.same_box(WEATHER, 38, CREAM, fill=0)
    bw_, bh_ = boxed[0].size
    deg = s_val.render('°')
    xr = centred_right_edge(cx, 1, deg.width)
    bg.alpha_composite(deg, (xr, vy))
    zones.append((codes.OPEN_WEATHER, (cx - col_w // 2 + 4, row_top - 6, cx + col_w // 2 - 4, val_cy + 34), [
        layout.image_list(face.add_set(boxed, 'weather'), cx - bw_ // 2, int(round(icon_cy - bh_ / 2.0)),
                          codes.WEATHER_ICON),
        layout.number(v_refs, xr, vy, codes.ALIGN_RIGHT, codes.TEMPERATURE, minus=minus_ref),
    ]))
    # steps
    cx = COLUMNS[2]
    walker = SYMBOLS.get('directions_walk', 36, CREAM)
    bg.alpha_composite(walker, (cx - walker.width // 2, int(round(icon_cy - walker.height / 2.0))))
    zones.append((codes.OPEN_STEPS, (cx - col_w // 2 + 4, row_top - 6, cx + col_w // 2 - 4, val_cy + 34), [
        layout.number(v_refs, centred_right_edge(cx, 4), vy, codes.ALIGN_RIGHT, codes.STEPS),
    ]))

    # --- pulse, small, above the route
    s_small = style(22, 500, CREAM)
    p_digits, p_cell = s_small.digits()
    heart = SYMBOLS.get('favorite', 16, CREAM)
    pulse_cy = STOPS_Y - 28
    py_ = s_small.top_for_digits_centred_on(pulse_cy)
    width = 2 * p_cell + 4 + heart.width
    p_right = W // 2 - width // 2 + 2 * p_cell
    bg.alpha_composite(heart, (p_right + 4, int(round(pulse_cy - heart.height / 2.0))))
    zones.append((codes.OPEN_HEART_RATE, (W // 2 - 52, pulse_cy - 14, W // 2 + 52, pulse_cy + 14), [
        layout.number(face.add_set(p_digits, 'pulse'), p_right, py_, codes.ALIGN_RIGHT, codes.HEART_RATE),
    ]))

    # --- the route: idle stops on the background, lit route revealed by the step goal
    bg.alpha_composite(stops(False))
    lit = stops(True)
    route_box = (STOPS_X[0] - 12, STOPS_Y - 12, STOPS_X[-1] + 12, STOPS_Y + 12)
    route_ref = face.add(lit.crop(route_box), 'route')
    date_items.append(layout.progress(route_ref, route_box, codes.PROGRESS_STEPS))

    # --- always-on screen: thin time, quiet date
    a_time = style(size, 300, DIM)
    at_digits, at_cell = a_time.digits(extra_pad=1)
    at_refs = face.add_set(at_digits, 'aod_time')
    acolon = Image.new('RGBA', (colon_w, a_time.height), (0, 0, 0, 0))
    ad = ImageDraw.Draw(acolon)
    at_top, at_bot = a_time.digit_ink
    for fy in (-0.2, 0.2):
        cy = (at_top + at_bot) / 2.0 + fy * (at_bot - at_top)
        ad.rounded_rectangle([colon_w / 2 - sq / 2.5, cy - sq / 2.5, colon_w / 2 + sq / 2.5, cy + sq / 2.5],
                             radius=2, fill=(150, 80, 30, 255))
    ax = (W - (4 * at_cell + colon_w)) // 2
    aty = a_time.top_for_digits_centred_on(tcy + 20)
    time_items += [
        layout.image_list(at_refs[0:3], ax, aty, codes.HOUR_TENS, aod=1),
        layout.image_list(at_refs, ax + at_cell, aty, codes.HOUR_UNITS, aod=1),
        layout.image(face.add(acolon, 'aod_colon'), ax + 2 * at_cell, aty, aod=1),
        layout.image_list(at_refs[0:6], ax + 2 * at_cell + colon_w, aty, codes.MINUTE_TENS, aod=1),
        layout.image_list(at_refs, ax + 3 * at_cell + colon_w, aty, codes.MINUTE_UNITS, aod=1),
    ]
    a_date = style(s_date.size, 400, DIM, 2, words + ''.join(suffixes))
    a_digits = a_date.digits()[0]

    def a_right(text):
        im = Image.new('RGBA', (week_box, a_date.height), (0, 0, 0, 0))
        t = a_date.render(text)
        im.alpha_composite(t, (week_box - t.width, 0))
        return im

    aw = face.add_set([a_right(t) for t in names['weekdays']], 'aod_week')
    am = face.add_set([a_date.render(t) for t in names['months']], 'aod_month')
    a_sep = a_date.render('·')
    date_items += [
        layout.image_list([aw[0]] + aw, week_x, ly + 40, codes.WEEKDAY, aod=1),
        layout.image(face.add(a_sep, 'aod_sep'), sep_x, ly + 40, aod=1),
        layout.number(face.add_set(a_digits, 'aod_day'), day_right, ly + 40, codes.ALIGN_RIGHT, codes.DAY_OF_MONTH, aod=1),
        layout.image_list([am[0]] + am, month_x, ly + 40, codes.MONTH, aod=1),
    ]
    if suffixes[0]:
        date_items.append(layout.image(face.add(a_date.render(suffixes[0]), 'aod_dot'), day_right, ly + 40, aod=1))

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
    ap.add_argument('--switchable', default='ru,en,fi')
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
