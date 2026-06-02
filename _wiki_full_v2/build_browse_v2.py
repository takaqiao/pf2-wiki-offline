"""Phase F.5: build browse-*.html landing pages.

CATEGORY-DRIVEN (v3): each browse bucket = the members of specific REAL wiki
categories (inverted from every page's parse.categories — same data build_v2.py
uses for category/ pages), restricted to ns=0 content. This replaces the old
keyword-substring classify() heuristic, which did not correspond to wiki
categories (e.g. "物品" substring swept ~9.5k pages incl. nav/maintenance; "特征"
swept ~16k into "other"). See src-tauri/CATEGORY_FIX_PROGRESS.md.

Anchor categories were verified against live pf2.huijiwiki.com (list=categorymembers):
creatures has no flat category -> union of SIZE categories (size is creature-exclusive);
archetypes = 变体（特征）; ancestries = 族裔 (not 祖先); deities = 信仰 (not 神祇);
locations = 地理 (not 地点).

Run:
    .venv\\Scripts\\python.exe build_browse_v2.py
"""

from __future__ import annotations

import html as html_lib
import json
import re
import sys
import time
import urllib.parse
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRAPER_OUT = ROOT.parent / "pf2wiki-scraper" / "out_v2"
PARSED_DIR = SCRAPER_OUT / "parsed"
META_FILE = SCRAPER_OUT / "metadata.json"
SNIPPET_TOPNAV_ROOT = ROOT / "_snippets" / "topnav_root.html"
SNIPPET_TOPNAV_SUB = ROOT / "_snippets" / "topnav_sub.html"
SNIPPET_SIDEBAR_SUB = ROOT / "_snippets" / "sidebar_sub.html"

CACHE_VER = "v3"

# Browse bucket -> list of REAL wiki categories whose ns=0 members make the bucket.
# A page in several of a bucket's categories appears once (union, deduped by title).
BUCKET_CATS = {
    "feats":        ["专长"],
    "spells":       ["法术"],
    "items":        ["物品"],
    # creatures: 生物 is near-empty; size is creature-exclusive -> union of sizes.
    "creatures":    ["微型", "小型", "中型", "大型", "巨型", "超大型"],
    "ancestries":   ["族裔"],
    "backgrounds":  ["背景"],
    "archetypes":   ["变体（特征）"],
    # NOTE: no "classes" bucket — the 职业 category is a 419-row archetype/feat
    # grab-bag; the curated 27-class hub at classes/index.html is the real nav.
    "deities":      ["信仰"],
    "locations":    ["地理"],
    # "other" historically a keyword grab-bag (~16k); redefine to conditions/状态.
    "other":        ["状态"],
}

BUCKET_LABELS = {
    "feats": "专长", "spells": "法术", "items": "物品", "creatures": "生物",
    "ancestries": "族裔", "backgrounds": "背景", "archetypes": "变体",
    "deities": "信仰", "locations": "地理", "other": "异常状态",
    "categories": "分类页面", "all": "全部条目",
}

# --- ns=3500 Data join: 中文 title -> useful fields (等级/环级/根源/物品分类/体型/稀有度) ---
# Lets browse lists show meaningful, scannable columns instead of the dead
# "类型 = 条目" column. Mirrors build_nav_stubs' table parsing.
_DATA_ROW_RX = re.compile(r"<th>(.*?)</th><td class=\"mw-jsonconfig-value\">(.*?)</td>", re.S)
_DATA_TAG_RX = re.compile(r"<[^>]+>")


def _data_clean(s: str) -> str:
    return _DATA_TAG_RX.sub("", s).replace("&amp;", "&").strip()


def build_data_index() -> dict:
    """中文 title -> {等级, 环级, 根源, 法术分类, 物品分类, 体型, 稀有度}."""
    idx: dict[str, dict] = {}
    KEEP = ("等级", "环级", "根源", "法术分类", "物品分类", "体型", "稀有度")
    for sub in PARSED_DIR.iterdir():
        if not sub.is_dir() or sub.name.startswith("_"):
            continue
        for f in sub.iterdir():
            if not f.name.endswith(".json"):
                continue
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if doc.get("ns") != 3500:
                continue
            rec = {_data_clean(a): _data_clean(b)
                   for a, b in _DATA_ROW_RX.findall(doc.get("parse", {}).get("text", "") or "")}
            name = rec.get("中文", "")
            if name:
                idx[name] = {k: rec.get(k, "") for k in KEEP}
    return idx


