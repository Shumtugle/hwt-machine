"""Plumb: black, the hour set above the minute like two lines of type, and a red
weight sliding down a cream thread once a minute. The date sits at the top, the
weather at the foot; everything hangs from one left margin.

Usage: python3 faces/plumb/build.py [locale ... | all] [--switchable ru,en,fi] [--out DIR]
"""
import argparse
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

from machine import codes, container, draw, effects, layout, simulate  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_TEXT = os.path.join(ROOT, 'fonts', 'Oswald.ttf')
SYMBOLS = draw.Symbols(os.path.join(ROOT, 'fonts', 'Symbols.ttf'), os.path.join(ROOT, 'fonts', 'symbols.codepoints'))

TITLE = 'Plumb'
AUTHOR = 'plumb'
NAME = 'plumb'
SCREEN = 'HWHD13'
FORMAT_VERSION = '2.5.1'
CHOICE_FUNCTIONS = [codes.FUNCTION_DATE, codes.FUNCTION_WEEKDAY, codes.FUNCTION_SUN]
W, H = 408, 480
SS = 4

CREAM = (236, 226, 206, 255)
CREAM_DIM = (150, 142, 128, 255)
THREAD = (236, 226, 206, 70)
NOTCH = (236, 226, 206, 110)
RED = (226, 40, 52, 255)
DIM = (120, 112, 100, 255)

WEATHER = ['cloud_off', 'sunny', 'clear_night', 'cloud', 'partly_cloudy_day', 'rainy',
           'thunderstorm', 'weather_snowy', 'air', 'mist', 'foggy']

MARGIN = 40                 # the one left margin everything hangs from
THREAD_X, THREAD_TOP, THREAD_BOTTOM = 304, 112, 392


def style(size, weight, color, tracking=0, sample=''):
    return draw.Style(FONT_TEXT, size, weight, color, tracking, sample)


def load_locale(locale):
    with open(os.path.join(HERE, 'locale', locale + '.json'), encoding='utf-8') as fh:
        return json.load(fh)


DECADE_GAP = 26


def thread(track):
    """The thread in six lengths of ten seconds, a notch between each."""
    im = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = THREAD_X * SS
    d.line([(x, (THREAD_TOP - 18) * SS), (x, THREAD_BOTTOM * SS)], fill=THREAD, width=int(1.4 * SS))
    marks = [track.points[0][1]] + [(track.points[10 * k - 1][1] + track.points[10 * k][1]) / 2.0
                                    for k in range(1, 6)] + [track.points[59][1]]
    for k, y in enumerate(marks):
        half = (7 if k in (0, 3, 6) else 4) * SS
        d.line([(x - half, y * SS), (x + half, y * SS)], fill=NOTCH, width=int(1.2 * SS))
    # where the thread is tied
    d.ellipse([x - 3 * SS, (THREAD_TOP - 21) * SS, x + 3 * SS, (THREAD_TOP - 15) * SS], fill=THREAD)
    return im.resize((W, H), Image.LANCZOS)


def weight_painter(track):
    """A small red weight with a soft shadow of light, hanging on the thread."""
    def paint(indices):
        im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        glow = track.draw_balls(indices, 7.5, RED[:3] + (90,))
        im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(2.5)))
        im.alpha_composite(track.draw_balls(indices, 5.2, RED))
        return im
    paint.reach = 10.5
    return paint


