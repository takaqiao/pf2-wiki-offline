"""Build A-Z + CJK letter browse pages.

Iterates metadata.pages, groups by first character (uppercased ASCII letter, or
"CJK" for CJK chars, or "_" for other), emits browse-<bucket>.html.

Run:
    .venv\\Scripts\\python.exe build_browse_letters_v2.py
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
META_FILE = ROOT.parent / "pf2wiki-scraper" / "out_v2" / "metadata.json"
SNIPPET_TOPNAV_SUB = ROOT / "_snippets" / "topnav_sub.html"
SNIPPET_SIDEBAR_SUB = ROOT / "_snippets" / "sidebar_sub.html"
CACHE_VER = "v2f"

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


def first_char_bucket(t: str) -> str:
    """Letter bucket for a title:
    - 'A' to 'Z' for ASCII letter starts
    - 'CJK' for CJK starts
    - '_' for digit/symbol starts
    """
    if not t:
        return "_"
    c = t[0]
    if "a" <= c.lower() <= "z":
        return c.upper()
    # CJK range check
    cp = ord(c)
    if (0x3400 <= cp <= 0x4DBF) or (0x4E00 <= cp <= 0x9FFF) or (0xF900 <= cp <= 0xFAFF):
        return "CJK"
    return "_"


def render_letter_page(letter: str, entries: list[dict], topnav: str, sidebar: str) -> str:
    rows = []
    for e in entries:
        rows.append(
            '<tr>'
            f'<td><a href="{e["href"]}">{html_lib.escape(e["title"])}</a></td>'
            f'<td class="ns">{html_lib.escape(e["ns_label"])}</td>'
            '</tr>'
        )
    table_body = "\n".join(rows)
    label = f"以 {letter} 起始" if letter != "CJK" else "中文条目"
    full_html = (
        '<!DOCTYPE html>\n<html lang="zh-Hans">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{html_lib.escape(label)} — PF2 离线百科</title>\n'
        f'<link rel="stylesheet" href="assets/style.css?v={CACHE_VER}">\n'
        f'<link rel="icon" href="assets/favicon.ico">\n'
        f'<script defer src="assets/topnav.js?v={CACHE_VER}"></script>\n'
        f'<script defer src="assets/theme.js?v={CACHE_VER}"></script>\n'
        f'<script defer src="assets/external_links.js?v={CACHE_VER}"></script>\n'
        f'<script defer src="assets/updater_ui.js?v={CACHE_VER}"></script>\n'
        f'<script defer src="assets/mw_collapsible.js?v={CACHE_VER}"></script>\n'
        '<style>\n'
        '.letter-nav { display: flex; flex-wrap: wrap; gap: 4px; margin: 16px 0; padding: 10px 12px; background: var(--bg-alt); border-radius: 4px; }\n'
        '.letter-nav a { padding: 4px 10px; background: var(--bg); border: 1px solid var(--border); border-radius: 3px; color: var(--link); font-weight: 600; min-width: 24px; text-align: center; }\n'
        '.letter-nav a.current { background: var(--accent); color: var(--accent-on); border-color: var(--accent); }\n'
        '.letter-nav a:hover { background: var(--accent); color: var(--accent-on); border-color: var(--accent); }\n'
        '.browse-table { width: 100%; border-collapse: collapse; font-size: 13.5px; }\n'
        '.browse-table th { background: var(--accent-band); color: var(--accent-on); padding: 8px 12px; text-align: left; }\n'
        '.browse-table td { padding: 6px 12px; border-bottom: 1px solid var(--border); }\n'
        '.browse-table tr:nth-child(even) { background: var(--bg-alt); }\n'
        '.browse-table tr:hover { background: rgba(255,179,0,0.15); }\n'
        '.browse-table td.ns { color: var(--fg-mute); font-size: 12px; }\n'
        '</style>\n</head>\n'
        f'<body class="mediawiki ltr sitedir-ltr action-view skin--responsive page-browse-{letter}">\n'
        '<a class="skip-link" href="#main-content">跳到主要内容</a>\n'
        f'{topnav}\n'
        '<header class="page-head">\n'
        f'  <h1>{html_lib.escape(label)}</h1>\n'
        '</header>\n'
        '<nav class="breadcrumb" aria-label="导航">'
        '<a href="index.html">首页</a><span class="sep">›</span>'
        '<a href="browse-all.html">浏览</a><span class="sep">›</span>'
        f'<span class="current">{html_lib.escape(letter)}</span>'
        '</nav>\n'
        '<div class="layout">\n'
        f'{sidebar}\n'
        '<main class="page-body" id="main-content">\n'
        '<div id="mw-content-text" class="mw-body-content mw-content-ltr">\n'
        '<div class="mw-parser-output">\n'
        '<nav class="letter-nav" aria-label="按字母浏览">\n'
        '  ' + " ".join(f'<a href="browse-{x}.html"{" class=\"current\"" if x == letter else ""}>{x}</a>'
                        for x in (list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["CJK", "_"])) + '\n'
        '</nav>\n'
        f'<p style="color:var(--fg-mute);margin:8px 0 16px">共 {len(entries):,} 条以 <strong>{html_lib.escape(letter)}</strong> 起始的条目。</p>\n'
        '<table class="browse-table">\n'
        '<thead><tr><th>名称</th><th>类型</th></tr></thead>\n'
        f'<tbody>\n{table_body}\n</tbody>\n'
        '</table>\n'
        '</div>\n</div>\n</main>\n</div>\n'
        '<footer class="page-foot"><small>本页内容来自 <a href="https://pf2.huijiwiki.com" rel="external">pf2.huijiwiki.com</a>，CC BY-SA 4.0。</small></footer>\n'
        '</body>\n</html>\n'
    )
    return full_html


def main() -> int:
    if not META_FILE.exists():
        print(f"ERROR: {META_FILE} missing")
        return 1
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    pages = meta.get("pages", [])
    topnav_sub = SNIPPET_TOPNAV_SUB.read_text(encoding="utf-8")
    topnav_root = topnav_sub.replace('href="../', 'href="')
    sidebar_sub = SNIPPET_SIDEBAR_SUB.read_text(encoding="utf-8") if SNIPPET_SIDEBAR_SUB.exists() else ""
    sidebar_root = sidebar_sub.replace('href="../', 'href="').replace('action="../', 'action="')

    print(f"[1/3] grouping {len(pages)} pages by first char ...")
    buckets: dict[str, list[dict]] = defaultdict(list)
    skip_prefixes = ("Category:", "分类:", "File:", "Template:", "Help:", "MediaWiki:", "User:")
    for p in pages:
        title = p.get("title", "")
        if any(title.startswith(s) for s in skip_prefixes):
            continue
        ns = p.get("ns", 0)
        if ns not in (0, 102, 14, 3500):
            continue
        target_dir, bare = determine_dir_bare(ns, title)
        bucket = first_char_bucket(bare)
        ns_label = {0: "条目", 14: "分类", 102: "资源", 3500: "数据"}.get(ns, "")
        buckets[bucket].append({
            "title": bare,
            "href": f"{target_dir}/{urllib.parse.quote(safe_title(bare))}.html",
            "ns_label": ns_label,
        })
    print(f"  buckets: {sorted(buckets.keys())}")

    print(f"[2/3] writing browse-X.html (A-Z + CJK + _) ...")
    t0 = time.time()
    for letter in list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["CJK", "_"]:
        entries = sorted(buckets.get(letter, []), key=lambda e: e["title"].lower())
        if not entries:
            print(f"  browse-{letter}.html: SKIP (0 entries)")
            continue
        html = render_letter_page(letter, entries, topnav_root, sidebar_root)
        (ROOT / f"browse-{letter}.html").write_text(html, encoding="utf-8")
        print(f"  browse-{letter}.html: {len(entries):,} entries")
    print(f"\n[3/3] done in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