# Per-bucket extra columns: (header, key, kind) — kind: 'text' | 'rarity' | 'size' | 'trad'.
# First data col replaces the dead 类型 column; second replaces/supplements 分类.
BUCKET_COLUMNS = {
    "feats":      [("等级", "等级", "text")],
    "spells":     [("环级", "环级", "text"), ("根源", "根源", "trad")],
    "creatures":  [("等级", "等级", "text"), ("体型", "体型", "size"), ("稀有度", "稀有度", "rarity")],
    "items":      [("等级", "等级", "text"), ("类别", "物品分类", "text"), ("稀有度", "稀有度", "rarity")],
    "archetypes": [("稀有度", "稀有度", "rarity")],
    "backgrounds": [("稀有度", "稀有度", "rarity")],
}


def _rarity_chip(v: str) -> str:
    v = (v or "").strip()
    if not v or v == "常见":
        return html_lib.escape(v)
    cls = "ui-chip-uncommon" if v == "罕见" else "ui-chip-rare"
    return f'<span class="ui-chip {cls}">{html_lib.escape(v)}</span>'


def _render_data_cell(val: str, kind: str) -> str:
    val = (val or "").strip()
    if kind == "rarity":
        return _rarity_chip(val)
    if kind == "size":
        return f'<span class="ui-chip ui-chip-size">{html_lib.escape(val)}</span>' if val else ""
    return html_lib.escape(val)

NS_TO_DIR = {0: "pages", 4: "project", 14: "category", 102: "pages", 3500: "data"}

SAFE_RX = re.compile(r'[*?"<>|]')


def safe_title(t: str) -> str:
    t = t.replace(":", "_").replace("/", "__").replace("\\", "_")
    return SAFE_RX.sub("", t)


def determine_dir_bare(ns: int, title: str) -> tuple[str, str]:
    target = NS_TO_DIR.get(ns, "pages")
    bare = title
    if ":" in title:
        prefix, rest = title.split(":", 1)
        if prefix in {"Category", "Data", "分类", "数据", "Project", "Help", "Template", "File"}:
            bare = rest
    return target, bare


def page_href(ns: int, title: str) -> str:
    d, bare = determine_dir_bare(ns, title)
    return f"{d}/{urllib.parse.quote(safe_title(bare))}.html"


def iter_parsed_with_cats():
    """Yield (ns, pageid, title, categories_list, displaytitle)."""
    for sub in PARSED_DIR.iterdir():
        if not sub.is_dir() or sub.name.startswith("_"):
            continue
        for f in sub.iterdir():
            if not f.name.endswith(".json"):
                continue
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            parse = doc.get("parse", {})
            cats = [
                c.get("category", "") for c in parse.get("categories", []) if isinstance(c, dict)
            ]
            yield (
                doc.get("ns", 0),
                doc.get("pageid"),
                doc.get("title", ""),
                cats,
                parse.get("displaytitle") or doc.get("title", ""),
            )


