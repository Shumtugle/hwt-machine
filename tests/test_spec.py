"""Faces built from descriptions. Run: python3 -m unittest discover tests"""
import copy
import importlib.util
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from machine import codes, container, simulate, spec  # noqa: E402


def legacy(name):
    s = importlib.util.spec_from_file_location('legacy_' + name.replace('-', '_'),
                                               os.path.join(ROOT, 'faces', name, 'build.py'))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def described(name, langs, out):
    desc = spec.load(os.path.join(ROOT, 'faces', name, 'face.json'))
    binary, _, _ = spec.package(spec.build(desc, os.path.join(ROOT, 'faces', name), langs),
                                os.path.join(out, '%s-%s.hwt' % (name, '-'.join(langs))))
    return binary


def handmade(name, langs, out):
    path, _, _ = legacy(name).package(langs, out, 'legacy-%s-%s' % (name, '-'.join(langs)))
    return container.read_package(path)[1]


class SameAsHandmade(unittest.TestCase):
    """The descriptions draw exactly what the hand-written scripts draw."""

    def check(self, name, lang):
        with tempfile.TemporaryDirectory() as out:
            new, old = described(name, [lang], out), handmade(name, [lang], out)
        for aod in (False, True):
            self.assertEqual(simulate.render(new, aod=aod).tobytes(), simulate.render(old, aod=aod).tobytes(),
                             '%s %s aod=%s' % (name, lang, aod))
        self.assertEqual(simulate.render.skipped, [])

    def test_vibe(self):
        self.check('vibe', 'en')

    def test_plumb_with_day_suffix(self):
        self.check('plumb', 'fi')

    def test_running_mark_on_the_thread(self):
        with tempfile.TemporaryDirectory() as out:
            binary = described('plumb', ['en'], out)
        from machine import draw
        track = draw.Track.line(408, 480, (304, 112), (304, 392), decade_gap=26)
        for second in (0, 9, 10, 31, 59):
            data = simulate.sample_data()
            data[codes.SECOND_TENS], data[codes.SECOND_UNITS] = divmod(second, 10)
            x, y = track.ball_centre(second)
            r, g, _, _ = simulate.render(binary, data=data).getpixel((int(round(x)), int(round(y))))
            self.assertTrue(r > 180 and g < 90, 'second %d' % second)


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
        desc = spec.load(os.path.join(ROOT, 'faces', 'plumb', 'face.json'))
        result = spec.build(desc, os.path.join(ROOT, 'faces', 'plumb'), ['en'])
        for im in result.face.images[3:]:
            px = im.tobytes()
            for i in range(0, len(px), 4):
                if px[i + 3] == 0:
                    self.assertEqual(px[i:i + 4], b'\0\0\0\0')


class Problems(unittest.TestCase):
    """A description with mistakes is refused with messages that say what to change."""

    def problems(self, change, langs=('en',)):
        desc = spec.load(os.path.join(ROOT, 'faces', 'plumb', 'face.json'))
        change(desc)
        with self.assertRaises(spec.SpecError) as e:
            spec.build(desc, os.path.join(ROOT, 'faces', 'plumb'), list(langs))
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

    def test_seconds_on_always_on(self):
        msg = self.problems(lambda d: d['aod']['elements'][0].update(seconds={'size': 20}))
        self.assertIn('once a minute', msg)


if __name__ == '__main__':
    unittest.main()
