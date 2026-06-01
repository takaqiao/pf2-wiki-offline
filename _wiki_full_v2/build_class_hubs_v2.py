"""Build classes/index.html (25 真职业 hub) + source/index.html (出版物索引).

Both reuse the parsed corpus + native CSS. Standalone — runs after build_v2.py.

Run:
    .venv\\Scripts\\python.exe build_class_hubs_v2.py
"""

from __future__ import annotations

import html as html_lib
import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRAPER_OUT = ROOT.parent / "pf2wiki-scraper" / "out_v2"
PARSED_DIR = SCRAPER_OUT / "parsed"
META_FILE = SCRAPER_OUT / "metadata.json"
SNIPPET_SUB = ROOT / "_snippets" / "topnav_sub.html"

CACHE_VER = "v2h"

# 27 PF2 真职业 — from the live 职业 page roster (canonical wiki titles, English
# verified against each page's intro, 2026-05-21). All present in the offline corpus.
# Mapping: 中文 wiki title -> English label (for tooltip / future i18n).
# Naming caught up with the wiki: Swashbuckler 斗士->浪客, Kineticist 元素使->御能师,
# Inventor 发明家->发明家（职业）, Psychic 灵媒->心能者 (灵媒 is now Animist!);
# new classes Guardian/Commander/Exemplar; dropped 圣武士 (a 神卫 cause, not a class).
KNOWN_CLASSES = {
    "野蛮人": "Barbarian",
    "吟游诗人": "Bard",
    "神卫": "Champion",
    "牧师": "Cleric",
    "德鲁伊": "Druid",
    "战士": "Fighter",
    "武僧": "Monk",
    "游侠": "Ranger",
    "游荡者": "Rogue",
    "术士": "Sorcerer",
    "法师": "Wizard",
    "炼金术士": "Alchemist",
    "调查员": "Investigator",
    "枪手": "Gunslinger",
    "魔战士": "Magus",
    "先知": "Oracle",
    "女巫": "Witch",
    "御能师": "Kineticist",
    "奇术师": "Thaumaturge",
    "心能者": "Psychic",
    "召唤师": "Summoner",
    "发明家（职业）": "Inventor",
    "浪客": "Swashbuckler",
    "灵媒": "Animist",
    "神源者": "Exemplar",
    "守护者": "Guardian",
    "统帅": "Commander",
}

SAFE_RX = re.compile(r'[*?"<>|]')


def safe_title(t: str) -> str:
    t = t.replace(":", "_").replace("/", "__").replace("\\", "_")
    return SAFE_RX.sub("", t)


def iter_parsed():
    for sub in PARSED_DIR.iterdir():
        if not sub.is_dir() or sub.name.startswith("_"):
            continue
        for f in sub.iterdir():
            if not f.name.endswith(".json"):
                continue
            try:
                yield json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue


def page_html(title: str, body: str, bucket_breadcrumb: str = "") -> str:
    topnav = SNIPPET_SUB.read_text(encoding="utf-8")
    bc_inner = bucket_breadcrumb or f'<span class="current">{html_lib.escape(title)}</span>'
    return (
        '<!DOCTYPE html>\n<html lang="zh-Hans">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{html_lib.escape(title)} — PF2 离线百科</title>\n'
        '<link rel="stylesheet" href="../assets/style.css">\n'
        '<link rel="icon" href="../assets/favicon.ico">\n'
        '<script defer src="../assets/topnav.js"></script>\n'
        '<script defer src="../assets/theme.js"></script>\n'
        '<script defer src="../assets/external_links.js"></script>\n'
        '<script defer src="../assets/mw_collapsible.js"></script>\n'
        '<script defer src="../assets/updater_ui.js"></script>\n'
        '<script defer src="../assets/bookmark.js"></script>\n'
        '</head>\n<body class="mediawiki ltr sitedir-ltr action-view skin--responsive">\n'
        '<a class="skip-link" href="#main-content">跳到主要内容</a>\n'
        f'{topnav}\n'
        f'<header class="page-head"><h1>{html_lib.escape(title)}</h1></header>\n'
        '<nav class="breadcrumb" aria-label="导航">'
        '<a href="../index.html">首页</a><span class="sep">›</span>'
        f'{bc_inner}'
        '</nav>\n'
        '<div class="layout">\n'
        '<nav class="wiki-sidebar" aria-label="百科导航"><!-- v2 sidebar placeholder --></nav>\n'
        '<main class="page-body" id="main-content">\n'
        '<div id="mw-content-text" class="mw-body-content mw-content-ltr">\n'
        '<div class="mw-parser-output">\n'
        f'{body}\n'
        '</div>\n</div>\n</main>\n</div>\n'
        '<footer class="page-foot"><small>'
        '本页内容来自 <a href="https://pf2.huijiwiki.com" rel="external">pf2.huijiwiki.com</a>，采用 CC BY-SA 4.0。'
        '</small></footer>\n</body>\n</html>\n'
    )


