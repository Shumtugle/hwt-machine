"""Faces built from descriptions. Run: python3 -m unittest discover tests"""
import importlib.util
import math
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from machine import codes, container, simulate, spec  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def home(name):
    """A face's folder: under faces/, or under tests/fixtures/ once it has left the page."""
    kept = os.path.join(FIXTURES, name)
    return kept if os.path.isdir(kept) else os.path.join(ROOT, 'faces', name)


def legacy(name):
    s = importlib.util.spec_from_file_location('legacy_' + name.replace('-', '_'),
                                               os.path.join(home(name), 'build.py'))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def described(name, langs, out):
    desc = spec.load(os.path.join(home(name), 'face.json'))
    binary, _, _ = spec.package(spec.build(desc, home(name), langs),
                                os.path.join(out, '%s-%s.hwt' % (name, '-'.join(langs))))
    return binary


def handmade(name, langs, out):
    path, _, _ = legacy(name).package(langs, out, 'legacy-%s-%s' % (name, '-'.join(langs)))
    return container.read_package(path)[1]


class SameAsHandmade(unittest.TestCase):
    """The descriptions draw exactly what the hand-written scripts draw."""

    def check(self, name, lang, screens=(False, True)):
        with tempfile.TemporaryDirectory() as out:
            new, old = described(name, [lang], out), handmade(name, [lang], out)
        for aod in screens:
            self.assertEqual(simulate.render(new, aod=aod).tobytes(), simulate.render(old, aod=aod).tobytes(),
                             '%s %s aod=%s' % (name, lang, aod))
        self.assertEqual(simulate.render.skipped, [])

    def test_thread_with_day_suffix(self):
        self.check('thread', 'fi')

    def test_running_mark_on_the_thread(self):
        with tempfile.TemporaryDirectory() as out:
            binary = described('thread', ['en'], out)
        from machine import draw
        track = draw.Track.line(408, 480, (304, 112), (304, 392), decade_gap=26)
        for second in (0, 9, 10, 31, 59):
            data = simulate.sample_data()
            data[codes.SECOND_TENS], data[codes.SECOND_UNITS] = divmod(second, 10)
            x, y = track.ball_centre(second)
            r, g, _, _ = simulate.render(binary, data=data).getpixel((int(round(x)), int(round(y))))
            self.assertTrue(r > 180 and g < 90, 'second %d' % second)


class InsideTheGlass(unittest.TestCase):
    """Rings, marks and cards stay where the glass shows them."""

    def test_vibe(self):
        desc = spec.load(os.path.join(ROOT, 'faces', 'vibe', 'face.json'))
        result = spec.build(desc, os.path.join(ROOT, 'faces', 'vibe'), ['ru'])
        self.assertEqual([w for w in result.warnings if 'bezel' in w or 'glass' in w], [])

    def test_rubis(self):
        desc = spec.load(os.path.join(ROOT, 'faces', 'rubis', 'face.json'))
        result = spec.build(desc, os.path.join(ROOT, 'faces', 'rubis'), ['fi'])
        self.assertEqual([w for w in result.warnings if 'bezel' in w or 'glass' in w], [])


class Levels(unittest.TestCase):
    """A level pours its sheet from its own height down: what lies just below the
    second's level is lit, what lies just above it is not lit by that sheet."""

    def test_sheet_follows_the_second(self):
        desc = spec.load(os.path.join(ROOT, 'faces', 'plumb', 'face.json'))
        lv = [e for e in desc['elements'] if e['type'] == 'level' and e['source'] == 'seconds'][0]
        with tempfile.TemporaryDirectory() as out:
            binary, _, _ = spec.package(spec.build(desc, os.path.join(ROOT, 'faces', 'plumb'), ['en']),
                                        os.path.join(out, 'p.hwt'))
        y = lv['from'] + (lv['to'] - lv['from']) * 30 / 60.0
        probe = (390, int(y))                    # right of the scale, clear of all text

        def at(second):
            data = simulate.sample_data()
            data[codes.SECONDS] = second
            data[codes.MINUTES] = data[codes.HOURS] = 59    # their sheets start below the probe
            return sum(simulate.render(binary, data=data).getpixel(probe)[:3])
        self.assertGreater(at(20), at(40))       # level above the probe: the probe is under the sheet


