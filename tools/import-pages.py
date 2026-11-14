#!/usr/bin/env python3
"""Bring an app's help and privacy drafts into this site, or wrap the pages
already here in the current shell.

The drafts live in each app's repo (docs/app-store/<version>/pages/). Their
words are kept as they are: this script takes each draft's <title>, meta
description, canonical URL and the inside of its <main>, and wraps them in
this site's shell (the kits' header and footer styles, doc.css, no script).
Run it again after the app's session revises a draft:

    python3 tools/import-pages.py pittari ../qrpass-ios/docs/app-store/1.0/pages
    python3 tools/import-pages.py enerbot-doll ../robodoll-ios/docs/app-store/1.0.0/pages
    python3 tools/import-pages.py celular-listo ../phonecheck-android/docs/play-store/pages

After a change to the shell, re-wrap the pages already here instead, which
takes their words from the pages themselves and so cannot pull in a draft
nobody meant to publish:

    python3 tools/import-pages.py --rewrap all      # or one app: --rewrap pittari

The shell around the words: a crumb back to the app's band in the catalog, a
kicker built from the app's facts (a privacy page keeps its draft's effective
date), the draft's contents list as a rail or a row of chips, and the family
shelf at the foot (also kept current by tools/build-catalog.py). A published
app's pages carry Safari's install banner, and its help page the icon and the
install button. App facts come from data/apps.json.

An app in several languages lists them under 'langs', its store record's
primary language first. That language's drafts sit at the top of the folder
and land at /<app>/; each other language's sit in <folder>/<lang>/ and land
at /<app>/<lang>/, the URL that language's store listing gives. A language
with no draft yet is skipped. Once two languages are in, every page names the
others: hreflang links in its head, and their own names beside the crumb.

It refuses a draft whose canonical URL is not this site's page for it, so a
draft written for another host or another language cannot land here by
mistake. amigos/ is frozen while Amigos de Enerbot's first version is in App
Review: this script never writes it.
"""
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from appdata import ORIGIN, SITE, by_id, crumb, family, load  # noqa: E402

FROZEN = {'amigos'}

ES = {
    'help': 'Ayuda', 'privacy': 'Privacidad', 'policy': 'Política de privacidad',
    'related': 'Páginas relacionadas', 'skip': 'Ir al contenido', 'part': 'Parte de Neorgon',
    'native': 'Español', 'langs': 'Idiomas', 'in_effect': 'Vigente desde',
    'install': 'Descargar en el {store}', 'icon_alt': 'Ícono de {name}',
}
EN = {
    'help': 'Help', 'privacy': 'Privacy', 'policy': 'Privacy policy',
    'related': 'Related pages', 'skip': 'Skip to content', 'part': 'Part of Neorgon',
    'native': 'English', 'langs': 'Languages', 'in_effect': 'In effect since',
    'install': 'Download on the {store}', 'icon_alt': '{name} icon',
}
# Written without a native speaker's read; used only if Enerbot Doll ships Japanese.
JA = {
    'help': 'ヘルプ', 'privacy': 'プライバシー', 'policy': 'プライバシーポリシー',
    'related': '関連ページ', 'skip': '本文へスキップ', 'part': 'Neorgon が運営',
    'native': '日本語', 'langs': '言語', 'in_effect': '施行日',
    'install': '{store} からダウンロード', 'icon_alt': '{name} のアイコン',
}
DATES = {
    'es': re.compile(r'(?:el )?\d{1,2} de \w+ de \d{4}'),
    'en': re.compile(r'\d{1,2} \w+ \d{4}'),
    'ja': re.compile(r'\d{4}年\d{1,2}月\d{1,2}日'),
}

APPS = {
    'pittari': {'langs': {'en': {**EN, 'help': 'Support'}}},
    'enerbot-doll': {'langs': {'es': ES, 'en': EN, 'ja': JA}},
    # An Android app, for Google Play; its listing's default language is Spanish (Latin America).
    'celular-listo': {'langs': {'es': ES, 'en': EN}},
    # Written by hand for this site from projects/headpain-ios: no drafts to import,
    # so only --rewrap reaches it, and it keeps its own head and kicker.
    'headpain': {'langs': {'en': {**EN, 'help': 'Support'}}, 'handwritten': True},
}

CSP = ("default-src 'none'; style-src 'self' https://cdn.neorgon.org/v1.0.0/; img-src 'self'; "
       "font-src 'self'; manifest-src 'self'; base-uri 'none'; form-action 'none'")
