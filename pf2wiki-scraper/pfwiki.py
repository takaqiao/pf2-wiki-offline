"""Shared helpers for pf2.huijiwiki.com scraping.

Everything goes through a single headed Chromium session with a persistent
user-data dir. API requests run inside the page via fetch() so Cloudflare sees
the real browser TLS fingerprint, UA, and cookies.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from playwright.sync_api import BrowserContext, Page, sync_playwright

ROOT = Path(__file__).resolve().parent
PROFILE_DIR = ROOT / ".browser-profile"
OUT_DIR = ROOT / "out"
OUT_DIR.mkdir(exist_ok=True)

BASE = "https://pf2.huijiwiki.com"
HOMEPAGE = f"{BASE}/wiki/%E9%A6%96%E9%A1%B5"
API_PATH = "/api.php"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _wait_clear(page: Page, timeout_ms: int = 60_000) -> None:
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


@contextmanager
def browser(headless: bool = False):
    """Yield (ctx, page) with CF already cleared. Reuses persistent profile."""
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=headless,
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
            user_agent=UA,
        )
        page = ctx.new_page()
        page.goto(HOMEPAGE, wait_until="domcontentloaded", timeout=60_000)
        _wait_clear(page)
        try:
            yield ctx, page
        finally:
            ctx.close()


_FETCH_JS = """
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


def api_get(page: Page, params: dict, *, retries: int = 3, backoff_s: float = 2.0) -> dict:
    """GET /api.php?... via in-page fetch. Retries on transient failure."""
    last_err: dict | None = None
    for attempt in range(retries):
        result = page.evaluate(_FETCH_JS, {"path": API_PATH, "params": params})
        if result.get("status") == 200 and result.get("json") is not None:
            return result["json"]
        last_err = result
        # 429 / 5xx -> wait and retry; 403 -> CF dropped us, also retry
        time.sleep(backoff_s * (attempt + 1))
    raise RuntimeError(f"api_get failed after {retries} attempts: {last_err}")


def api_query_continue(page: Page, params: dict) -> Iterable[dict]:
    """Yield each page of a `action=query` call, following `continue` tokens."""
    params = {"format": "json", "formatversion": "2", **params, "action": "query"}
    while True:
        data = api_get(page, params)
        yield data
        cont = data.get("continue")
        if not cont:
            break
        # Merge continue tokens into next request
        params = {**params, **cont}
