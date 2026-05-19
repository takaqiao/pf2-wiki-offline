"""Warmup: launch Playwright once, capture CF clearance cookies, export to JSON.

After warmup, dump_parsed_v2_concurrent.py uses curl_cffi (Chrome TLS impersonation)
+ these cookies for high-concurrency scraping — no Playwright per request.

Cookies typically valid for 30-60 min (cf_clearance) and 30 min (__cf_bm).
Re-run this when concurrent scraper starts seeing 403s.

Usage:
    .venv\\Scripts\\python.exe cookie_warmup_v2.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from pfwiki import browser

ROOT = Path(__file__).resolve().parent
OUT_V2 = ROOT / "out_v2"
OUT_V2.mkdir(exist_ok=True)
COOKIES_FILE = OUT_V2 / "cookies.json"


def main() -> int:
    print("[1/2] launching headed Chromium to clear CF ...")
    with browser(headless=False) as (ctx, page):
        # CF already cleared by pfwiki.browser(). Also probe the API once to
        # ensure __cf_bm is fresh.
        page.evaluate("""
            async () => {
                const r = await fetch('/api.php?action=query&meta=siteinfo&format=json', {credentials: 'include'});
                return r.status;
            }
        """)
        # Wait a tick for cookie jar to settle
        page.wait_for_timeout(500)
        cookies = ctx.cookies()

        # Keep only huijiwiki domain cookies
        relevant = [
            c for c in cookies
            if "huijiwiki.com" in (c.get("domain") or "")
        ]
        COOKIES_FILE.write_text(
            json.dumps(relevant, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"[2/2] wrote {len(relevant)} cookies to {COOKIES_FILE.name}")
        for c in relevant:
            name = c.get("name", "")
            val = (c.get("value") or "")
            print(f"    {name}={val[:30]}{'...' if len(val) > 30 else ''}  domain={c.get('domain')}")
        # Surface cf_clearance / __cf_bm explicitly
        has_clr = any(c["name"] == "cf_clearance" for c in relevant)
        has_bm = any(c["name"] == "__cf_bm" for c in relevant)
        print(f"\n    cf_clearance present: {has_clr}")
        print(f"    __cf_bm present: {has_bm}")
        if not has_clr:
            print("    WARNING: cf_clearance missing — CF may not be fully cleared. Try interactive challenge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
