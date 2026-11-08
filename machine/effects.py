"""Composite tricks built only from verified element kinds."""
from PIL import Image, ImageFilter

from . import codes, layout


def glowing(ring, radius, color, halo=0, halo_alpha=150):
    """Painter for running_mark: a solid ball, optionally inside a soft halo."""
    def paint(indices):
        im = Image.new('RGBA', (ring.width, ring.height), (0, 0, 0, 0))
        if halo:
            glow = ring.draw_balls(indices, radius + halo * 0.6, color[:3] + (halo_alpha,))
            im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(halo * 0.45)))
        im.alpha_composite(ring.draw_balls(indices, radius, color))
        return im
    paint.reach = radius + halo
    return paint


def running_mark(face, background, ring, radius=None, color=None, cover_grow=1.5, painter=None):
    """A mark that steps around the ring once a minute, one tick per second.

    The watch offers the tens and the units of the second as separate sources, never
    the second itself. So the mark is two layers:
      * six strips, one per ten seconds, keyed by the units digit; strip d shows the
        mark at tick 10*d + units;
      * one full-frame layer keyed by the tens digit that repaints every other strip's
        area with the untouched background, leaving only the current strip visible.
    `background` must already contain everything drawn under the ring.
    Returns the elements; place them before anything that may overlap the ring."""
    paint = painter or glowing(ring, radius, color)
    reach = getattr(paint, 'reach', radius)
    clean = background.copy()
    w, h = background.size
    items = []
    for dec in range(6):
        span = list(range(dec * 10, dec * 10 + 10))
        box = ring.draw_balls(span, reach + 1, (255, 255, 255, 255)).getchannel('A').getbbox()
        frames = [paint([dec * 10 + u]).crop(box) for u in range(10)]
        refs = face.add_set(frames, ('mark_units', dec))
        items.append(layout.image_list(refs, box[0], box[1], codes.SECOND_UNITS))
    frames = []
    for k in range(6):
        others = [i for i in range(60) if i // 10 != k]
        mask = ring.draw_balls(others, reach + cover_grow, (255, 255, 255, 255))
        patch = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        patch.paste(clean, (0, 0), mask.getchannel('A').point(lambda a: 255 if a > 0 else 0))
        frames.append(patch)
    refs = face.add_set(frames, 'mark_tens')
    items.append(layout.image_list(refs, 0, 0, codes.SECOND_TENS))
    return items
