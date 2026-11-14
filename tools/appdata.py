"""data/apps.json, read and checked, plus the pieces every app page shares.

build-catalog.py and import-pages.py both import this module, so the catalog,
the help and privacy pages and the help pages hosted elsewhere draw the same
shelf, crumb and licence line from the same data. Python standard library only.
"""
import html
import json
import re
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
DATA = SITE / 'data' / 'apps.json'
ORIGIN = 'https://apps.neorgon.com/'

STATUSES = ('available', 'soon', 'test')
STATUS_LABEL = {
    'es': {'soon': 'Próximamente', 'test': 'Prueba abierta'},
    'en': {'soon': 'Coming soon', 'test': 'Open test'},
}
GROUPS = (
    ('available', {'es': 'En el App Store', 'en': 'On the App Store'}),
    ('soon', {'es': 'Próximamente', 'en': 'Coming soon'}),
)
# Words a visitor never reads here: release operations, relative ages and
# defences of where a picture came from. Checked against every page this
# module helps write, so a typo in the data cannot put them back.
FORBIDDEN = re.compile(
    r'\b(TestFlight|builds?|App Store Connect|simulador|servidor de desarrollo|maqueta|'
    r'capturas reales|Nuev[ao]s?|[Úú]ltim[ao]s?|latest|newest|New)\b')
FORBIDDEN_KEYS = re.compile(r'build|review|testflight|submitted|released|date', re.I)

LABELS = {
    'es': {
        'catalog': 'Apps de Neorgon', 'all': 'Todas las apps', 'crumb': 'Ruta',
        'family': 'Apps de Neorgon', 'help': 'Ayuda', 'privacy': 'Privacidad',
        'licence': ('En el App Store rige la <a href="https://www.apple.com/legal/internet-services/itunes/dev/stdeula/" '
                    'rel="noreferrer">licencia estándar de Apple</a>. El arte de Enerbot es de Zikri Kader, vía '
                    '<a href="https://robohash.org/" rel="noreferrer">RoboHash</a>, con licencia CC BY.'),
    },
    'en': {
        'catalog': 'Neorgon apps', 'all': 'All apps', 'crumb': 'Breadcrumb',
        'family': 'Neorgon apps', 'help': 'Help', 'privacy': 'Privacy',
        'licence': ('On the App Store, Apple’s <a href="https://www.apple.com/legal/internet-services/itunes/dev/stdeula/" '
                    'rel="noreferrer">standard licence</a> applies. Enerbot’s art is by Zikri Kader, via '
                    '<a href="https://robohash.org/" rel="noreferrer">RoboHash</a>, under a CC BY licence.'),
    },
}

esc = html.escape


def load():
    """The data, checked. Exits with a message on the first problem."""
    data = json.loads(DATA.read_text(encoding='utf-8'))
    problems = []
    seen = set()
    for app in data['apps']:
        where = app.get('id', '?')
        for key in app:
            if FORBIDDEN_KEYS.search(key):
                problems.append(f'{where}: field "{key}" is release state; it belongs in the app repo')
        for key in ('id', 'name', 'promise', 'category', 'platforms', 'status', 'pages', 'hue', 'ink', 'icon'):
            if not app.get(key):
                problems.append(f'{where}: no {key}')
        if app.get('id') in seen:
            problems.append(f'{where}: duplicate id')
        seen.add(app.get('id'))
        if app.get('status') not in STATUSES:
            problems.append(f'{where}: status must be one of {", ".join(STATUSES)}')
        if app.get('status') == 'available' and not app.get('store'):
            problems.append(f'{where}: available, but no store link')
        if app.get('category') not in data['categories']:
            problems.append(f'{where}: category {app.get("category")} has no labels')
        for kind in ('help', 'privacy'):
            if not app.get('pages', {}).get(kind):
                problems.append(f'{where}: no {kind} page')
        for i, shot in enumerate(app.get('screenshots', []), 1):
            if not shot.get('alt', '').strip():
                problems.append(f'{where}: screenshot {i} has no alt text')
            if not shot.get('caption', '').strip():
                problems.append(f'{where}: screenshot {i} has no caption')
            if not (SITE / shot.get('src', '')).is_file():
                problems.append(f'{where}: screenshot {i} missing on disk ({shot.get("src")})')
        for key in ('icon', 'icon_png'):
            if app.get(key) and not (SITE / app[key]).is_file():
                problems.append(f'{where}: {key} missing on disk ({app[key]})')
        for text in [app.get('promise', '')] + app.get('traits', []) + \
                [s.get('caption', '') for s in app.get('screenshots', [])]:
            if FORBIDDEN.search(text):
                problems.append(f'{where}: "{text}" has a word the catalog does not print')
    if problems:
        raise SystemExit('data/apps.json:\n  ' + '\n  '.join(problems))
    return data


