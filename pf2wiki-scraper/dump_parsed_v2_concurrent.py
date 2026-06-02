"""Phase B (concurrent edition) — uses curl_cffi + CF cookies from warmup.

Bypasses Playwright per-request. Speeds up Phase B ~5-10x at 4-8 concurrency.

Pre-req:
    .venv\\Scripts\\python.exe cookie_warmup_v2.py     # one-shot

Run:
    .venv\\Scripts\\python.exe dump_parsed_v2_concurrent.py             # 4 workers
    .venv\\Scripts\\python.exe dump_parsed_v2_concurrent.py -c 8        # 8 workers
    .venv\\Scripts\\python.exe dump_parsed_v2_concurrent.py --limit 50  # test
    .venv\\Scripts\\python.exe dump_parsed_v2_concurrent.py --ns 0      # one namespace

State / failure / resume all compatible with dump_parsed_v2.py (same files).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from curl_cffi import requests as crequests

ROOT = Path(__file__).resolve().parent
OUT_V2 = ROOT / "out_v2"
PARSED_DIR = OUT_V2 / "parsed"
PARSED_DIR.mkdir(parents=True, exist_ok=True)
META_FILE = OUT_V2 / "metadata.json"
STATE_FILE = PARSED_DIR / "_state.json"
FAIL_FILE = PARSED_DIR / "_failures.jsonl"
COOKIES_FILE = OUT_V2 / "cookies.json"

API_URL = "https://pf2.huijiwiki.com/api.php"
HOMEPAGE_URL = "https://pf2.huijiwiki.com/wiki/%E9%A6%96%E9%A1%B5"
IMPERSONATE = "chrome131"

state_lock = threading.Lock()
fail_lock = threading.Lock()


def sha_path(pageid: int) -> Path:
    h = hashlib.sha1(str(pageid).encode()).hexdigest()
    return PARSED_DIR / h[:2] / f"{h[2:]}.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            # Corrupt state (e.g. killed mid-write): rebuild done-set from the
            # parsed files actually on disk so a resume doesn't re-fetch everything.
            done = []
            for pf in PARSED_DIR.rglob("*.json"):
                if pf.name.startswith("_"):
                    continue
                try:
                    d = json.loads(pf.read_text(encoding="utf-8"))
                    if d.get("pageid") is not None:
                        done.append(d["pageid"])
                except Exception:
                    continue
            print(f"[state] corrupt _state.json — rebuilt {len(done)} done from disk")
            return {"done": sorted(set(done)), "started_at": None}
    return {"done": [], "started_at": None}


def save_state(state: dict) -> None:
    # Atomic: write to a temp file then os.replace so a kill mid-write can't
    # truncate _state.json (which previously crashed/zeroed resume).
    with state_lock:
        tmp = STATE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, STATE_FILE)


def make_session(cookies: list[dict]) -> "crequests.Session":
    s = crequests.Session(impersonate=IMPERSONATE)
    s.headers.update({
        "Accept": "application/json, text/html, */*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": HOMEPAGE_URL,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    })
    for c in cookies:
        try:
            s.cookies.set(
                name=c["name"],
                value=c["value"],
                domain=c.get("domain", ".huijiwiki.com"),
                path=c.get("path", "/"),
            )
        except Exception:
            # curl_cffi cookies API differs slightly; fallback
            s.cookies[c["name"]] = c["value"]
    return s


class CFExpired(Exception):
    pass


class RateLimited(Exception):
    pass


def fetch_parse(session: "crequests.Session", pageid: int) -> dict:
    params = {
        "action": "parse",
        "pageid": str(pageid),
        "prop": "text|categories|images|links|sections|displaytitle|properties|templates",
        "disableeditsection": "1",
        "disabletoc": "0",
        "format": "json",
        "formatversion": "2",
    }
    # Bounded retry-with-backoff on transient 429/5xx (honor Retry-After) so a
    # momentary blip doesn't permanently record a fail. CF 403 is NOT retried
    # here (cookies are stale -> the caller must re-warm).
    last_exc = None
    for attempt in range(4):
        try:
            r = session.get(API_URL, params=params, timeout=30)
        except Exception as e:
            last_exc = RuntimeError(f"request error: {e}")
            time.sleep(min(8, 0.6 * (2 ** attempt)))
            continue
        if r.status_code == 403:
            body = r.text[:200]
            if "just a moment" in body.lower() or "cloudflare" in body.lower():
                raise CFExpired("CF re-challenged (cookies stale)")
            raise CFExpired(f"403: {body}")
        if r.status_code == 429 or r.status_code >= 500:
            ra = r.headers.get("Retry-After")
            try:
                wait = float(ra) if ra else min(8, 0.6 * (2 ** attempt))
            except ValueError:
                wait = min(8, 0.6 * (2 ** attempt))
            last_exc = RateLimited(f"{r.status_code} {r.text[:80]}")
            if attempt < 3:
                time.sleep(wait)
                continue
            raise last_exc
        if r.status_code != 200:
            raise RuntimeError(f"http {r.status_code}: {r.text[:200]}")
        j = r.json()
        if "error" in j:
            raise RuntimeError(f"api error: {j['error'].get('code','?')} {j['error'].get('info','')}")
        return j
    raise last_exc or RuntimeError("fetch_parse exhausted retries")


def append_fail(pid: int, title: str, error: str) -> None:
    rec = {
        "pageid": pid,
        "title": title,
        "error": error[:500],
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with fail_lock:
        with FAIL_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def worker(work_item: dict, threadlocal: threading.local, cookies: list[dict]) -> tuple[int, str, float, str | None]:
    pid = work_item["pageid"]
    title = work_item.get("title", "")
    if not hasattr(threadlocal, "s"):
        threadlocal.s = make_session(cookies)
    session = threadlocal.s
    t0 = time.time()
    try:
        result = fetch_parse(session, pid)
    except (CFExpired, RateLimited) as e:
        append_fail(pid, title, str(e))
        return pid, "throttle", time.time() - t0, str(e)[:100]
    except Exception as e:
        append_fail(pid, title, f"{type(e).__name__}: {e}")
        return pid, "fail", time.time() - t0, f"{type(e).__name__}: {str(e)[:80]}"

    payload = {
        "pageid": pid,
        "ns": work_item.get("ns"),
        "title": title,
        "parse": result.get("parse", {}),
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    dest = sha_path(pid)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write so a kill mid-write can't leave a truncated parsed JSON that
    # the corrupt-state rebuild path would then trust.
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, dest)
    return pid, "ok", time.time() - t0, None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--concurrency", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ns", type=int, default=-1)
    ap.add_argument("--max-throttle", type=int, default=20, help="abort if N consecutive throttle events")
    ap.add_argument("--max-fail", type=int, default=100, help="abort if N total failures")
    args = ap.parse_args(argv[1:])

    if not COOKIES_FILE.exists():
        print(f"ERROR: {COOKIES_FILE} missing — run cookie_warmup_v2.py first")
        return 1
    cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
    has_clr = any(c.get("name") == "cf_clearance" for c in cookies)
    print(f"[plan] loaded {len(cookies)} cookies (cf_clearance={'YES' if has_clr else 'NO'})")

    if not META_FILE.exists():
        print(f"ERROR: {META_FILE} missing — run dump_metadata_v2.py first")
        return 1
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    pages = meta.get("pages", [])
    targets = [p for p in pages if not p.get("is_redirect")]
    if args.ns >= 0:
        targets = [p for p in targets if p.get("ns") == args.ns]
    if args.limit:
        targets = targets[: args.limit]

    state = load_state()
    done_set = set(state.get("done", []))
    if state.get("started_at") is None:
        state["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    todo = [p for p in targets if p["pageid"] not in done_set]
    print(f"[plan] {len(pages)} total, {len(targets)} non-redirect, {len(done_set)} done, {len(todo)} todo")
    print(f"[plan] concurrency={args.concurrency} impersonate={IMPERSONATE}")
    if not todo:
        print("[plan] nothing to do")
        return 0

    threadlocal = threading.local()
    t0 = time.time()
    completed = 0
    n_ok = 0
    n_fail = 0
    n_throttle = 0
    consecutive_throttle = 0

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        future_to_item = {
            pool.submit(worker, p, threadlocal, cookies): p
            for p in todo
        }
        for future in as_completed(future_to_item):
            pid, status, latency, err = future.result()
            completed += 1
            if status == "ok":
                done_set.add(pid)
                n_ok += 1
                consecutive_throttle = 0
            elif status == "throttle":
                n_throttle += 1
                consecutive_throttle += 1
            else:
                n_fail += 1
                consecutive_throttle = 0

            if completed % 50 == 0 or status != "ok":
                state["done"] = sorted(done_set)
                save_state(state)
                elapsed = time.time() - t0
                rate = completed / max(elapsed, 0.001)
                remaining = len(todo) - completed
                eta_min = remaining / max(rate, 0.001) / 60
                title = future_to_item[future].get("title", "").encode("ascii", "replace").decode()[:30]
                tag = {"ok": "  ", "throttle": "TT", "fail": "FF"}[status]
                print(
                    f"  [{completed}/{len(todo)}] {tag} pid={pid:>6} t={latency*1000:>4.0f}ms "
                    f"rate={rate:>5.2f}/s ok={n_ok} fail={n_fail} thr={n_throttle} "
                    f"eta={eta_min:>5.1f}min  {title}"
                    + (f"  ERR: {err}" if err else ""),
                    flush=True,
                )

            if consecutive_throttle >= args.max_throttle:
                print(f"\n[abort] {args.max_throttle} consecutive throttle events — cookies likely stale")
                print("[abort] re-run cookie_warmup_v2.py then resume this script")
                break
            if n_fail >= args.max_fail:
                print(f"\n[abort] {args.max_fail} total failures — investigate")
                break

    state["done"] = sorted(done_set)
    save_state(state)
    elapsed = time.time() - t0
    print(f"\n[done] processed {completed} pages in {elapsed:.0f}s")
    print(f"       ok={n_ok} fail={n_fail} throttle={n_throttle}")
    print(f"       avg rate {completed/max(elapsed,0.001):.2f} req/sec")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
