"""Resolve missing redirect targets in metadata.json — curl_cffi concurrent.

Replaces resolve_redirect_targets_v2.py (Playwright-based, ~2 min) with a
parallel curl_cffi version. Single-threaded curl_cffi at ~10 req/sec finishes
2229 redirect resolutions in ~4 sec.

Pre-req: cookies.json from cookie_warmup_v2.py.

Run:
    .venv\\Scripts\\python.exe resolve_redirect_targets_v2_concurrent.py
"""

from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from curl_cffi import requests as crequests

ROOT = Path(__file__).resolve().parent
OUT_V2 = ROOT / "out_v2"
META_FILE = OUT_V2 / "metadata.json"
COOKIES_FILE = OUT_V2 / "cookies.json"

API_URL = "https://pf2.huijiwiki.com/api.php"
HOMEPAGE_URL = "https://pf2.huijiwiki.com/wiki/%E9%A6%96%E9%A1%B5"
IMPERSONATE = "chrome131"
BATCH = 50
CONCURRENCY = 8


def make_session(cookies: list[dict]) -> "crequests.Session":
    s = crequests.Session(impersonate=IMPERSONATE)
    s.headers.update({
        "Accept": "application/json,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": HOMEPAGE_URL,
    })
    for c in cookies:
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ".huijiwiki.com"), path=c.get("path", "/"))
        except Exception:
            s.cookies[c["name"]] = c["value"]
    return s


def resolve_batch(session: "crequests.Session", titles: list[str]) -> tuple[list[dict], list[dict]]:
    params = {
        "action": "query",
        "titles": "|".join(titles),
        "redirects": "1",
        "format": "json",
        "formatversion": "2",
    }
    r = session.get(API_URL, params=params, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"http {r.status_code}: {r.text[:200]}")
    j = r.json()
    redirects = (j.get("query") or {}).get("redirects", []) or []
    normalized = (j.get("query") or {}).get("normalized", []) or []
    return redirects, normalized


def worker(batch: list[str], threadlocal: threading.local, cookies: list[dict]) -> tuple[list[dict], list[dict], str | None]:
    if not hasattr(threadlocal, "s"):
        threadlocal.s = make_session(cookies)
    try:
        r, n = resolve_batch(threadlocal.s, batch)
        return r, n, None
    except Exception as e:
        return [], [], f"{type(e).__name__}: {e}"


def main() -> int:
    if not COOKIES_FILE.exists():
        print(f"ERROR: {COOKIES_FILE} missing — run cookie_warmup_v2.py first")
        return 1
    cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))

    if not META_FILE.exists():
        print(f"ERROR: {META_FILE} missing")
        return 1
    data = json.loads(META_FILE.read_text(encoding="utf-8"))
    redirect_map = data.get("redirect_map") or {}

    redirect_sources = [p["title"] for p in data.get("pages", []) if p.get("is_redirect")]
    todo = [t for t in redirect_sources if not redirect_map.get(t)]
    for src, tgt in list(redirect_map.items()):
        if not tgt and src not in todo:
            todo.append(src)
    print(f"[plan] {len(redirect_sources)} redirect pages, {len(todo)} unresolved")
    if not todo:
        print("[plan] nothing to do")
        return 0

    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    threadlocal = threading.local()
    t0 = time.time()
    resolved = 0
    n_fail = 0

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(worker, b, threadlocal, cookies): b for b in batches}
        done = 0
        for fut in as_completed(futures):
            redirects, normalized, err = fut.result()
            done += 1
            if err:
                n_fail += 1
                print(f"  [batch {done}/{len(batches)}] FAIL: {err}")
                continue
            norm_map = {n["from"]: n["to"] for n in normalized}
            for r in redirects:
                src = r.get("from")
                tgt = r.get("to")
                if not src or not tgt:
                    continue
                for orig, ntitle in norm_map.items():
                    if ntitle == src and orig != src:
                        redirect_map[orig] = tgt
                redirect_map[src] = tgt
                resolved += 1
            if done % 10 == 0:
                rate = done / (time.time() - t0)
                print(f"  [batch {done}/{len(batches)}] resolved={resolved} rate={rate:.1f} batch/s")

    data["redirect_map"] = redirect_map
    META_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    elapsed = time.time() - t0
    filled = sum(1 for v in redirect_map.values() if v)
    print(f"\n[done] resolved {resolved} targets in {elapsed:.1f}s ({n_fail} batch failures)")
    print(f"       redirect_map: {len(redirect_map)} entries, {filled} with targets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
