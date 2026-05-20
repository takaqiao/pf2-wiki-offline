"""Build the OFFLINE category ground-truth index by inverting parse.categories.

This mirrors exactly what _wiki_full_v2/build_v2.py does (L867-896) to populate
category/ pages (mechanism B). We invert it here so we can diff offline category
membership against live wiki (list=categorymembers) in the audit.

Outputs (UTF-8 JSON, console-safe) into out_v2/_cat_audit/ (gitignored via out_v2/):
  _offline_cat_index.json   {category: [[ns, title], ...]}
  _offline_cat_summary.json counts + ns histogram + top categories + missing list

Usage: .venv\\Scripts\\python.exe cat_audit\\build_offline_cat_index.py
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # pf2wiki-scraper/
PARSED = ROOT / "out_v2" / "parsed"
OUT = ROOT / "out_v2" / "_cat_audit"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    t0 = time.time()
    cat_members: dict[str, list] = defaultdict(list)   # cat -> [[ns, title], ...]
    missing_flagged: set[str] = set()                  # cat seen with missing:true
    ns_counts: dict[int, int] = defaultdict(int)
    page_count = 0
    read_fail = 0

    files = sorted(PARSED.rglob("*.json"))
    for pf in files:
        if pf.name.startswith("_"):
            continue
        try:
            d = json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            read_fail += 1
            continue
        title = d.get("title", "")
        ns = d.get("ns", 0)
        if not title:
            continue
        page_count += 1
        ns_counts[ns] += 1
        for c in (d.get("parse", {}) or {}).get("categories", []) or []:
            if not isinstance(c, dict):
                continue
            cat = c.get("category", "")
            if not cat:
                continue
            cat = cat.replace("_", " ")
            cat_members[cat].append([ns, title])
            if c.get("missing"):
                missing_flagged.add(cat)

    # Deterministic: sort member lists by (ns, title)
    for k in cat_members:
        cat_members[k].sort(key=lambda x: (x[0], x[1]))

    (OUT / "_offline_cat_index.json").write_text(
        json.dumps(cat_members, ensure_ascii=False), encoding="utf-8"
    )

    top = sorted(((len(v), k) for k, v in cat_members.items()), reverse=True)[:50]
    summary = {
        "parsed_files_scanned": len(files),
        "pages_with_title": page_count,
        "read_fail": read_fail,
        "distinct_categories": len(cat_members),
        "missing_flagged_categories": len(missing_flagged),
        "ns_histogram": dict(sorted(ns_counts.items())),
        "top50_by_member_count": [[c, n] for n, c in top],
        "elapsed_s": round(time.time() - t0, 1),
    }
    (OUT / "_offline_cat_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"scanned={len(files)} pages={page_count} cats={len(cat_members)} "
          f"missing_flagged={len(missing_flagged)} fail={read_fail} "
          f"in {summary['elapsed_s']}s")
    print(f"wrote {OUT / '_offline_cat_index.json'}")
    print(f"wrote {OUT / '_offline_cat_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
