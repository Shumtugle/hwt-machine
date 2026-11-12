"""Build a watch face from a description written as data.

A description is a JSON object: the screen, a palette, the background as layers, and
elements with their data sources, styles and positions. Everything the hand-written
faces learned the hard way is applied here, so a description cannot break a package:

  * transparent pixels are stored as 00000000, so runs stay short;
  * numbers keep one digit width, so values never jitter;
  * glyphs are placed by their visible ink, not by font metrics;
  * words are laid out once per language, and only what differs between languages
    becomes a choice in the face editor, each choice under its own function code;
  * the second mark is built from the two sources the watch really offers.

Positions may refer to other elements: "day.right+12" is twelve pixels right of the
element whose id is "day"; "parent.middle" is the middle of the enclosing tap zone.
The authoring guide lists the whole vocabulary.
"""
import difflib
import hashlib
import io
import json
import math
import os
import re

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import check, codes, container, draw, effects, layout, simulate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, 'fonts')
LOCALE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'locales')

SCREENS = {'HWHD13': (408, 480)}
FORMAT_VERSION = '2.5.1'
FONTS = {'Oswald': 'Oswald.ttf', 'Cormorant': 'Cormorant.ttf', 'Segments': None}   # Segments: drawn, digits only
SYMBOLS = draw.Symbols(os.path.join(FONT_DIR, 'Symbols.ttf'), os.path.join(FONT_DIR, 'symbols.codepoints'))

# name -> (data source, digits to reserve, verified on a watch)
NUMBER_SOURCES = {
    'steps': (codes.STEPS, 5, True),
    'heart_rate': (codes.HEART_RATE, 3, True),
    'temperature': (codes.TEMPERATURE, 2, True),
    'battery': (codes.BATTERY_PERCENT, 3, True),
    'calories': (codes.CALORIES, 4, False),
    'temperature_high': (codes.TEMPERATURE_HIGH, 2, False),
    'temperature_low': (codes.TEMPERATURE_LOW, 2, False),
}
SIGNED_SOURCES = {'temperature', 'temperature_high', 'temperature_low'}

# name -> (tap target, verified)
TAP_TARGETS = {
    'steps': (codes.OPEN_STEPS, True),
    'heart_rate': (codes.OPEN_HEART_RATE, True),
    'weather': (codes.OPEN_WEATHER, True),
    'settings': (codes.OPEN_SETTINGS, True),
    'messages': (codes.OPEN_MESSAGES, False),
    'sleep': (codes.OPEN_SLEEP, True),
    'calories': (codes.OPEN_CALORIES, True),
    'emotions': (codes.OPEN_EMOTIONS, True),
    'altitude': (codes.OPEN_ALTITUDE, True),
    'pressure': (codes.OPEN_PRESSURE, True),
    'activity': (codes.OPEN_ACTIVITY, True),
    'workouts': (codes.OPEN_WORKOUTS, True),
    'alarms': (codes.OPEN_ALARMS, True),
    'stopwatch': (codes.OPEN_STOPWATCH, True),
    'timer': (codes.OPEN_TIMER, True),
    'contacts': (codes.OPEN_CONTACTS, True),
    'music': (codes.OPEN_MUSIC, False),
    'recorder': (codes.OPEN_RECORDER, False),
}

# values the watch writes itself, in its own font: name -> (source, sample)
TEXT_SOURCES = {
    'sleep': (codes.SLEEP, '7h23m'),
    'distance': (codes.DISTANCE, '1.94'),
    'calories': (codes.CALORIES, '535'),
    'pressure': (codes.PRESSURE, '990'),
    'altitude': (codes.ALTITUDE, '229'),
    'emotions': (codes.EMOTIONS, '--'),
    'steps': (codes.STEPS, '7645'),
    'heart_rate': (codes.HEART_RATE, '72'),
    'battery': (codes.BATTERY_PERCENT, '80'),
}
TEXT_STYLE_VERIFIED = 149
DEAD_TAP_TARGETS = {'battery': 'does nothing on this watch; open "settings" instead'}

WEATHER_SYMBOLS = ['cloud_off', 'sunny', 'clear_night', 'cloud', 'partly_cloudy_day', 'rainy',
                   'thunderstorm', 'weather_snowy', 'air', 'mist', 'foggy']

# the editor folds slots that share a function code, so each language needs its own
CHOICE_FUNCTIONS = [codes.FUNCTION_DATE, codes.FUNCTION_WEEKDAY, codes.FUNCTION_SUN]

WORD_FORMS = {
    'weekday': {'full': 'weekdays', 'short': 'weekdays_short'},
    'month': {'full': 'months', 'standalone': 'months_standalone', 'short': 'months_short'},
}

STYLE_FIELDS = {'style', 'font', 'size', 'weight', 'color', 'tracking', 'features', 'segments'}
PLACE_FIELDS = {'id', 'x', 'align', 'y', 'quiet'}
FIELDS = {
    'time': STYLE_FIELDS | PLACE_FIELDS | {'pad', 'layout', 'line_gap', 'colon', 'space', 'seconds',
                                           'like', 'max_width', 'leading_zero'},
    'day': STYLE_FIELDS | PLACE_FIELDS | {'pad', 'suffix', 'gap', 'digits', 'centred'},
    'weekday': STYLE_FIELDS | PLACE_FIELDS | {'form', 'case', 'max_right'},
    'month': STYLE_FIELDS | PLACE_FIELDS | {'form', 'case', 'max_right'},
    'number': STYLE_FIELDS | PLACE_FIELDS | {'source', 'pad', 'unit', 'gap', 'digits'},
    'text': STYLE_FIELDS | PLACE_FIELDS | {'text'},
    'symbol': PLACE_FIELDS | {'name', 'size', 'color', 'fill', 'weight'},
    'weather_icon': PLACE_FIELDS | {'size', 'color', 'fill', 'weight', 'icons'},
    'battery_icon': PLACE_FIELDS | {'color', 'low_color', 'width', 'height'},
    'seconds_mark': {'id', 'path', 'layers', 'reach', 'cover_grow'},
    'hands': {'id', 'centre', 'hour', 'minute', 'second', 'pin', 'behind'},
    'system_text': {'id', 'source', 'x', 'y', 'width', 'height', 'align', 'color', 'text_style', 'quiet'},
    'tap': {'id', 'box', 'open', 'card', 'elements'},
}
REQUIRED = {
    'time': {'size', 'x', 'y'}, 'day': {'size', 'x', 'y'}, 'weekday': {'size', 'x', 'y'},
    'month': {'size', 'x', 'y'}, 'number': {'source', 'size', 'x', 'y'}, 'text': {'text', 'size', 'x', 'y'},
    'symbol': {'name', 'size', 'x', 'y'}, 'weather_icon': {'size', 'x', 'y'}, 'battery_icon': {'x', 'y'},
    'seconds_mark': {'layers'}, 'tap': {'box', 'open', 'elements'}, 'hands': {'centre', 'hour', 'minute'},
    'system_text': {'source', 'x', 'y'},
}
TIME_GROUP = {'time', 'seconds_mark'}
LAYER_FIELDS = {
    'fill': {'color'},
    'gradient': {'top', 'bottom'},
    'glow': {'color', 'centre', 'reach', 'power', 'edge'},
    'card': {'box', 'radius', 'fill_alpha', 'rim_alpha'},
    'ticks': {'color', 'major_color'},
    'shapes': {'ss', 'items'},
    'picture': {'file'},
    'dial': {'box', 'radius', 'frame', 'minute', 'hour', 'inset', 'centre'},
    'lcd': {'box', 'radius', 'centre', 'edge', 'focus', 'reach', 'power', 'rim', 'rim_alpha', 'outline'},
}
DYNAMIC = ('list', 'number', 'hand', 'overlay', 'systext')
HAND_SOURCES = {'hour': codes.HAND_HOUR, 'minute': codes.HAND_MINUTE, 'second': codes.HAND_SECOND}
TOP_FIELDS = {'name', 'author', 'screen', 'font', 'colors', 'styles', 'ring', 'background', 'elements',
              'aod', 'languages', 'locales', 'notes'}
Y_ANCHORS = ('top', 'middle', 'bottom', 'digits_top', 'digits_middle', 'digits_bottom',
             'caps_top', 'caps_middle', 'caps_bottom')
EDGES = ('left', 'right', 'center', 'top', 'bottom', 'middle', 'width', 'height',
         'digits_top', 'digits_bottom', 'digits_middle', 'caps_top', 'caps_bottom', 'caps_middle')


class SpecError(Exception):
    """Raised with every problem found, each as 'where: what, and what to do'."""

    def __init__(self, problems):
        self.problems = problems
        super().__init__('\n'.join(problems))


def _near(word, options):
    hit = difflib.get_close_matches(str(word), list(options), n=1, cutoff=0.6)
    return ' (did you mean "%s"?)' % hit[0] if hit else ''


def _known(options):
    return ', '.join('"%s"' % o for o in sorted(options))


# ---------------------------------------------------------------- images