ARROW = ('<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">'
         '<path d="M7 17 17 7M9 7h8v8" fill="none" stroke="currentColor" stroke-width="2.2" '
         'stroke-linecap="round" stroke-linejoin="round"/></svg>')
MARK = re.compile(r'<!-- draft:(head|toc|body) -->\n(.*?)\n<!-- /draft:\1 -->', re.S)


def one(pattern, text, what, path):
    m = re.search(pattern, text, re.S)
    if not m:
        sys.exit(f'{path}: no {what}')
    return m.group(1).strip()


def split(inner, path):
    """The draft's <main> as (head, contents, body): the kicker, h1 and lead,
    its contents list, and its sections. A page this script already wrapped
    marks the three parts, so they come back exactly as they went in."""
    marked = dict(MARK.findall(inner))
    if marked:
        return marked.get('head', ''), marked.get('toc', ''), marked.get('body', '')
    # The shell's own crumb, on a page wrapped by the older shell, is not the draft's.
    inner = re.sub(r'^\s*(<p class="crumb">.*?</p>|<div class="crumb-row">.*?</nav></div>)\s*', '', inner, flags=re.S)
    m = re.search(r'\n?[ \t]*<nav class="contents"[^>]*>.*?</nav>', inner, re.S)
    if not m:
        sys.exit(f'{path}: no <nav class="contents"> to split the head from the sections')
    head, toc, body = inner[:m.start()], m.group(0), inner[m.end():]
    # The draft's first line lost its indent when <main> was trimmed; give it back.
    head = head.rstrip()
    if not head.startswith((' ', '\t')):
        head = '    ' + head
    return head, toc.strip('\n'), body.strip('\n')


def kicker(head, app, cfg, privacy, path):
    """Replace the draft's kicker with one built from the app's facts; a privacy
    page keeps its draft's effective date, with its label."""
    m = re.search(r'<p class="kicker">(.*?)</p>', head, re.S)
    if not m:
        sys.exit(f'{path}: no <p class="kicker">')
    if privacy:
        date = DATES[cfg['lang']].search(re.sub(r'<[^>]+>', '', m.group(1)))
        if not date:
            sys.exit(f'{path}: no effective date in the kicker "{m.group(1)}"')
        text = f'{cfg["policy"]} · {cfg["in_effect"]} {date.group(0)}'
    else:
        text = f'{app["name"]} · {" · ".join(app["platforms"])} · {cfg["help"]}'
    return head[:m.start()] + f'<p class="kicker">{html.escape(text, quote=False)}</p>' + head[m.end():]


