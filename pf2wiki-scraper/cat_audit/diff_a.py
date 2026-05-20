"""P3-A: quantify how wrong the keyword browse buckets (mechanism A) are vs the
real live wiki category that should define each bucket.

Replicates build_browse_v2.classify() over the offline corpus to get current
bucket membership, then for each bucket with a known live anchor category,
diffs (ns=0 content pages) against the live anchor:
  false_pos = in browse bucket but NOT in real category  (wrongly included)
  false_neg = in real category but NOT in browse bucket   (wrongly missed)

Anchor map uses CORRECTED live names (creatures=生物, locations=地理, ...).
Anchors not present in the live cache are skipped (reported as unresolved).

Writes out_v2/_cat_audit/_a_diff_report.json (UTF-8) + prints ASCII summary.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARSED = ROOT / "out_v2" / "parsed"
AUD = ROOT / "out_v2" / "_cat_audit"
LIVE = AUD / "_live"

# --- replicate build_browse_v2.py BUCKETS + classify ---
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

# bucket -> live anchor category (CORRECTED names). None = needs design/probe.
ANCHOR = {
    "feats": "专长",
    "spells": "法术",
    "items": "物品",
    "creatures": "生物",      # NOT 怪物
    "ancestries": "族裔",     # probe confirmed: 祖先 missing, 族裔=246
    "backgrounds": "背景",
    "archetypes": "变体",
    "classes": "职业",
    "deities": "信仰",        # probe confirmed: 神祇 missing, 信仰=478
    "locations": "地理",      # NOT 地点
    "other": None,            # grab-bag, no single anchor
}


def classify(cats, title):
    blob = (" ".join(cats) + " " + title).lower()
    out = set()
    for b, keys in BUCKETS.items():
        for k in keys:
            if k.lower() in blob:
                out.add(b)
                break
    return out


def safe_key(name):
    return hashlib.sha1(name.encode("utf-8")).hexdigest()[:16]


def norm(t):
    return t.replace("_", " ").strip()


def live_ns0(cat):
    f = LIVE / f"{safe_key(cat)}.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    return {norm(m.get("title", "")) for m in d.get("members", []) if m.get("ns") == 0}


def main() -> int:
    # 1) current bucket membership (ns=0 only, mirrors what users browse as content)
    bucket0 = defaultdict(set)
    for pf in PARSED.rglob("*.json"):
        if pf.name.startswith("_"):
            continue
        try:
            d = json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            continue
        ns = d.get("ns", 0)
        if ns not in (0, 102, 14, 3500):
            continue
        title = d.get("title", "")
        cats = [c.get("category", "") for c in (d.get("parse", {}) or {}).get("categories", []) if isinstance(c, dict)]
        if ns == 14:
            continue  # "categories" bucket = ns14, not a content-keyword bucket
        for b in classify(cats, title):
            if ns == 0:
                bucket0[b].add(norm(title))

    report = {}
    print("=== A DIFF (browse keyword bucket vs real live category, ns=0) ===")
    print(f"{'bucket':<12}{'cur':>7}{'real':>7}{'falsePos':>9}{'falseNeg':>9}  anchor")
    for b in BUCKETS:
        anc = ANCHOR.get(b)
        cur = bucket0.get(b, set())
        if not anc:
            report[b] = {"current": len(cur), "anchor": None, "note": "no single anchor (design)"}
            print(f"{b:<12}{len(cur):>7}{'-':>7}{'-':>9}{'-':>9}  (none)")
            continue
        real = live_ns0(anc)
        if real is None:
            report[b] = {"current": len(cur), "anchor": anc, "note": "anchor NOT in live cache"}
            print(f"{b:<12}{len(cur):>7}{'?':>7}{'?':>9}{'?':>9}  {anc} (uncached)")
            continue
        fp = cur - real
        fn = real - cur
        report[b] = {
            "current": len(cur), "anchor": anc, "anchor_size": len(real),
            "false_pos": len(fp), "false_neg": len(fn),
            "false_pos_sample": sorted(fp)[:20],
            "false_neg_sample": sorted(fn)[:20],
        }
        print(f"{b:<12}{len(cur):>7}{len(real):>7}{len(fp):>9}{len(fn):>9}  {anc}")

    (AUD / "_a_diff_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {AUD / '_a_diff_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
