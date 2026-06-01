"""Build the 17 sub-zone browse pages as REAL filtered content (v3).

Previously these were meta-refresh stubs that jumped to the UNFILTERED parent
(browse-items/spells/creatures.html) — so every spell tradition / item subtype /
creature level band landed on the same full list (cosmetic only). Now each
sub-zone is a real browse page whose members are derived from the ns=3500 Data:
pages (mw-jsonconfig tables), joined to ns=0 articles by their 中文 field:

  spells   -> 根源 (tradition: 奥术/神术/异能/原能) + 法术分类 (戏法 cantrip / 聚能 focus)
  creatures-> 等级 (level bands)
  items    -> 物品分类 (item category, curated groups)

Reuses render_browse_html / page_href from build_browse_v2.py. Run AFTER
build_browse_v2.py (same dir):
    .venv\\Scripts\\python.exe build_nav_stubs.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from build_browse_v2 import (
    PARSED_DIR, SNIPPET_TOPNAV_SUB, SNIPPET_SIDEBAR_SUB,
    render_browse_html, page_href,
)

ROOT = Path(__file__).resolve().parent

ROW_RX = re.compile(r"<th>(.*?)</th><td class=\"mw-jsonconfig-value\">(.*?)</td>", re.S)
TAG_RX = re.compile(r"<[^>]+>")


def clean(s: str) -> str:
    return TAG_RX.sub("", s).replace("&amp;", "&").strip()


def parse_table(text: str) -> dict:
    return {clean(a): clean(b) for a, b in ROW_RX.findall(text or "")}


def toks(v: str):
    return [x.strip() for x in re.split(r"[,，、/]", v or "") if x.strip()]


def to_int(v: str):
    try:
        return int(str(v).strip())
    except Exception:
        return None


# --- sub-zone specs: slug -> (label, predicate(rec)->bool, display_field) ---
# rec carries: _type (Spells/Creatures/Items), plus parsed table fields.
# Mapped from the 83 distinct 物品分类 values in the corpus. Broadened so the six
# equipment subzones cover the recognizable item types (shields->armor,
# wands/staves/grimoires->implements, amulets/tattoos/implants->worn, etc.)
# instead of dropping ~half of items into the unfiltered parent only. Truly
# generic gear (冒险道具/材料/货物/神器…) intentionally stays parent-only.
ITEM_GROUPS = {
    "weapons":     {"特殊魔法武器", "珍贵材料武器", "魔兽枪"},
    "armor":       {"特殊魔法护甲", "珍贵材料护甲", "特殊魔法盾牌", "珍贵材料盾牌"},
    "runes":       {"武器性能符文", "护甲性能符文", "配件符文"},
    "worn":        {"穿戴物品", "护符", "魔法刺青", "植入体", "圣物种子"},
    "consumables": {"药水", "油", "炼金灵药", "炼金毒素", "炼金炸弹", "炼金食物",
                    "炼金药物", "炼金弹药", "其他消耗品", "消耗品", "茶", "魔法弹药",
                    "永久炼金物品", "瓶装气息", "瓶装怪物", "炼金工具", "圈套",
                    "符箓", "法术触媒", "魔法圈套"},
    "implements":  {"咒心", "法杖", "特殊魔杖", "魔杖", "魔典", "天命套牌", "尾声乐器"},
}


def spell_root(rec, t):
    return rec["_type"] == "Spells" and t in toks(rec.get("根源", ""))


def spell_class(rec, c):
    return rec["_type"] == "Spells" and rec.get("法术分类", "") == c


def creature_band(rec, lo, hi):
    if rec["_type"] != "Creatures":
        return False
    lv = to_int(rec.get("等级", ""))
    return lv is not None and lo <= lv <= hi


def item_group(rec, key):
    if rec["_type"] != "Items":
        return False
    return any(t in ITEM_GROUPS[key] for t in toks(rec.get("物品分类", "")))


# Parent bucket categories (must match build_browse_v2.BUCKET_CATS) — used to
# intersect each subzone with its parent so subzones stay a strict subset.
SIZE_CATS = {"微型", "小型", "中型", "大型", "巨型", "超大型"}
PARENT_OF_FAMILY = {"spells": "spells", "creatures": "creatures", "items": "items"}


def family_of(slug: str) -> str:
    if "spells" in slug:
        return "spells"
    if "creatures" in slug:
        return "creatures"
    return "items"


SUBZONES = [
    ("browse-spells-arcane",  "奥术法术", lambda r: spell_root(r, "奥术"), "根源"),
    ("browse-spells-divine",  "神术法术", lambda r: spell_root(r, "神术"), "根源"),
    ("browse-spells-occult",  "异能法术", lambda r: spell_root(r, "异能"), "根源"),
    ("browse-spells-primal",  "原能法术", lambda r: spell_root(r, "原能"), "根源"),
    ("browse-spells-cantrips", "戏法",    lambda r: spell_class(r, "戏法"), "根源"),
    ("browse-spells-focus",   "聚能法术", lambda r: spell_class(r, "聚能"), "根源"),
    ("browse-creatures-level-0-3",   "0-3 级生物",   lambda r: creature_band(r, -99, 3),  "等级"),
    ("browse-creatures-level-4-7",   "4-7 级生物",   lambda r: creature_band(r, 4, 7),    "等级"),
    ("browse-creatures-level-8-12",  "8-12 级生物",  lambda r: creature_band(r, 8, 12),   "等级"),
    ("browse-creatures-level-13-17", "13-17 级生物", lambda r: creature_band(r, 13, 17),  "等级"),
    ("browse-creatures-level-18-25", "18-25 级生物", lambda r: creature_band(r, 18, 99),  "等级"),
    ("browse-items-weapons",     "武器",     lambda r: item_group(r, "weapons"),     "物品分类"),
    ("browse-items-armor",       "护甲",     lambda r: item_group(r, "armor"),       "物品分类"),
    ("browse-items-consumables", "消耗品",   lambda r: item_group(r, "consumables"), "物品分类"),
    ("browse-items-worn",        "穿戴物品", lambda r: item_group(r, "worn"),        "物品分类"),
    ("browse-items-runes",       "符文",     lambda r: item_group(r, "runes"),       "物品分类"),
    ("browse-items-implements",  "法器",     lambda r: item_group(r, "implements"),  "物品分类"),
]


def main() -> int:
    # one pass: ns=0 parent-bucket membership (for subset intersection) +
    # ns=3500 data records.
    parent = {"spells": set(), "creatures": set(), "items": set()}
    records = []
    for sub in PARSED_DIR.iterdir():
        if not sub.is_dir() or sub.name.startswith("_"):
            continue
        for f in sub.iterdir():
            if not f.name.endswith(".json"):
                continue
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            ns = d.get("ns", 0)
            if ns == 0:
                t = d.get("title", "")
                cats = {c.get("category", "").replace("_", " ")
                        for c in (d.get("parse", {}) or {}).get("categories", [])
                        if isinstance(c, dict)}
                if "法术" in cats:
                    parent["spells"].add(t)
                if cats & SIZE_CATS:
                    parent["creatures"].add(t)
                if "物品" in cats:
                    parent["items"].add(t)
            elif ns == 3500:
                m = re.match(r"Data:([A-Za-z]+)-", d.get("title", ""))
                if not m:
                    continue
                rec = parse_table(d.get("parse", {}).get("text", ""))
                rec["_type"] = m.group(1)
                records.append(rec)
    print(f"  scanned: parents spells={len(parent['spells'])} "
          f"creatures={len(parent['creatures'])} items={len(parent['items'])}, "
          f"{len(records)} data records")

    topnav_sub = SNIPPET_TOPNAV_SUB.read_text(encoding="utf-8")
    topnav_root = topnav_sub.replace('href="../', 'href="').replace('action="../', 'action="')
    sidebar_sub = SNIPPET_SIDEBAR_SUB.read_text(encoding="utf-8")
    sidebar_root = sidebar_sub.replace('href="../', 'href="').replace('action="../', 'action="')

    written = 0
    for slug, label, pred, disp in SUBZONES:
        pset = parent[family_of(slug)]   # intersect with parent -> strict subset
        seen = set()
        entries = []
        skipped = 0
        for rec in records:
            if not pred(rec):
                continue
            name = rec.get("中文", "")
            if not name or name in seen:
                continue
            seen.add(name)
            if name not in pset:
                skipped += 1
                continue  # not in parent bucket -> exclude (keeps subzone ⊆ parent)
            entries.append({
                "ns": 0, "ns_label": "条目", "title": name,
                "href": page_href(0, name), "cats": [rec.get(disp, "")],
            })
        entries.sort(key=lambda e: e["title"].lower())
        html = render_browse_html(slug, entries, topnav_root, sidebar_root, label=label)
        (ROOT / f"{slug}.html").write_text(html, encoding="utf-8")
        note = f"  (excluded {skipped} not-in-parent)" if skipped else ""
        print(f"  {slug}.html: {len(entries):,} entries{note}")
        written += 1
    print(f"wrote {written} real sub-zone pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