def page(data, app_id, cfg, parts, meta, privacy, sub='', editions=(), original=None):
    """One page. `sub` is '' or '<lang>/'; `editions` lists (lang, sub, native name)
    for every language the app has, or nothing for a one-language app.
    `original` is a hand-written page whose head and header are kept."""
    app = by_id(data)[app_id]
    title, desc, canonical = meta
    tail = 'privacy/' if privacy else ''
    want = f'{ORIGIN}{app_id}/{sub}{tail}'
    if canonical != want:
        sys.exit(f'{app_id} {sub}{tail}: canonical is {canonical}, expected {want}')
    lang = cfg['lang']
    root = '../' * (1 + sub.count('/') + (1 if privacy else 0))
    home = '../' if privacy else './'
    head, toc, body = parts
    if not APPS[app_id].get('handwritten'):
        head = kicker(head, app, cfg, privacy, f'{app_id}/{sub}{tail}')
    published = app['status'] == 'available' and app.get('store')

    languages = ''.join(
        f'<a href="/{app_id}/{s}{tail}" hreflang="{code}" lang="{code}">{html.escape(native)}</a>'
        for code, s, native in editions if code != lang)
    langs_nav = f'<nav class="doc-langs" aria-label="{cfg["langs"]}">{languages}</nav>' if languages else ''
    crumb_html = crumb(lang, app, home, f'{root}#{app_id}', privacy, langs_nav)

    hero_icon, install, hero = '', '', ''
    if published and not privacy:
        hero = ' doc-head--hero'
        hero_icon = (f'\n      <img class="doc-hero__icon" src="{root}{app["icon"]}" alt="" width="88" height="88">')
        install = (f'\n      <p class="doc-install"><a class="doc-install__cta" href="{app["store"]["url"]}" '
                   f'rel="noreferrer">{cfg["install"].format(store=app["store"]["name"])}{ARROW}</a></p>')

    main = (f'<main id="main" class="doc-main doc-main--shell" tabindex="-1">\n'
            f'    <!-- neo-apps:crumb -->{crumb_html}<!-- /neo-apps:crumb -->\n'
            f'    <div class="doc-head{hero}">{hero_icon}\n'
            f'<!-- draft:head -->\n{head}\n<!-- /draft:head -->{install}\n'
            f'    </div>\n'
            f'    <div class="doc-shell">\n'
            f'<!-- draft:toc -->\n{toc}\n<!-- /draft:toc -->\n'
            f'      <div class="doc-body">\n'
            f'<!-- draft:body -->\n{body}\n<!-- /draft:body -->\n'
            f'      </div>\n'
            f'    </div>\n'
            f'  </main>')
    footer_first = (f'<a href="../">{cfg["help"]}</a>' if privacy
                    else f'<a href="privacy/">{cfg["policy"]}</a>')
    foot = (f'  <!-- neo-apps:family -->{family(data, lang, app_id, root, root + "assets/icons/")}'
            f'<!-- /neo-apps:family -->\n'
            f'  <footer class="neo-footer doc-footer" data-footer-mode="minimal"><div class="neo-footer-inner">'
            f'<span>&copy; 2026 Neorgon</span><nav class="doc-related" aria-label="{cfg["related"]}">{footer_first}'
            f'<a href="https://neorgon.com/" rel="noreferrer">{cfg["part"]}</a></nav></div></footer>\n')

    if original is not None:
        # A hand-written page keeps everything above <main> as it was, plus the
        # two stylesheets the shell needs.
        top = original[:original.index('<main')]
        if 'css/family.css' not in top:
            top = top.replace(f'<link rel="stylesheet" href="{root}css/doc.css">',
                              f'<link rel="stylesheet" href="{root}css/doc.css">\n'
                              f'  <link rel="stylesheet" href="{root}css/family.css">\n'
                              f'  <link rel="stylesheet" href="{root}css/apps.css">', 1)
        top = re.sub(r'<body class="doc doc--[\w-]+"[^>]*>', f'<body class="doc doc--{app_id}" data-app="{app_id}">', top, 1)
        return top + main + '\n' + foot + '</body>\n</html>\n'

    alternates = ''.join(
        f'\n  <link rel="alternate" hreflang="{code}" href="{ORIGIN}{app_id}/{s}{tail}">'
        for code, s, _ in editions)
    if editions:
        alternates += f'\n  <link rel="alternate" hreflang="x-default" href="{ORIGIN}{app_id}/{tail}">'
    itunes = f'\n  <meta name="apple-itunes-app" content="app-id={app["store"]["id"]}">' if published else ''
    name = html.escape(app['name'])
    skin = f' data-header-skin="{app["skin"]}"' if app.get('skin') else ''
    here_help = '' if privacy else ' aria-current="page"'
    here_priv = ' aria-current="page"' if privacy else ''
    priv_href = './' if privacy else 'privacy/'
    icon_alt = cfg['icon_alt'].format(name=app['name'])
    return f'''<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <!-- Generated by tools/import-pages.py from the app's draft; edit the draft and run it again. -->
  <meta http-equiv="Content-Security-Policy" content="{CSP}">
  <meta name="referrer" content="no-referrer">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <link rel="canonical" href="{canonical}">{alternates}
  <meta name="robots" content="index, follow">
  <meta name="theme-color" content="#040714">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Neorgon">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{ORIGIN}{app["icon_png"]}">
  <meta property="og:image:alt" content="{html.escape(icon_alt)}">
  <meta name="twitter:card" content="summary">{itunes}
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="icon" type="image/x-icon" href="/favicon.ico" sizes="16x16 32x32 48x48">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <meta name="apple-mobile-web-app-title" content="Neorgon Apps">
  <link rel="manifest" href="/site.webmanifest">
  <meta name="neo-mark" content="on">
  <link rel="stylesheet" href="https://cdn.neorgon.org/v1.0.0/styles/base.css">
  <link rel="stylesheet" href="{root}css/style.css">
  <link rel="stylesheet" href="{root}css/neorgon-header.css">
  <link rel="stylesheet" href="{root}css/neorgon-footer.css">
  <link rel="stylesheet" href="{root}css/doc.css">
  <link rel="stylesheet" href="{root}css/family.css">
  <link rel="stylesheet" href="{root}css/apps.css">
</head>
<body class="doc doc--{app_id}" data-app="{app_id}">
  <a class="skip-link" href="#main">{cfg["skip"]}</a>
  <header class="header-bar doc-header" data-header-mode="app"{skin}>
    <div class="header-logo"><a class="header-title-link" href="{home}"><span class="doc-brand"><img src="{root}assets/icons/{app_id}.png" alt="" width="36" height="36"><span class="doc-brand-name">{name}</span></span></a></div>
    <nav class="doc-nav" aria-label="{name}"><a href="{home}"{here_help}>{cfg["help"]}</a><a href="{priv_href}"{here_priv}>{cfg["privacy"]}</a></nav>
  </header>
  {main}
{foot}</body>
</html>
'''