def by_id(data):
    return {a['id']: a for a in data['apps']}


def ordered(data):
    """Apps in shelf order: the store group first, each group in file order."""
    out = []
    for status, _ in GROUPS:
        for app in data['apps']:
            group = 'available' if app['status'] == 'available' else 'soon'
            if group == status:
                out.append(app)
    return out


def page_for(app, kind, lang):
    """The help or privacy page in `lang` when it exists, else the app's first."""
    pages = app['pages'][kind]
    for p in pages:
        if p['lang'] == lang:
            return p
    return pages[0]


def local(url, root):
    """An apps.neorgon.com URL as a path from `root` ('' at the site root, '../' one down)."""
    if url.startswith(ORIGIN):
        rest = url[len(ORIGIN):]
        return (root + rest) or './'
    return url


def category_icon(cat_id):
    """The category's icon, inline, or '' when it has not been copied in yet."""
    path = SITE / 'assets' / 'categories' / f'{cat_id}.svg'
    if not path.is_file():
        return ''
    svg = path.read_text(encoding='utf-8').strip()
    svg = re.sub(r'\s*\n\s*', '', svg)
    return svg.replace('<svg ', '<svg class="chip__icon" aria-hidden="true" focusable="false" width="16" height="16" ', 1)


def crumb(lang, app, page_root, catalog_href, privacy=False, langs_nav=''):
    """'Apps de Neorgon / Pittari' (and '/ Privacidad' on a privacy page), with the
    language switch beside it when the app has more than one language."""
    t = LABELS[lang]
    cat_lang = '' if lang == 'es' else ' hreflang="es"'
    parts = [f'<a href="{catalog_href}"{cat_lang}>{t["catalog"]}</a>']
    if privacy:
        parts.append(f'<a href="{page_root}">{esc(app["name"])}</a>')
        parts.append(f'<span aria-current="page">{t["privacy"]}</span>')
    else:
        parts.append(f'<span aria-current="page">{esc(app["name"])}</span>')
    sep = '<span class="neo-crumb__sep" aria-hidden="true">/</span>'
    nav = f'<nav class="neo-crumb" aria-label="{t["crumb"]}">{sep.join(parts)}</nav>'
    if langs_nav:
        return f'<div class="neo-crumb-row">{nav}{langs_nav}</div>'
    return nav


def family(data, lang, current, catalog_root, icon_root, size=44):
    """The family shelf: every app, each linking to its band in the catalog,
    then the way to the whole catalog and the licence line."""
    t = LABELS[lang]
    cat_lang = '' if lang == 'es' else ' hreflang="es"'
    items = []
    for app in ordered(data):
        here = ' aria-current="true"' if app['id'] == current else ''
        icon = icon_root + Path(app['icon']).name
        items.append(
            f'<li><a class="neo-family__app" href="{catalog_root}#{app["id"]}"{cat_lang}{here}>'
            f'<img src="{icon}" alt="" width="{size}" height="{size}" loading="lazy" decoding="async">'
            f'<span>{esc(app["name"])}</span></a></li>')
    return (f'<nav class="neo-family" aria-label="{t["family"]}">'
            f'<div class="neo-family__inner">'
            f'<p class="neo-family__all"><a href="{catalog_root}"{cat_lang}>{t["all"]}</a></p>'
            f'<ul class="neo-family__shelf">{"".join(items)}</ul>'
            f'<p class="neo-family__legal">{t["licence"]}</p>'
            f'</div></nav>')


def replace_block(text, name, content, path):
    """Swap what sits between <!-- name --> and <!-- /name -->."""
    pattern = re.compile(rf'(<!-- {re.escape(name)} -->)(.*?)(<!-- /{re.escape(name)} -->)', re.S)
    if not pattern.search(text):
        raise SystemExit(f'{path}: no <!-- {name} --> block')
    return pattern.sub(lambda m: m.group(1) + content + m.group(3), text, count=1)