def render_browse_html(bucket: str, entries: list[dict], topnav: str, sidebar: str,
                        label: str | None = None, data_index: dict | None = None) -> str:
    label = label or BUCKET_LABELS.get(bucket, bucket)
    data_index = data_index or {}
    cols = BUCKET_COLUMNS.get(bucket, [])
    # Header cells: 名称 + each data column + 分类 (source). Without data cols,
    # fall back to the old 分类 column only (drop the useless "类型 = 条目").
    head_cells = ['<th>名称</th>'] + [f'<th>{html_lib.escape(h)}</th>' for h, _, _ in cols] + ['<th>分类</th>']
    thead = '<thead><tr>' + ''.join(head_cells) + '</tr></thead>'
    rows = []
    for e in entries:
        d = data_index.get(e["title"], {})
        cells = [f'<td><a href="{e["href"]}">{html_lib.escape(e["title"])}</a></td>']
        for _, key, kind in cols:
            cells.append(f'<td class="bc-{kind}">{_render_data_cell(d.get(key, ""), kind)}</td>')
        cells.append(f'<td class="cats">{html_lib.escape(", ".join(e.get("cats", [])[:2]))}</td>')
        rows.append('<tr>' + ''.join(cells) + '</tr>')
    table_body = "\n".join(rows)
    sub_label = f"{label} 共 {len(entries):,} 条"

    full_html = (
        '<!DOCTYPE html>\n'
        '<html lang="zh-Hans">\n'
        '<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<script>/* pre-paint theme to avoid FOUC */(function(){try{var t=localStorage.getItem(\'theme\');if(t===\'dark\'||(t!==\'light\'&&window.matchMedia&&matchMedia(\'(prefers-color-scheme:dark)\').matches))document.documentElement.classList.add(\'dark\');}catch(e){}})();</script>\n'
        f'<title>{html_lib.escape(label)} 浏览 — PF2 离线百科</title>\n'
        f'<meta name="description" content="PF2 中文百科 {html_lib.escape(label)} 浏览，共 {len(entries):,} 条。">\n'
        '<link rel="stylesheet" href="assets/style.css">\n'
        '<link rel="icon" href="assets/favicon.ico">\n'
        '<script defer src="assets/topnav.js"></script>\n'
        '<script defer src="assets/theme.js"></script>\n'
        '<script defer src="assets/wikitable_sort.js"></script>\n'
        '<script defer src="assets/external_links.js"></script>\n'
        '<script defer src="assets/updater_ui.js"></script>\n'
        '<script defer src="assets/mw_collapsible.js"></script>\n'
        '<script defer src="assets/bookmark.js"></script>\n'
        '<script defer src="assets/keybindings.js"></script>\n'
        '<script defer src="assets/wikitable_paginate.js"></script>\n'
        '<style>\n'
        '.browse-table { width: 100%; border-collapse: collapse; margin: 20px 0; background: var(--card); font-size: 13.5px; }\n'
        '.browse-table thead th { background: var(--accent-band); color: var(--accent-on); padding: 8px 12px; text-align: left; font-weight: 600; cursor: pointer; user-select: none; }\n'
        '.browse-table tbody td { padding: 6px 12px; border-bottom: 1px solid var(--border); }\n'
        '.browse-table tbody tr:nth-child(even) { background: var(--bg-alt); }\n'
        '.browse-table tbody tr:hover { background: rgba(255, 179, 0, 0.15); }\n'
        '.browse-table td.ns, .browse-table td.cats { color: var(--fg-mute); font-size: 12.5px; }\n'
        '.browse-controls { display: flex; gap: 16px; align-items: center; padding: 8px 0; }\n'
        '.browse-controls input { padding: 6px 10px; border: 1px solid var(--border); border-radius: 3px; font: inherit; min-width: 200px; }\n'
        '.browse-info { color: var(--fg-mute); font-size: 13px; }\n'
        '</style>\n'
        '</head>\n'
        f'<body class="mediawiki ltr sitedir-ltr action-view skin--responsive page-browse-{bucket}">\n'
        '<a class="skip-link" href="#main-content">跳到主要内容</a>\n'
        f'{topnav}\n'
        '<header class="page-head">\n'
        f'  <h1>{html_lib.escape(label)} 浏览</h1>\n'
        '</header>\n'
        '<nav class="breadcrumb" aria-label="导航">'
        '<a href="index.html">首页</a><span class="sep">›</span>'
        '<span>浏览</span><span class="sep">›</span>'
        f'<span class="current">{html_lib.escape(label)}</span>'
        '</nav>\n'
        '<div class="layout">\n'
        f'{sidebar}\n'
        '<main class="page-body" id="main-content">\n'
        '<div id="mw-content-text" class="mw-body-content mw-content-ltr">\n'
        '<div class="mw-parser-output">\n'
        f'<p class="browse-info">{html_lib.escape(sub_label)}。点表头排序；下方分页栏可搜索 / 翻页 / 调整每页条数。</p>\n'
        '<table class="browse-table wikitable" id="browse-tbl">\n'
        f'{thead}\n'
        f'<tbody>\n{table_body}\n</tbody>\n'
        '</table>\n'
        '</div>\n'
        '</div>\n'
        '</main>\n'
        '</div>\n'
        '<footer class="page-foot">\n'
        '  <small>本页内容来自 <a href="https://pf2.huijiwiki.com" rel="external">pf2.huijiwiki.com</a>，采用 CC BY-SA 4.0。</small>\n'
        '</footer>\n'
        '</body>\n</html>\n'
    )
    return full_html


