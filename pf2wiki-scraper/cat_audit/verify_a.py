"""Verify the NEW category-driven browse buckets match live wiki.

For each bucket, build the offline member set (union of BUCKET_CATS categories,
ns=0, from the inverted parse.categories index) and the live member set (same
categories' live ns=0 members). Diff should be staleness-level (like B's 89.5%),
NOT the huge keyword errors diff_a found before the fix.

BUCKET_CATS is kept in sync with _wiki_full_v2/build_browse_v2.py.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUD = ROOT / "out_v2" / "_cat_audit"
LIVE = AUD / "_live"

BUCKET_CATS = {
    "feats":        ["专长"],
    "spells":       ["法术"],
    "items":        ["物品"],
    "creatures":    ["微型", "小型", "中型", "大型", "巨型", "超大型"],
    "ancestries":   ["族裔"],
    "backgrounds":  ["背景"],
    "archetypes":   ["变体（特征）"],
    "classes":      ["职业"],
    "deities":      ["信仰"],
    "locations":    ["地理"],
    "other":        ["状态"],
}


def key(n):
    return hashlib.sha1(n.encode("utf-8")).hexdigest()[:16]


def norm(t):
    return t.replace("_", " ").strip()


def main() -> int:
    idx = json.loads((AUD / "_offline_cat_index.json").read_text(encoding="utf-8"))

    def off_ns0(cat):
        return {norm(t) for ns, t in idx.get(cat, []) if ns == 0}

    def live_ns0(cat):
        f = LIVE / f"{key(cat)}.json"
        if not f.exists():
            return None
        d = json.loads(f.read_text(encoding="utf-8"))
        return {norm(m.get("title", "")) for m in d.get("members", []) if m.get("ns") == 0}

    print("=== VERIFY A (new buckets: offline vs live, ns=0) ===")
    print(f"{'bucket':<12}{'offline':>8}{'live':>8}{'false+':>8}{'false-':>8}  uncached")
    report = {}
    all_ok = True
    for bucket, cats in BUCKET_CATS.items():
        off = set()
        live = set()
        uncached = []
        for c in cats:
            off |= off_ns0(c)
            l = live_ns0(c)
            if l is None:
                uncached.append(c)
            else:
                live |= l
        fp = off - live
        fn = live - off
        report[bucket] = {
            "offline": len(off), "live": len(live),
            "false_pos": len(fp), "false_neg": len(fn),
            "uncached": uncached,
            "false_pos_sample": sorted(fp)[:10],
            "false_neg_sample": sorted(fn)[:10],
        }
        # staleness threshold: a handful is fine; tens+ would be suspicious
        if uncached or len(fp) > 30 or len(fn) > 30:
            all_ok = False
        print(f"{bucket:<12}{len(off):>8}{len(live):>8}{len(fp):>8}{len(fn):>8}  {','.join(uncached) if uncached else ''}")

    (AUD / "_a_verify_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nAll buckets staleness-level (<=30 diff, no uncached): {all_ok}")
    print(f"-> {AUD / '_a_verify_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
