"""Look inside any watch face package.

Usage:
  python3 tools/inspect.py FACE.hwt                 print manifest and layout
  python3 tools/inspect.py FACE.hwt --images DIR    also write every image as PNG
  python3 tools/inspect.py FACE.hwt --render PNG    also draw the screen with sample data
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from machine import codes, container, simulate  # noqa: E402

KIND_NAMES = {codes.TEXT: 'text', codes.IMAGE: 'image', codes.IMAGE_LIST: 'list', codes.NUMBER: 'number',
              codes.HAND: 'hand', codes.PROGRESS: 'progress', codes.ARC: 'arc',
              codes.TEXT_FORMATTED: 'text+unit'}
SOURCE_NAMES = {v: k.lower() for k, v in vars(codes).items()
                if k.isupper() and isinstance(v, int) and not k.startswith(('OPEN_', 'ALIGN_', 'FUNCTION_'))
                and k not in ('IMAGE', 'IMAGE_LIST', 'NUMBER', 'HAND', 'PROGRESS', 'TEXT', 'TEXT_FORMATTED', 'ARC')}
TARGET_NAMES = {v: k[5:].lower() for k, v in vars(codes).items() if k.startswith('OPEN_')}


def get(node, f, default=None):
    for k, v in node:
        if k == f:
            return v
    return default


def fmt(v):
    if isinstance(v, list):
        return '{' + ' '.join('%s:%s' % (a, fmt(b)) for a, b in v) + '}'
    return repr(v) if isinstance(v, (str, bytes)) else str(v)


def ids(refs):
    if not refs:
        return '-'
    if len(refs) == 1:
        return refs[0]
    return '%s..%s (%d)' % (refs[0], refs[-1], len(refs))


def element(el, indent):
    kind = get(el, 2)
    body = next((v for k, v in el if k not in (1, 2) and isinstance(v, list)), [])
    refs = [v for k, v in body if k == 1 and isinstance(v, str)]
    rest = [(k, v) for k, v in body if not (k == 1 and isinstance(v, str))]
    src = {codes.IMAGE_LIST: 3, codes.NUMBER: 5, codes.HAND: 6, codes.TEXT: 5, codes.TEXT_FORMATTED: 6}.get(kind)
    label = ''
    if src is not None and get(body, src) is not None:
        label = '  <%s>' % SOURCE_NAMES.get(get(body, src), 'source %s' % get(body, src))
    print('%s%-9s %-18s %s%s' % (indent, KIND_NAMES.get(kind, 'kind %s' % kind), ids(refs),
                                 ' '.join('%s:%s' % (k, fmt(v)) for k, v in rest), label))


def main():
    ap = argparse.ArgumentParser(description='Inspect a watch face package.')
    ap.add_argument('face')
    ap.add_argument('--images')
    ap.add_argument('--render')
    a = ap.parse_args()
    manifest, binary, previews = container.read_package(a.face)
    print(manifest.strip())
    ver, plen, tlen, dlen, _ = struct.unpack('<HHIII', binary[:16])
    print('\nbinary %d bytes: version %d, layout %d, %d images, blob %d' % (len(binary), ver, plen, tlen // 8, dlen))
    tree, images = container.unpack(binary)
    unknown = sum(im is None for im in images)
    if unknown:
        print('%d images use an encoding this machine does not read; they are left out' % unknown)
    for k, group in tree:
        if k != 1:
            print('field %d: %s' % (k, fmt(group)))
            continue
        print('\ngroup ' + ' '.join('%s:%s' % (x, fmt(y)) for x, y in group if not isinstance(y, list)))
        for f, item in group:
            if f == 5:
                element(item, '  ')
            elif f == 8:
                r = get(item, 5, [])
                tgt = get(item, 8)
                print('  zone %s -> %s' % ([get(r, i, 0) for i in (1, 2, 3, 4)],
                                           TARGET_NAMES.get(tgt, tgt) if tgt is not None else 'choice'))
                for g, sub in item:
                    if g == 6:
                        element(sub, '    ')
            elif isinstance(item, list):
                print('  field %d: %s' % (f, fmt(item)[:160]))
    if a.images:
        os.makedirs(a.images, exist_ok=True)
        for i, im in enumerate(images):
            if im is not None:
                im.save(os.path.join(a.images, '%03d.png' % (i + 1)))
        print('\n%d images written' % len(images))
    if a.render:
        simulate.render(binary).convert('RGB').save(a.render)
        if simulate.render.skipped:
            print('not drawn: kinds %s' % simulate.render.skipped)


if __name__ == '__main__':
    main()
