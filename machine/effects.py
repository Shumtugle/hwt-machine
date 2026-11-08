"""Composite tricks built only from verified element kinds."""
from PIL import Image

from . import codes, layout


def running_mark(face, background, ring, radius, color, cover_grow=1.5):
    """A mark that steps around the ring once a minute, one tick per second.

    The watch offers the tens and the units of the second as separate sources, never
    the second itself. So the mark is two layers:
      * six strips, one per ten seconds, keyed by the units digit; strip d shows the
        mark at tick 10*d + units;
      * one full-frame layer keyed by the tens digit that repaints every other strip's
        area with the untouched background, leaving only the current strip visible.
    `background` must already contain everything drawn under the ring.
    Returns the elements; place them before anything that may overlap the ring."""
    clean = background.copy()
    w, h = background.size
    items = []
    for dec in range(6):
        span = list(range(dec * 10, dec * 10 + 10))
        box = ring.draw_balls(span, radius + 1, color).getchannel('A').getbbox()
        frames = [ring.draw_balls([dec * 10 + u], radius, color).crop(box) for u in range(10)]
        refs = face.add_set(frames, ('mark_units', dec))
        items.append(layout.image_list(refs, box[0], box[1], codes.SECOND_UNITS))
    frames = []
    for k in range(6):
        others = [i for i in range(60) if i // 10 != k]
        mask = ring.draw_balls(others, radius + cover_grow, (255, 255, 255, 255))
        patch = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        patch.paste(clean, (0, 0), mask.getchannel('A').point(lambda a: 255 if a > 0 else 0))
        frames.append(patch)
    refs = face.add_set(frames, 'mark_tens')
    items.append(layout.image_list(refs, 0, 0, codes.SECOND_TENS))
    return items
