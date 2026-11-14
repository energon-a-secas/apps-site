#!/usr/bin/env python3
"""Bring an app's help and privacy drafts into this site.

The drafts live in each app's repo (docs/app-store/<version>/pages/). Their
words are kept as they are: this script takes each draft's <title>, meta
description, canonical URL and the inside of its <main>, and wraps them in
this site's shell (the kits' header and footer styles, doc.css, no script).
Run it again after the app's session revises a draft:

    python3 tools/import-pages.py amigos ../amigos-ios/docs/app-store/1.0.0/pages
    python3 tools/import-pages.py pittari ../qrpass-ios/docs/app-store/1.0/pages
    python3 tools/import-pages.py enerbot-doll ../robodoll-ios/docs/app-store/1.0.0/pages
    python3 tools/import-pages.py celular-listo ../phonecheck-android/docs/play-store/pages

An app in several languages lists them under 'langs', its store record's
primary language first. That language's drafts sit at the top of the folder
and land at /<app>/; each other language's sit in <folder>/<lang>/ and land
at /<app>/<lang>/, the URL that language's store listing gives. A
language with no draft yet is skipped. Once two languages are in, every page
names the others: hreflang links in its head, and their own names beside the
way back to the catalog (the header keeps its two tabs).

It refuses a draft whose canonical URL is not this site's page for it, so a
draft written for another host or another language cannot land here by
mistake.
"""
import html
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent

APPS = {
    'amigos': {
        'name': 'Amigos de Enerbot', 'lang': 'es',
        'help': 'Ayuda', 'privacy': 'Privacidad', 'policy': 'Política de privacidad',
        'all': 'Todas las apps', 'crumb': 'Todas las apps de Neorgon', 'related': 'Páginas relacionadas',
        'skip': 'Ir al contenido', 'part': 'Parte de Neorgon', 'skin': '',
    },
    'pittari': {
        'name': 'Pittari', 'lang': 'en',
        'help': 'Support', 'privacy': 'Privacy', 'policy': 'Privacy policy',
        'all': 'All apps', 'crumb': 'All Neorgon apps', 'related': 'Related pages',
        'skip': 'Skip to content', 'part': 'Part of Neorgon', 'skin': 'brass',
    },
    'enerbot-doll': {
        'name': 'Enerbot Doll', 'skin': '',
        'langs': {
            'es': {
                'help': 'Ayuda', 'privacy': 'Privacidad', 'policy': 'Política de privacidad',
                'all': 'Todas las apps', 'crumb': 'Todas las apps de Neorgon', 'related': 'Páginas relacionadas',
                'skip': 'Ir al contenido', 'part': 'Parte de Neorgon',
                'native': 'Español', 'langs': 'Idiomas',
            },
            'en': {
                'help': 'Help', 'privacy': 'Privacy', 'policy': 'Privacy policy',
                'all': 'All apps', 'crumb': 'All Neorgon apps', 'related': 'Related pages',
                'skip': 'Skip to content', 'part': 'Part of Neorgon',
                'native': 'English', 'langs': 'Languages',
            },
            # Written without a native speaker's read; used only if Enerbot Doll ships Japanese.
            'ja': {
                'help': 'ヘルプ', 'privacy': 'プライバシー', 'policy': 'プライバシーポリシー',
                'all': 'アプリ一覧', 'crumb': 'Neorgon のアプリ一覧', 'related': '関連ページ',
                'skip': '本文へスキップ', 'part': 'Neorgon が運営',
                'native': '日本語', 'langs': '言語',
            },
        },
    },
    # An Android app, for Google Play; its listing's default language is Spanish (Latin America).
    'celular-listo': {
        'name': 'Celular Listo', 'skin': 'jade',
        'langs': {
            'es': {
                'help': 'Ayuda', 'privacy': 'Privacidad', 'policy': 'Política de privacidad',
                'all': 'Todas las apps', 'crumb': 'Todas las apps de Neorgon', 'related': 'Páginas relacionadas',
                'skip': 'Ir al contenido', 'part': 'Parte de Neorgon',
                'native': 'Español', 'langs': 'Idiomas',
            },
            'en': {
                'help': 'Help', 'privacy': 'Privacy', 'policy': 'Privacy policy',
                'all': 'All apps', 'crumb': 'All Neorgon apps', 'related': 'Related pages',
                'skip': 'Skip to content', 'part': 'Part of Neorgon',
                'native': 'English', 'langs': 'Languages',
            },
        },
    },
}

CSP = ("default-src 'none'; style-src 'self' https://cdn.neorgon.org/v1.0.0/; img-src 'self'; "
       "font-src 'self'; manifest-src 'self'; base-uri 'none'; form-action 'none'")


def one(pattern, text, what, path):
    m = re.search(pattern, text, re.S)
    if not m:
        sys.exit(f'{path}: no {what}')
    return m.group(1).strip()


