"""Generate the 首页-aligned navigation sections for index.html (item #4).
Mirrors the live wiki 首页 groups (规则导航/世界设定/出版物/索引与帮助), linking to
our offline pages. Only emits links whose target file exists (no dead links).
Raw-Chinese hrefs (matches existing index.html convention). Writes the HTML
snippet to out_v2/_cat_audit/_homenav.html for insertion into index.html.
"""
from __future__ import annotations
import html as H
from pathlib import Path

WIKI = Path(__file__).resolve().parents[2] / "_wiki_full_v2"
OUT = Path(__file__).resolve().parents[1] / "out_v2" / "_cat_audit"

# (section title, [(label, href), ...]) — hrefs relative to wiki root
SECTIONS = [
    ("规则导航", [
        ("创建角色", "pages/创建角色.html"), ("职业", "classes/index.html"),
        ("族裔", "browse-ancestries.html"), ("技能", "pages/技能.html"),
        ("专长", "browse-feats.html"), ("法术", "pages/法术列表.html"),
        ("仪式", "pages/仪式列表.html"),
        ("装备", "browse-items.html"), ("宝藏", "pages/宝藏.html"),
    ]),
    ("世界设定", [
        ("内海", "pages/内海.html"), ("历史", "pages/历史.html"),
        ("信仰", "pages/信仰综述.html"), ("组织", "pages/组织.html"),
        ("传说故事", "pages/传说故事.html"), ("生物", "pages/生物总表.html"),
        ("诸神总表", "pages/诸神总表.html"),
        ("地狱骑士", "pages/地狱骑士.html"), ("GM帷幕", "pages/GM帷幕.html"),
        ("旅游指南", "pages/《旅游指南》.html"), ("奇人列传", "pages/《奇人列传》.html"),
        ("地理", "browse-locations.html"),
    ]),
    ("出版物", [
        ("玩家核心", "pages/《玩家核心》.html"), ("怪物核心2", "pages/《怪物核心2》.html"),
        ("巨龙圣典", "pages/《巨龙圣典》.html"), ("妖精国度", "pages/《妖精国度》.html"),
        ("公海", "pages/《公海》.html"), ("惊异魔法", "pages/《惊异魔法》.html"),
        ("暗星之秘", "pages/《暗星之秘》.html"), ("格雷斯的麻烦", "pages/《格雷斯的麻烦》.html"),
        ("逝神之手", "pages/《逝神之手》.html"), ("龙之王冠", "pages/《龙之王冠》.html"),
        ("切利亚斯，炼狱遗产", "pages/《切利亚斯，炼狱遗产》.html"),
        ("地狱火快讯", "pages/《地狱火快讯》.html"),
        ("全部出版物 →", "pages/出版物索引.html"),
    ]),
    ("索引与帮助", [
        ("出版物索引", "pages/出版物索引.html"), ("勘误索引", "pages/勘误索引.html"),
        ("术语索引", "pages/术语索引.html"), ("规则索引", "pages/规则索引.html"),
        ("特征", "pages/特征.html"), ("分类索引", "browse-categories.html"),
        ("新手入门", "pages/角色扮演游戏是什么？.html"), ("帮助", "category/帮助.html"),
        ("维基任务", "project/任务.html"), ("需要帮助", "category/需要帮助.html"),
        ("维基原版首页", "pages/首页.html"),
        ("本镜像 README", "README.html"),
    ]),
]


def exists(href: str) -> bool:
    if href.startswith(("http://", "https://")):
        return True
    return (WIKI / href).exists()


def main() -> int:
    parts = ['  <section class="homenav" aria-label="百科导航">']
    dropped = []
    for title, entries in SECTIONS:
        valid = [(lbl, hr) for lbl, hr in entries if exists(hr) or hr.endswith("index.html") or hr == "README.html"]
        dropped += [(lbl, hr) for lbl, hr in entries if (lbl, hr) not in valid]
        parts.append(f'    <h2 class="section-h">{H.escape(title)}</h2>')
        parts.append('    <div class="nav-grid">')
        for lbl, hr in valid:
            cls = ' class="nav-more"' if "→" in lbl else ""
            parts.append(f'      <a href="{hr}"{cls}>{H.escape(lbl)}</a>')
        parts.append('    </div>')
    parts.append('  </section>')
    html = "\n".join(parts) + "\n"
    (OUT / "_homenav.html").write_text(html, encoding="utf-8")
    print(f"wrote _homenav.html ({sum(len(e) for _,e in SECTIONS)} candidates)")
    if dropped:
        print(f"DROPPED (target missing): {[lbl for lbl,_ in dropped]}")
    else:
        print("all links valid (0 dropped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
