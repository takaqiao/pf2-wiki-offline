"""Find correct live page titles for the 2 broken class-hub links
(元素使 Kineticist, 魂铸者 Animist) — check existence/redirect + search."""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pfwiki import browser, api_get  # noqa: E402

OUT = ROOT / "out_v2" / "_cat_audit"
CANDIDATES = ["元素使", "魂铸者", "动能术士", "动能师", "析能师", "通灵师", "魂师", "执灵师"]

with browser(headless=False) as (ctx, page):
    res = {}
    # 1) existence + redirect for candidate titles
    info = api_get(page, {"action": "query", "titles": "|".join(CANDIDATES),
                          "redirects": "1", "format": "json", "formatversion": "2"})
    q = info.get("query", {})
    res["redirects"] = q.get("redirects", [])
    res["pages"] = [{"title": p.get("title"), "missing": p.get("missing", False)} for p in q.get("pages", [])]
    # 2) full-text search for the two classes (English + concept)
    for term in ["Kineticist", "Animist", "动能", "魂铸"]:
        s = api_get(page, {"action": "query", "list": "search", "srsearch": term,
                           "srlimit": "5", "format": "json", "formatversion": "2"})
        res[f"search_{term}"] = [h.get("title") for h in s.get("query", {}).get("search", [])]
    (OUT / "_class_probe.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote _class_probe.json")