def page(app, cfg, draft, privacy, sub='', editions=()):
    """One page. `sub` is '' or '<lang>/'; `editions` lists (lang, sub, native name)
    for every language the app has drafts in, or nothing for a one-language app."""
    if not draft.is_file():
        sys.exit(f'{draft}: missing')
    text = draft.read_text(encoding='utf-8')
    title = one(r'<title>(.*?)</title>', text, 'title', draft)
    # The fleet's meta descriptions end without a period; the draft's words are kept.
    desc = one(r'<meta name="description" content="(.*?)">', text, 'description', draft).rstrip('.')
    canonical = one(r'<link rel="canonical" href="(.*?)">', text, 'canonical', draft)
    tail = 'privacy/' if privacy else ''
    want = f'https://apps.neorgon.com/{app}/{sub}{tail}'
    if canonical != want:
        sys.exit(f'{draft}: canonical is {canonical}, expected {want}')
    main = one(r'<main id="main" tabindex="-1">(.*?)</main>', text, '<main id="main">', draft)
    root = '../' * (1 + sub.count('/') + (1 if privacy else 0))
    home = '../' if privacy else './'
    here_help = '' if privacy else ' aria-current="page"'
    here_priv = ' aria-current="page"' if privacy else ''
    priv_href = './' if privacy else 'privacy/'
    footer_first = (f'<a href="../">{cfg["help"]}</a>' if privacy
                    else f'<a href="privacy/">{cfg["policy"]}</a>')
    name = html.escape(cfg['name'])
    skin = f' data-header-skin="{cfg["skin"]}"' if cfg['skin'] else ''
    # Search engines get every language's copy of this page; readers get the
    # other languages, each in its own name and marked with its own lang.
    alternates = ''.join(
        f'\n  <link rel="alternate" hreflang="{lang}" href="https://apps.neorgon.com/{app}/{s}{tail}">'
        for lang, s, _ in editions)
    if editions:
        alternates += f'\n  <link rel="alternate" hreflang="x-default" href="https://apps.neorgon.com/{app}/{tail}">'
    languages = ''.join(
        f'<a href="/{app}/{s}{tail}" hreflang="{lang}" lang="{lang}">{html.escape(native)}</a>'
        for lang, s, native in editions if lang != cfg['lang'])
    crumb = f'<p class="crumb"><a href="{root}">&larr; {cfg["crumb"]}</a></p>'
    if languages:
        crumb = (f'<div class="crumb-row">{crumb}'
                 f'<nav class="doc-langs" aria-label="{cfg["langs"]}">{languages}</nav></div>')
    return f'''<!doctype html>
<html lang="{cfg["lang"]}">
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
</head>
<body class="doc doc--{app}">
  <a class="skip-link" href="#main">{cfg["skip"]}</a>
  <header class="header-bar doc-header" data-header-mode="app"{skin}>
    <div class="header-logo"><a class="header-title-link" href="{home}"><span class="doc-brand"><img src="{root}assets/icons/{app}.png" alt="" width="36" height="36"><span class="doc-brand-name">{name}</span></span></a></div>
    <nav class="doc-nav" aria-label="{name}"><a href="{home}"{here_help}>{cfg["help"]}</a><a href="{priv_href}"{here_priv}>{cfg["privacy"]}</a></nav>
  </header>
  <main id="main" class="doc-main" tabindex="-1">
    {crumb}
    {main}
  </main>
  <footer class="neo-footer doc-footer" data-footer-mode="minimal"><div class="neo-footer-inner"><span>&copy; 2026 Neorgon</span><nav class="doc-related" aria-label="{cfg["related"]}">{footer_first}<a href="{root}">{cfg["all"]}</a><a href="https://neorgon.com/" rel="noreferrer">{cfg["part"]}</a></nav></div></footer>
</body>
</html>
'''


def languages_of(app, pages):
    """(lang, labels, sub, draft folder) for each language the app has drafts in."""
    entry = APPS[app]
    if 'langs' not in entry:
        return [(entry['lang'], entry, '', pages)]
    found = []
    for i, (lang, labels) in enumerate(entry['langs'].items()):
        folder = pages / lang if i else pages
        if not (folder / 'index.html').is_file():
            if i == 0:
                sys.exit(f'{folder}: no draft in {lang}, the first language of {app}')
            continue
        cfg = {'name': entry['name'], 'skin': entry['skin'], 'lang': lang, **labels}
        found.append((lang, cfg, f'{lang}/' if i else '', folder))
    return found


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in APPS:
        sys.exit(__doc__)
    app, pages = sys.argv[1], Path(sys.argv[2])
    found = languages_of(app, pages)
    editions = [(lang, sub, cfg['native']) for lang, cfg, sub, _ in found] if len(found) > 1 else []
    # Every draft is checked before any page is written, so a refused draft
    # leaves the site as it was rather than half imported.
    pending = []
    for lang, cfg, sub, folder in found:
        for privacy in (False, True):
            draft = folder / ('privacy/index.html' if privacy else 'index.html')
            out = SITE / app / sub / ('privacy/index.html' if privacy else 'index.html')
            pending.append((draft, out, page(app, cfg, draft, privacy, sub, editions)))
    for draft, out, text in pending:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding='utf-8')
        print(f'{draft} -> {out.relative_to(SITE)}')


if __name__ == '__main__':
    main()