def render_browse_all_hub(bucket_entries: dict, letters: list, topnav: str, sidebar: str) -> str:
    """browse-all as a lightweight hub: type cards (with counts) + letter strip."""
    order = ["feats", "spells", "items", "creatures", "ancestries", "backgrounds",
             "archetypes", "deities", "locations", "other", "categories"]
    cards = []
    for b in order:
        if b not in bucket_entries:
            continue
        cards.append(
            f'<a class="ba-card ba-{b}" href="browse-{b}.html">'
            f'<span class="ba-card-label">{html_lib.escape(BUCKET_LABELS.get(b, b))}</span>'
            f'<span class="ba-card-count">{len(bucket_entries[b]):,}</span></a>'
        )
    letter_links = "".join(
        f'<a href="browse-{x}.html">{html_lib.escape("#" if x == "_" else x)}</a>' for x in letters
    )
    body = (
        '<p class="browse-info">按类型或首字母浏览全部条目。</p>'
        '<h2 class="ui-section-h">按类型</h2>'
        '<div class="ba-grid">' + "".join(cards) + '</div>'
        '<h2 class="ui-section-h">按首字母</h2>'
        '<div class="ba-letters">' + letter_links + '</div>'
    )
    style = (
        '<style>'
        '.ba-grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));margin:14px 0}'
        '.ba-card{display:flex;justify-content:space-between;align-items:center;padding:14px 16px;'
        'background:var(--card);border:1px solid var(--border);border-left:3px solid var(--accent-500);'
        'border-radius:var(--r-md);box-shadow:var(--e-1);text-decoration:none;color:var(--fg);'
        'font-size:var(--fs-lg);font-weight:var(--fw-medium);transition:transform .12s,box-shadow .15s,border-color .12s,background .12s}'
        '.ba-card:hover{transform:translateY(-2px);box-shadow:var(--e-2);border-left-color:var(--accent);'
        'background:var(--surface-accent);color:var(--accent);text-decoration:none}'
        '.ba-card-count{font-variant-numeric:tabular-nums;color:var(--fg-mute);font-size:var(--fs-sm)}'
        '.ba-card:hover .ba-card-count{color:var(--accent)}'
        '.ba-letters{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}'
        '.ba-letters a{display:inline-block;min-width:34px;text-align:center;padding:7px 10px;'
        'background:var(--card);border:1px solid var(--border);border-radius:var(--r-sm);'
        'color:var(--link);text-decoration:none;font-weight:var(--fw-medium)}'
        '.ba-letters a:hover{background:var(--surface-accent);border-color:var(--accent);color:var(--accent)}'
        '</style>'
    )
    return (
        '<!DOCTYPE html>\n<html lang="zh-Hans">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<script>/* pre-paint theme */(function(){try{var t=localStorage.getItem(\'theme\');if(t===\'dark\'||(t!==\'light\'&&window.matchMedia&&matchMedia(\'(prefers-color-scheme:dark)\').matches))document.documentElement.classList.add(\'dark\');}catch(e){}})();</script>\n'
        '<title>全部条目 — PF2 离线百科</title>\n'
        '<link rel="stylesheet" href="assets/style.css">\n<link rel="icon" href="assets/favicon.ico">\n'
        '<script defer src="assets/topnav.js"></script>\n<script defer src="assets/theme.js"></script>\n'
        '<script defer src="assets/external_links.js"></script>\n<script defer src="assets/updater_ui.js"></script>\n'
        '<script defer src="assets/mw_collapsible.js"></script>\n<script defer src="assets/bookmark.js"></script>\n'
        '<script defer src="assets/keybindings.js"></script>\n' + style + '\n</head>\n'
        '<body class="mediawiki ltr sitedir-ltr action-view skin--responsive page-browse-all">\n'
        '<a class="skip-link" href="#main-content">跳到主要内容</a>\n'
        f'{topnav}\n<header class="page-head"><h1>全部条目</h1></header>\n'
        '<nav class="breadcrumb" aria-label="导航"><a href="index.html">首页</a>'
        '<span class="sep">›</span><span class="current">全部条目</span></nav>\n'
        f'<div class="layout">\n{sidebar}\n<main class="page-body" id="main-content">\n'
        '<div id="mw-content-text" class="mw-body-content mw-content-ltr"><div class="mw-parser-output">\n'
        f'{body}\n</div></div>\n</main>\n</div>\n'
        '<footer class="page-foot"><small>本页内容来自 <a href="https://pf2.huijiwiki.com" rel="external">pf2.huijiwiki.com</a>，采用 CC BY-SA 4.0。</small></footer>\n'
        '</body>\n</html>\n'
    )