def languages_of(app_id, folder):
    """(lang, labels, sub, folder) for each language with a page in `folder`."""
    found = []
    for i, (lang, labels) in enumerate(APPS[app_id]['langs'].items()):
        where = folder / lang if i else folder
        if not (where / 'index.html').is_file():
            if i == 0:
                sys.exit(f'{where}: no page in {lang}, the first language of {app_id}')
            continue
        found.append((lang, {'lang': lang, **labels}, f'{lang}/' if i else '', where))
    return found


def read(path, rewrap):
    """(title, description, canonical) and the three parts of a draft, or of a
    page already on this site."""
    if not path.is_file():
        sys.exit(f'{path}: missing')
    text = path.read_text(encoding='utf-8')
    title = one(r'<title>(.*?)</title>', text, 'title', path)
    # The fleet's meta descriptions end without a period; the draft's words are kept.
    desc = one(r'<meta name="description" content="(.*?)">', text, 'description', path).rstrip('.')
    canonical = one(r'<link rel="canonical" href="(.*?)">', text, 'canonical', path)
    pattern = r'<main id="main"[^>]*>(.*?)</main>' if rewrap else r'<main id="main" tabindex="-1">(.*?)</main>'
    inner = one(pattern, text, '<main id="main">', path)
    if rewrap:
        inner = re.sub(r'^<!-- neo-apps:crumb -->.*?<!-- /neo-apps:crumb -->\s*', '', inner, flags=re.S)
    return (title, desc, canonical), split(inner, path), text


def build(data, app_id, folder, rewrap):
    found = languages_of(app_id, folder)
    editions = [(lang, sub, cfg['native']) for lang, cfg, sub, _ in found] if len(found) > 1 else []
    # Every page is built before any is written, so a refused one leaves the site as it was.
    pending = []
    for lang, cfg, sub, where in found:
        for privacy in (False, True):
            source = where / ('privacy/index.html' if privacy else 'index.html')
            meta, parts, text = read(source, rewrap)
            original = text if APPS[app_id].get('handwritten') else None
            out = SITE / app_id / sub / ('privacy/index.html' if privacy else 'index.html')
            pending.append((source, out, page(data, app_id, cfg, parts, meta, privacy, sub, editions, original)))
    return pending


def main(argv):
    rewrap = '--rewrap' in argv
    args = [a for a in argv if a != '--rewrap']
    if rewrap and len(args) == 1:
        targets = list(APPS) if args[0] == 'all' else [args[0]]
    elif not rewrap and len(args) == 2:
        targets = [args[0]]
    else:
        sys.exit(__doc__)
    for app_id in targets:
        if app_id in FROZEN:
            sys.exit(f'{app_id}/ is frozen while its first version is in App Review; nothing was written')
        if app_id not in APPS:
            sys.exit(f'{app_id}: not an app this script wraps ({", ".join(APPS)})')
        if APPS[app_id].get('handwritten') and not rewrap:
            sys.exit(f'{app_id}: written by hand for this site, so there are no drafts to import; use --rewrap')
    data = load()
    pending = []
    for app_id in targets:
        folder = SITE / app_id if rewrap else Path(args[1])
        pending += build(data, app_id, folder, rewrap)
    for source, out, text in pending:
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.is_file() or out.read_text(encoding='utf-8') != text:
            out.write_text(text, encoding='utf-8')
            print(f'{source.relative_to(SITE) if source.is_relative_to(SITE) else source} -> {out.relative_to(SITE)}')


if __name__ == '__main__':
    main(sys.argv[1:])
