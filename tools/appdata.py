"""data/apps.json, read and checked, plus the pieces every app page shares.

build-catalog.py and import-pages.py both import this module, so the catalog,
the help and privacy pages and the help pages hosted elsewhere draw the same
shelf, crumb and licence line from the same data. Python standard library only.
"""
import html
import json
import math
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
# The available group says where to get the apps only while every one of them
# is in the same store; Celular Listo on Google Play turns it into this.
AVAILABLE_MIXED = {'es': 'Disponibles', 'en': 'Available'}
# Words a visitor never reads here: release operations, relative ages and
# defences of where a picture came from. Checked against every page this
# module helps write, so a typo in the data cannot put them back.
FORBIDDEN = re.compile(
    r'\b(TestFlight|builds?|App Store Connect|App Review|simulador|servidor de desarrollo|maqueta|'
    r'capturas reales|Nuev[ao]s?|[Úú]ltim[ao]s?|latest|newest|New|'
    r'en revisi[óo]n|in review|revisi[óo]n de Apple|beta|prueba interna|internal test|'
    r'hace (?:\d+|un|una|unos|unas|poco)|\d+ (?:days?|weeks?|months?) ago|ago\b|'
    r'esta semana|este mes|reci[ée]n|this week|this month|today|hoy)\b', re.I)
FORBIDDEN_KEYS = re.compile(r'build|review|testflight|submitted|released|date|version|beta|note', re.I)
# Every key an app may carry. A key outside this list is refused, so a release
# field cannot slip in under a name the pattern above does not know.
APP_KEYS = {'id', 'name', 'promise', 'category', 'platforms', 'traits', 'status', 'featured', 'store',
            'web', 'os', 'schema_category', 'pages', 'contact', 'hue', 'ink', 'skin', 'icon',
            'icon_png', 'screenshots', 'credit'}

LICENCE = {
    'es': ('En el App Store rige la <a href="https://www.apple.com/legal/internet-services/itunes/dev/stdeula/" '
           'rel="noreferrer">licencia estándar de Apple</a>.'),
    'en': ('On the App Store, Apple’s <a href="https://www.apple.com/legal/internet-services/itunes/dev/stdeula/" '
           'rel="noreferrer">standard licence</a> applies.'),
}
CREDIT = {
    'es': ('El arte de Enerbot es de Zikri Kader, vía <a href="https://robohash.org/" rel="noreferrer">RoboHash</a>, '
           'con licencia CC BY.'),
    'en': ('Enerbot’s art is by Zikri Kader, via <a href="https://robohash.org/" rel="noreferrer">RoboHash</a>, '
           'under a CC BY licence.'),
}

LABELS = {
    'es': {
        'catalog': 'Apps de Neorgon', 'all': 'Todas las apps', 'crumb': 'Ruta',
        'family': 'Apps de Neorgon', 'help': 'Ayuda', 'privacy': 'Privacidad',
        'licence': f"{LICENCE['es']} {CREDIT['es']}",
    },
    'en': {
        'catalog': 'Neorgon apps', 'all': 'All apps', 'crumb': 'Breadcrumb',
        'family': 'Neorgon apps', 'help': 'Help', 'privacy': 'Privacy',
        'licence': f"{LICENCE['en']} {CREDIT['en']}",
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
            if key not in APP_KEYS:
                problems.append(f'{where}: field "{key}" is not one this catalog knows')
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
        for text in [app.get('name', ''), app.get('promise', '')] + app.get('traits', []) + \
                [s.get('caption', '') for s in app.get('screenshots', [])] + \
                [s.get('alt', '') for s in app.get('screenshots', [])]:
            if FORBIDDEN.search(text):
                problems.append(f'{where}: "{text}" has a word the catalog does not print')
    if problems:
        raise SystemExit('data/apps.json:\n  ' + '\n  '.join(problems))
    return data


def by_id(data):
    return {a['id']: a for a in data['apps']}


apps_by_id = by_id


def group_label(data, status, lang='es'):
    """'En el App Store' while every available app is there, else 'Disponibles'."""
    label = dict(GROUPS)[status][lang]
    if status == 'available':
        stores = {(a.get('store') or {}).get('name') for a in data['apps'] if a['status'] == 'available'}
        if stores != {'App Store'}:
            return AVAILABLE_MIXED[lang]
    return label


def legal_line(app, lang):
    """The licence and credit an app's own pages need, and nothing else: Apple's
    licence only for an app on the App Store, the Enerbot credit only for an app
    whose art is Enerbot's ('credit': 'enerbot' in the data)."""
    parts = []
    if app['status'] == 'available' and (app.get('store') or {}).get('name') == 'App Store':
        parts.append(LICENCE[lang])
    if app.get('credit') == 'enerbot':
        parts.append(CREDIT[lang])
    return f'<p class="neo-family__legal">{" ".join(parts)}</p>' if parts else ''


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
            f'{legal_line(apps_by_id(data)[current], lang)}'
            f'</div></nav>')


def replace_block(text, name, content, path):
    """Swap what sits between <!-- name --> and <!-- /name -->."""
    pattern = re.compile(rf'(<!-- {re.escape(name)} -->)(.*?)(<!-- /{re.escape(name)} -->)', re.S)
    if not pattern.search(text):
        raise SystemExit(f'{path}: no <!-- {name} --> block')
    return pattern.sub(lambda m: m.group(1) + content + m.group(3), text, count=1)


# ── Colour ───────────────────────────────────────────────────────────────────
# Each band is drawn from its app's own hue: the hue angle and chroma of the
# app colour, at a low lightness, so amber stays warm and green stays green
# (mixing the hue into the blue-black page turned them grey). Plain OKLCH maths,
# so css/apps.css carries hex values every browser reads.

def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gamma(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def oklch(hex_colour):
    r, g, b = (_lin(int(hex_colour[i:i + 2], 16) / 255) for i in (1, 3, 5))
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    bb = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def oklch_hex(L, C, H):
    """The colour as #rrggbb, its chroma lowered until it fits in sRGB."""
    while True:
        a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
        l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
        m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
        s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
        rgb = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
               -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
               -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
        if all(-1e-6 <= x <= 1 + 1e-6 for x in rgb) or C <= 0:
            break
        C -= 0.001
    return '#' + ''.join(f'{round(max(0.0, min(1.0, _gamma(max(0.0, x)))) * 255):02x}' for x in rgb)


def tints(hue):
    """(band, stage) for an app colour. Warm hues (35 to 115 degrees) turn 20
    degrees toward red, so amber reads as rust on a dark band, never olive."""
    _, C, H = oklch(hue)
    if 35 <= H <= 115:
        H -= 20
    return oklch_hex(0.25, min(0.065, C * 0.55), H), oklch_hex(0.37, min(0.075, C * 0.6), H)


def luminance(hex_colour):
    r, g, b = (_lin(int(hex_colour[i:i + 2], 16) / 255) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)
