"""Build 17 nav-stub redirect pages — fixes ~80% of dead links.

Each generated stub is a meta-refresh that jumps to its parent browse hub
(browse-items.html / browse-spells.html / browse-creatures.html). These
sub-categories never had dedicated landing pages in the corpus but ~74,112 of
the wiki's category/nav links target them, so users used to hit 404s. After
this script, all 17 targets resolve.

Run: .venv\\Scripts\\python.exe build_nav_stubs.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STUBS = {
    'browse-items-weapons': ('browse-items.html', '武器'),
    'browse-items-armor': ('browse-items.html', '护甲'),
    'browse-items-consumables': ('browse-items.html', '消耗品'),
    'browse-items-worn': ('browse-items.html', '佩戴物品'),
    'browse-items-runes': ('browse-items.html', '符文'),
    'browse-items-implements': ('browse-items.html', '法器'),
    'browse-spells-arcane': ('browse-spells.html', '奥术'),
    'browse-spells-divine': ('browse-spells.html', '神圣'),
    'browse-spells-occult': ('browse-spells.html', '神秘'),
    'browse-spells-primal': ('browse-spells.html', '原初'),
    'browse-spells-cantrips': ('browse-spells.html', '戏法'),
    'browse-spells-focus': ('browse-spells.html', '专注'),
    'browse-creatures-level-0-3': ('browse-creatures.html', '0-3 级'),
    'browse-creatures-level-4-7': ('browse-creatures.html', '4-7 级'),
    'browse-creatures-level-8-12': ('browse-creatures.html', '8-12 级'),
    'browse-creatures-level-13-17': ('browse-creatures.html', '13-17 级'),
    'browse-creatures-level-18-25': ('browse-creatures.html', '18-25 级'),
}

TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={target}">
<title>{label} — 跳转中</title>
</head>
<body>
<p>正在跳转到 <a href="{target}">{label}（{parent}）</a>...</p>
</body>
</html>
'''

def main():
    count = 0
    for slug, (target, label) in STUBS.items():
        out = ROOT / f'{slug}.html'
        out.write_text(
            TEMPLATE.format(target=target, label=label, parent=target.replace('.html', '')),
            encoding='utf-8'
        )
        count += 1
    print(f'wrote {count} nav stubs')

if __name__ == '__main__':
    main()