def build(locales):
    langs = [load_locale(l) for l in locales]
    names = langs[0]
    face = layout.Face(W, H)
    aod_bg = face.add(Image.new('RGBA', (W, H), (0, 0, 0, 255)), 'aod_bg')
    bg = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    track = draw.Track.line(W, H, (THREAD_X, THREAD_TOP), (THREAD_X, THREAD_BOTTOM), decade_gap=DECADE_GAP)
    bg.alpha_composite(thread(track))

    # --- the hour above the minute, as large as the room between date and foot allows
    top_room, bottom_room = 112, 392
    gap = 26
    for size in range(240, 100, -2):
        s_time = style(size, 500, CREAM)
        digits, cell = s_time.digits(extra_pad=2)
        ink_h = s_time.digit_ink[1] - s_time.digit_ink[0]
        if 2 * ink_h + gap <= bottom_room - top_room and MARGIN + 2 * cell <= THREAD_X - 30:
            break
    t_refs = face.add_set(digits, 'time')
    hy = top_room - s_time.digit_ink[0]
    my = top_room + ink_h + gap - s_time.digit_ink[0]
    x = MARGIN - 2
    time_items = effects.running_mark(face, bg, track, painter=weight_painter(track)) + [
        layout.image_list(t_refs[0:3], x, hy, codes.HOUR_TENS),
        layout.image_list(t_refs, x + cell, hy, codes.HOUR_UNITS),
        layout.image_list(t_refs[0:6], x, my, codes.MINUTE_TENS),
        layout.image_list(t_refs, x + cell, my, codes.MINUTE_UNITS),
    ]

    # --- the date: day and month on one line, the weekday quieter under it, all from the margin
    def date_block(n):
        sfx = n.get('day_suffix', '')
        sample = ''.join(n['weekdays'] + n['months']) + sfx
        for size in range(30, 14, -1):
            big = style(size, 500, CREAM, 1, sample)
            small = style(int(size * 0.72), 400, CREAM_DIM, 2, sample)
            dg, dcell = big.digits()
            dot = big.render(sfx) if sfx else None
            month_x = MARGIN + 2 * dcell + (dot.width if dot else 0) + 8
            if month_x + max(big.width(m) for m in n['months']) <= THREAD_X - 20:
                break
        return {'big': big, 'small': small, 'digits': dg, 'cell': dcell, 'dot': dot, 'month_x': month_x}

    blocks = [date_block(n) for n in langs]
    line1_bottom = 46
    date_items, slots, choices = [], [], []

    def block_items(n, B, key, origin=(0, 0), slot_mode=False):
        big, small = B['big'], B['small']
        y1 = line1_bottom - big.cap_ink[1]
        y2 = line1_bottom + 12 - small.cap_ink[0]
        ox, oy = origin
        day_right = MARGIN + 2 * B['cell']
        mr = face.add_set([big.render(t) for t in n['months']], ('month', key))
        wr = face.add_set([small.render(t) for t in n['weekdays']], ('week', key))
        if slot_mode:
            out = [layout.slot_number(face.add_set(B['digits'], ('day', key)), day_right - ox, y1 - oy,
                                      codes.ALIGN_RIGHT, codes.DAY_OF_MONTH),
                   layout.slot_image_list([mr[0]] + mr, B['month_x'] - ox, y1 - oy, codes.MONTH),
                   layout.slot_image_list([wr[0]] + wr, MARGIN - ox, y2 - oy, codes.WEEKDAY)]
            if B['dot']:
                out.append(layout.slot_image(face.add(B['dot'], ('dot', key)), day_right - ox, y1 - oy))
        else:
            out = [layout.number(face.add_set(B['digits'], ('day', key)), day_right, y1, codes.ALIGN_RIGHT,
                                 codes.DAY_OF_MONTH),
                   layout.image_list([mr[0]] + mr, B['month_x'], y1, codes.MONTH),
                   layout.image_list([wr[0]] + wr, MARGIN, y2, codes.WEEKDAY)]
            if B['dot']:
                bg.alpha_composite(B['dot'], (day_right, y1))
        return out, (y1, y2)

    if len(langs) == 1:
        items, _ = block_items(names, blocks[0], 0)
        date_items += items
    else:
        zone = (MARGIN - 8, 10, THREAD_X - 14, 96)
        zx, zy = zone[0], zone[1]
        zw, zh = zone[2] - zx, zone[3] - zy
        frame = Image.new('RGBA', (zw, zh), (0, 0, 0, 0))
        ImageDraw.Draw(frame).rounded_rectangle([1, 1, zw - 2, zh - 2], radius=10, outline=RED, width=2)
        frame_ref = face.add(frame, 'choice_frame')
        for i, (n, B) in enumerate(zip(langs, blocks)):
            items, (y1, y2) = block_items(n, B, i, (zx, zy), slot_mode=True)
            thumb = Image.new('RGBA', (zw, zh), (0, 0, 0, 0))
            d_im = B['big'].render('8')
            thumb.alpha_composite(d_im, (MARGIN + 2 * B['cell'] - d_im.width - zx, y1 - zy))
            thumb.alpha_composite(B['big'].render(n['months'][10]), (B['month_x'] - zx, y1 - zy))
            thumb.alpha_composite(B['small'].render(n['weekdays'][6]), (MARGIN - zx, y2 - zy))
            slots.append(layout.slot(i, items, face.add(thumb, ('thumb', i)), frame_ref,
                                     CHOICE_FUNCTIONS[i % len(CHOICE_FUNCTIONS)]))
        choices.append((zone, list(range(len(langs))), 0))

    # --- the foot: the sky and its warmth, one quiet line from the margin
    s_foot = style(26, 400, CREAM_DIM, sample='°')
    f_digits, f_cell = s_foot.digits()
    f_refs = face.add_set(f_digits, 'foot')
    minus_ref = face.add(s_foot.render('-'), 'minus')
    foot_cy = 436
    fy = s_foot.top_for_digits_centred_on(foot_cy)
    sky = SYMBOLS.same_box(WEATHER, 26, CREAM_DIM, fill=0)
    sky_y = int(round(foot_cy - sky[0].height / 2.0))
    deg = s_foot.render('°')
    temp_right = MARGIN + sky[0].width + 8 + 2 * f_cell
    bg.alpha_composite(deg, (temp_right, fy))
    zones = [
        (codes.OPEN_WEATHER, (MARGIN - 8, foot_cy - 22, temp_right + deg.width + 12, foot_cy + 22), [
            layout.image_list(face.add_set(sky, 'sky'), MARGIN, sky_y, codes.WEATHER_ICON),
            layout.number(f_refs, temp_right, fy, codes.ALIGN_RIGHT, codes.TEMPERATURE, minus=minus_ref),
        ]),
    ]

    # --- always-on: the two lines of type, thin and dim, nothing else
    a_time = style(s_time.size, 300, DIM)
    a_digits = face.add_set(a_time.digits(extra_pad=2)[0], 'aod_time')
    time_items += [
        layout.image_list(a_digits[0:3], x, hy, codes.HOUR_TENS, aod=1),
        layout.image_list(a_digits, x + cell, hy, codes.HOUR_UNITS, aod=1),
        layout.image_list(a_digits[0:6], x, my, codes.MINUTE_TENS, aod=1),
        layout.image_list(a_digits, x + cell, my, codes.MINUTE_UNITS, aod=1),
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
