"""Assemble a watch face: register images, describe elements, group them, pack.

Groups are drawn in the order they are written, elements inside a group likewise.
Every element carries a mode flag: 0 draws on the normal screen, 1 on the
always-on screen.
"""
from . import codes
from .container import pb_encode

THUMB, BACKGROUND, PREVIEW = '001', '002', '003'


class Face:
    """Image registry. Slots 001..003 are reserved: picker thumbnail, background,
    full-size preview. Identical keys share one stored image."""

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.images = [None, None, None]
        self.cache = {}

    def add(self, im, key=None):
        if key is not None and key in self.cache:
            return self.cache[key]
        self.images.append(im)
        ref = '%03d' % len(self.images)
        if key is not None:
            self.cache[key] = ref
        return ref

    def add_set(self, ims, key):
        return [self.add(im, (key, i)) for i, im in enumerate(ims)]

    def set_reserved(self, ref, im):
        self.images[int(ref) - 1] = im


# ---------------------------------------------------------------- elements

def image(ref, x, y, aod=0):
    return (codes.IMAGE, [(1, ref), (2, [(1, x), (2, y)]), (5, aod)])


def image_list(refs, x, y, source, aod=0):
    return (codes.IMAGE_LIST, [(1, r) for r in refs] + [(2, [(1, x), (2, y)]), (3, source), (6, aod)])


def number(digit_refs, x, y, align, source, aod=0, minus=''):
    """x is the anchor named by align; y is the top of the digit images."""
    return (codes.NUMBER, [(1, r) for r in digit_refs] + [
        (2, ''), (3, [(1, x), (2, y)]), (4, align), (5, source), (6, minus), (7, 0), (8, 0), (13, aod)])


def progress(ref, box, source, aod=0):
    """Picture the size of box, revealed from the left in proportion to the value."""
    x0, y0, x1, y1 = box
    return (codes.PROGRESS, [(1, ref), (2, [(1, x0), (2, y0), (3, x1 - x0), (4, y1 - y0)]), (3, source), (6, aod)])


def hand(ref, cx, cy, pivot_x, pivot_y, source, aod=0):
    """Picture drawn pointing up, rotated about (pivot_x, pivot_y), placed on (cx, cy)."""
    side = 2 * pivot_y
    rect = [(1, cx - pivot_y), (2, cy - pivot_y), (3, side), (4, side)]
    return (codes.HAND, [(1, ref), (2, rect), (3, [(1, pivot_x), (2, pivot_y)]),
                         (4, 0), (5, 360), (6, source), (9, aod)])


# ---------------------------------------------------------------- editable choices
# A choice zone lets the wearer pick one of several slots in the face editor. Elements
# inside a slot sit at (0, 0) and carry an offset from the zone's top-left corner.

def slot_image(ref, dx, dy, aod=0):
    return (codes.IMAGE, [(1, ref), (2, [(1, 0), (2, 0)]), (4, [(1, dx), (2, dy)]), (5, aod)])


def slot_image_list(refs, dx, dy, source, aod=0):
    return (codes.IMAGE_LIST, [(1, r) for r in refs] + [
        (2, [(1, 0), (2, 0)]), (3, source), (5, [(1, dx), (2, dy)]), (6, aod)])


def slot(index, items, thumb, frame, target):
    """One choice: its elements, a thumbnail for the editor, the editor's selection
    frame, and what a tap opens while this choice is active."""
    return [(1, index)] + _wrap(items, 2) + [(3, thumb), (4, frame), (5, target)]


def choice_zone(index, box, slot_indices, default):
    x0, y0, x1, y1 = box
    return [(1, index), (2, 1), (3, bytes(slot_indices)), (4, default),
            (5, [(1, x0), (2, y0), (3, x1 - x0), (4, y1 - y0)])]


def _wrap(items, field):
    return [(field, [(1, i), (2, kind), (codes.BODY_FIELD[kind], body)]) for i, (kind, body) in enumerate(items)]


def zone(index, target, box, items):
    """Touch area opening `target`; it carries the elements drawn inside it."""
    x0, y0, x1, y1 = box
    rect = [(1, x0), (2, y0), (3, x1 - x0), (4, y1 - y0)]
    return [(1, index), (2, 0), (5, rect)] + _wrap(items, 6) + [(8, target)]


# ---------------------------------------------------------------- whole layout

def layout(title, background_items, zones, date_items, time_items, slots=(), choices=()):
    """Four groups in the order the reference faces use: background, touch zones,
    date, time. zones: [(target, box, items)]; slots: built with slot();
    choices: [(box, slot indices, default)]."""
    zone_fields = [(8, zone(i, t, box, items)) for i, (t, box, items) in enumerate(zones)]
    zone_fields += [(8, choice_zone(len(zones) + i, box, idx, default))
                    for i, (box, idx, default) in enumerate(choices)]
    groups = [
        [(1, 0), (2, 0), (4, PREVIEW)] + _wrap(background_items, 5),
        [(1, 3), (2, 0)] + [(7, s) for s in slots] + zone_fields,
        [(1, 2), (2, 0), (4, '')] + _wrap(date_items, 5),
        [(1, 1), (2, 0), (4, '')] + _wrap(time_items, 5),
    ]
    return pb_encode([(1, g) for g in groups] + [(2, title), (3, title)])