class DigitWords(unittest.TestCase):
    """Segments spell a month when every month is a number, and nothing else."""

    def desc(self, months):
        return {"name": "t", "font": "Oswald", "languages": {"default": ["en"]},
                "locales": {"en": {"months": months}},
                "elements": [{"type": "month", "font": "Segments", "size": 40, "color": "#FFFFFF",
                              "x": 40, "y": {"digits_middle": 240}}]}

    def test_numbers(self):
        spec.build(self.desc(["%02d" % i for i in range(1, 13)]), ROOT, ['en'])

    def test_words(self):
        with self.assertRaises(spec.SpecError):
            spec.build(self.desc(["Jan"] + ["%02d" % i for i in range(2, 13)]), ROOT, ['en'])


class Sweep(unittest.TestCase):
    """A radar sweep: bright at its leading edge, fading behind it, nothing ahead or inside."""

    def test_shape(self):
        from machine import draw
        im, px, py = draw.sweep(100, 60, (255, 0, 0, 200), (255, 0, 0, 255), start=30)
        alpha = lambda r, deg: im.getpixel((int(round(px - r * math.sin(math.radians(deg)))),
                                            int(round(py - r * math.cos(math.radians(deg))))))[3]
        self.assertGreater(alpha(70, 2), 150)             # just behind the leading edge, pointing to 12
        self.assertGreater(alpha(70, 10), alpha(70, 40))  # fading behind it, anticlockwise
        self.assertEqual(alpha(70, 70), 0)                # beyond the trail
        self.assertEqual(alpha(15, 10), 0)                # inside the start
        self.assertEqual(im.getpixel((min(im.width - 1, int(px) + 4), int(py) - 70))[3], 0)  # ahead of it


class Instruments(unittest.TestCase):
    """Hands, a dial and crystal digits."""

    @classmethod
    def setUpClass(cls):
        desc = spec.load(os.path.join(ROOT, 'faces', 'duo', 'face.json'))
        cls.result = spec.build(desc, os.path.join(ROOT, 'faces', 'duo'), ['en'])
        with tempfile.TemporaryDirectory() as out:
            cls.binary, _, _ = spec.package(cls.result, os.path.join(out, 'duo.hwt'))

    def at(self, t, aod=False):
        import datetime
        return simulate.render(self.binary, aod=aod, data=simulate.sample_data(datetime.datetime(2026, 11, 9, *t)))

    def test_everything_is_confirmed(self):
        self.assertEqual([w for w in self.result.warnings if 'confirmed' in w], [])

    def test_hands_turn(self):
        quarter = self.at((3, 0, 30))           # hour hand to the right, minute hand up
        # sampled between the pin and the slit, where the hands are solid
        self.assertGreater(sum(quarter.getpixel((88 + 9, 111))[:3]), 500)
        self.assertGreater(sum(quarter.getpixel((88, 111 - 9))[:3]), 500)
        self.assertLess(sum(quarter.getpixel((88 - 30, 111))[:3]), 100)

    def test_blank_leading_digit(self):
        early, late = self.at((8, 5, 0)), self.at((18, 5, 0))
        box = (24, 250, 92, 370)               # the first digit cell
        bright = lambda im: max(max(p[:3]) for p in im.crop(box).getdata())
        self.assertLess(bright(early), 80)     # unlit segments only
        self.assertGreater(bright(late), 200)


class LitWindow(unittest.TestCase):
    """Dark segments on a lit crystal window, a centred day."""

    def test_window_and_digits(self):
        import datetime
        desc = spec.load(os.path.join(FIXTURES, 'lit-window.json'))
        result = spec.build(desc, FIXTURES, ['ru'])
        with tempfile.TemporaryDirectory() as out:
            binary, _, _ = spec.package(result, os.path.join(out, 'lit-window.hwt'))
        im = simulate.render(binary, data=simulate.sample_data(datetime.datetime(2026, 11, 9, 18, 18, 0)))
        r, g, b, _ = im.getpixel((204, 260))                       # backlight above the digits
        self.assertTrue(r > 200 and b < 150, (r, g, b))
        dark = [p for p in im.crop((30, 270, 380, 370)).getdata() if sum(p[:3]) < 150]
        self.assertGreater(len(dark), 3000)                         # lit segments are dark
        self.assertTrue(any('31 pictures' in w for w in result.warnings))
        # the date line set like a maker's name proved too small on a wrist
        self.assertTrue(any('elements[4]' in w and 'read at a glance' in w for w in result.warnings))


