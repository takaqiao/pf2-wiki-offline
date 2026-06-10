import io, os, re, sys, glob, urllib.parse, random
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(r'C:\Users\Taka\Desktop\fvtt\_wiki_full_v2')

# 1. RC1: victim anchors (title="武器" linking to category/武器) must be 0
q = urllib.parse.quote('武器')
victim_rx = re.compile(r'href="\.\./category/%s\.html"[^>]*title="武器"' % q)
victims = 0
allpages = sorted(glob.glob('pages/*.html'))
random.seed(42)
sample = random.sample(allpages, 6000)
for f in sample:
    s = io.open(f, encoding='utf-8', errors='ignore').read()
    if victim_rx.search(s):
        victims += 1
print(f'[RC1] victim anchors (sample 6000 pages): {victims} files (expect 0)')
p = 'pages/长剑.html'
if os.path.exists(p):
    s = io.open(p, encoding='utf-8', errors='ignore').read()
    if f'../pages/{q}.html' in s:
        verdict = 'pages OK'
    elif f'../category/{q}.html"' in s and 'title="武器"' in s:
        verdict = 'CATEGORY (bad)'
    else:
        verdict = 'no 武器 link on this page'
    print('[RC1] 长剑.html links 武器 →', verdict)

# 2. CF1: linked images present
imgcnt = 0
pages_with_img = 0
for f in random.sample(allpages, 3000):
    n = io.open(f, encoding='utf-8', errors='ignore').read().count('<img')
    imgcnt += n
    pages_with_img += (1 if n else 0)
print(f'[CF1] imgs in 3000-page sample: {imgcnt} tags across {pages_with_img} pages')

# 3. RC3: a known pointer stub now jumps
for cand in ['治疗药水__次等治疗药水', '燃焰战旗__上等燃焰战旗', '武装弹__武装弹']:
    p = f'pages/{cand}.html'
    if os.path.exists(p):
        s = io.open(p, encoding='utf-8').read()
        has_js = 'location.replace' in s
        has_meta = 'http-equiv="refresh"' in s
        print(f'[RC3] {cand}: script-jump={has_js} meta={has_meta}')
        break
else:
    print('[RC3] no known stub candidate found on disk — check naming')

# 4. RC7: no stub->stub chains, no self loops
stub_rx = re.compile(r'http-equiv="refresh" content="0; url=([^"]+)"')
stubs = {}
for d in ['pages', 'category', 'data', 'project']:
    for f in glob.glob(d + '/*.html'):
        key = f.replace(os.sep, '/')
        try:
            s = io.open(f, encoding='utf-8', errors='ignore').read(4096)
        except OSError:
            continue
        m = stub_rx.search(s)
        if m and len(s) < 4096:
            stubs[key] = m.group(1)
multi = 0
selfloop = 0
examples = []
for src, url in stubs.items():
    t = urllib.parse.unquote(url.split('#')[0])
    base = os.path.dirname(src)
    tgt = os.path.normpath(os.path.join(base, t)).replace(os.sep, '/')
    if tgt == src:
        selfloop += 1
        examples.append(('SELF', src))
    elif tgt in stubs:
        multi += 1
        examples.append(('CHAIN', src + ' -> ' + tgt))
print(f'[RC7] redirect stubs scanned: {len(stubs)}, stub->stub: {multi}, self-loop: {selfloop} (expect 0/0)')
for kind, ex in examples[:8]:
    print('   ', kind, ex)

# 5. RC4: maintenance cats gone, real cats alive
for c, want in [('相关', False), ('PC', False), ('武器', True), ('法术', True)]:
    print(f'[RC4] category/{c}.html exists={os.path.exists("category/" + c + ".html")} (want {want})')

# 6. LINK-3: edit/history links gone
n_edit = 0
for f in random.sample(allpages, 3000):
    s = io.open(f, encoding='utf-8', errors='ignore').read()
    if re.search(r'href="https?://[^"]*huijiwiki\.com/index\.php\?[^"]*action=(edit|history)', s):
        n_edit += 1
print(f'[LINK-3] pages with edit/history hrefs (3000 sample): {n_edit} (expect 0)')

# 7. cache stamps on a built page
s = io.open('pages/法师.html', encoding='utf-8').read()
print('[CACHE] style.css?v=v2i:', 'assets/style.css?v=v2i' in s,
      '| mw_collapsible.js?v=v2i:', 'mw_collapsible.js?v=v2i' in s)

# 8. search index: AC alias present
t = io.open('index/titles.js', encoding='utf-8', errors='ignore').read()
print('[SRCH-1] alias marker in titles.js:', ('重定向' in t), '| "AC" token present:', ('"AC"' in t))
