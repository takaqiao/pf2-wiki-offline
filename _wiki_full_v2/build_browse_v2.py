"""Phase F.5: build browse-*.html landing pages.

Classifies pages by their categories (from parsed JSON) into well-known browse
buckets, then emits sorted tables to _wiki_full_v2/browse-<bucket>.html.

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

CACHE_VER = "v2f"

# Browse bucket definitions: bucket_name -> set of category keywords (any match)
BUCKETS = {
    "feats":        ["专长", "feat"],
    "spells":       ["法术", "spell", "戏法", "聚能"],
    "items":        ["物品", "装备", "武器", "护甲", "消耗品", "戴持物品", "符文", "法器", "item"],
    "creatures":    ["怪物", "creature", "monster"],
    "ancestries":   ["祖先", "ancestry"],
    "backgrounds":  ["背景", "background"],
    "archetypes":   ["变体", "archetype"],
    "classes":      ["职业", "class"],
    "deities":      ["神祇", "deity"],
    "locations":    ["地点", "location", "城市", "国家", "区域"],
    "other":        ["状态", "特征", "trait", "condition"],
}

BUCKET_LABELS = {
    "feats": "专长", "spells": "法术", "items": "物品", "creatures": "怪物",
    "ancestries": "祖先", "backgrounds": "背景", "archetypes": "变体",
    "classes": "职业", "deities": "神祇", "locations": "地点", "other": "状态/特征",
    "categories": "分类页面", "all": "全部条目",
}

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


def classify(cats: list[str], title: str) -> set[str]:
    """Return all buckets a page falls into (a page can be in multiple)."""
    cat_blob = (" ".join(cats) + " " + title).lower()
    out: set[str] = set()
    for bucket, keys in BUCKETS.items():
        for k in keys:
            if k.lower() in cat_blob:
                out.add(bucket)
                break
    return out


def render_browse_html(bucket: str, entries: list[dict], topnav: str, sidebar: str) -> str:
    label = BUCKET_LABELS.get(bucket, bucket)
    rows = []
    for e in entries:
        row = (
            '<tr>'
            f'<td><a href="{e["href"]}">{html_lib.escape(e["title"])}</a></td>'
            f'<td class="ns">{html_lib.escape(e.get("ns_label",""))}</td>'
            f'<td class="cats">{html_lib.escape(", ".join(e.get("cats", [])[:3]))}</td>'
            '</tr>'
        )
        rows.append(row)
    table_body = "\n".join(rows)
    sub_label = f"{label} 共 {len(entries):,} 条"

    full_html = (
        '<!DOCTYPE html>\n'
        '<html lang="zh-Hans">\n'
        '<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{html_lib.escape(label)} 浏览 — PF2 离线百科</title>\n'
        f'<meta name="description" content="PF2 中文百科 {html_lib.escape(label)} 浏览，共 {len(entries):,} 条。">\n'
        f'<link rel="stylesheet" href="assets/style.css?v={CACHE_VER}">\n'
        f'<link rel="icon" href="assets/favicon.ico">\n'
        f'<script defer src="assets/topnav.js?v={CACHE_VER}"></script>\n'
        f'<script defer src="assets/theme.js?v={CACHE_VER}"></script>\n'
        f'<script defer src="assets/aon_table.js?v={CACHE_VER}"></script>\n'
        f'<script defer src="assets/external_links.js?v={CACHE_VER}"></script>\n'
        f'<script defer src="assets/updater_ui.js?v={CACHE_VER}"></script>\n'
        f'<script defer src="assets/mw_collapsible.js?v={CACHE_VER}"></script>\n'
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
        f'<p class="browse-info">{html_lib.escape(sub_label)}。点表头排序，输入框筛选。</p>\n'
        '<div class="browse-controls">\n'
        '  <input type="search" id="browse-filter" placeholder="筛选名称…" oninput="filterBrowse(this.value)">\n'
        '  <span class="browse-info" id="browse-count"></span>\n'
        '</div>\n'
        '<table class="browse-table aon-table sortable" id="browse-tbl">\n'
        '<thead><tr><th>名称 ▾</th><th>类型</th><th>分类</th></tr></thead>\n'
        f'<tbody>\n{table_body}\n</tbody>\n'
        '</table>\n'
        '<script>\n'
        'function filterBrowse(q) {\n'
        '  q = q.trim().toLowerCase();\n'
        '  const tbl = document.getElementById("browse-tbl");\n'
        '  let shown = 0;\n'
        '  for (const tr of tbl.tBodies[0].rows) {\n'
        '    const txt = tr.cells[0].textContent.toLowerCase();\n'
        '    const ok = !q || txt.indexOf(q) !== -1;\n'
        '    tr.style.display = ok ? "" : "none";\n'
        '    if (ok) shown++;\n'
        '  }\n'
        '  document.getElementById("browse-count").textContent = q ? `匹配 ${shown} 条` : "";\n'
        '}\n'
        '</script>\n'
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


def main() -> int:
    if not META_FILE.exists():
        print(f"ERROR: {META_FILE} missing")
        return 1
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))

    # Determine topnav: browse-*.html lives at root, so use root-prefix topnav
    # We don't have topnav_root.html so we'll generate from topnav_sub.html by stripping "../"
    topnav_sub = SNIPPET_TOPNAV_SUB.read_text(encoding="utf-8")
    topnav_root = topnav_sub.replace('href="../', 'href="')
    sidebar_sub = SNIPPET_SIDEBAR_SUB.read_text(encoding="utf-8")
    sidebar_root = sidebar_sub.replace('href="../', 'href="').replace('action="../', 'action="')

    print("[1/3] scanning parsed corpus + classifying ...")
    t0 = time.time()
    bucket_entries: dict[str, list[dict]] = defaultdict(list)
    all_entries: list[dict] = []
    cat_pages_index: dict[str, set] = defaultdict(set)  # category title -> pageids
    seen = 0
    for ns, pid, title, cats, display in iter_parsed_with_cats():
        if ns not in (0, 102, 14, 3500):
            continue
        href = page_href(ns, title)
        ns_label = {0: "条目", 14: "分类", 102: "资源", 3500: "数据"}.get(ns, "")
        # Pretty-strip namespace prefix from display
        bare = title
        for prefix in ("Category:", "分类:", "Data:", "数据:"):
            if bare.startswith(prefix):
                bare = bare[len(prefix):]
        entry = {
            "pageid": pid, "ns": ns, "ns_label": ns_label,
            "title": bare, "href": href, "cats": cats,
        }
        all_entries.append(entry)
        for c in cats:
            cat_pages_index[c].add(pid)
        # categories namespace becomes its own bucket
        if ns == 14:
            bucket_entries["categories"].append(entry)
            continue
        # classify by category keywords
        buckets = classify(cats, title)
        if not buckets:
            continue
        for b in buckets:
            bucket_entries[b].append(entry)
        seen += 1
    print(f"  classified {seen} pages into {len(bucket_entries)} buckets in {time.time()-t0:.1f}s")

    # Sort each bucket alphabetically
    print("[2/3] writing browse-*.html files ...")
    written = 0
    for bucket, entries in bucket_entries.items():
        entries.sort(key=lambda e: e["title"].lower())
        html = render_browse_html(bucket, entries, topnav_root, sidebar_root)
        out_path = ROOT / f"browse-{bucket}.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"  browse-{bucket}.html: {len(entries):,} entries")
        written += 1

    # Also build browse-all alphabetical
    all_entries.sort(key=lambda e: e["title"].lower())
    html = render_browse_html("all", all_entries, topnav_root, sidebar_root)
    (ROOT / "browse-all.html").write_text(html, encoding="utf-8")
    print(f"  browse-all.html: {len(all_entries):,} entries")
    written += 1

    print(f"[3/3] done — {written} browse pages written in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