def clear_transparent(im):
    """Fully transparent pixels become 00000000, whatever colour they carried."""
    im = im.convert('RGBA')
    alpha = im.getchannel('A')
    if alpha.getextrema()[0] == 255:
        return im
    out = Image.new('RGBA', im.size, (0, 0, 0, 0))
    out.paste(im, (0, 0), alpha.point(lambda a: 255 if a else 0))
    return out


def _digest(im):
    return hashlib.sha1(im.tobytes()).hexdigest() + '%dx%d' % im.size


class CleanFace(layout.Face):
    """Image registry that clears transparency and stores each distinct picture once."""

    def add(self, im, key=None):
        im = clear_transparent(im)
        return super().add(im, ('px', _digest(im)))


# ---------------------------------------------------------------- pieces
# A resolved element is a list of pieces. Pieces are compared across languages: the
# ones that agree are drawn once, the ones that differ become editor choices.

class Piece:
    """kind: 'image' (static picture), 'paint' (drawn straight onto the background),
    'list' (picture picked by a source), 'number' (digits of a source)."""

    def __init__(self, kind, **kw):
        self.kind = kind
        self.__dict__.update(kw)

    def signature(self):
        if self.kind == 'image':
            return ('image', _digest(self.im), self.x, self.y)
        if self.kind == 'paint':
            return ('paint', self.key)
        if self.kind == 'list':
            return ('list', tuple(_digest(i) for i in self.ims), self.x, self.y, self.source)
        if self.kind == 'overlay':
            return ('overlay', _digest(self.im), self.x, self.y)
        if self.kind == 'hand':
            return ('hand', _digest(self.im), self.cx, self.cy, self.px, self.py, self.source)
        if self.kind == 'systext':
            return ('systext', self.rect, self.color, self.style, self.align, self.source)
        return ('number', tuple(_digest(i) for i in self.ims), self.x, self.y, self.align, self.source,
                _digest(self.minus) if self.minus is not None else None)

    def box(self):
        if self.kind == 'paint':
            return self.bbox
        if self.kind in ('image', 'overlay'):
            return (self.x, self.y, self.x + self.im.width, self.y + self.im.height)
        if self.kind == 'systext':
            x, y, w, h = self.rect
            return (x, y, x + w, y + h)
        if self.kind == 'hand':
            r = self.reach
            return (int(self.cx - r), int(self.cy - r), int(math.ceil(self.cx + r)), int(math.ceil(self.cy + r)))
        w = max(i.width for i in self.ims)
        h = max(i.height for i in self.ims)
        if self.kind == 'list':
            return (self.x, self.y, self.x + w, self.y + h)
        span = self.width
        x0 = {codes.ALIGN_LEFT: self.x, codes.ALIGN_RIGHT: self.x - span}.get(self.align, self.x - span // 2)
        return (x0, self.y, x0 + span, self.y + h)


class Placed:
    def __init__(self, kind, group, pieces, edges, box, path):
        self.kind, self.group, self.pieces, self.edges, self.box, self.path = kind, group, pieces, edges, box, path
        self.children = []
        self.geometry = None
        self.mark = None
        self.quiet = False
        self.behind = False
        self.ink_h = None


# ---------------------------------------------------------------- expressions

_TERM = re.compile(r'\s*([+-]?)\s*([A-Za-z_]\w*\.[A-Za-z_]+|\d+(?:\.\d+)?)\s*')


class Builder:
    """Turns one description into a face for a list of languages."""

    def __init__(self, spec, base_dir='.', langs=None):
        self.spec = spec
        self.base_dir = base_dir
        self.errors, self.warnings = [], []
        self._styles = {}
        self._check_top()
        if self.errors:
            raise SpecError(self.errors)
        self.width, self.height = SCREENS[spec.get('screen', 'HWHD13')]
        self.palette = {}
        for name, value in (spec.get('colors') or {}).items():
            self.palette[name] = self.color(value, 'colors.' + name)
        self.font = spec.get('font', 'Oswald')
        self.langs = list(langs or self.default_langs())
        if len(self.langs) > len(CHOICE_FUNCTIONS):
            raise SpecError(['languages: one face switches between at most %d languages; this asks for %d (%s)' % (
                len(CHOICE_FUNCTIONS), len(self.langs), ', '.join(self.langs))])
        if len(set(self.langs)) != len(self.langs):
            raise SpecError(['languages: "%s" lists a language twice' % ','.join(self.langs)])
        self.locales = {l: self._locale(l) for l in self.langs}
        rs = dict(spec.get('ring') or {})
        self.ring = draw.Ring(self.width, self.height, inset=rs.get('inset', 3), radius=rs.get('radius', 64),
                              length=tuple(rs.get('length', (5, 8))), thickness=tuple(rs.get('thickness', (1.8, 2.6))))
        self._check_elements(spec.get('elements', []), 'elements', aod=False)
        self._check_elements((spec.get('aod') or {}).get('elements', []), 'aod.elements', aod=True)
        for i, layer in enumerate(spec.get('background', [])):
            self._check_layer(layer, 'background[%d]' % i)
        for i, layer in enumerate((spec.get('aod') or {}).get('background', [])):
            self._check_layer(layer, 'aod.background[%d]' % i)
        if self.errors:
            raise SpecError(self.errors)

    # ------------------------------------------------------------ checks of shape

    def default_langs(self):
        lg = self.spec.get('languages') or {}
        return lg.get('default', ['en'])

    def _check_top(self):
        s = self.spec
        if not isinstance(s, dict):
            self.errors.append('description: must be a JSON object')
            return
        for k in s:
            if k not in TOP_FIELDS:
                self.errors.append('%s: unknown top-level field%s; known: %s' % (k, _near(k, TOP_FIELDS), _known(TOP_FIELDS)))
        if 'name' not in s:
            self.errors.append('name: missing; give the face a short title')
        if s.get('screen', 'HWHD13') not in SCREENS:
            self.errors.append('screen: "%s" is not supported; use %s' % (s.get('screen'), _known(SCREENS)))
        if s.get('font', 'Oswald') not in FONTS:
            self.errors.append('font: "%s" is not available%s; fonts: %s' % (s.get('font'), _near(s.get('font'), FONTS), _known(FONTS)))
        if not s.get('elements'):
            self.errors.append('elements: missing or empty; a face needs at least the time')
        lg = s.get('languages') or {}
        for k in lg:
            if k not in ('default', 'zone', 'frame'):
                self.errors.append('languages.%s: unknown field; known: "default", "zone", "frame"' % k)

    def _check_elements(self, elements, path, aod, inside_tap=False):
        ids = set()
        for i, el in enumerate(elements):
            p = '%s[%d]' % (path, i)
            if not isinstance(el, dict) or 'type' not in el:
                self.errors.append('%s: every element is an object with a "type"' % p)
                continue
            t = el['type']
            if t not in FIELDS:
                self.errors.append('%s.type: unknown element "%s"%s; known: %s' % (p, t, _near(t, FIELDS), _known(FIELDS)))
                continue
            for k in el:
                if k != 'type' and k not in FIELDS[t]:
                    self.errors.append('%s.%s: "%s" has no field "%s"%s; it takes %s' % (
                        p, k, t, k, _near(k, FIELDS[t]), _known(FIELDS[t])))
            missing = REQUIRED[t] - set(el)
            if t == 'time' and 'like' in el:
                missing = set()
            for k in sorted(missing):
                self.errors.append('%s: "%s" needs "%s"' % (p, t, k))
            if 'id' in el:
                if not re.match(r'^[A-Za-z_]\w*$', str(el['id'])) or el['id'] in ('screen', 'parent'):
                    self.errors.append('%s.id: "%s" must be letters, digits and _ and not "screen" or "parent"' % (p, el['id']))
                if el['id'] in ids:
                    self.errors.append('%s.id: "%s" is used twice' % (p, el['id']))
                ids.add(el['id'])
            if t == 'number' and 'source' in el and el['source'] not in NUMBER_SOURCES:
                self.errors.append('%s.source: unknown "%s"%s; sources: %s' % (
                    p, el['source'], _near(el['source'], NUMBER_SOURCES), _known(NUMBER_SOURCES)))
            elif t == 'number' and el.get('source') in NUMBER_SOURCES and not NUMBER_SOURCES[el['source']][2]:
                self.warnings.append('%s.source: "%s" is seen in other faces but not yet confirmed on a watch' % (p, el['source']))
            if t == 'system_text' and el.get('source') not in TEXT_SOURCES:
                self.errors.append('%s.source: unknown "%s"%s; the watch writes %s' % (
                    p, el.get('source'), _near(el.get('source'), TEXT_SOURCES), _known(TEXT_SOURCES)))
            if t == 'system_text' and aod:
                self.errors.append('%s: system text on the always-on screen is not confirmed; leave it out' % p)
            if t == 'symbol' and 'name' in el and el['name'] not in SYMBOLS.cp:
                self.errors.append('%s.name: no symbol "%s"%s' % (p, el['name'], _near(el['name'], SYMBOLS.cp)))
            if t in ('weekday', 'month') and el.get('form', 'full') not in WORD_FORMS[t]:
                self.errors.append('%s.form: "%s" takes %s' % (p, t, _known(WORD_FORMS[t])))
            if t in ('weekday', 'month') and el.get('case', 'upper') not in ('upper', 'lower', 'title', 'as_is'):
                self.errors.append('%s.case: use "upper", "lower", "title" or "as_is"' % p)
            if 'align' in el and el['align'] not in ('left', 'center', 'right'):
                self.errors.append('%s.align: use "left", "center" or "right"' % p)
            if 'font' in el and el['font'] not in FONTS:
                self.errors.append('%s.font: "%s" is not available%s; fonts: %s' % (p, el['font'], _near(el['font'], FONTS), _known(FONTS)))
            if 'style' in el and el['style'] not in (self.spec.get('styles') or {}):
                self.errors.append('%s.style: no style "%s" under "styles"%s' % (p, el['style'], _near(el['style'], self.spec.get('styles') or {})))
            if aod:
                if t in ('tap', 'seconds_mark'):
                    self.errors.append('%s: "%s" is not shown on the always-on screen; leave it out of "aod"' % (p, t))
                if t == 'time' and 'seconds' in el:
                    self.errors.append('%s.seconds: the always-on screen changes once a minute; remove "seconds"' % p)
            if t == 'tap':
                if inside_tap:
                    self.errors.append('%s: a tap zone cannot sit inside another' % p)
                o = el.get('open')
                if o in DEAD_TAP_TARGETS:
                    self.errors.append('%s.open: "%s" %s' % (p, o, DEAD_TAP_TARGETS[o]))
                elif o not in TAP_TARGETS:
                    self.errors.append('%s.open: unknown "%s"%s; targets: %s' % (p, o, _near(o, TAP_TARGETS), _known(TAP_TARGETS)))
                elif not TAP_TARGETS[o][1]:
                    self.warnings.append('%s.open: "%s" is seen in other faces but not yet confirmed on a watch' % (p, o))
                self._check_elements(el.get('elements', []), p + '.elements', aod, inside_tap=True)

    def _check_layer(self, layer, p):
        t = layer.get('type') if isinstance(layer, dict) else None
        if t not in LAYER_FIELDS:
            self.errors.append('%s.type: unknown layer "%s"%s; layers: %s' % (p, t, _near(t, LAYER_FIELDS), _known(LAYER_FIELDS)))
            return
        for k in layer:
            if k != 'type' and k not in LAYER_FIELDS[t]:
                self.errors.append('%s.%s: layer "%s" has no field "%s"%s; it takes %s' % (
                    p, k, t, k, _near(k, LAYER_FIELDS[t]), _known(LAYER_FIELDS[t])))

    # ------------------------------------------------------------ values

    def note_warning(self, msg):
        if msg not in self.warnings:
            self.warnings.append(msg)

    def color(self, v, path):
        if isinstance(v, str) and v in getattr(self, 'palette', {}):
            return self.palette[v]
        if isinstance(v, str) and re.match(r'^#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$', v):
            h = v[1:]
            c = tuple(int(h[i:i + 2], 16) for i in range(0, len(h), 2))
            return c if len(c) == 4 else c + (255,)
        if isinstance(v, (list, tuple)) and len(v) in (3, 4) and all(isinstance(c, int) and 0 <= c <= 255 for c in v):
            return tuple(v) if len(v) == 4 else tuple(v) + (255,)
        known = list(getattr(self, 'palette', {}))
        raise SpecError(['%s: "%s" is not a colour; use "#RRGGBB", "#RRGGBBAA", [r, g, b, a] or a palette name%s' % (
            path, v, _near(v, known) if known else '')])

    def style(self, font, size, weight, color, tracking=0, sample='', features=None, segments=None):
        if font == 'Segments':
            sg = segments or {}
            key = ('seg', size, color, sg.get('ghost'), sg.get('aspect', 0.5), sg.get('thickness', 0.13),
                   sg.get('shadow'))
            if key not in self._styles:
                self._styles[key] = draw.Segments(size, color, sg.get('ghost'), sg.get('aspect', 0.5),
                                                  sg.get('thickness', 0.13), sg.get('shadow'))
            return self._styles[key]
        key = (font, size, weight, color, tracking, sample, tuple(features or ()))
        if key not in self._styles:
            self._styles[key] = draw.Style(os.path.join(FONT_DIR, FONTS[font]), size, weight, color, tracking,
                                           sample, features=list(features) if features else None)
        return self._styles[key]

    def _locale(self, lang):
        table = {}
        path = os.path.join(LOCALE_DIR, lang + '.json')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as fh:
                table = json.load(fh)
        table.update((self.spec.get('locales') or {}).get(lang, {}))
        need = {'weekdays': 7, 'months': 12}
        for k, n in need.items():
            if len(table.get(k, [])) != n:
                raise SpecError(['locales.%s.%s: language "%s" is not built in; give %d words' % (lang, k, lang, n)])
        table.setdefault('weekdays_short', table['weekdays'])
        table.setdefault('months_standalone', table['months'])
        table.setdefault('months_short', table['months'])
        table.setdefault('day_suffix', '')
        return table

    def words(self, kind, form, case, lang):
        ws = self.locales[lang][WORD_FORMS[kind][form]]
        if case == 'upper':
            return [w.upper() for w in ws]
        if case == 'lower':
            return [w.lower() for w in ws]
        if case == 'title':
            return [w[:1].upper() + w[1:] for w in ws]
        return list(ws)


class Resolver:
    """Places every element of one screen mode for one language. Elements are placed
    on demand, so references may point forwards as long as they do not go round."""

    def __init__(self, b, lang, elements, path, fallback=None):
        self.b, self.lang, self.fallback = b, lang, fallback
        self.entries = {}
        self.order = []
        self.done = {}
        self.active = []
        for i, el in enumerate(elements):
            key = el.get('id') or '#%s[%d]' % (path, i)
            self.entries[key] = (el, '%s[%d]' % (path, i), None)
            self.order.append(key)
            if el['type'] == 'tap':
                for j, ch in enumerate(el.get('elements', [])):
                    ck = ch.get('id') or '#%s[%d].elements[%d]' % (path, i, j)
                    self.entries[ck] = (ch, '%s[%d].elements[%d]' % (path, i, j), key)

    def run(self):
        return [self.get(k) for k in self.order]

    def get(self, key, ref_path=None):
        if key in self.done:
            return self.done[key]
        if key not in self.entries:
            if self.fallback is not None and key in self.fallback.entries:
                return self.fallback.get(key, ref_path)
            known = [k for k in self.entries if not k.startswith('#')]
            raise SpecError(['%s: no element with id "%s"%s' % (ref_path, key, _near(key, known))])
        if key in self.active:
            chain = ' -> '.join(self.active[self.active.index(key):] + [key])
            raise SpecError(['%s: positions refer to each other in a circle: %s' % (self.entries[key][1], chain)])
        self.active.append(key)
        el, path, parent = self.entries[key]
        placed = getattr(self, 'place_' + el['type'])(el, path, parent)
        placed.quiet = bool(el.get('quiet'))
        placed.behind = bool(el.get('behind'))
        e = placed.edges
        if el['type'] in ('time', 'day', 'number') and 'digits_top' in e:
            placed.ink_h = int(round(e['digits_bottom'] - e['digits_top'])) if el['type'] != 'time' else \
                int(round(placed.geometry and (e['digits_bottom'] - e['digits_top']) or 0))
        elif el['type'] in ('weekday', 'month', 'text') and 'caps_top' in e:
            placed.ink_h = int(round(e['caps_bottom'] - e['caps_top']))
        self.active.pop()
        self.done[key] = placed
        return placed

    # ------------------------------------------------------------ values

    def value(self, v, path, parent):
        if isinstance(v, bool) or v is None:
            raise SpecError(['%s: expected a number or a reference like "day.right+12"' % path])
        if isinstance(v, (int, float)):
            return v
        if not isinstance(v, str):
            raise SpecError(['%s: expected a number or a reference like "day.right+12"' % path])
        pos, total = 0, 0.0
        while pos < len(v):
            m = _TERM.match(v, pos)
            if not m or m.end() == pos or (pos > 0 and not m.group(1)):
                raise SpecError(['%s: cannot read "%s"; write a number or "id.edge" joined by + and -' % (path, v)])
            sign = -1 if m.group(1) == '-' else 1
            term = m.group(2)
            total += sign * (float(term) if term[0].isdigit() else self.ref(term, path, parent))
            pos = m.end()
        return int(total) if total == int(total) else total

    def ref(self, term, path, parent):
        name, edge = term.split('.')
        if edge not in EDGES:
            raise SpecError(['%s: "%s" has no edge "%s"%s; edges: %s' % (path, term, edge, _near(edge, EDGES), _known(EDGES))])
        if name == 'screen':
            W, H = self.b.width, self.b.height
            e = {'left': 0, 'right': W, 'center': W / 2.0, 'top': 0, 'bottom': H, 'middle': H / 2.0,
                 'width': W, 'height': H}
            if edge not in e:
                raise SpecError(['%s: the screen has no "%s"' % (path, edge)])
            v = e[edge]
            return int(v) if v == int(v) else v
        if name == 'parent':
            if parent is None:
                raise SpecError(['%s: "parent" only exists inside a tap zone' % path])
            name = parent
        target = self.get(name, path)
        if edge not in target.edges:
            raise SpecError(['%s: "%s" has no "%s" line; it has %s' % (path, name, edge, _known(target.edges))])
        return target.edges[edge]

    def style(self, el, path, sample=''):
        s = dict((self.b.spec.get('styles') or {}).get(el.get('style'), {}))
        s.update((k, el[k]) for k in STYLE_FIELDS if k in el and k != 'style')
        font = s.get('font', self.b.font)
        size = s.get('size')
        if not isinstance(size, int) or not 6 <= size <= 400:
            raise SpecError(['%s.size: give a whole number of pixels between 6 and 400' % path])
        color = self.b.color(s.get('color', '#FFFFFF'), path + '.color')
        seg = None
        if font == 'Segments':
            seg = dict(s.get('segments') or {})
            for k in seg:
                if k not in ('ghost', 'aspect', 'thickness', 'shadow'):
                    raise SpecError(['%s.segments.%s: unknown; segments take "ghost", "aspect", "thickness", '
                                     '"shadow"' % (path, k)])
            if seg.get('ghost') is not None:
                seg['ghost'] = self.b.color(seg['ghost'], path + '.segments.ghost')
            if seg.get('shadow'):
                sh = seg['shadow']
                seg['shadow'] = (self.b.color(sh.get('color', '#00000060'), path + '.segments.shadow.color'),
                                 sh.get('dx', 2), sh.get('dy', 3), sh.get('blur', 1.0))
        return self.b.style(font, size, s.get('weight', 400), color, s.get('tracking', 0), sample, s.get('features'),
                            seg)

    def place_y(self, yv, path, parent, height, st=None):
        """Top of the picture so that the named line lands on the given value."""
        if not isinstance(yv, dict):
            return int(round(self.value(yv, path, parent)))
        if len(yv) != 1 or next(iter(yv)) not in Y_ANCHORS:
            raise SpecError(['%s: name one line to place, one of %s' % (path, _known(Y_ANCHORS))])
        k, raw = next(iter(yv.items()))
        v = self.value(raw, path + '.' + k, parent)
        if k == 'top':
            return int(round(v))
        if k == 'bottom':
            return int(round(v)) - height
        if k == 'middle':
            return int(round(v - height / 2.0))
        if st is None:
            raise SpecError(['%s: "%s" needs text; for pictures use "top", "middle" or "bottom"' % (path, k)])
        t, b = st.digit_ink if k.startswith('digits') else st.cap_ink
        if k.endswith('_top'):
            return int(round(v)) - t
        if k.endswith('_bottom'):
            return int(round(v)) - b
        return int(round(v - (t + b) / 2.0))

    def place_x(self, el, path, parent, width):
        v = self.value(el['x'], path + '.x', parent)
        align = el.get('align', 'left')
        if align == 'right':
            return int(round(v)) - width
        if align == 'center':
            return int(math.floor(v - width / 2.0))
        return int(round(v))

    @staticmethod
    def edges(box, st=None, y=None):
        x0, y0, x1, y1 = box
        e = {'left': x0, 'right': x1, 'top': y0, 'bottom': y1, 'width': x1 - x0, 'height': y1 - y0,
             'center': (x0 + x1) / 2.0, 'middle': (y0 + y1) / 2.0}
        if st is not None:
            dt, db = y + st.digit_ink[0], y + st.digit_ink[1]
            ct, cb = y + st.cap_ink[0], y + st.cap_ink[1]
            e.update(digits_top=dt, digits_bottom=db, digits_middle=(dt + db) / 2.0,
                     caps_top=ct, caps_bottom=cb, caps_middle=(ct + cb) / 2.0)
        for k, v in list(e.items()):
            if isinstance(v, float) and v == int(v):
                e[k] = int(v)
        return e

    def numeric_sample(self, extra=''):
        sfx = ''.join(self.b.locales[l]['day_suffix'] for l in self.b.langs)
        return '%°' + extra + sfx

    # ------------------------------------------------------------ elements

    def place_time(self, el, path, parent):
        like = None
        if 'like' in el:
            like = self.get(el['like'], path + '.like')
            if like.kind != 'time':
                raise SpecError(['%s.like: "%s" is not a time' % (path, el['like'])])
            base = dict(self.spec_of(el['like']))
            base.update((k, v) for k, v in el.items() if k not in ('like', 'id'))
            base.pop('seconds', None)
            el = base
        stacked = el.get('layout', 'line') == 'stacked'
        if el.get('layout', 'line') not in ('line', 'stacked'):
            raise SpecError(['%s.layout: use "line" or "stacked"' % path])
        pad = el.get('pad', 2)
        colon = el.get('colon')
        secs = el.get('seconds')
        size = el.get('size')
        while True:
            st = self.style(dict(el, size=size), path)
            digits, cell = st.digits(extra_pad=pad)
            if secs:
                ss = dict(secs)
                ssize = ss.get('size') or max(8, int(size * ss.get('scale', 0.32)))
                over = dict((k, ss[k]) for k in ('font', 'segments', 'weight', 'color', 'tracking') if k in ss)
                sst = self.style(dict(el, size=ssize, **over), path + '.seconds')
                sdigits, scell = sst.digits(extra_pad=ss.get('pad', 1))
                sgap = ss.get('gap', 10)
            cw = colon.get('width', 26) if colon else el.get('space', int(round(size * 0.2)))
            if stacked:
                total = 2 * cell + ((sgap + 2 * scell) if secs else 0)
            else:
                total = 4 * cell + cw + ((sgap + 2 * scell) if secs else 0)
            if like or 'max_width' not in el or total <= el['max_width'] or size <= 12:
                break
            size -= 1
        t, b = st.digit_ink
        ink_h = b - t
        if like:
            g = like.geometry
            tx, ty, cols, rows = g['tx'], g['ty'], g['cols'], g['rows']
        else:
            tx = self.place_x(el, path, parent, total)
            if stacked:
                block = 2 * ink_h + el.get('line_gap', 20)
                yv = el['y']
                k = next(iter(yv)) if isinstance(yv, dict) else 'top'
                if k == 'digits_top':
                    top = int(round(self.value(yv[k], path + '.y.' + k, parent)))
                elif k == 'digits_bottom':
                    top = int(round(self.value(yv[k], path + '.y.' + k, parent))) - block
                elif k == 'digits_middle':
                    top = int(round(self.value(yv[k], path + '.y.' + k, parent) - block / 2.0))
                else:
                    raise SpecError(['%s.y: a stacked time is placed by "digits_top", "digits_middle" or "digits_bottom"' % path])
                ty = top - t
                rows = [ty, top + ink_h + el.get('line_gap', 20) - t]
                cols = [tx, tx + cell, tx, tx + cell]
            else:
                ty = self.place_y(el['y'], path + '.y', parent, st.height, st)
                rows = [ty, ty]
                cols = [tx, tx + cell, tx + 2 * cell + cw, tx + 3 * cell + cw]
        if stacked:
            ys = [rows[0], rows[0], rows[1], rows[1]]
        else:
            ys = [rows[0]] * 4
        sources = [(codes.HOUR_TENS, 3), (codes.HOUR_UNITS, 10), (codes.MINUTE_TENS, 6), (codes.MINUTE_UNITS, 10)]
        pieces = [Piece('list', ims=digits[:n], x=cols[i], y=ys[i], source=src) for i, (src, n) in enumerate(sources)]
        if el.get('leading_zero', True) is False:
            blank = st.blank(pad) if hasattr(st, 'blank') else Image.new('RGBA', digits[0].size, (0, 0, 0, 0))
            pieces[0].ims = [blank] + digits[1:3]
        last_y = ys[3]
        if colon and not stacked:
            ccol = self.b.color(colon.get('color', el.get('color', '#FFFFFF')), path + '.colon.color')
            cx = cols[1] + cell + cw / 2.0
            ctop, cbot = ys[0] + t, ys[0] + b
            r, spread = colon.get('radius', 5), colon.get('spread', 0.22)

            square = colon.get('shape', 'round') == 'square'
            if colon.get('shape', 'round') not in ('round', 'square'):
                raise SpecError(['%s.colon.shape: use "round" or "square"' % path])

            shadow = getattr(st, 'shadow', None)

            def paint(img, cx=cx, ctop=ctop, cbot=cbot, r=r, ccol=ccol, spread=spread, square=square, shadow=shadow):
                if not square:
                    draw.colon(img, cx, ctop, cbot, r, ccol, spread)
                    return
                mid, off = (ctop + cbot) / 2.0, (cbot - ctop) * spread

                def squares(g, color, dx=0, dy=0):
                    for cy in (mid - off, mid + off):
                        g.rectangle([int(round(cx - r)) + dx, int(round(cy - r)) + dy,
                                     int(round(cx + r)) - 1 + dx, int(round(cy + r)) - 1 + dy], fill=color)
                if shadow:
                    col, dx, dy, blur = shadow
                    sh = Image.new('RGBA', img.size, (0, 0, 0, 0))
                    squares(ImageDraw.Draw(sh), col, int(round(dx)), int(round(dy)))
                    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)) if blur else sh)
                squares(ImageDraw.Draw(img), ccol)
            off = (cbot - ctop) * spread
            pieces.insert(2, Piece('paint', fn=paint, key=('colon', cx, ctop, cbot, r, ccol, spread, square, shadow), role='colon',
                                   bbox=(int(cx - r), int((ctop + cbot) / 2.0 - off - r),
                                         int(math.ceil(cx + r)), int(math.ceil((ctop + cbot) / 2.0 + off + r)))))
        if secs and not like:
            sx = cols[3] + cell + sgap
            sy = last_y + b - sst.digit_ink[1]
            quiet = bool(secs.get('quiet'))
            pieces += [Piece('list', ims=sdigits[:6], x=sx, y=sy, source=codes.SECOND_TENS, role='seconds', quiet=quiet),
                       Piece('list', ims=sdigits, x=sx + scell, y=sy, source=codes.SECOND_UNITS, role='seconds',
                             quiet=quiet)]
        box = (tx, ys[0] + t, tx + total, last_y + b)
        p = Placed('time', 'time', pieces, self.edges(box, st, ys[0]), box, path)
        p.edges.update(digits_top=ys[0] + t, digits_bottom=last_y + b, digits_middle=(ys[0] + t + last_y + b) / 2.0)
        p.geometry = {'tx': tx, 'ty': ty, 'cols': cols, 'rows': rows}
        return p

    def _number(self, el, path, parent, source, max_digits, unit, minus, kind):
        """Digits of a source, right-aligned inside a box of max_digits cells: the only
        alignment confirmed on a watch, and the value never moves. A unit (or the
        day's suffix) follows the cells. x and align place the whole box."""
        st = self.style(el, path, self.numeric_sample(el.get('unit', '')))
        digits, cell = st.digits(extra_pad=el.get('pad', 0))
        md = el.get('digits', max_digits)
        y = self.place_y(el['y'], path + '.y', parent, st.height, st)
        minus_im = st.render('-') if minus else None
        unit_im = st.render(unit) if unit else None
        uw = unit_im.width if unit_im else 0
        gap = el.get('gap', 0) if unit_im else 0
        left = self.place_x(el, path, parent, md * cell + gap + uw)
        dr = left + md * cell
        pieces = [Piece('number', ims=digits, x=dr, y=y, align=codes.ALIGN_RIGHT, source=source,
                        minus=minus_im, width=md * cell),
                  Piece('image', im=unit_im, x=dr + gap, y=y, role='unit') if unit_im else None]
        box = (left, y + st.digit_ink[0], dr + gap + uw, y + st.digit_ink[1])
        return Placed(kind, 'date', pieces, self.edges(box, st, y), box, path)

    def place_day(self, el, path, parent):
        sfx = self.b.locales[self.lang]['day_suffix'] if el.get('suffix', True) else ''
        if el.get('centred'):
            return self._day_pictures(el, path, parent, sfx)
        return self._number(el, path, parent, codes.DAY_OF_MONTH, el.get('digits', 2), sfx, False, 'day')

    def _day_pictures(self, el, path, parent, sfx):
        """The day as 31 ready pictures, each centred in one cell with its suffix, so
        '9' sits as centred as '25.'. Not yet confirmed on a watch."""
        self.b.note_warning('%s.centred: a day drawn as 31 pictures is not yet confirmed on a watch; if it shows '
                            'nothing, drop "centred"' % path)
        st = self.style(el, path, self.numeric_sample())
        texts = [str(d) + sfx for d in range(1, 32)]
        ims = [st.render(tx) for tx in texts]
        cw = max(i.width for i in ims)
        cells = []
        for im in ims:
            c = Image.new('RGBA', (cw, im.height), (0, 0, 0, 0))
            c.alpha_composite(im, ((cw - im.width) // 2, 0))
            cells.append(c)
        x = self.place_x(el, path, parent, cw)
        y = self.place_y(el['y'], path + '.y', parent, st.height, st)
        piece = Piece('list', ims=[cells[0]] + cells, x=x, y=y, source=codes.DAY_OF_MONTH)
        box = (x, y + st.digit_ink[0], x + cw, y + st.digit_ink[1])
        return Placed('day', 'date', [piece], self.edges(box, st, y), box, path)

    def place_number(self, el, path, parent):
        src, md, _ = NUMBER_SOURCES[el['source']]
        return self._number(el, path, parent, src, md, el.get('unit', ''), el['source'] in SIGNED_SOURCES, 'number')

    def _words(self, el, path, parent, kind):
        form, case = el.get('form', 'full'), el.get('case', 'upper')
        sample = ''.join(w for l in self.b.langs for w in self.b.words(kind, form, case, l))
        mine = self.b.words(kind, form, case, self.lang)
        st = self.style(el, path, sample)
        if isinstance(st, draw.Segments):
            raise SpecError(['%s.font: segment digits cannot spell words; use "Oswald" or "Cormorant"' % path])
        x = self.value(el['x'], path + '.x', parent)
        if 'max_right' in el:
            limit = self.value(el['max_right'], path + '.max_right', parent)
            while st.size > 8 and x + max(st.width(w) for w in mine) > limit:
                st = self.style(dict(el, size=st.size - 1), path, sample)
            if x + max(st.width(w) for w in mine) > limit:
                raise SpecError(['%s.max_right: the words do not fit even at size 8' % path])
        ims = [st.render(w) for w in mine]
        align = el.get('align', 'left')
        if align != 'left':
            cw = max(i.width for i in ims)
            cells = []
            for im in ims:
                c = Image.new('RGBA', (cw, im.height), (0, 0, 0, 0))
                c.alpha_composite(im, (cw - im.width if align == 'right' else (cw - im.width) // 2, 0))
                cells.append(c)
            ims = cells
        w = max(i.width for i in ims)
        left = self.place_x(el, path, parent, w)
        y = self.place_y(el['y'], path + '.y', parent, st.height, st)
        source = codes.WEEKDAY if kind == 'weekday' else codes.MONTH
        piece = Piece('list', ims=[ims[0]] + ims, x=left, y=y, source=source)
        box = (left, y + st.cap_ink[0], left + w, y + st.cap_ink[1])
        return Placed(kind, 'date', [piece], self.edges(box, st, y), box, path)

    def place_weekday(self, el, path, parent):
        return self._words(el, path, parent, 'weekday')

    def place_month(self, el, path, parent):
        return self._words(el, path, parent, 'month')

    def _image(self, el, path, parent, im, kind, st=None):
        x = self.place_x(el, path, parent, im.width)
        y = self.place_y(el['y'], path + '.y', parent, im.height, st)
        box = (x, y, x + im.width, y + im.height)
        return x, y, box

    def place_text(self, el, path, parent):
        st = self.style(el, path, el['text'])
        im = st.render(el['text'])
        x, y, _ = self._image(el, path, parent, im, 'text', st)
        box = (x, y + st.cap_ink[0], x + im.width, y + st.cap_ink[1])
        return Placed('text', 'date', [Piece('image', im=im, x=x, y=y)], self.edges(box, st, y), box, path)

    def place_symbol(self, el, path, parent):
        col = self.b.color(el.get('color', '#FFFFFF'), path + '.color')
        im = SYMBOLS.get(el['name'], el['size'], col, el.get('fill', 1), el.get('weight', 500))
        x, y, box = self._image(el, path, parent, im, 'symbol')
        return Placed('symbol', 'date', [Piece('image', im=im, x=x, y=y)], self.edges(box), box, path)

    def place_weather_icon(self, el, path, parent):
        col = self.b.color(el.get('color', '#FFFFFF'), path + '.color')
        names = el.get('icons', WEATHER_SYMBOLS)
        if len(names) != len(WEATHER_SYMBOLS) or any(n not in SYMBOLS.cp for n in names):
            raise SpecError(['%s.icons: give %d symbol names, one per weather state: %s' % (
                path, len(WEATHER_SYMBOLS), ', '.join(codes.WEATHER_STATES))])
        ims = SYMBOLS.same_box(names, el['size'], col, el.get('fill', 1))
        x, y, box = self._image(el, path, parent, ims[0], 'weather_icon')
        return Placed('weather_icon', 'date', [Piece('list', ims=ims, x=x, y=y, source=codes.WEATHER_ICON)],
                      self.edges(box), box, path)

    def place_battery_icon(self, el, path, parent):
        col = self.b.color(el.get('color', '#FFFFFF'), path + '.color')
        low = self.b.color(el.get('low_color', el.get('color', '#FFFFFF')), path + '.low_color')
        w, h = el.get('width', 40), el.get('height', 22)
        ims = [draw.battery(i, col, low, w, h) for i in range(11)]
        x, y, box = self._image(el, path, parent, ims[10], 'battery_icon')
        return Placed('battery_icon', 'date', [Piece('list', ims=ims, x=x, y=y, source=codes.BATTERY_LEVEL)],
                      self.edges(box), box, path)

    def place_seconds_mark(self, el, path, parent):
        p = el.get('path', 'ring')
        W, H = self.b.width, self.b.height
        if p == 'ring':
            track = self.b.ring
        elif isinstance(p, dict) and set(p) == {'line'}:
            ln = p['line']
            try:
                start = tuple(self.value(v, path + '.path.line.from', parent) for v in ln['from'])
                end = tuple(self.value(v, path + '.path.line.to', parent) for v in ln['to'])
            except (KeyError, TypeError):
                raise SpecError(['%s.path.line: give "from": [x, y] and "to": [x, y]' % path])
            track = draw.Track.line(W, H, start, end, decade_gap=ln.get('decade_gap', 0))
        else:
            raise SpecError(['%s.path: use "ring" or {"line": {"from": [x, y], "to": [x, y], "decade_gap": n}}' % path])
        layers = []
        for i, ly in enumerate(el['layers']):
            if 'radius' not in ly:
                raise SpecError(['%s.layers[%d]: each layer needs a "radius"' % (path, i)])
            layers.append((ly['radius'], self.b.color(ly.get('color', '#FFFFFF'), '%s.layers[%d].color' % (path, i)),
                           ly.get('blur', 0)))
        reach = el.get('reach', max(r + 2 * bl for r, _, bl in layers))

        def paint(indices):
            im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            for r, c, bl in layers:
                balls = track.draw_balls(indices, r, c)
                if bl:
                    balls = balls.filter(ImageFilter.GaussianBlur(bl))
                im.alpha_composite(balls)
            return im
        paint.reach = reach
        pts = [track.ball_centre(i) for i in range(60)]
        box = (int(min(x for x, _ in pts) - reach), int(min(y for _, y in pts) - reach),
               int(math.ceil(max(x for x, _ in pts) + reach)), int(math.ceil(max(y for _, y in pts) + reach)))
        placed = Placed('seconds_mark', 'time', [], self.edges(box), box, path)
        placed.mark = (track, paint, el.get('cover_grow', 1.5))
        return placed

    def place_hands(self, el, path, parent):
        """Hour, minute and optionally second hands turning about one centre, with a pin on top."""
        c = el['centre']
        if not isinstance(c, list) or len(c) != 2:
            raise SpecError(['%s.centre: give [x, y]' % path])
        cx = self.value(c[0], path + '.centre[0]', parent)
        cy = self.value(c[1], path + '.centre[1]', parent)
        pieces, reach = [], 0
        for name in ('hour', 'minute', 'second'):
            hs = el.get(name)
            if hs is None:
                continue
            hp = '%s.%s' % (path, name)
            for k in hs:
                if k not in ('length', 'tail', 'width', 'color', 'inner'):
                    raise SpecError(['%s.%s: a hand takes "length", "tail", "width", "color", "inner"%s' % (
                        hp, k, _near(k, ('length', 'tail', 'width', 'color', 'inner')))])
            if 'length' not in hs:
                raise SpecError(['%s: give the hand a "length" in pixels from the centre' % hp])
            tail = hs.get('tail', 0)
            if tail > hs['length']:
                raise SpecError(['%s.tail: the tail must be shorter than the hand' % hp])
            inner = None
            if hs.get('inner'):
                inner = dict(hs['inner'])
                inner['color'] = self.b.color(inner.get('color', '#000000'), hp + '.inner.color')
                inner.setdefault('inset', 2)
            ink = self.b.color(hs.get('color', '#FFFFFF'), hp + '.color')
            im, px, py = draw.hand(hs['length'], tail, hs.get('width', 4), ink, inner)
            if name == 'second':
                self.b.note_warning('%s: the second hand is seen in other faces but not yet confirmed on a watch' % hp)
            pieces.append(Piece('hand', im=im, cx=cx, cy=cy, px=px, py=py, source=HAND_SOURCES[name],
                                reach=hs['length'], role=name, ink=ink))
            reach = max(reach, hs['length'])
        if el.get('pin'):
            rings = [(r['radius'], self.b.color(r.get('color', '#FFFFFF'), '%s.pin[%d].color' % (path, i)))
                     for i, r in enumerate(el['pin'])]
            im = draw.pin(sorted(rings, key=lambda rc: -rc[0]))
            pieces.append(Piece('overlay', im=im, x=int(round(cx - im.width / 2.0)), y=int(round(cy - im.height / 2.0)),
                                role='pin'))
        box = (int(cx - reach), int(cy - reach), int(math.ceil(cx + reach)), int(math.ceil(cy + reach)))
        return Placed('hands', 'time', pieces, self.edges(box), box, path)

    def place_system_text(self, el, path, parent):
        """A value the watch writes in its own font into a box. Its size is the watch's to
        choose by the style code; only style 149 has been seen on this screen."""
        src, sample = TEXT_SOURCES[el['source']]
        w, h = el.get('width', 120), el.get('height', 31)
        align = el.get('align', 'left')
        x = self.place_x(el, path, parent, w)
        y = self.place_y(el['y'], path + '.y', parent, h)
        col = self.b.color(el.get('color', '#FFFFFF'), path + '.color')
        style = el.get('text_style', TEXT_STYLE_VERIFIED)
        if style != TEXT_STYLE_VERIFIED:
            self.b.note_warning('%s.text_style: %s is seen in other faces; only %d is confirmed on this screen' % (
                path, style, TEXT_STYLE_VERIFIED))
        piece = Piece('systext', rect=(x, y, w, h), color=col, style=style, source=src, sample=sample,
                      align={'left': 0, 'center': 1, 'right': 2}[align])
        box = (x, y, x + w, y + h)
        return Placed('system_text', 'date', [piece], self.edges(box), box, path)

    def place_tap(self, el, path, parent):
        bx = el['box']
        if not isinstance(bx, list) or len(bx) != 4:
            raise SpecError(['%s.box: give [left, top, right, bottom]' % path])
        box = tuple(int(round(self.value(v, '%s.box[%d]' % (path, i), None))) for i, v in enumerate(bx))
        if box[2] <= box[0] or box[3] <= box[1]:
            raise SpecError(['%s.box: right must exceed left and bottom must exceed top' % path])
        placed = Placed('tap', 'zone', [], self.edges(box), box, path)
        self.done[self._key_of(el)] = placed     # children may refer to their parent
        pieces = []
        if 'card' in el:
            card = el['card'] if isinstance(el['card'], dict) else {}
            radius = card.get('radius', 22)
            fa, ra = card.get('fill_alpha', 14), card.get('rim_alpha', 46)

            def paint(img, box=box, radius=radius, fa=fa, ra=ra):
                draw.glass(img, box, radius=radius, fill_alpha=fa, rim_alpha=ra)
            pieces.append(Piece('paint', fn=paint, key=('card', box, radius, fa, ra), bbox=box, card=(box, radius)))
        placed.pieces = pieces
        placed.target = TAP_TARGETS[el['open']][0]
        for ch in el.get('elements', []):
            placed.children.append(self.get(self._key_of(ch)))
        return placed

    def _key_of(self, el):
        return next(k for k, (e, _, _) in self.entries.items() if e is el)

    def spec_of(self, key):
        if key in self.entries:
            return self.entries[key][0]
        return self.fallback.spec_of(key)


# ---------------------------------------------------------------- background layers

def paint_layer(b, img, layer, path):
    t = layer['type']
    W, H = img.size
    if t == 'fill':
        img.alpha_composite(Image.new('RGBA', (W, H), b.color(layer.get('color', '#000000'), path + '.color')))
    elif t == 'gradient':
        top, bot = b.color(layer['top'], path + '.top'), b.color(layer['bottom'], path + '.bottom')
        g = Image.new('RGBA', (1, H))
        for y in range(H):
            k = y / float(max(1, H - 1))
            g.putpixel((0, y), tuple(int(round(top[i] + (bot[i] - top[i]) * k)) for i in range(4)))
        img.alpha_composite(g.resize((W, H)))
    elif t == 'glow':
        c = b.color(layer.get('color', '#FF0000'), path + '.color')
        img.alpha_composite(draw.glow(W, H, c[:3], tuple(layer.get('centre', (0.5, 0.47))),
                                      tuple(layer.get('reach', (0.80, 0.66))), layer.get('power', 1.5),
                                      tuple(layer.get('edge', (6, 70)))))
    elif t == 'card':
        draw.glass(img, tuple(layer['box']), radius=layer.get('radius', 22),
                   fill_alpha=layer.get('fill_alpha', 14), rim_alpha=layer.get('rim_alpha', 46))
    elif t == 'ticks':
        minor = b.color(layer.get('color', '#333333'), path + '.color')
        major = b.color(layer.get('major_color', layer.get('color', '#555555')), path + '.major_color')
        img.alpha_composite(b.ring.draw_ticks(range(60), lambda i: major if b.ring.ticks[i][2] else minor))
    elif t == 'shapes':
        ss = layer.get('ss', 4)
        im = Image.new('RGBA', (W * ss, H * ss), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for i, it in enumerate(layer.get('items', [])):
            p = '%s.items[%d]' % (path, i)
            col = b.color(it.get('color', '#FFFFFF'), p + '.color')
            if 'line' in it:
                d.line([(x * ss, y * ss) for x, y in it['line']], fill=col, width=max(1, int(it.get('width', 1) * ss)))
            elif 'ellipse' in it:
                d.ellipse([v * ss for v in it['ellipse']], fill=col)
            elif 'rect' in it:
                d.rounded_rectangle([v * ss for v in it['rect']], radius=it.get('radius', 0) * ss, fill=col)
            else:
                raise SpecError(['%s: a shape is "line": [[x, y], ...], "ellipse": [l, t, r, b] or "rect": [l, t, r, b]' % p])
        img.alpha_composite(im.resize((W, H), Image.LANCZOS))
    elif t == 'lcd':
        o = layer.get('outline')
        img.alpha_composite(draw.lcd_window(
            (W, H), tuple(layer['box']), layer.get('radius', 20),
            b.color(layer.get('centre', '#F8C470'), path + '.centre'), b.color(layer.get('edge', '#BE7024'), path + '.edge'),
            tuple(layer.get('focus', (0.42, 0.38))), tuple(layer.get('reach', (0.62, 0.95))), layer.get('power', 1.6),
            layer.get('rim', 7), layer.get('rim_alpha', 140),
            (b.color(o.get('color', '#3A3A38'), path + '.outline.color'), o.get('width', 2)) if o else None))
    elif t == 'dial':
        def part(name):
            v = layer.get(name)
            if not v:
                return None
            v = dict(v)
            v['color'] = b.color(v.get('color', '#FFFFFF'), '%s.%s.color' % (path, name))
            v.setdefault('width', 1)
            v.setdefault('length', 6)
            return v
        img.alpha_composite(draw.dial((W, H), tuple(layer['box']), layer.get('radius', 20), part('frame'),
                                      part('minute'), part('hour'), layer.get('inset', 5),
                                      tuple(layer['centre']) if 'centre' in layer else None))
    elif t == 'picture':
        f = os.path.join(b.base_dir, layer['file'])
        if not os.path.exists(f):
            raise SpecError(['%s.file: no picture "%s" next to the description' % (path, layer['file'])])
        pic = Image.open(f).convert('RGBA')
        k = max(W / float(pic.width), H / float(pic.height))
        pic = pic.resize((int(math.ceil(pic.width * k)), int(math.ceil(pic.height * k))), Image.LANCZOS)
        img.alpha_composite(pic.crop(((pic.width - W) // 2, (pic.height - H) // 2,
                                      (pic.width - W) // 2 + W, (pic.height - H) // 2 + H)))


# ---------------------------------------------------------------- assembly

def _layout_items(pieces, face, aod, origin=None):
    """Pieces -> layout elements; origin set means inside a choice slot."""
    out = []
    for p in pieces:
        if p is None:
            continue
        if p.kind == 'image':
            ref = face.add(p.im)
            out.append(layout.slot_image(ref, p.x - origin[0], p.y - origin[1], aod) if origin
                       else layout.image(ref, p.x, p.y, aod))
        elif p.kind == 'list':
            refs = face.add_set(p.ims, None)
            out.append(layout.slot_image_list(refs, p.x - origin[0], p.y - origin[1], p.source, aod) if origin
                       else layout.image_list(refs, p.x, p.y, p.source, aod))
        elif p.kind == 'overlay':
            ref = face.add(p.im)
            out.append(layout.slot_image(ref, p.x - origin[0], p.y - origin[1], aod) if origin
                       else layout.image(ref, p.x, p.y, aod))
        elif p.kind == 'systext':
            if origin:
                raise SpecError(['system text cannot depend on the language'])
            x, y, w, h = p.rect
            out.append((codes.TEXT, [(1, [(1, x), (2, y), (3, w), (4, h)]),
                                     (2, [(1, p.color[0]), (2, p.color[1]), (3, p.color[2]), (4, p.color[3])]),
                                     (3, p.style), (4, p.align), (5, p.source), (7, aod)]))
        elif p.kind == 'hand':
            if origin:
                raise SpecError(['hands cannot depend on the language'])
            out.append(layout.hand(face.add(p.im), int(round(p.cx)), int(round(p.cy)), int(round(p.px)),
                                   int(round(p.py)), p.source, aod))
        elif p.kind == 'number':
            refs = face.add_set(p.ims, None)
            minus = face.add(p.minus) if p.minus is not None else ''
            out.append(layout.slot_number(refs, p.x - origin[0], p.y - origin[1], p.align, p.source, aod, minus)
                       if origin else layout.number(refs, p.x, p.y, p.align, p.source, aod, minus))
    return out


def _paint_static(img, piece):
    if piece.kind == 'image':
        img.alpha_composite(piece.im, (piece.x, piece.y))
    elif piece.kind == 'paint':
        piece.fn(img)


def _sample_render(pieces, size, origin, values):
    """Draw slot pieces for the editor's thumbnail."""
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    for p in pieces:
        if p is None:
            continue
        x, y = p.x - origin[0], p.y - origin[1]
        if p.kind == 'image':
            simulate._put(im, p.im, x, y)
        elif p.kind == 'list':
            i = values.get(p.source, 0)
            if 0 <= i < len(p.ims):
                simulate._put(im, p.ims[i], x, y)
        elif p.kind == 'number':
            parts = [p.ims[int(c)] for c in str(values.get(p.source, 8))]
            w = sum(q.width for q in parts)
            x -= w if p.align == codes.ALIGN_RIGHT else (w // 2 if p.align == codes.ALIGN_CENTER else 0)
            for q in parts:
                simulate._put(im, q, x, y)
                x += q.width
        elif p.kind == 'paint':
            layer = Image.new('RGBA', (size[0] + origin[0], size[1] + origin[1]), (0, 0, 0, 0))
            p.fn(layer)
            im.alpha_composite(layer.crop((origin[0], origin[1], origin[0] + size[0], origin[1] + size[1])))
    return im


def _union(boxes):
    boxes = [b for b in boxes if b]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _walk(placed):
    for p in placed:
        yield p
        for c in p.children:
            yield c


class Result:
    def __init__(self, face, layout_bytes, warnings, title, author):
        self.face, self.layout, self.warnings, self.title, self.author = face, layout_bytes, warnings, title, author


def build(spec, base_dir='.', langs=None):
    """Description -> Result. Several languages become choices in the face editor,
    the first one the default. Raises SpecError listing every problem found."""
    b = Builder(spec, base_dir, langs)
    W, H = b.width, b.height
    face = b.face = CleanFace(W, H)
    problems = []

    def resolve(lang, elements, path, fallback=None):
        try:
            r = Resolver(b, lang, elements, path, fallback)
            return r, r.run()
        except SpecError as e:
            problems.extend(e.problems)
            return None, None

    runs = {l: resolve(l, spec['elements'], 'elements') for l in b.langs}
    if problems:
        raise SpecError(problems)
    aod_spec = spec.get('aod') or {}
    aod_r, aod_placed = resolve(b.langs[0], aod_spec.get('elements', []), 'aod.elements', runs[b.langs[0]][0])
    if problems:
        raise SpecError(problems)

    # --- what agrees between languages is drawn once, the rest becomes choices
    first = runs[b.langs[0]][1]
    shared, per_lang = [], {l: [] for l in b.langs}
    for i, pl in enumerate(first):
        others = [runs[l][1][i] for l in b.langs]
        if pl.kind == 'tap':
            sig = [tuple(q.signature() for c in o.children for q in c.pieces if q) for o in others]
            if len(set(sig)) > 1:
                problems.append('%s: what is drawn inside a tap zone must not depend on the language' % pl.path)
            shared.append((pl, None))
            continue
        keep = []
        for j, piece in enumerate(pl.pieces):
            sigs = [(o.pieces[j].signature() if o.pieces[j] else None) for o in others]
            if len(set(sigs)) == 1:
                keep.append(piece)
            else:
                for l, o in zip(b.langs, others):
                    per_lang[l].append(o.pieces[j])
                keep.append(None)
        shared.append((pl, keep))
    if problems:
        raise SpecError(problems)

    # --- the background, then everything static that every language shares
    bg = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    for i, layer in enumerate(spec.get('background', [])):
        paint_layer(b, bg, layer, 'background[%d]' % i)
    for pl, keep in shared:
        if pl.kind == 'tap':
            for q in pl.pieces:
                _paint_static(bg, q)
            for c in pl.children:
                for q in c.pieces:
                    if q is not None and q.kind in ('image', 'paint'):
                        _paint_static(bg, q)
        else:
            for q in keep:
                if q is not None and q.kind in ('image', 'paint'):
                    _paint_static(bg, q)

    # --- checks: bounds and cards, then what collides, hides or cannot be read
    for l in b.langs:
        _check_geometry(b, runs[l][1], problems)
    if aod_placed:
        _check_geometry(b, aod_placed, problems, aod=True)
    problems[:] = list(dict.fromkeys(problems))
    if problems:
        raise SpecError(problems)
    plain = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    for i, layer in enumerate(spec.get('background', [])):
        paint_layer(b, plain, layer, 'background[%d]' % i)
    for pl, _ in shared:
        for q in pl.pieces if pl.kind == 'tap' else ():
            _paint_static(plain, q)
    mark_area = None
    for pl, _ in shared:
        if pl.kind == 'seconds_mark':
            track, paint, grow = pl.mark
            m = check.mask(track.draw_balls(range(60), paint.reach + grow, (255, 255, 255, 255)))
            mark_area = m if mark_area is None else ImageChops.lighter(mark_area, m)
    # the background's own drawings and the second mark's path, against the bezel
    for i, layer in enumerate(spec.get('background', [])):
        if layer.get('type') in ('card', 'ticks', 'shapes', 'dial', 'lcd'):
            alone = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            paint_layer(b, alone, layer, 'background[%d]' % i)
            b.warnings.extend(check.bezel_messages('background[%d]' % i, 'the "%s" layer' % layer['type'],
                                                   check.mask(alone), (W, H)))
    for pl, _ in shared:
        if pl.kind == 'seconds_mark':
            track, paint, grow = pl.mark
            b.warnings.extend(check.bezel_messages(pl.path, 'the second mark\'s path',
                                                   check.mask(paint(range(60))), (W, H)))
    found = {}
    for l in b.langs:
        errs, warns = check.inspect(_inspectable(b, runs[l][1]), plain, mark_area, (W, H))
        for kind, msgs in (('e', errs), ('w', warns)):
            for msg in msgs:
                found.setdefault((kind, msg), []).append(l)
    aod_plain = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    for i, layer in enumerate(aod_spec.get('background', [])):
        paint_layer(b, aod_plain, layer, 'aod.background[%d]' % i)
    if aod_placed:
        errs, warns = check.inspect(_inspectable(b, aod_placed), aod_plain, None, (W, H))
        for kind, msgs in (('e', errs), ('w', warns)):
            for msg in msgs:
                found.setdefault((kind, msg), []).append(None)
    for (kind, msg), ls in found.items():
        if None not in ls and len(ls) < len(b.langs):
            msg = msg.replace(':', ' (%s):' % ', '.join(ls), 1)
        (problems if kind == 'e' else b.warnings).append(msg)
    if problems:
        raise SpecError(problems)

    # --- groups
    zones, date_items, time_items = [], [], []
    marks = []
    for pl, keep in shared:
        if pl.kind == 'tap':
            items = []
            for c in pl.children:
                items += _layout_items([q for q in c.pieces if q is not None and q.kind in DYNAMIC], face, 0)
            zones.append((pl.target, pl.box, items))
        elif pl.kind == 'seconds_mark':
            marks.append((len(time_items), pl))
            time_items.append(None)
        else:
            items = _layout_items([q for q in keep if q is not None and q.kind in DYNAMIC], face, 0)
            (time_items if pl.group == 'time' else date_items).extend(items)

    slots, choices = [], []
    if len(b.langs) > 1 and any(per_lang[l] for l in b.langs):
        lg = spec.get('languages') or {}
        if 'zone' in lg:
            zone = tuple(int(v) for v in lg['zone'])
        else:
            u = _union([q.box() for l in b.langs for q in per_lang[l] if q is not None])
            zone = (max(0, u[0] - 6), max(0, u[1] - 6), min(W, u[2] + 6), min(H, u[3] + 6))
        zw, zh = zone[2] - zone[0], zone[3] - zone[1]
        fr = lg.get('frame') or {}
        frame = Image.new('RGBA', (zw, zh), (0, 0, 0, 0))
        ImageDraw.Draw(frame).rounded_rectangle([1, 1, zw - 2, zh - 2], radius=fr.get('radius', 12),
                                                outline=b.color(fr.get('color', '#FFFFFF'), 'languages.frame.color'),
                                                width=fr.get('width', 2))
        frame_ref = face.add(frame)
        values = {codes.WEEKDAY: 7, codes.MONTH: 11, codes.DAY_OF_MONTH: 8}
        for i, l in enumerate(b.langs):
            items = _layout_items(per_lang[l], face, 0, origin=zone[:2])
            thumb = _sample_render(per_lang[l], (zw, zh), zone[:2], values)
            slots.append(layout.slot(i, items, face.add(thumb), frame_ref, CHOICE_FUNCTIONS[i]))
        choices.append((zone, list(range(len(b.langs))), 0))

    # --- always-on screen: the default language, drawn on black
    aod_bg = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    for i, layer in enumerate(aod_spec.get('background', [])):
        paint_layer(b, aod_bg, layer, 'aod.background[%d]' % i)
    for pl in aod_placed or []:
        for q in pl.pieces:
            if q is None:
                continue
            if q.kind in ('image', 'paint'):
                _paint_static(aod_bg, q)
        items = _layout_items([q for q in pl.pieces if q is not None and q.kind in DYNAMIC], face, 1)
        (time_items if pl.group == 'time' else date_items).extend(items)

    # --- the second mark last: its covering layer repaints the finished background
    for at, pl in reversed(marks):
        track, paint, grow = pl.mark
        time_items[at:at + 1] = effects.running_mark(face, bg, track, painter=paint, cover_grow=grow)

    face.set_reserved(layout.BACKGROUND, bg)
    aod_ref = face.add(aod_bg)
    background = [layout.image(layout.BACKGROUND, 0, 0), layout.image(aod_ref, 0, 0, aod=1)]
    title = spec['name']
    lay = layout.layout(title, background, zones, date_items, time_items, slots, choices)
    return Result(face, lay, b.warnings, title, spec.get('author', re.sub(r'\W+', '-', title.lower()).strip('-') or 'face'))


def _inspectable(b, placed):
    items = []
    for p in placed:
        if p.kind == 'seconds_mark':
            continue
        if p.kind == 'tap':
            for c in p.children:
                items.append({'path': c.path, 'kind': c.kind, 'pieces': c.pieces, 'tap_box': p.box,
                              'quiet': c.quiet, 'ink_h': c.ink_h})
        else:
            items.append({'path': p.path, 'kind': p.kind, 'pieces': p.pieces, 'quiet': p.quiet, 'ink_h': p.ink_h,
                          'behind': p.behind})
    return items


def _check_geometry(b, placed, problems, aod=False):
    W, H = b.width, b.height
    ring_used = any(l.get('type') == 'ticks' for l in b.spec.get('background', [])) or any(
        p.kind == 'seconds_mark' and p.mark and p.mark[0] is b.ring for p in placed)
    for p in _walk(placed):
        if p.kind == 'seconds_mark':
            continue
        x0, y0, x1, y1 = p.box
        out = []
        if x0 < 0:
            out.append('%d px past the left edge' % -x0)
        if y0 < 0:
            out.append('%d px past the top' % -y0)
        if x1 > W:
            out.append('%d px past the right edge' % (x1 - W))
        if y1 > H:
            out.append('%d px past the bottom' % (y1 - H))
        if out:
            problems.append('%s: "%s" spans %s and runs %s of the %dx%d screen' % (
                p.path, p.kind, list(p.box), ', '.join(out), W, H))
        for q in p.pieces:
            if q is not None and getattr(q, 'card', None) and ring_used and not b.ring.clear(*q.card):
                problems.append('%s.card: the card %s runs into the ring of ticks; move it at least %d px in from the edge' % (
                    p.path, list(q.card[0]), b.ring.inset + b.ring.length[1] + 3))
    if not aod:
        for i, layer in enumerate(b.spec.get('background', [])):
            if layer.get('type') == 'card' and ring_used and not b.ring.clear(tuple(layer['box']), layer.get('radius', 22)):
                problems.append('background[%d]: the card %s runs into the ring of ticks' % (i, layer['box']))


# ---------------------------------------------------------------- package

def _jpeg(im, size):
    buf = io.BytesIO()
    im.convert('RGB').resize(size, Image.LANCZOS).save(buf, 'JPEG', quality=92)
    return buf.getvalue()


def package(result, path, screen='HWHD13'):
    """Result -> .hwt on disk with previews drawn from the packed binary.
    Returns (binary, normal preview, always-on preview)."""
    face, lay = result.face, result.layout
    W, H = face.width, face.height
    blank = Image.new('RGBA', (W, H))
    face.set_reserved(layout.THUMB, blank.resize((240, 282)))
    face.set_reserved(layout.PREVIEW, blank)
    first = container.pack(lay, face.images)
    normal = simulate.render(first, size=(W, H))
    aod = simulate.render(first, aod=True, size=(W, H))
    face.set_reserved(layout.THUMB, normal.resize((240, 282), Image.LANCZOS))
    face.set_reserved(layout.PREVIEW, normal)
    binary = container.pack(lay, face.images)
    previews = {'cover.jpg': _jpeg(normal, (816, 960)), 'icon_small.jpg': _jpeg(normal, (332, 390)),
                'aod.jpg': _jpeg(aod, (816, 960))}
    container.write_package(path, binary, result.title, result.author, screen, FORMAT_VERSION, previews)
    return binary, normal, aod


def load(path):
    with open(path, encoding='utf-8') as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as e:
            raise SpecError(['%s: not valid JSON at line %d, column %d: %s' % (
                os.path.basename(path), e.lineno, e.colno, e.msg)])
