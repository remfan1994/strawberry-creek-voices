#!/usr/bin/env python3
"""Update SCV EPUB hrefs to the 174-anchor editions. Run from the repo root."""
import argparse
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote, unquote, urlsplit

PREFIXES = {
    'en': 'Strawberry_Creek_Voices_Anchors_',
    'es': 'SCV_es_Anclas_',
    'fr': 'SCV_fr_Ancrages_',
    'de': 'SCV_de_Anker_',
    'pt': 'SCV_pt_Ancoras_',
    'ar': 'SCV_ar_Anchors_',
    'fa': 'SCV_fa_Anchors_',
    'hi': 'SCV_hi_Anchors_',
    'ja': 'SCV_ja_Anchors_',
    'ko': 'SCV_ko_Anchors_',
    'vi': 'SCV_vi_Anchors_',
    'tl': 'SCV_tl_Anchors_',
    'zhs': 'SCV_zh-Hans_Anchors_',
    'zht': 'SCV_zh-Hant_Anchors_',
}
RANGES = {lang: re.compile(re.escape(prefix) + r'0*1-(126|132|174)(?:_[^/]+)?\.epub$', re.I)
          for lang, prefix in PREFIXES.items()}
HREF = re.compile(r'''(?i)(?<![\w:-])(href\s*=\s*)(["'])([^"']+)\2''')
PARA = re.compile(r'<p\b[^>]*>.*?</p\s*>', re.I | re.S)
COUNT = re.compile(r'(?<![\d])1(\s*(?:-|\u2013|\u2014|~|\u301c|\uff5e|\u00e0)\s*)(126|132)(?!\d)')
FA_COUNT = re.compile(r'\u06f1(\s+\u062a\u0627\s+)(?:\u06f1\u06f2\u06f6|\u06f1\u06f3\u06f2)(?!\d)')


def edition(name):
    for lang, pattern in RANGES.items():
        match = pattern.fullmatch(name)
        if match:
            return lang, match[1]
    return None, None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true', help='write changes (default: preview only)')
    p.add_argument('--root', default='.', help='repository root (default: current directory)')
    args = p.parse_args()
    root = Path(args.root).resolve()
    if not (root / 'en' / 'index.html').is_file():
        sys.exit('Run from the SCV repository root, containing en/index.html.')
    found = {lang: [] for lang in PREFIXES}
    htmls = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and not (Path(folder)/d).is_symlink())
        for name in sorted(files):
            path = Path(folder) / name
            if path.is_symlink():
                continue
            lang, end = edition(name)
            if lang and end == '174':
                found[lang].append(path)
            if path.suffix.lower() in ('.html', '.htm'):
                htmls.append(path)
    errors = []
    for lang, paths in found.items():
        if len(paths) != 1:
            errors.append(f'{lang}: expected exactly one 174-anchor EPUB, found {len(paths)}')
            errors.extend('  ' + str(x.relative_to(root)) for x in paths)
    if errors:
        sys.exit('\n'.join(errors) + '\nNo files changed.')
    targets = {lang: paths[0] for lang, paths in found.items()}
    print('EPUB targets:')
    for lang, path in targets.items():
        print(f'  {lang}: {path.relative_to(root)}')
    changes = []
    link_total = count_total = 0
    homepages = {root / lang / 'index.html' for lang in PREFIXES}
    for path in sorted(htmls):
        # Keep original UTF-8 bytes and line endings, except for the edits.
        old = path.read_bytes()
        try:
            source = old.decode('utf-8')
        except UnicodeDecodeError:
            sys.exit(f'Non-UTF-8 HTML: {path.relative_to(root)}. No files changed.')
        links = counts = 0
        def replace_href(m):
            nonlocal links
            try:
                url = urlsplit(m[3])
            except ValueError:
                return m[0]
            if url.scheme or url.netloc:
                return m[0]
            lang, end = edition(unquote(url.path).rsplit('/', 1)[-1])
            if lang is None:
                return m[0]
            relative = os.path.relpath(targets[lang], path.parent).replace(os.sep, '/')
            new = quote(relative, safe='/._-')
            if url.query:
                new += '?' + url.query
            if url.fragment:
                new += '#' + url.fragment
            if new == m[3]:
                return m[0]
            links += 1
            return m[1] + m[2] + new + m[2]
        result = HREF.sub(replace_href, source)
        if path in homepages:
            def replace_count(m):
                nonlocal counts
                text = m[0]
                # Only update the prose describing the full EPUB, not anchor IDs or excerpts.
                if 'epub' not in text.lower() or re.search(r'<a\b', text, re.I):
                    return text
                text, n = COUNT.subn(lambda a: '1' + a[1] + '174', text)
                text, k = FA_COUNT.subn(lambda a: '\u06f1' + a[1] + '\u06f1\u06f7\u06f4', text)
                counts += n + k
                return text
            result = PARA.sub(replace_count, result)
        if result != source:
            changes.append((path, result.encode('utf-8')))
            link_total += links
            count_total += counts
            print(f'{path.relative_to(root)}: {links} link(s), {counts} edition count(s)')
    if args.apply:
        for path, content in changes:
            path.write_bytes(content)
    print(f'{"Updated" if args.apply else "Would update"} {len(changes)} HTML file(s): '
          f'{link_total} links, {count_total} edition counts.')
    if not args.apply:
        print('Preview only. Re-run with --apply to write changes.')

if __name__ == '__main__':
    main()
