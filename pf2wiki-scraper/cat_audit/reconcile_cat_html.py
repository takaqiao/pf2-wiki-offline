"""Reconcile the 358 category/*.html files vs the 354 ns=14 category targets.
Find the 4 extra HTML files that have no scraped ns=14 Category page."""
import json
import re
from pathlib import Path

WIKI = Path(__file__).resolve().parents[2] / "_wiki_full_v2"
CATDIR = WIKI / "category"
AUD = Path(__file__).resolve().parents[1] / "out_v2" / "_cat_audit"
SAFE = re.compile(r'[*?"<>|]')


def safe_title(t: str) -> str:
    t = t.replace(":", "_").replace("/", "__").replace("\\", "_")
    return SAFE.sub("", t)


targets = [l.strip() for l in (AUD / "_b_category_targets.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
expected = {safe_title(t) + ".html" for t in targets}
actual = {p.name for p in CATDIR.glob("*.html")}
extra = sorted(actual - expected)
missing = sorted(expected - actual)
print("actual html:", len(actual), "expected(354):", len(expected))
print("EXTRA (html w/o ns14 doc):", len(extra))
print("MISSING (ns14 doc w/o html):", len(missing))
(AUD / "_cat_reconcile.json").write_text(
    json.dumps({"extra": extra, "missing": missing}, ensure_ascii=False, indent=1), encoding="utf-8")
