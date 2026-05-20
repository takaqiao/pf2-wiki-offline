"""Verify C sub-zones are consistent with their parent browse bucket.

Each sub-zone (e.g. browse-spells-arcane) must list only pages that are also in
its parent (browse-spells). We parse the generated HTML <a> titles and check the
subset relation, reporting any out-of-parent members (would indicate the
data-driven subzone disagrees with the category-driven parent).
"""
from __future__ import annotations

import re
from pathlib import Path

WIKI = Path(__file__).resolve().parents[2] / "_wiki_full_v2"
A_RX = re.compile(r'<td><a href="[^"]+">(.*?)</a></td>')
TAG = re.compile(r"<[^>]+>")


def titles(slug: str) -> set:
    f = WIKI / f"{slug}.html"
    if not f.exists():
        return set()
    return {TAG.sub("", m).strip() for m in A_RX.findall(f.read_text(encoding="utf-8"))}


PARENTS = {
    "spells": "browse-spells",
    "creatures": "browse-creatures",
    "items": "browse-items",
}
SUBZONES = {
    "spells": ["browse-spells-arcane", "browse-spells-divine", "browse-spells-occult",
               "browse-spells-primal", "browse-spells-cantrips", "browse-spells-focus"],
    "creatures": ["browse-creatures-level-0-3", "browse-creatures-level-4-7",
                  "browse-creatures-level-8-12", "browse-creatures-level-13-17",
                  "browse-creatures-level-18-25"],
    "items": ["browse-items-weapons", "browse-items-armor", "browse-items-consumables",
              "browse-items-worn", "browse-items-runes", "browse-items-implements"],
}


def main() -> int:
    print("=== VERIFY C (subzone subset of parent) ===")
    all_ok = True
    for fam, parent_slug in PARENTS.items():
        parent = titles(parent_slug)
        print(f"\n[{fam}] parent {parent_slug} = {len(parent)} members")
        union = set()
        for slug in SUBZONES[fam]:
            s = titles(slug)
            union |= s
            out = s - parent
            flag = "" if not out else f"  <-- {len(out)} NOT in parent! e.g. {sorted(out)[:3]}"
            if out:
                all_ok = False
            print(f"  {slug:<32} {len(s):>5}{flag}")
        cover = len(union & parent)
        print(f"  union covers {cover}/{len(parent)} of parent "
              f"({len(parent)-cover} parent members in no subzone)")
    print(f"\nAll subzones subset of parent: {all_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