def main() -> int:
    if not META_FILE.exists():
        print(f"ERROR: {META_FILE} missing")
        return 1
    json.loads(META_FILE.read_text(encoding="utf-8"))  # validate present

    topnav_sub = SNIPPET_TOPNAV_SUB.read_text(encoding="utf-8")
    # NOTE: rewrite BOTH href="../ and action="../ — the topnav search <form
    # action="../search.html"> would otherwise 404 from a root-level browse page.
    topnav_root = topnav_sub.replace('href="../', 'href="').replace('action="../', 'action="')
    sidebar_sub = SNIPPET_SIDEBAR_SUB.read_text(encoding="utf-8")
    sidebar_root = sidebar_sub.replace('href="../', 'href="').replace('action="../', 'action="')

    print("[1/3] scanning parsed corpus + building category index (ns=0) ...")
    t0 = time.time()
    cat_to_entries: dict[str, list[dict]] = defaultdict(list)
    cat_seen: dict[str, set] = defaultdict(set)   # dedup per category by title
    all_entries: list[dict] = []
    ns14_entries: list[dict] = []
    for ns, pid, title, cats, display in iter_parsed_with_cats():
        if ns not in (0, 102, 14, 3500):
            continue
        href = page_href(ns, title)
        ns_label = {0: "条目", 14: "分类", 102: "资源", 3500: "数据"}.get(ns, "")
        bare = title
        for prefix in ("Category:", "分类:", "Data:", "数据:"):
            if bare.startswith(prefix):
                bare = bare[len(prefix):]
        entry = {
            "pageid": pid, "ns": ns, "ns_label": ns_label,
            "title": bare, "href": href, "cats": cats,
        }
        all_entries.append(entry)
        if ns == 14:
            ns14_entries.append(entry)
            continue
        if ns == 0:
            for c in cats:
                cc = c.replace("_", " ")
                if title not in cat_seen[cc]:
                    cat_seen[cc].add(title)
                    cat_to_entries[cc].append(entry)
    print(f"  indexed {len(cat_to_entries)} ns0 categories in {time.time()-t0:.1f}s")

    # ns=3500 Data join for meaningful browse columns (等级/环级/根源/体型/稀有度…)
    data_index = build_data_index()
    print(f"  built data index: {len(data_index)} entries")

    # Assemble buckets from BUCKET_CATS (union of mapped categories, deduped by title)
    bucket_entries: dict[str, list[dict]] = {}
    for bucket, catlist in BUCKET_CATS.items():
        seen: set = set()
        members: list[dict] = []
        for c in catlist:
            for e in cat_to_entries.get(c, []):
                if e["title"] not in seen:
                    seen.add(e["title"])
                    members.append(e)
        bucket_entries[bucket] = members
    # categories bucket: list EVERY category that has a generated page (build_v2
    # generates a member-list page for all referenced categories ~3646, not just
    # the 354 scraped ns=14 docs). cat_to_entries keys = categories with >=1 ns0
    # member, which is what build_v2 [4b] renders. Union with scraped ns14 titles.
    cat_names = set(cat_to_entries.keys())
    for e in ns14_entries:
        cat_names.add(e["title"])
    cat_entries = []
    for cat in cat_names:
        n = len(cat_to_entries.get(cat, []))
        cat_entries.append({
            "pageid": 0, "ns": 14, "ns_label": "分类", "title": cat,
            "href": page_href(14, f"Category:{cat}"),
            "cats": [f"{n} 个页面"] if n else [],
        })
    bucket_entries["categories"] = cat_entries

    print("[2/3] writing browse-*.html files ...")
    written = 0
    for bucket, entries in bucket_entries.items():
        entries.sort(key=lambda e: e["title"].lower())
        html = render_browse_html(bucket, entries, topnav_root, sidebar_root, data_index=data_index)
        (ROOT / f"browse-{bucket}.html").write_text(html, encoding="utf-8")
        print(f"  browse-{bucket}.html: {len(entries):,} entries")
        written += 1

    # browse-all is now a HUB (was a 25k-row / 5.3 MB single table that janked
    # WebView2). Link the type buckets (with counts) + the by-letter pages that
    # actually exist (computed from the corpus, same letters build_browse_letters
    # emits) instead of dumping every row into one DOM.
    all_content = [e for e in all_entries if e["ns"] != 3500]
    def first_letter(t):
        c = (t or " ")[0]
        if "a" <= c.lower() <= "z":
            return c.upper()
        cp = ord(c)
        if (0x3400 <= cp <= 0x4DBF) or (0x4E00 <= cp <= 0x9FFF) or (0xF900 <= cp <= 0xFAFF):
            return "CJK"
        return "_"
    letters = sorted({first_letter(e["title"]) for e in all_content},
                     key=lambda b: (0, ord(b)) if len(b) == 1 and "A" <= b <= "Z" else (2, 0) if b == "_" else (1, ord(b[0])))
    (ROOT / "browse-all.html").write_text(
        render_browse_all_hub(bucket_entries, letters, topnav_root, sidebar_root), encoding="utf-8")
    print(f"  browse-all.html: HUB ({len(bucket_entries)} type cards + {len(letters)} letters; was {len(all_content):,}-row table)")
    written += 1

    print(f"[3/3] done — {written} browse pages written in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
