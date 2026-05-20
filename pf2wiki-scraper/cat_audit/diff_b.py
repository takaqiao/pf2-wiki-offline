"""P3 diff for mechanism B: offline category/ membership vs live categorymembers.

Offline truth = _offline_cat_index.json (inverted parse.categories, same as build_v2).
Live truth    = _live/<sha1>.json (full categorymembers per B target).

KEY NORMALIZATION (see ledger FINDINGS): the offline corpus only scrapes
namespaces {0,4,14,102,3500}. Live categories can include members in OTHER
namespaces (10=Template, 6=File, ...). Those are NOT defects — the offline site
doesn't host them. So we split diffs into HOSTED-ns (real, user-facing) vs
NON-HOSTED-ns (expected, ignored). Titles normalized (_ -> space, strip).

Outputs out_v2/_cat_audit/_b_diff_report.json + prints an ASCII summary.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUD = ROOT / "out_v2" / "_cat_audit"
LIVE = AUD / "_live"

HOSTED_NS = {0, 4, 14, 102, 3500}
SAMPLE = 15  # cap per-category sample lists in the report


def norm(t: str) -> str:
    return t.replace("_", " ").strip()


def safe_key(name: str) -> str:
    return hashlib.sha1(name.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    targets = [ln.strip() for ln in (AUD / "_b_category_targets.txt").read_text(
        encoding="utf-8").splitlines() if ln.strip()]
    offline = json.loads((AUD / "_offline_cat_index.json").read_text(encoding="utf-8"))

    per_cat = {}
    n_clean = 0
    n_no_live = 0
    agg = Counter()  # aggregate counters
    offenders_missing = []   # hosted-ns members live has, offline lacks
    offenders_extra = []     # hosted-ns members offline has, live lacks

    for name in targets:
        lf = LIVE / f"{safe_key(name)}.json"
        if not lf.exists():
            n_no_live += 1
            continue
        live = json.loads(lf.read_text(encoding="utf-8"))
        live_set = {(m.get("ns"), norm(m.get("title", ""))) for m in live.get("members", [])}
        off_set = {(ns, norm(t)) for ns, t in offline.get(name, [])}

        only_live = live_set - off_set      # offline MISSING
        only_off = off_set - live_set       # offline EXTRA

        ol_hosted = sorted([x for x in only_live if x[0] in HOSTED_NS])
        oo_hosted = sorted([x for x in only_off if x[0] in HOSTED_NS])
        ol_nonhost = Counter(x[0] for x in only_live if x[0] not in HOSTED_NS)
        oo_nonhost = Counter(x[0] for x in only_off if x[0] not in HOSTED_NS)

        clean = not ol_hosted and not oo_hosted
        if clean:
            n_clean += 1
        rec = {
            "live_size": len(live_set),
            "offline_size": len(off_set),
            "page_missing_on_wiki": live.get("category_page_missing"),
            "missing_hosted": len(ol_hosted),     # live has, offline lacks (hosted ns)
            "extra_hosted": len(oo_hosted),        # offline has, live lacks (hosted ns)
            "missing_nonhosted_by_ns": dict(ol_nonhost),
            "extra_nonhosted_by_ns": dict(oo_nonhost),
            "clean": clean,
            "missing_hosted_sample": ol_hosted[:SAMPLE],
            "extra_hosted_sample": oo_hosted[:SAMPLE],
        }
        per_cat[name] = rec
        agg["missing_hosted_total"] += len(ol_hosted)
        agg["extra_hosted_total"] += len(oo_hosted)
        if ol_hosted:
            offenders_missing.append((len(ol_hosted), name))
        if oo_hosted:
            offenders_extra.append((len(oo_hosted), name))

    offenders_missing.sort(reverse=True)
    offenders_extra.sort(reverse=True)

    summary = {
        "b_targets": len(targets),
        "with_live": len(per_cat),
        "no_live_cache": n_no_live,
        "clean_categories": n_clean,
        "categories_with_hosted_diff": len(per_cat) - n_clean,
        "missing_hosted_total": agg["missing_hosted_total"],
        "extra_hosted_total": agg["extra_hosted_total"],
        "top20_missing": [[n, c] for c, n in offenders_missing[:20]],
        "top20_extra": [[n, c] for c, n in offenders_extra[:20]],
    }
    out = {"summary": summary, "per_category": per_cat}
    (AUD / "_b_diff_report.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print("=== B DIFF SUMMARY (offline vs live, hosted-ns only) ===")
    for k, v in summary.items():
        if not k.startswith("top"):
            print(f"  {k}: {v}")
    print(f"  (full report -> {AUD / '_b_diff_report.json'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