class Reference(unittest.TestCase):
    """The reference description passes every check in every language; the only notes allowed
    are about features still to be confirmed on a wrist."""

    def test_clean(self):
        desc = spec.load(os.path.join(FIXTURES, 'reference.json'))
        for langs in (['ru'], ['en'], ['fi'], ['ru', 'en', 'fi']):
            result = spec.build(desc, FIXTURES, langs)
            # only notes about features still to be confirmed on a wrist are allowed
            self.assertEqual([w for w in result.warnings if 'not yet on this watch' not in w], [], langs)


class Beams(unittest.TestCase):
    """Hands of light drawn under everything, units that change with the language."""

    @classmethod
    def setUpClass(cls):
        desc = spec.load(os.path.join(ROOT, 'faces', 'strobe', 'face.json'))
        cls.result = spec.build(desc, os.path.join(ROOT, 'faces', 'strobe'), ['ru', 'en'])
        with tempfile.TemporaryDirectory() as out:
            cls.binary, _, _ = spec.package(cls.result, os.path.join(out, 'strobe.hwt'))

    def test_beams_lie_under_everything(self):
        import subprocess
        with tempfile.TemporaryDirectory() as out:
            path = os.path.join(out, 'strobe.hwt')
            spec.package(self.result, path)
            text = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'inspect.py'), path],
                                  capture_output=True, text=True).stdout
        lines = [l.strip() for l in text.splitlines()]
        first_zone = next(i for i, l in enumerate(lines) if l.startswith('zone'))
        self.assertTrue(lines[first_zone].startswith('zone [0, 0, 0, 0]'), lines[first_zone])
        under = lines[first_zone + 1:first_zone + 5]
        # the frame's marker, the background over all but the band, then the two beams
        self.assertTrue(under[0].startswith('hand') and under[0].endswith('<hand_second>'), under[0])
        self.assertTrue(under[1].startswith('image'), under[1])
        self.assertTrue(under[2].startswith('hand') and under[3].startswith('hand'), under[2:])

    def test_frame_marker_shows_only_in_the_band(self):
        import datetime
        # at a quarter past the marker points right, where neither beam goes at half past six
        im = simulate.render(self.binary, data=simulate.sample_data(datetime.datetime(2026, 11, 9, 6, 30, 15)))
        red = lambda box: [p for p in im.crop(box).getdata() if p[0] > 150 and p[1] < 110]
        self.assertGreater(len(red((383, 232, 397, 248))), 20)      # in the band
        self.assertEqual(red((250, 232, 380, 248)), [])              # covered on its way there

    def test_laser_shows_and_digits_stay_on_top(self):
        import datetime
        im = simulate.render(self.binary, data=simulate.sample_data(datetime.datetime(2026, 11, 9, 21, 8, 12)))
        reds = [px for px in im.crop((240, 40, 400, 160)).getdata() if px[0] > 150 and px[1] < 110]
        self.assertGreater(len(reds), 40)                          # the minute laser, up and to the right
        self.assertEqual(simulate.render.skipped, [])

    def test_units_follow_the_language(self):
        import datetime
        t = simulate.sample_data(datetime.datetime(2026, 11, 9, 21, 8, 12))
        ru, en = simulate.render(self.binary, data=t, choice=0), simulate.render(self.binary, data=t, choice=1)
        self.assertNotEqual(ru.crop((160, 400, 210, 445)).tobytes(), en.crop((160, 400, 210, 445)).tobytes())


