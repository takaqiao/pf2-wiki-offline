"""Root-cause the 37 B diffs: classify each missing/extra member.

Hypothesis: the diffs are scrape staleness (wiki grew since 2026-05-19), not a
build_v2 logic bug. Test: cross-check every diff title against the FULL offline
page universe (all scraped pages).

  missing (live has, offline lacks):
    - not_in_corpus  -> page absent offline entirely = new/unscraped (staleness)
    - in_corpus      -> page exists offline but its parse.categories lacked this
                        cat = page-level staleness OR redirect/alias (needs look)
  extra (offline has, live lacks):
    - page recategorized/removed on wiki, or redirect alias.

Writes out_v2/_cat_audit/_b_findings_analysis.json (UTF-8).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARSED = ROOT / "out_v2" / "parsed"
AUD = ROOT / "out_v2" / "_cat_audit"


def norm(t: str) -> str:
    return t.replace("_", " ").strip()


def main() -> int:
    # full offline page universe: (ns, normtitle)
    offline_pages = set()
    offline_titles_only = set()
    for pf in PARSED.rglob("*.json"):
        if pf.name.startswith("_"):
            continue
        try:
            d = json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            continue
        nt = norm(d.get("title", ""))
        offline_pages.add((d.get("ns", 0), nt))
        offline_titles_only.add(nt)

    report = json.loads((AUD / "_b_diff_report.json").read_text(encoding="utf-8"))
    pc = report["per_category"]

    miss_in = miss_out = 0
    miss_in_other_ns = 0
    miss_not_anywhere = []
    miss_in_corpus = []
    extra_list = []

    for cat, rec in pc.items():
        for ns, t in rec["missing_hosted_sample"]:
            nt = norm(t)
            if (ns, nt) in offline_pages:
                miss_in += 1
                miss_in_corpus.append([cat, ns, t])
            elif nt in offline_titles_only:
                # exists under a different ns (e.g. live lists ns=0, we have it elsewhere)
                miss_in_other_ns += 1
                miss_in_corpus.append([cat, ns, t, "other_ns"])
            else:
                miss_out += 1
                miss_not_anywhere.append([cat, ns, t])
        for ns, t in rec["extra_hosted_sample"]:
            extra_list.append([cat, ns, t, norm(t) in offline_titles_only])

    out = {
        "missing_total_hosted": report["summary"]["missing_hosted_total"],
        "missing_not_in_corpus": miss_out,         # pure staleness (new pages)
        "missing_in_corpus_same_ns": miss_in,      # page present, lacked the cat link
        "missing_in_corpus_other_ns": miss_in_other_ns,
        "extra_total_hosted": report["summary"]["extra_hosted_total"],
        "missing_not_in_corpus_samples": miss_not_anywhere,
        "missing_in_corpus_samples": miss_in_corpus[:40],
        "extra_samples": extra_list,
    }
    (AUD / "_b_findings_analysis.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("missing_not_in_corpus (new/unscraped =staleness):", miss_out)
    print("missing_in_corpus_same_ns (page present, lacked cat):", miss_in)
    print("missing_in_corpus_other_ns:", miss_in_other_ns)
    print("extra_hosted (offline has, live lacks):", len(extra_list))
    print("->", AUD / "_b_findings_analysis.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
