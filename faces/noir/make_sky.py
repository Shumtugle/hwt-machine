"""Draws the weather pictures of Noir: the glossy skies of Flip, made smaller.

    python3 make_sky.py OUT_DIR

writes sky-0.png ... sky-10.png in the watch's order of weather states.
"""
import importlib.util
import os
import sys

from PIL import Image

SIDE = 76


def flip_pictures():
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location('flip_case', os.path.join(here, '..', 'flip', 'make_case.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(out):
    flip = flip_pictures()
    for state in range(11):
        flip.sky(state).resize((SIDE, SIDE), Image.LANCZOS).save(os.path.join(out, 'sky-%d.png' % state))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
