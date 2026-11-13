"""Run: python3 -m unittest discover tests"""
import os
import random
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'faces', 'vibe'))

from PIL import Image  # noqa: E402

from machine import codes, container, simulate  # noqa: E402


class ImageCodec(unittest.TestCase):
    def test_round_trip(self):
        rnd = random.Random(7)
        im = Image.new('RGBA', (37, 23))
        px = []
        for i in range(37 * 23):
            if i % 11 < 6:
                px.append((10, 20, 30, 255))
            else:
                px.append(tuple(rnd.randrange(256) for _ in range(4)))
        im.putdata(px)
        self.assertEqual(container.decode_image(container.encode_image(im)).tobytes(), im.tobytes())

    def test_solid_fill_is_tiny(self):
        self.assertEqual(len(container.encode_image(Image.new('RGBA', (400, 400), (1, 2, 3, 255)))), 20)


class Protobuf(unittest.TestCase):
    def test_round_trip(self):
        tree = [(1, [(1, 0), (2, 0), (4, '003'), (5, [(1, 0), (2, 1), (4, [(1, '002'), (2, [(1, 0), (2, -7)])])])]),
                (2, 'Name'), (3, 'Name')]
        self.assertEqual(container.pb_decode(container.pb_encode(tree)), tree)


class Vibe(unittest.TestCase):
    def test_build_and_read_back(self):
        import build as vibe
        with tempfile.TemporaryDirectory() as out:
            path, size, count = vibe.package(['en'], out, 'vibe-en')
            manifest, binary, previews = container.read_package(path)
            self.assertIn('<screen>HWHD13</screen>', manifest)
            self.assertEqual(set(previews), {'cover.jpg', 'icon_small.jpg', 'aod.jpg'})
            tree, images = container.unpack(binary, strict=True)
            self.assertEqual(len(images), count)
            # repacking what was read gives the same bytes
            plen = int.from_bytes(binary[2:4], 'little')
            self.assertEqual(container.pb_encode(tree), binary[16:16 + plen])
            self.assertEqual(container.pack(binary[16:16 + plen], images), binary)
            screen = simulate.render(binary)
            self.assertEqual(simulate.render.skipped, [])
            self.assertEqual(screen.size, (408, 480))

    def test_running_mark_shows_one_mark(self):
        import build as vibe
        with tempfile.TemporaryDirectory() as out:
            path, _, _ = vibe.package(['en'], out, 'vibe-en')
            _, binary, _ = container.read_package(path)
        ring = vibe.draw.Ring(408, 480)
        for second in (0, 9, 10, 37, 59):
            data = simulate.sample_data()
            data[codes.SECOND_TENS], data[codes.SECOND_UNITS] = divmod(second, 10)
            screen = simulate.render(binary, data=data)
            lit = []
            for i in range(60):
                x, y = ring.ball_centre(i)
                r, g, b, _ = screen.getpixel((int(round(x)), int(round(y))))
                if r > 200 and g > 180:
                    lit.append(i)
            self.assertEqual(lit, [second], 'second %d' % second)

    def test_switchable_languages(self):
        import build as vibe
        with tempfile.TemporaryDirectory() as out:
            path, _, _ = vibe.package(['ru', 'en'], out, 'vibe')
            _, binary, _ = container.read_package(path)
            single, _, _ = vibe.package(['ru'], out, 'vibe-ru')
            _, binary_ru, _ = container.read_package(single)
        tree, _ = container.unpack(binary)
        zones = [g for k, g in tree if k == 1 and dict((a, b) for a, b in g if not isinstance(b, list)).get(1) == 3][0]
        self.assertEqual(sum(1 for f, _ in zones if f == 7), 2)
        # the default choice draws exactly what the single-language face draws
        self.assertEqual(simulate.render(binary).tobytes(), simulate.render(binary_ru).tobytes())


class NightTram(unittest.TestCase):
    def test_build_and_draw(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('night_tram', os.path.join(ROOT, 'faces', 'night-tram', 'build.py'))
        tram = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tram)
        with tempfile.TemporaryDirectory() as out:
            path, _, _ = tram.package(['ru', 'en'], out, 'night-tram')
            _, binary, _ = container.read_package(path)
        simulate.render(binary)
        self.assertEqual(simulate.render.skipped, [])
        # the lamp by the date lights for unread messages
        none = simulate.sample_data(); none[codes.UNREAD_MESSAGES] = 0
        some = simulate.sample_data(); some[codes.UNREAD_MESSAGES] = 1
        self.assertNotEqual(simulate.render(binary, data=none).tobytes(), simulate.render(binary, data=some).tobytes())

class Thread(unittest.TestCase):
    def test_weight_whole_at_every_second(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('thread', os.path.join(ROOT, 'tests', 'fixtures', 'thread', 'build.py'))
        thread = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(thread)
        with tempfile.TemporaryDirectory() as out:
            path, _, _ = thread.package(['en'], out, 'thread-en')
            _, binary, _ = container.read_package(path)
        track = thread.draw.Track.line(408, 480, (thread.THREAD_X, thread.THREAD_TOP), (thread.THREAD_X, thread.THREAD_BOTTOM),
                                      decade_gap=thread.DECADE_GAP)
        for second in range(60):
            data = simulate.sample_data()
            data[codes.SECOND_TENS], data[codes.SECOND_UNITS] = divmod(second, 10)
            screen = simulate.render(binary, data=data)
            x, y = track.ball_centre(second)
            for dy in (-4, 0, 4):   # top, middle and bottom of the weight are all red
                r, g, b, _ = screen.getpixel((int(round(x)), int(round(y + dy))))
                self.assertTrue(r > 180 and g < 90, 'second %d' % second)


class Lighthouse(unittest.TestCase):
    def test_build_and_draw(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('lighthouse', os.path.join(ROOT, 'faces', 'lighthouse', 'build.py'))
        lh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lh)
        with tempfile.TemporaryDirectory() as out:
            path, _, _ = lh.package(['ru', 'en'], out, 'lighthouse')
            _, binary, _ = container.read_package(path)
        simulate.render(binary)
        self.assertEqual(simulate.render.skipped, [])


class Pages(unittest.TestCase):
    def test_three_editions_are_up_to_date(self):
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'pages.py'), '--check'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_every_offered_file_exists(self):
        import json
        data = json.load(open(os.path.join(ROOT, 'tools', 'page', 'strings.json'), encoding='utf-8'))
        for lang in data['languages']:
            for name in data['order']:
                self.assertTrue(os.path.exists(os.path.join(ROOT, 'docs', 'faces', '%s-%s.hwt' % (name, lang))),
                                '%s-%s' % (name, lang))


if __name__ == '__main__':
    unittest.main()