class Languages(unittest.TestCase):
    def test_every_choice_draws_its_single_face(self):
        with tempfile.TemporaryDirectory() as out:
            both = described('vibe', ['ru', 'fi'], out)
            singles = [described('vibe', [l], out) for l in ('ru', 'fi')]
        for i, single in enumerate(singles):
            self.assertEqual(simulate.render(both, choice=i).tobytes(), simulate.render(single).tobytes())
        tree, _ = container.unpack(both)
        zones = [g for k, g in tree if k == 1 and dict((a, b) for a, b in g if not isinstance(b, list)).get(1) == 3][0]
        slots = [s for f, s in zones if f == 7]
        functions = [dict((a, b) for a, b in s if not isinstance(b, list))[5] for s in slots]
        self.assertEqual(functions, [codes.FUNCTION_DATE, codes.FUNCTION_WEEKDAY])

    def test_transparent_pixels_carry_no_colour(self):
        desc = spec.load(os.path.join(FIXTURES, 'thread', 'face.json'))
        result = spec.build(desc, os.path.join(FIXTURES, 'thread'), ['en'])
        for im in result.face.images[3:]:
            px = im.tobytes()
            for i in range(0, len(px), 4):
                if px[i + 3] == 0:
                    self.assertEqual(px[i:i + 4], b'\0\0\0\0')


class Problems(unittest.TestCase):
    """A description with mistakes is refused with messages that say what to change."""

    def problems(self, change, langs=('en',)):
        desc = spec.load(os.path.join(FIXTURES, 'thread', 'face.json'))
        change(desc)
        with self.assertRaises(spec.SpecError) as e:
            spec.build(desc, os.path.join(FIXTURES, 'thread'), list(langs))
        return '\n'.join(e.exception.problems)

    def test_misspelt_field(self):
        msg = self.problems(lambda d: d['elements'][1].update(colour='#FFFFFF'))
        self.assertIn('elements[1].colour', msg)
        self.assertIn('did you mean "color"', msg)

    def test_unknown_reference(self):
        self.assertIn('did you mean "day"', self.problems(lambda d: d['elements'][3].update(x='dya.right+8')))

    def test_circular_positions(self):
        def change(d):
            d['elements'][2]['x'] = 'time.left'
            d['elements'][1]['x'] = 'day.left'
        self.assertIn('circle', self.problems(change))

    def test_off_screen(self):
        self.assertIn('past the right edge', self.problems(lambda d: d['elements'][4].update(x=380)))

    def test_dead_tap_target(self):
        self.assertIn('"settings"', self.problems(lambda d: d['elements'][5].update(open='battery')))

    def test_too_many_languages(self):
        self.assertIn('at most 3', self.problems(lambda d: None, ('ru', 'en', 'fi', 'sv')))

    def test_card_in_the_ring(self):
        def change(d):
            d['background'] += [{'type': 'ticks'}, {'type': 'card', 'box': [2, 2, 100, 100]}]
        self.assertIn('ring of ticks', self.problems(change))

    def test_collision(self):
        msg = self.problems(lambda d: d['elements'][4]['y'].update(caps_top=40))
        self.assertIn('overlaps', msg)
        self.assertIn('elements[4]', msg)

    def test_on_the_path_of_the_mark(self):
        self.assertIn('path of the second mark', self.problems(lambda d: d['elements'][4].update(x=290, y={'caps_top': 200})))

    def test_invisible(self):
        self.assertIn('cannot be seen', self.problems(lambda d: d['elements'][4].update(color='#0A0A0A')))

    def warnings(self, change):
        desc = spec.load(os.path.join(FIXTURES, 'thread', 'face.json'))
        change(desc)
        return '\n'.join(spec.build(desc, os.path.join(FIXTURES, 'thread'), ['en']).warnings)

    def test_faint_but_allowed_when_quiet(self):
        self.assertIn('hard to read', self.warnings(lambda d: d['elements'][4].update(color='#3A3A3A')))
        self.assertNotIn('hard to read', self.warnings(lambda d: d['elements'][4].update(color='#3A3A3A', quiet=True)))

    def test_rounded_corner(self):
        self.assertIn('under the bezel', self.warnings(lambda d: d['elements'].append(
            {'type': 'symbol', 'name': 'favorite', 'size': 20, 'color': '#FFFFFF', 'x': 2, 'y': 2})))

    def test_outside_its_tap_zone(self):
        self.assertIn('outside its tap zone', self.warnings(lambda d: d['elements'][5].update(box=[32, 414, 70, 458])))

    def test_seconds_on_always_on(self):
        msg = self.problems(lambda d: d['aod']['elements'][0].update(seconds={'size': 20}))
        self.assertIn('once a minute', msg)


if __name__ == '__main__':
    unittest.main()
