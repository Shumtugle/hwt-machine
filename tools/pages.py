"""Writes the three pages, one per language, from tools/page/template.html and
tools/page/strings.json: docs/index.html in English, docs/ru/ and docs/fi/.

Every page previews and offers only its own language's packages.

    python3 tools/pages.py           # write the pages
    python3 tools/pages.py --check   # fail if a page differs from what would be written
"""
import html
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, 'tools', 'page')


def render(lang, data, template):
    s = data['strings'][lang]
    path = data['paths'][lang]
    base = '../' * path.count('/')
    here = lambda other: base + data['paths'][other]
    chips = '\n'.join('            <a class="chip" href="%s" aria-pressed="%s" lang="%s">%s</a>'
                      % (here(o), 'true' if o == lang else 'false', o, o.upper()) for o in data['languages'])
    sky = ''.join('<option value="%d"%s>%s</option>' % (i, ' selected' if i == 4 else '', html.escape(w))
                  for i, w in enumerate(s['sky']))
    cards = '\n'.join('      <div class="card"><h3>%s</h3><p>%s</p></div>' % (h, p) for h, p in s['cards'])
    js = dict(s['js'], download=s['download'], names=data['names'],
              gallery=[[f, data['names'][f], s['gallery'][f]] for f in data['order']])
    values = dict(s, lang=lang, base=base, lang_chips=chips,
                  sky_options='            ' + sky, cards=cards,
                  strings=json.dumps(js, ensure_ascii=False))
    out = template
    for k, v in values.items():
        if isinstance(v, str):
            out = out.replace('{{%s}}' % k, v)
    if '{{' in out:
        raise SystemExit('unfilled place in the template: ' + out[out.index('{{'):out.index('{{') + 30])
    return os.path.join(ROOT, 'docs', path, 'index.html'), out


def main():
    check = '--check' in sys.argv
    with open(os.path.join(PAGE, 'template.html'), encoding='utf-8') as fh:
        template = fh.read()
    with open(os.path.join(PAGE, 'strings.json'), encoding='utf-8') as fh:
        data = json.load(fh)
    stale = []
    for lang in data['languages']:
        path, text = render(lang, data, template)
        old = open(path, encoding='utf-8').read() if os.path.exists(path) else None
        if check:
            if old != text:
                stale.append(os.path.relpath(path, ROOT))
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        print(os.path.relpath(path, ROOT))
    if stale:
        raise SystemExit('pages out of date, run tools/pages.py: ' + ', '.join(stale))


if __name__ == '__main__':
    main()
