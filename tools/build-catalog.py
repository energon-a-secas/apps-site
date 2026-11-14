#!/usr/bin/env python3
"""Write everything the catalog says about the apps from data/apps.json.

    python3 tools/build-catalog.py            # write the outputs below
    python3 tools/build-catalog.py --check    # exit 1 when a committed output differs
    python3 tools/build-catalog.py --stamp-family [--check] [HOST]

Outputs, all committed so the site needs no build step:
  index.html     the shelf and the app bands, between <!-- catalog --> markers,
                 and the JSON-LD (a CollectionPage with an ItemList), between
                 <!-- catalog-jsonld --> markers
  404.html       the shelf and every help and privacy page, between markers
  css/apps.css   each app's hue and ink, for the catalog and the app pages
  llms.txt       the plain-text catalog, visitor status only
  sitemap.xml    the catalog and every page this site hosts
  the app pages  the family shelf at the foot of every help and privacy page
                 that carries <!-- neo-apps:family --> markers (amigos/ is
                 frozen and never touched)

--stamp-family writes the crumb and the family shelf into the Kurukuru help
pages on hobbyorbit-site (HOST defaults to ../hobbyorbit-site), copies the app
icons and css/family.css beside them (that site's CSP allows only its own
images), and with --check reports drift instead.

It refuses a screenshot without alt text or a caption, and it never writes a
relative age ("Nueva", "latest") or a release word into a page.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from appdata import (FORBIDDEN, GROUPS, LABELS, ORIGIN, SITE, STATUS_LABEL, by_id,  # noqa: E402
                     category_icon, crumb, esc, family, load, local, ordered, page_for,
                     replace_block)

FROZEN = ('amigos/',)
EXTERNAL_ARROW = ('<svg class="cta__icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">'
                  '<path d="M7 17 17 7M9 7h8v8" fill="none" stroke="currentColor" stroke-width="2.2" '
                  'stroke-linecap="round" stroke-linejoin="round"/></svg>')
MAIL_ICON = ('<svg class="cta__icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">'
             '<rect x="3" y="5" width="18" height="14" rx="2.5" fill="none" stroke="currentColor" stroke-width="2"/>'
             '<path d="m4 7 8 6 8-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
             'stroke-linejoin="round"/></svg>')


def visible(markup):
    """The words a visitor reads: no comments, scripts, styles or tags."""
    markup = re.sub(r'<!--.*?-->', ' ', markup, flags=re.S)
    markup = re.sub(r'<(script|style)\b.*?</\1>', ' ', markup, flags=re.S)
    markup = re.sub(r'\salt="([^"]*)"', r' >\1<', markup)
    return re.sub(r'<[^>]+>', ' ', markup)


def guard(name, markup):
    hit = FORBIDDEN.search(visible(markup))
    if hit:
        raise SystemExit(f'{name}: refusing to write "{hit.group(0)}" (release words and relative ages stay out)')
    return markup


# ── The catalog ──────────────────────────────────────────────────────────────

def shelf(data, root='', size=72, heading=True):
    groups = []
    for status, label in GROUPS:
        apps = [a for a in ordered(data) if (a['status'] == 'available') == (status == 'available')]
        if not apps:
            continue
        items = ''.join(
            f'\n          <li><a class="shelf__app" href="{root}#{a["id"]}">'
            f'<img src="{root}{a["icon"]}" alt="" width="{size}" height="{size}">'
            f'<span class="shelf__name">{esc(a["name"])}</span></a></li>'
            for a in apps)
        groups.append(
            f'\n      <div class="shelf__group shelf__group--{status}">'
            f'\n        <p class="shelf__label" id="shelf-{status}">{label["es"]}</p>'
            f'\n        <ul class="shelf__grid" aria-labelledby="shelf-{status}">{items}\n        </ul>'
            f'\n      </div>')
    title = '\n    <h2 class="sr-only" id="catalog-title">Catálogo de apps</h2>' if heading else ''
    label = 'aria-labelledby="catalog-title"' if heading else 'aria-label="Apps de Neorgon"'
    return (f'\n  <nav class="shelf" {label}>{title}'
            f'\n    <div class="shelf__inner">{"".join(groups)}\n    </div>\n  </nav>')


def chips(data, app):
    cat = app['category']
    label = data['categories'][cat]['es']
    icon = category_icon(cat)
    out = [f'<li><a class="chip chip--category" href="https://neorgon.com/{cat}/">{icon}<span>{esc(label)}</span></a></li>']
    out += [f'<li><span class="chip">{esc(p)}</span></li>' for p in app['platforms']]
    out += [f'<li><span class="chip">{esc(t)}</span></li>' for t in app.get('traits', [])]
    return ''.join(out)


def action(app):
    """One primary action: the store, the web version, or a note to be told."""
    if app['status'] == 'available' and app.get('store'):
        return (f'<a class="cta" href="{app["store"]["url"]}" rel="noreferrer">'
                f'Descargar en el {esc(app["store"]["name"])}{EXTERNAL_ARROW}</a>')
    if app.get('web'):
        return f'<a class="cta" href="{app["web"]}" rel="noreferrer">Úsala en la web{EXTERNAL_ARROW}</a>'
    if app.get('contact'):
        subject = f'Avísame cuando salga {app["name"]}'.replace(' ', '%20')
        return (f'<a class="cta cta--quiet" href="mailto:{app["contact"]}?subject={subject}">'
                f'{MAIL_ICON}Avísame cuando salga</a>')
    return ''


def meta_row(app):
    help_ = page_for(app, 'help', 'es')
    priv = page_for(app, 'privacy', 'es')
    english = help_['lang'] != 'es' or priv['lang'] != 'es'
    note_id = f'{app["id"]}-lang'
    links = []
    for label, page in (('Ayuda', help_), ('Privacidad', priv)):
        attrs = f' hreflang="{page["lang"]}"' if page['lang'] != 'es' else ''
        if page['lang'] != 'es':
            attrs += f' aria-describedby="{note_id}"'
        links.append(f'<a href="{local(page["url"], "")}"{attrs}>{label}</a>')
    note = f'<span class="band__note" id="{note_id}">(en inglés)</span>' if english else ''
    return f'<p class="band__meta">{"".join(links)}{note}</p>'


def stage(app, eager):
    if not app.get('screenshots'):
        return ''
    loading = '' if eager else ' loading="lazy"'
    frames = ''.join(
        f'\n            <li class="stage__frame"><figure>'
        f'<a class="stage__shot" href="{s["src"]}"><img src="{s["src"]}" alt="{esc(s["alt"])}" '
        f'width="480" height="1043"{loading} decoding="async"></a>'
        f'<figcaption>{esc(s["caption"])}</figcaption></figure></li>'
        for s in app['screenshots'])
    return (f'\n        <div class="stage" role="region" aria-label="Capturas de {esc(app["name"])}">'
            f'\n          <ol class="stage__strip">{frames}\n          </ol>\n        </div>')


def band(data, app, first):
    featured = ' band--featured' if app.get('featured') else ''
    compact = '' if app.get('screenshots') else ' band--compact'
    size = 152 if app.get('featured') else 128
    pill = ''
    if app['status'] != 'available':
        pill = (f'<span class="pill" data-state="{app["status"]}"><span class="pill__glyph" aria-hidden="true">'
                f'</span>{STATUS_LABEL["es"][app["status"]]}</span>')
    act = action(app)
    act = f'\n          <p class="band__action">{act}</p>' if act else ''
    return (
        f'\n    <article class="band{featured}{compact}" id="{app["id"]}" data-app="{app["id"]}" '
        f'aria-labelledby="{app["id"]}-name">'
        f'\n      <div class="band__inner">'
        f'\n        <div class="band__info">'
        f'\n          <img class="band__icon" src="{app["icon"]}" alt="" width="{size}" height="{size}">'
        f'\n          <div class="band__title"><h3 class="band__name" id="{app["id"]}-name">{esc(app["name"])}</h3>{pill}</div>'
        f'\n          <p class="band__promise">{esc(app["promise"])}</p>'
        f'\n          <ul class="band__chips">{chips(data, app)}</ul>{act}'
        f'\n          {meta_row(app)}'
        f'\n        </div>{stage(app, first)}'
        f'\n      </div>'
        f'\n    </article>')


def catalog(data):
    parts = [shelf(data)]
    first = True
    for status, label in GROUPS:
        apps = [a for a in ordered(data) if (a['status'] == 'available') == (status == 'available')]
        if not apps:
            continue
        hidden = ' sr-only' if status == 'available' else ''
        bands = ''.join(band(data, a, first and i == 0) for i, a in enumerate(apps))
        first = False
        parts.append(
            f'\n  <section class="group group--{status}" aria-labelledby="group-{status}">'
            f'\n    <h2 class="group__title{hidden}" id="group-{status}">{label["es"]}</h2>{bands}'
            f'\n  </section>')
    return guard('index.html catalog', ''.join(parts) + '\n  ')


def jsonld(data):
    items = []
    for i, app in enumerate(ordered(data), 1):
        help_ = page_for(app, 'help', 'es')
        item = {
            '@type': 'MobileApplication',
            'name': app['name'],
            'description': app['promise'],
            'operatingSystem': app['os'],
            'applicationCategory': app['schema_category'],
            'url': help_['url'],
            'image': ORIGIN + app['icon_png'],
        }
        if app['status'] == 'available' and app.get('store'):
            item['installUrl'] = app['store']['url']
        items.append({'@type': 'ListItem', 'position': i, 'item': item})
    doc = {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        'name': 'Apps de Neorgon',
        'url': ORIGIN,
        'inLanguage': 'es',
        'publisher': {'@type': 'Organization', 'name': 'Neorgon', 'url': 'https://neorgon.com/'},
        'mainEntity': {'@type': 'ItemList', 'itemListElement': items},
    }
    body = json.dumps(doc, ensure_ascii=False, indent=2)
    body = '\n'.join('  ' + line for line in body.splitlines())
    return f'\n  <script type="application/ld+json">\n{body}\n  </script>\n  '


def apps_css(data):
    lines = ['/* Generated by tools/build-catalog.py from data/apps.json: each app\'s hue,',
             '   read from its icon, and a light tint of it (ink) for text and rules on the',
             '   dark page. Edit the data and run the tool; a hand edit here is overwritten. */']
    for app in data['apps']:
        lines.append(f'[data-app="{app["id"]}"] {{ --app-hue: {app["hue"]}; --app-ink: {app["ink"]}; }}')
    return '\n'.join(lines) + '\n'


def llms(data):
    out = ['# Apps de Neorgon', '',
           '> Las apps de Neorgon para iPhone y Android, en https://apps.neorgon.com/ (en español).',
           '> Cada app tiene su ayuda y su política de privacidad; las de Naninani y Kurukuru',
           '> están en sus propios sitios.', '']
    for status, label in GROUPS:
        apps = [a for a in ordered(data) if (a['status'] == 'available') == (status == 'available')]
        if not apps:
            continue
        out += [f'## {label["es"]}', '']
        for app in apps:
            cat = data['categories'][app['category']]['es']
            facts = app['platforms'] + [cat] + app.get('traits', [])
            if app['status'] != 'available':
                facts.insert(0, STATUS_LABEL['es'][app['status']])
            out.append(f'- {app["name"]}: {app["promise"]}')
            out.append(f'  {" · ".join(facts)}')
            if app['status'] == 'available' and app.get('store'):
                out.append(f'  {app["store"]["name"]}: {app["store"]["url"]}')
            elif app.get('web'):
                out.append(f'  En la web: {app["web"]}')
            for kind, word in (('help', 'Ayuda'), ('privacy', 'Privacidad')):
                for p in app['pages'][kind]:
                    note = '' if p['lang'] == 'es' else ' (en inglés)'
                    out.append(f'  {word}{note}: {p["url"]}')
        out.append('')
    out += ['## Notas', '',
            '- Las páginas de ayuda y de privacidad no cargan ningún script.',
            '- Ninguna app tiene términos propios: en el App Store rige la licencia estándar de Apple.',
            '- El arte de Enerbot es de Zikri Kader, vía RoboHash, con licencia CC BY.',
            '- Contacto: contact@neorgon.com y support@neorgon.org.', '']
    return guard('llms.txt', '\n'.join(out))


def hosted_pages(data):
    urls = []
    for app in data['apps']:
        for kind in ('help', 'privacy'):
            urls += [p['url'] for p in app['pages'][kind] if p['url'].startswith(ORIGIN)]
    return urls


def sitemap(data):
    urls = [ORIGIN] + hosted_pages(data)
    rows = ''.join(f'\n  <url><loc>{u}</loc></url>' for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}\n</urlset>\n')


def notfound_pages(data):
    """Each app's help and privacy page, in Spanish when there is one; an app
    that also has its pages in English gets one more link, in English."""
    def href(url):
        return '/' + url[len(ORIGIN):] if url.startswith(ORIGIN) else url
    rows = []
    for app in ordered(data):
        links = []
        for kind, word in (('help', 'Ayuda'), ('privacy', 'Privacidad')):
            p = page_for(app, kind, 'es')
            lang = '' if p['lang'] == 'es' else f' hreflang="{p["lang"]}"'
            suffix = '' if p['lang'] == 'es' else ' <span class="lang">(en inglés)</span>'
            links.append(f'<a href="{href(p["url"])}"{lang}>{word}{suffix}</a>')
        english = [p for p in app['pages']['help'] if p['lang'] == 'en']
        if english and page_for(app, 'help', 'es')['lang'] == 'es':
            links.append(f'<a href="{href(english[0]["url"])}" hreflang="en" lang="en">In English</a>')
        rows.append(f'\n        <li><span class="app">{esc(app["name"])}</span> {"".join(links)}</li>')
    return guard('404.html', f'\n      <ul class="pages">{"".join(rows)}\n      </ul>\n      ')


# ── App pages ────────────────────────────────────────────────────────────────

def doc_pages():
    for path in sorted(SITE.glob('**/index.html')):
        rel = path.relative_to(SITE).as_posix()
        if rel == 'index.html' or rel.startswith(FROZEN) or '/.' in '/' + rel:
            continue
        yield path, rel


def stamp_docs(data, write):
    """The family shelf at the foot of every app page that has the markers."""
    changed = []
    apps = by_id(data)
    for path, rel in doc_pages():
        text = path.read_text(encoding='utf-8')
        if '<!-- neo-apps:family -->' not in text:
            continue
        lang = re.search(r'<html lang="(\w+)"', text).group(1)
        app = re.search(r'<body[^>]*\sdata-app="([\w-]+)"', text).group(1)
        if app not in apps:
            raise SystemExit(f'{rel}: data-app="{app}" is not in data/apps.json')
        root = '../' * rel.count('/')
        block = guard(rel, family(data, lang, app, root, root + 'assets/icons/'))
        new = replace_block(text, 'neo-apps:family', block, rel)
        if new != text:
            changed.append(rel)
            if write:
                path.write_text(new, encoding='utf-8')
    return changed


# ── Help pages on other hosts (Kurukuru on hobbyorbit-site) ──────────────────

HOSTED = {
    # page on that host -> (app, lang, catalog root, the app's help page, privacy?)
    'kurukuru/index.html': ('kurukuru', 'en', ORIGIN, './', False),
    'kurukuru/privacy/index.html': ('kurukuru', 'en', ORIGIN, '../', True),
}
HOSTED_ASSETS = 'kurukuru/apps/'
HOSTED_CSS = 'kurukuru/family.css'


def stamp_family(data, host, check):
    stale = []
    apps = by_id(data)
    want = {}
    for app in data['apps']:
        want[HOSTED_ASSETS + Path(app['icon']).name] = (SITE / app['icon']).read_bytes()
    want[HOSTED_CSS] = (SITE / 'css' / 'family.css').read_bytes()
    for rel, (app_id, lang, catalog_root, help_root, privacy) in HOSTED.items():
        path = host / rel
        text = path.read_text(encoding='utf-8')
        icon_root = '../' * (rel.count('/') - 1) + 'apps/'
        new = replace_block(text, 'neo-apps:crumb',
                            crumb(lang, apps[app_id], help_root, catalog_root + f'#{app_id}', privacy), rel)
        new = replace_block(new, 'neo-apps:family',
                            guard(rel, family(data, lang, app_id, catalog_root, icon_root)), rel)
        if new != text:
            stale.append(rel)
            if not check:
                path.write_text(new, encoding='utf-8')
    for rel, blob in want.items():
        path = host / rel
        if not path.is_file() or path.read_bytes() != blob:
            stale.append(rel)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(blob)
    extra = sorted(p.relative_to(host).as_posix() for p in (host / HOSTED_ASSETS).glob('*')
                   if p.relative_to(host).as_posix() not in want) if (host / HOSTED_ASSETS).is_dir() else []
    for rel in extra:
        stale.append(rel + ' (no app uses it)')
        if not check:
            (host / rel).unlink()
    return stale


# ── Main ─────────────────────────────────────────────────────────────────────

def outputs(data):
    files = {}
    index = (SITE / 'index.html').read_text(encoding='utf-8')
    index = replace_block(index, 'catalog', catalog(data), 'index.html')
    index = replace_block(index, 'catalog-jsonld', jsonld(data), 'index.html')
    files['index.html'] = index
    nf = (SITE / '404.html').read_text(encoding='utf-8')
    nf = replace_block(nf, 'catalog-shelf', guard('404.html', shelf(data, root='/', size=64, heading=False) + '\n    '), '404.html')
    nf = replace_block(nf, 'catalog-pages', notfound_pages(data), '404.html')
    files['404.html'] = nf
    files['css/apps.css'] = apps_css(data)
    files['llms.txt'] = llms(data)
    files['sitemap.xml'] = sitemap(data)
    return files


def main(argv):
    check = '--check' in argv
    data = load()
    if '--stamp-family' in argv:
        rest = [a for a in argv if not a.startswith('--')]
        host = Path(rest[0]).resolve() if rest else (SITE.parent / 'hobbyorbit-site')
        if not host.is_dir():
            raise SystemExit(f'{host}: no such site')
        stale = stamp_family(data, host, check)
        if check:
            if stale:
                print('stale on ' + host.name + ': ' + ', '.join(stale))
                return 1
            print(f'{host.name}: the Kurukuru pages carry the current crumb, shelf and icons')
            return 0
        print(f'{host.name}: ' + (', '.join(stale) if stale else 'already current'))
        return 0
    stale = []
    for rel, text in outputs(data).items():
        path = SITE / rel
        current = path.read_text(encoding='utf-8') if path.is_file() else None
        if current != text:
            stale.append(rel)
            if not check:
                path.write_text(text, encoding='utf-8')
    stale += stamp_docs(data, write=not check)
    if check:
        if stale:
            print('stale: ' + ', '.join(stale) + ' (run python3 tools/build-catalog.py)')
            return 1
        print('catalog, 404, css/apps.css, llms.txt, sitemap.xml and the app pages match data/apps.json')
        return 0
    print('wrote ' + (', '.join(stale) if stale else 'nothing; everything was current'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
