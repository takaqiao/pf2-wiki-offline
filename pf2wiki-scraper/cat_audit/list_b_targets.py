"""List mechanism-B targets: the bare titles of every ns=14 Category page that
build_v2.py actually renders into _wiki_full_v2/category/*.html.

These are the categories whose offline membership (inverted parse.categories)
we diff against live `list=categorymembers`.

Writes out_v2/_cat_audit/_b_category_targets.txt (UTF-8, one bare name per line).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARSED = ROOT / "out_v2" / "parsed"
OUT = ROOT / "out_v2" / "_cat_audit"
OUT.mkdir(parents=True, exist_ok=True)

PREFIXES = ("Category:", "分类:")


def bare(t: str) -> str:
    for pre in PREFIXES:
        if t.startswith(pre):
            return t[len(pre):]
    return t


def main() -> int:
    titles = set()
    raw_count = 0
    for pf in PARSED.rglob("*.json"):
        if pf.name.startswith("_"):
            continue
        try:
            d = json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("ns") == 14:
            raw_count += 1
            t = bare(d.get("title", ""))
            if t:
                titles.add(t)
    out = sorted(titles)
    (OUT / "_b_category_targets.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"ns14_docs={raw_count} distinct_bare_titles={len(out)} -> {OUT / '_b_category_targets.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
