"""Fetch the live wiki 首页 (home page) structure to align our offline index.html,
and resolve the Animist class page name (for the 职业 hub fix)."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pfwiki import browser, api_get  # noqa: E402

OUT = ROOT / "out_v2" / "_cat_audit"

with browser(headless=False) as (ctx, page):
    # 1) home page rendered HTML + links
    r = api_get(page, {"action": "parse", "page": "首页",
                       "prop": "text|links|images|templates", "format": "json", "formatversion": "2"})
    parse = r.get("parse", {})
    html = parse.get("text", "") or ""
    (OUT / "_homepage_live.html").write_text(html, encoding="utf-8")

    # extract section headings + internal link titles for a quick structure view
    heads = re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, re.S)
    heads = [re.sub(r"<[^>]+>", "", h).strip() for h in heads]
    links = [l.get("title") for l in parse.get("links", []) if l.get("ns") in (0, 14)]
    summary = {
        "title": parse.get("title"),
        "html_len": len(html),
        "headings": [h for h in heads if h][:40],
        "n_internal_links": len(links),
        "links_sample": links[:120],
        "templates": [t.get("title") for t in parse.get("templates", [])][:30],
    }

    # 2) resolve Animist class page name
    animist = {}
    for t in ["铸念师", "通灵师", "灵能师", "执灵师", "魂铸者", "御能师"]:
        info = api_get(page, {"action": "query", "titles": t, "redirects": "1",
                              "format": "json", "formatversion": "2"})
        q = info.get("query", {})
        pages = q.get("pages", [])
        animist[t] = {"redirects": q.get("redirects", []),
                      "missing": pages[0].get("missing", False) if pages else None,
                      "resolved": pages[0].get("title") if pages else None}
    summary["class_name_probe"] = animist

    (OUT / "_homepage_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote _homepage_live.html + _homepage_summary.json")
    print("headings:", len([h for h in heads if h]), "links:", len(links))
