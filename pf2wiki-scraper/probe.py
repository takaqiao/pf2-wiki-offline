"""Probe pf2.huijiwiki.com.

Strategy: launch a headed Chromium with a persistent user-data dir so the
Cloudflare cf_clearance cookie sticks across runs. Then run API queries via
`page.evaluate(fetch)` — this keeps the browser's TLS fingerprint, UA, and
cookies, which is what CF actually checks. Playwright's APIRequestContext does
NOT reuse the browser's TLS stack and gets blocked with 403 / "Just a moment".

Usage:
    python probe.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
PROFILE_DIR = ROOT / ".browser-profile"
OUT_DIR = ROOT / "out"
OUT_DIR.mkdir(exist_ok=True)

BASE = "https://pf2.huijiwiki.com"
HOMEPAGE = f"{BASE}/wiki/%E9%A6%96%E9%A1%B5"
API_PATH = "/api.php"

PROBES = [
    {
        "name": "siteinfo",
        "params": {
            "action": "query",
            "meta": "siteinfo",
            "siprop": "general|statistics|namespaces",
            "format": "json",
        },
    },
    {
        "name": "allpages_sample",
        "params": {
            "action": "query",
            "list": "allpages",
            "aplimit": "10",
            "apnamespace": "0",
            "format": "json",
        },
    },
]


def wait_for_content(page, timeout_ms: int = 60_000) -> None:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        title = page.title() or ""
        if title and "just a moment" not in title.lower():
            try:
                body_len = page.evaluate("document.body.innerText.length")
            except Exception:
                body_len = 0
            if body_len and body_len > 500:
                return
        page.wait_for_timeout(1000)
    raise TimeoutError("Cloudflare challenge did not clear within timeout.")


def api_get(page, path: str, params: dict) -> dict:
    """Run fetch() inside the page so CF sees a normal browser request."""
    js = """
    async ({path, params}) => {
      const u = new URL(path, location.origin);
      for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v);
      const r = await fetch(u.toString(), {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });
      const text = await r.text();
      let json = null;
      try { json = JSON.parse(text); } catch (_) {}
      return { status: r.status, url: u.toString(), json, raw_preview: json ? null : text.slice(0, 500) };
    }
    """
    return page.evaluate(js, {"path": path, "params": params})


def main() -> int:
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
            # Real Chrome UA (must match the browser CF sees)
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        print(f"[1/3] Navigating to {HOMEPAGE}")
        page.goto(HOMEPAGE, wait_until="domcontentloaded", timeout=60_000)

        print("[2/3] Waiting for Cloudflare challenge to clear ...")
        try:
            wait_for_content(page)
        except TimeoutError as e:
            print(f"ERROR: {e}  Solve any interactive challenge manually, then rerun.")
            ctx.close()
            return 2
        print(f"    ok — page title loaded")

        results: dict = {}
        for probe in PROBES:
            print(f"[3/3] Probe: {probe['name']}")
            result = api_get(page, API_PATH, probe["params"])
            result["ok"] = result["status"] == 200 and result["json"] is not None
            results[probe["name"]] = result
            print(f"    status={result['status']} ok={result['ok']}")

        out_file = OUT_DIR / "probe-result.json"
        out_file.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nWrote {out_file}")

        si = results.get("siteinfo", {}).get("json") or {}
        general = si.get("query", {}).get("general", {})
        stats = si.get("query", {}).get("statistics", {})
        if general:
            print(f"  sitename  : {general.get('sitename')}")
            print(f"  mainpage  : {general.get('mainpage')}")
            print(f"  generator : {general.get('generator')}")
        if stats:
            print(f"  pages={stats.get('pages')}  articles={stats.get('articles')}")

        ap = results.get("allpages_sample", {}).get("json") or {}
        pages = ap.get("query", {}).get("allpages", []) or []
        if pages:
            print(f"  sample titles ({len(pages)}):")
            for entry in pages:
                print(f"    - {entry.get('title')}  (pageid={entry.get('pageid')})")

        ctx.close()
        return 0 if all(r["ok"] for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
