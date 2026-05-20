"""Probe the ns=3500 Data: page schema (mw-jsonconfig tables) to drive C subzones.

Each Data:<Type>-<Name>.json renders a <table class="mw-jsonconfig"> of
<th>field</th><td class="mw-jsonconfig-value">value</td> rows. We parse those,
group by Type (Spells/Creatures/Items/...), and tally field names + distinct
values for the fields that should drive subzones (spell tradition/rank, creature
level, item type). Output: out_v2/_cat_audit/_schema.json (UTF-8).
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARSED = ROOT / "out_v2" / "parsed"
AUD = ROOT / "out_v2" / "_cat_audit"

ROW_RX = re.compile(
    r"<th>(.*?)</th><td class=\"mw-jsonconfig-value\">(.*?)</td>", re.S)
TAG_RX = re.compile(r"<[^>]+>")


def clean(s: str) -> str:
    s = TAG_RX.sub("", s)
    return s.replace("&amp;", "&").strip()


def parse_table(text: str) -> dict:
    out = {}
    for th, td in ROW_RX.findall(text):
        out[clean(th)] = clean(td)
    return out


def main() -> int:
    type_fields = defaultdict(Counter)     # type -> Counter(field names)
    type_count = Counter()
    # interesting distinct-value tallies
    spell_root = Counter()      # 根源 token (split on , and 、)
    spell_class = Counter()     # 法术分类
    spell_rank = Counter()      # 环级
    creature_fields_vals = defaultdict(Counter)   # creature field -> values (for level)
    item_fields_vals = defaultdict(Counter)

    def toks(v):
        return [x for x in re.split(r"[,，、/]", v) if x.strip()]

    for pf in PARSED.rglob("*.json"):
        if pf.name.startswith("_"):
            continue
        try:
            d = json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("ns") != 3500:
            continue
        title = d.get("title", "")
        m = re.match(r"Data:([A-Za-z]+)-", title)
        typ = m.group(1) if m else "?"
        type_count[typ] += 1
        rec = parse_table(d.get("parse", {}).get("text", "") or "")
        for k in rec:
            type_fields[typ][k] += 1
        if typ == "Spells":
            for t in toks(rec.get("根源", "")):
                spell_root[t] += 1
            spell_class[rec.get("法术分类", "")] += 1
            spell_rank[rec.get("环级", "")] += 1
        elif typ == "Creatures":
            for k in ("等级", "级别", "level", "Level", "CR"):
                if k in rec:
                    creature_fields_vals[k][rec[k]] += 1
        elif typ == "Items":
            for k in ("类型", "种类", "物品类型", "category", "类别"):
                if k in rec:
                    item_fields_vals[k][rec[k]] += 1

    out = {
        "type_counts": dict(type_count.most_common()),
        "type_top_fields": {t: c.most_common(30) for t, c in type_fields.items()},
        "spell_root_traditions": spell_root.most_common(),
        "spell_class": spell_class.most_common(),
        "spell_rank": spell_rank.most_common(),
        "creature_level_fields": {k: c.most_common(40) for k, c in creature_fields_vals.items()},
        "item_type_fields": {k: c.most_common(40) for k, c in item_fields_vals.items()},
    }
    (AUD / "_schema.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("types:", dict(type_count.most_common()))
    print("spell traditions:", spell_root.most_common())
    print("-> _schema.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
