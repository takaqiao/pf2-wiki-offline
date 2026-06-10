"""Full-site internal dead-link scan (same scope as the v0.3.29 0.92% baseline:
all anchors into pages/category/data/project from every built HTML)."""
import io, os, re, sys, glob, urllib.parse
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(r'C:\Users\Taka\Desktop\fvtt\_wiki_full_v2')

# existing-file sets per dir (casefold for NTFS semantics)
exists = {}
for d in ('pages', 'category', 'data', 'project', 'classes', 'source'):
    exists[d] = {fn.casefold() for fn in os.listdir(d)} if os.path.isdir(d) else set()
root_files = {fn.casefold() for fn in os.listdir('.') if fn.endswith('.html')}

HREF_RX = re.compile(r'href="((?:\.\./)?(?:pages|category|data|project|classes|source)/[^"#]+\.html)')
total = 0
dead = 0
dead_targets = Counter()

scan_dirs = ['pages', 'category', 'data', 'project', 'classes']
files = []
for d in scan_dirs:
    files.extend(glob.glob(d + '/*.html'))
files.extend(glob.glob('*.html'))

for f in files:
    try:
        s = io.open(f, encoding='utf-8', errors='ignore').read()
    except OSError:
        continue
    for href in HREF_RX.findall(s):
        total += 1
        rel = urllib.parse.unquote(href.replace('../', '', 1))
        d, _, fn = rel.partition('/')
        if fn.casefold() not in exists.get(d, set()):
            dead += 1
            dead_targets[rel] += 1

print(f'files scanned: {len(files):,}')
print(f'internal anchors: {total:,}')
print(f'dead: {dead:,} = {100.0*dead/max(total,1):.2f}%  (baseline v0.3.29: 0.92%)')
print(f'unique dead targets: {len(dead_targets):,}')
print('top 15 dead targets:')
for t, n in dead_targets.most_common(15):
    print(f'  {n:6,}  {t}')
