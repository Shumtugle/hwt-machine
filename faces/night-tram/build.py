"""Night Tram: ink background, cream numerals, amber lights. A lamp runs along the
copper frame with the seconds; the small lamp by the date lights up while messages
wait unread.

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
CHOICE_FUNCTIONS = [codes.FUNCTION_DATE, codes.FUNCTION_WEEKDAY, codes.FUNCTION_SUN]  # one per language slot
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

FRAME_INSET, FRAME_RADIUS = 11, 82
COLUMNS = [84, 204, 324]
PULSE_Y = 428


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
    """A thin horizon above the time with a few stars."""
    im = canvas()
    d = ImageDraw.Draw(im)
    R, top = 700, 98
    cx, cy = W / 2, top + R
    half = math.degrees(math.asin(140 / float(R)))
    d.arc([(cx - R) * SS, (cy - R) * SS, (cx + R) * SS, (cy + R) * SS], 270 - half, 270 + half,
          fill=MINT, width=int(1.3 * SS))

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
    ticks = draw.Ring(W, H, inset=FRAME_INSET + 6, radius=FRAME_RADIUS - 6, length=(5, 8), thickness=(1.4, 2.0))
    bg.alpha_composite(ticks.draw_ticks(range(60), lambda i: CREAM_TICK_MAJOR if ticks.ticks[i][2] else CREAM_TICK))
    bg.alpha_composite(night_arc())

    # --- date line: lamp, weekday, separator, day, month; each language centred on its own
    lamp_d, gap = 11, 10
    line_cy = 56
    lamp_box = lamp_d + 12
    lamp_frames = []
    for on in (False, True):
        # the lamp is lit while there are unread messages, and only glows faintly otherwise
        fr = Image.new('RGBA', (lamp_box, lamp_box), (0, 0, 0, 0))
        core = draw.dot(lamp_d, AMBER if on else (96, 58, 24, 255))
        if on:
            halo = Image.new('RGBA', (lamp_box, lamp_box), (0, 0, 0, 0))
            halo.alpha_composite(draw.dot(lamp_d + 6, AMBER[:3] + (150,)), (3, 3))
            fr.alpha_composite(halo.filter(ImageFilter.GaussianBlur(3)))
        fr.alpha_composite(core, (6, 6))
        lamp_frames.append(fr)
    lamp_refs = face.add_set(lamp_frames, 'lamp')

    def date_line(n):
        """Sizes and places one language's line so that a typical date sits in the middle:
        the mean weekday, a two-digit day and the mean month; the longest must still fit."""
        sfx = n.get('day_suffix', '')
        own = ''.join(n['weekdays'] + n['months']) + sfx + '·'
        for size in range(33, 16, -1):
            st = style(size, 500, CREAM, 2, own)
            digits, cell = st.digits()
            weeks = [st.width(w) for w in n['weekdays']]
            months = [st.width(m) for m in n['months']]
            dot = st.render(sfx) if sfx else None
            sep = st.render('·')
            week_box = int(math.ceil(max(weeks)))
            fixed = lamp_d + 12 + week_box + gap + sep.width + gap + 2 * cell + (dot.width if dot else 0) + gap
            typical = fixed + sum(months) / len(months)
            x0 = int(round((W - typical) / 2.0))
            # centred on a typical date, the longest month must still end inside the ticks
            if x0 >= 44 and x0 + fixed + max(months) <= W - 44:
                break
        L = {'style': st, 'digits': digits, 'cell': cell, 'dot': dot, 'sep': sep, 'week_box': week_box,
             'lamp_x': x0, 'y': st.top_for_digits_centred_on(line_cy)}
        L['week_x'] = x0 + lamp_d + 12
        L['sep_x'] = L['week_x'] + week_box + gap
        L['day_right'] = L['sep_x'] + sep.width + gap + 2 * cell
        L['month_x'] = L['day_right'] + (dot.width if dot else 0) + gap
        L['right'] = int(L['month_x'] + max(months))
        L['lamp_y'] = int(line_cy - lamp_d / 2.0) - 6
        return L

    lines = [date_line(n) for n in langs]
    date_items, slots, choices = [], [], []
    message_zone = None
    if len(langs) == 1:
        L = lines[0]
        st, ly = L['style'], L['y']
        date_items += [
            layout.image_list(lamp_refs, L['lamp_x'] - 6, L['lamp_y'], codes.UNREAD_MESSAGES),
            layout.number(face.add_set(L['digits'], 'day'), L['day_right'], ly, codes.ALIGN_RIGHT, codes.DAY_OF_MONTH),
        ]
        wr = face.add_set([st.render(t) for t in names['weekdays']], 'week')
        mr = face.add_set([st.render(t) for t in names['months']], 'month')
        date_items += [layout.image_list([wr[0]] + wr, L['week_x'], ly, codes.WEEKDAY),
                       layout.image_list([mr[0]] + mr, L['month_x'], ly, codes.MONTH)]
        bg.alpha_composite(L['sep'], (L['sep_x'], ly))
        if L['dot']:
            bg.alpha_composite(L['dot'], (L['day_right'], ly))
        message_zone = (L['lamp_x'] - 12, L['lamp_y'] - 6, L['lamp_x'] + lamp_box, L['lamp_y'] + lamp_box + 6)
    else:
        zone = (min(L['lamp_x'] for L in lines) - 10, min(L['y'] for L in lines) - 6,
                max(L['right'] for L in lines) + 8, max(L['y'] + L['style'].height for L in lines) + 6)
        zx, zy = zone[0], zone[1]
        zw, zh = zone[2] - zx, zone[3] - zy
        frame = Image.new('RGBA', (zw, zh), (0, 0, 0, 0))
        ImageDraw.Draw(frame).rounded_rectangle([1, 1, zw - 2, zh - 2], radius=10, outline=AMBER, width=2)
        frame_ref = face.add(frame, 'choice_frame')
        for i, (n, L) in enumerate(zip(langs, lines)):
            st, ly = L['style'], L['y']
            wr = face.add_set([st.render(t) for t in n['weekdays']], ('week', i))
            mr = face.add_set([st.render(t) for t in n['months']], ('month', i))
            items = [
                layout.slot_image_list(lamp_refs, L['lamp_x'] - 6 - zx, L['lamp_y'] - zy, codes.UNREAD_MESSAGES),
                layout.slot_image_list([wr[0]] + wr, L['week_x'] - zx, ly - zy, codes.WEEKDAY),
                layout.slot_image(face.add(L['sep'], ('sep', i)), L['sep_x'] - zx, ly - zy),
                layout.slot_number(face.add_set(L['digits'], ('day', i)), L['day_right'] - zx, ly - zy,
                                   codes.ALIGN_RIGHT, codes.DAY_OF_MONTH),
                layout.slot_image_list([mr[0]] + mr, L['month_x'] - zx, ly - zy, codes.MONTH),
            ]
            thumb = Image.new('RGBA', (zw, zh), (0, 0, 0, 0))
            thumb.alpha_composite(lamp_frames[0], (L['lamp_x'] - 6 - zx, L['lamp_y'] - zy))
            thumb.alpha_composite(st.render(n['weekdays'][6]), (L['week_x'] - zx, ly - zy))
            thumb.alpha_composite(L['sep'], (L['sep_x'] - zx, ly - zy))
            thumb.alpha_composite(st.render(n['months'][10]), (L['month_x'] - zx, ly - zy))
            if L['dot']:
                items.append(layout.slot_image(face.add(L['dot'], ('dot', i)), L['day_right'] - zx, ly - zy))
                thumb.alpha_composite(L['dot'], (L['day_right'] - zx, ly - zy))
            slots.append(layout.slot(i, items, face.add(thumb, ('thumb', i)), frame_ref,
                                     CHOICE_FUNCTIONS[i % len(CHOICE_FUNCTIONS)]))
        choices.append((zone, list(range(len(langs))), 0))
    L0 = lines[0]
    s_date, ly = L0['style'], L0['y']
    week_x, sep_x, day_right, month_x, week_box = L0['week_x'], L0['sep_x'], L0['day_right'], L0['month_x'], L0['week_box']

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
                                      painter=effects.glowing(lamp_ring, 3.4, AMBER_LAMP, halo=6, halo_alpha=170))
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

    zones = [(codes.OPEN_MESSAGES, message_zone, [])] if message_zone else []
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

    # --- pulse, quiet, at the foot of the face
    s_small = style(26, 500, CREAM)
    p_digits, p_cell = s_small.digits()
    heart = SYMBOLS.get('favorite', 19, CREAM)
    pulse_cy = PULSE_Y
    py_ = s_small.top_for_digits_centred_on(pulse_cy)
    width = 2 * p_cell + 4 + heart.width
    p_right = W // 2 - width // 2 + 2 * p_cell
    bg.alpha_composite(heart, (p_right + 4, int(round(pulse_cy - heart.height / 2.0))))
    zones.append((codes.OPEN_HEART_RATE, (W // 2 - 52, pulse_cy - 14, W // 2 + 52, pulse_cy + 14), [
        layout.number(face.add_set(p_digits, 'pulse'), p_right, py_, codes.ALIGN_RIGHT, codes.HEART_RATE),
    ]))

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

    aw = face.add_set([a_date.render(t) for t in names['weekdays']], 'aod_week')
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
