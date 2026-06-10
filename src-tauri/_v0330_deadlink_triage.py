"""Triage top dead targets: metadata ns0 ghost (RC1 flip damage) vs wiki red link
vs RC4-swept category."""
import io, os, re, sys, json, glob, urllib.parse
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(r'C:\Users\Taka\Desktop\fvtt\_wiki_full_v2')

meta = json.load(io.open(r'..\pf2wiki-scraper\out_v2\metadata.json', encoding='utf-8'))
ns_by_title = {}
for p in meta.get('pages', []):
    ns_by_title.setdefault(p.get('title', ''), p.get('ns', 0))
redirect_map = meta.get('redirect_map', {}) or {}

exists = {}
for d in ('pages', 'category', 'data', 'project', 'classes', 'source'):
    exists[d] = {fn.casefold() for fn in os.listdir(d)} if os.path.isdir(d) else set()

HREF_RX = re.compile(r'href="((?:\.\./)?(?:pages|category|data|project|classes|source)/[^"#]+\.html)')
dead_targets = Counter()
files = []
for d in ['pages', 'category', 'data', 'project', 'classes']:
    files.extend(glob.glob(d + '/*.html'))
files.extend(glob.glob('*.html'))
for f in files:
    try:
        s = io.open(f, encoding='utf-8', errors='ignore').read()
    except OSError:
        continue
    for href in HREF_RX.findall(s):
        rel = urllib.parse.unquote(href.replace('../', '', 1))
        d, _, fn = rel.partition('/')
        if fn.casefold() not in exists.get(d, set()):
            dead_targets[rel] += 1

cat_dead = sum(n for t, n in dead_targets.items() if t.startswith('category/'))
print(f'dead into category/: {cat_dead:,} anchors, {sum(1 for t in dead_targets if t.startswith("category/")):,} targets')
print('top dead category targets:')
for t, n in [x for x in dead_targets.most_common(200) if x[0].startswith('category/')][:10]:
    print(f'  {n:6,}  {t}')

print()
print('top 25 dead pages/ targets — triage:')
for t, n in [x for x in dead_targets.most_common(60) if x[0].startswith('pages/')][:25]:
    name = t.split('/', 1)[1][:-5].replace('__', '/')
    in_meta_ns = ns_by_title.get(name, None)
    cat_alt = ('分类:' + name) in ns_by_title or ('Category:' + name) in ns_by_title
    redir = redirect_map.get(name, None)
    klass = 'wiki-redlink' if in_meta_ns is None else f'ns{in_meta_ns}-GHOST(meta-but-no-file)'
    print(f'  {n:6,}  {name[:30]:32} meta={in_meta_ns} cat-twin={cat_alt} redir={repr(redir)[:25]} -> {klass}')