def build_classes_hub():
    """Build classes/index.html — strict allowlist of 25 真职业.

    Only includes pages whose title is in KNOWN_CLASSES dict. Falls back to
    placeholder row for titles not yet scraped.
    """
    print(f"[classes] scanning for known classes (strict {len(KNOWN_CLASSES)} allowlist) ...")
    found: dict[str, dict] = {}
    for doc in iter_parsed():
        title = doc.get("title", "")
        if title not in KNOWN_CLASSES:
            continue
        parse = doc.get("parse", {})
        text = parse.get("text") or ""
        # Strip ALL HTML before slicing — avoid partial-tag fragments
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"&[a-zA-Z]+;", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        excerpt = clean[:80]
        cats = [c.get("category", "") for c in parse.get("categories", []) if isinstance(c, dict)]
        found[title] = {
            "title": title,
            "en": KNOWN_CLASSES[title],
            "href": f"../pages/{urllib.parse.quote(safe_title(title))}.html",
            "excerpt": excerpt,
            "cats": cats[:5],
        }
    print(f"  found {len(found)} of {len(KNOWN_CLASSES)} known classes in corpus")
    # Sort by KNOWN_CLASSES dict order (canonical PF2r order)
    sorted_titles = [t for t in KNOWN_CLASSES.keys()]
    rows = []
    for name in sorted_titles:
        e = found.get(name)
        if e:
            rows.append(
                '<tr>'
                f'<td><a href="{e["href"]}"><strong>{html_lib.escape(e["title"])}</strong></a>'
                f' <small style="color:var(--fg-mute)">{html_lib.escape(e["en"])}</small></td>'
                f'<td class="cats" style="color:var(--fg-mute);font-size:12.5px">{html_lib.escape(e["excerpt"])}…</td>'
                '</tr>'
            )
        else:
            en = KNOWN_CLASSES[name]
            rows.append(
                f'<tr><td><span style="color:var(--fg-mute)">{html_lib.escape(name)}</span>'
                f' <small style="color:var(--fg-mute)">{html_lib.escape(en)}</small></td>'
                f'<td><em style="color:var(--fg-mute)">尚未抓取</em></td></tr>'
            )
    body = (
        f'<p>共 {len(found)} 真职业（PF2r 2024 玩家核心 + Player Core 2 + 出版物补充）。</p>'
        '<table class="aon-table" style="width:100%;border-collapse:collapse;font-size:14px;margin:16px 0">'
        '<thead><tr><th style="background:var(--accent-band);color:var(--accent-on);padding:8px 12px;text-align:left">职业</th>'
        '<th style="background:var(--accent-band);color:var(--accent-on);padding:8px 12px;text-align:left">简介</th></tr></thead>'
        '<tbody>' + "\n".join(rows) + '</tbody></table>'
        '<style>.aon-table tbody td{padding:8px 12px;border-bottom:1px solid var(--border)}'
        '.aon-table tbody tr:nth-child(even){background:var(--bg-alt)}'
        '.aon-table tbody tr:hover{background:rgba(255,179,0,0.15)}</style>'
    )
    bc = '<span>玩家选项</span><span class="sep">›</span><span class="current">职业</span>'
    html = page_html("职业 — 27 真职业 hub", body, bc)
    out = ROOT / "classes" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"  wrote classes/index.html ({len(found)} class links)")


def build_source_index():
    """Build source/index.html — group pages by their |source= field if available.

    Heuristic: scan parse.text for known PF2 publication name patterns.
    For first iteration, just list known PF2 books with placeholder counts.
    """
    print("[source] building source/index.html (publication index) ...")
    # Known PF2 publications (translated names from huiji wiki)
    known_pubs = [
        ("玩家核心 (PF2r)", "Player Core"),
        ("玩家核心 2 (PF2r)", "Player Core 2"),
        ("GM核心 (PF2r)", "GM Core"),
        ("怪物核心 (PF2r)", "Monster Core"),
        ("玩家手册 (PF2e)", "Core Rulebook"),
        ("怪物图鉴 (PF2e)", "Bestiary"),
        ("怪物图鉴2 (PF2e)", "Bestiary 2"),
        ("怪物图鉴3 (PF2e)", "Bestiary 3"),
        ("高级玩家指南", "Advanced Player's Guide"),
        ("黑暗潮汐", "Dark Tides"),
        ("流浪猫救援团", "Stray Cats"),
        ("莽林卫士", "Outlaws"),
        ("失落天体", "Lost Omens"),
        ("国王缔造者", "Kingmaker"),
    ]
    rows = []
    for cn, en in known_pubs:
        rows.append(
            '<tr>'
            f'<td><strong>{html_lib.escape(cn)}</strong><br><small style="color:var(--fg-mute)">{html_lib.escape(en)}</small></td>'
            f'<td><a href="../search.html?q={urllib.parse.quote(cn)}">搜索</a></td>'
            '</tr>'
        )
    body = (
        '<p>下面是已知的 PF2 出版物列表。点击「搜索」会跳到搜索页并按出版物名查询(search.html 读取 ?q=)。</p>'
        '<table class="aon-table" style="width:100%;border-collapse:collapse;font-size:14px;margin:16px 0">'
        '<thead><tr><th style="background:var(--accent-band);color:var(--accent-on);padding:8px 12px;text-align:left">出版物</th>'
        '<th style="background:var(--accent-band);color:var(--accent-on);padding:8px 12px;text-align:left">索引</th></tr></thead>'
        '<tbody>' + "\n".join(rows) + '</tbody></table>'
        '<p><em>注：完整出版物索引需要后续从 parse.text 提取每页的 |source= 字段统计；首版仅列已知出版物名。</em></p>'
    )
    bc = '<span>规则</span><span class="sep">›</span><span class="current">出版物</span>'
    html = page_html("出版物 — 索引", body, bc)
    out = ROOT / "source" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"  wrote source/index.html ({len(known_pubs)} known publications)")


def main() -> int:
    if not META_FILE.exists():
        print(f"ERROR: {META_FILE} missing")
        return 1
    build_classes_hub()
    build_source_index()
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
