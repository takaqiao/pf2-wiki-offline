"""Smoke test: verify cached CF clearance still works against pf2.huijiwiki.com.

Times: browser warm-up, CF clear, siteinfo round-trip, single action=parse round-trip.

Run:
    .venv\\Scripts\\python.exe smoke_test_v2.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from pfwiki import OUT_DIR, api_get, browser

OUT_V2 = Path(__file__).resolve().parent / "out_v2"
OUT_V2.mkdir(exist_ok=True)


def main() -> int:
    t0 = time.time()
    print("[1/4] launching headed Chromium with persistent profile ...")
    with browser(headless=False) as (_ctx, page):
        t_cf = time.time() - t0
        print(f"    CF cleared in {t_cf:.1f}s")

        print("[2/4] siteinfo round-trip ...")
        t1 = time.time()
        si = api_get(page, {
            "action": "query",
            "meta": "siteinfo",
            "siprop": "general|statistics|namespaces|extensions",
            "format": "json",
            "formatversion": "2",
        })
        t_si = time.time() - t1
        general = si.get("query", {}).get("general", {})
        stats = si.get("query", {}).get("statistics", {})
        ns = si.get("query", {}).get("namespaces", [])
        print(f"    siteinfo ok in {t_si*1000:.0f}ms")
        print(f"    sitename={general.get('sitename')}  generator={general.get('generator')}")
        print(f"    articles={stats.get('articles')}  pages={stats.get('pages')}  images={stats.get('images')}")
        print(f"    namespaces={len(ns)}")

        print("[3/4] action=parse single-page benchmark (战士) ...")
        t2 = time.time()
        parse = api_get(page, {
            "action": "parse",
            "page": "战士",
            "prop": "text|categories|images|links|sections|displaytitle|properties",
            "disableeditsection": "1",
            "disabletoc": "0",
            "format": "json",
            "formatversion": "2",
        })
        t_parse = time.time() - t2
        ptext = (parse.get("parse") or {}).get("text", "") or ""
        pimages = (parse.get("parse") or {}).get("images", []) or []
        plinks = (parse.get("parse") or {}).get("links", []) or []
        pcats = (parse.get("parse") or {}).get("categories", []) or []
        print(f"    parse ok in {t_parse*1000:.0f}ms")
        print(f"    text_len={len(ptext)}  images={len(pimages)}  links={len(plinks)}  categories={len(pcats)}")
        print(f"    text head: {ptext[:200].encode('ascii', 'replace').decode()!r}")

        print("[4/4] action=parse benchmark x10 to estimate scrape rate ...")
        # Pull 10 random page titles via allpages
        ap = api_get(page, {
            "action": "query",
            "list": "allpages",
            "aplimit": "10",
            "apnamespace": "0",
            "format": "json",
            "formatversion": "2",
        })
        pages = (ap.get("query") or {}).get("allpages", [])[:10]

        rt_list = []
        for p in pages:
            t3 = time.time()
            api_get(page, {
                "action": "parse",
                "pageid": str(p["pageid"]),
                "prop": "text",
                "disableeditsection": "1",
                "format": "json",
                "formatversion": "2",
            })
            rt = time.time() - t3
            rt_list.append(rt)
            print(f"    pageid={p['pageid']:>7} title={p['title']!s:30}  {rt*1000:.0f}ms")

        avg = sum(rt_list) / len(rt_list) if rt_list else 0
        print(f"\n    avg parse latency: {avg*1000:.0f}ms")
        # At 1.5 req/sec ceiling, but server may be slower:
        eff_rate = 1.0 / max(avg, 0.5)
        print(f"    sustainable rate: ~{eff_rate:.2f} req/sec")

        # Stash for scout_report.md
        result = {
            "smoke_test_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cf_clear_seconds": round(t_cf, 1),
            "siteinfo_ms": round(t_si * 1000, 0),
            "single_parse_ms": round(t_parse * 1000, 0),
            "sample_parse_avg_ms": round(avg * 1000, 0),
            "sample_parse_rates_ms": [round(rt * 1000, 0) for rt in rt_list],
            "sustainable_req_per_sec": round(eff_rate, 2),
            "siteinfo_summary": {
                "sitename": general.get("sitename"),
                "generator": general.get("generator"),
                "articles": stats.get("articles"),
                "pages": stats.get("pages"),
                "images": stats.get("images"),
                "namespaces_count": len(ns),
            },
        }
        (OUT_V2 / "smoke_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[done] wrote out_v2/smoke_result.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
