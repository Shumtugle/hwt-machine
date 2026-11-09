"""Build watch faces from a description.

Usage: python3 tools/build.py face.json [--langs ru,en,fi] [--out DIR] [--check]

Writes one package per language, one that carries all of them as editor choices
(the first is the default), and PNG previews of both screen modes. With --check
it only reads the description and reports problems. Problems go to standard
output, one per line, each saying where it is and what to change; the exit code
is 1 when there are any.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from machine import spec  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('description')
    ap.add_argument('--langs', default='', help='comma-separated languages; default: the description\'s own')
    ap.add_argument('--out', default=os.path.join(ROOT, 'dist'))
    ap.add_argument('--name', default='', help='file stem; default: the description\'s file or folder name')
    ap.add_argument('--check', action='store_true', help='report problems without writing anything')
    a = ap.parse_args()

    path = os.path.abspath(a.description)
    base = os.path.dirname(path)
    stem = a.name or (os.path.basename(base) if os.path.basename(path) == 'face.json'
                      else os.path.splitext(os.path.basename(path))[0])
    try:
        desc = spec.load(path)
        langs = [l for l in a.langs.split(',') if l] or list((desc.get('languages') or {}).get('default', ['en']))
        jobs = [([l], '%s-%s' % (stem, l)) for l in langs]
        if len(langs) > 1:
            jobs.append((langs, stem))
        results = [(spec.build(desc, base, ls), name, ls) for ls, name in jobs]
    except spec.SpecError as e:
        for p in e.problems:
            print('error: ' + p)
        return 1
    for w in sorted({w for r, _, _ in results for w in r.warnings}):
        print('warning: ' + w)
    if a.check:
        print('ok: %d package(s) would be built' % len(results))
        return 0
    os.makedirs(a.out, exist_ok=True)
    for result, name, ls in results:
        out = os.path.join(a.out, name)
        binary, normal, aod = spec.package(result, out + '.hwt')
        normal.convert('RGB').save(out + '.png')
        aod.convert('RGB').save(out + '-aod.png')
        size = len(binary)
        note = '  (larger than any face confirmed on a watch, 2.4 MB)' if size > 2_500_000 else ''
        print('%s.hwt  %d bytes  %d images  %s%s' % (os.path.relpath(out, ROOT), size, len(result.face.images),
                                                     '+'.join(ls), note))
    return 0


if __name__ == '__main__':
    sys.exit(main())
