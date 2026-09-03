"""Phase A.5 - drop pages the wiki has edited since we captured them.

`dump_parsed_v2_concurrent.py` resumes with

    todo = [p for p in targets if p["pageid"] not in done_set]

so a re-run only ever fetches pages that are *new*.  A page that existed at the
last capture and has been edited since stays in `done` forever and is never
re-fetched: the offline corpus silently rots.

This closes that hole.  For every page still listed as done it asks the API for
`touched` (the last edit timestamp) and compares it against the `captured_at`
stamp the parsed file wrote for itself - per page, so it also catches pages
edited *between* two runs of a multi-day scrape.  Stale pageids are removed
from `_state.json`, which is exactly what makes the next dump re-fetch them.

`recentchanges` is deliberately not used: the last capture is far outside the
default `$wgRCMaxAge` window, so it would silently under-report.

Run (from the scraper dir, after dump_metadata_v2.py):
    .venv\\Scripts\\python.exe invalidate_stale_v2.py            # report only
    .venv\\Scripts\\python.exe invalidate_stale_v2.py --write    # rewrite _state.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from curl_cffi import requests as crequests

ROOT = Path(__file__).resolve().parent
OUT_V2 = ROOT / "out_v2"
PARSED_DIR = OUT_V2 / "parsed"
META_FILE = OUT_V2 / "metadata.json"
STATE_FILE = PARSED_DIR / "_state.json"
COOKIES_FILE = OUT_V2 / "cookies.json"

API_URL = "https://pf2.huijiwiki.com/api.php"
HOMEPAGE_URL = "https://pf2.huijiwiki.com/wiki/%E9%A6%96%E9%A1%B5"
IMPERSONATE = "chrome131"

# Anonymous API cap for pageids= is 50 per request.
BATCH = 50

print_lock = threading.Lock()


def sha_path(pageid: int) -> Path:
    h = hashlib.sha1(str(pageid).encode()).hexdigest()
    return PARSED_DIR / h[:2] / f"{h[2:]}.json"


def make_session(cookies):
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
            s.cookies.set(name=c["name"], value=c["value"],
                          domain=c.get("domain", ".huijiwiki.com"), path=c.get("path", "/"))
        except Exception:
            s.cookies[c["name"]] = c["value"]
    return s


class CFExpired(Exception):
    pass


def fetch_info(session, pageids):
    params = {
        "action": "query",
        "prop": "info",
        "pageids": "|".join(str(p) for p in pageids),
        "format": "json",
        "formatversion": "2",
    }
    for attempt in range(4):
        try:
            r = session.get(API_URL, params=params, timeout=30)
        except Exception:
            time.sleep(min(8, 0.6 * (2 ** attempt)))
            continue
        if r.status_code == 403:
            raise CFExpired("CF re-challenged (cookies stale) - re-run cookie_warmup_v2.py")
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(8, 0.6 * (2 ** attempt)))
            continue
        if r.status_code != 200:
            raise RuntimeError(f"http {r.status_code}: {r.text[:200]}")
        j = r.json()
        if "error" in j:
            raise RuntimeError(f"api error: {j['error'].get('code', '?')}")
        out = {}
        for p in (j.get("query") or {}).get("pages", []) or []:
            if p.get("missing"):
                out[p.get("pageid", -1)] = {"missing": True}
            else:
                out[p["pageid"]] = {"touched": p.get("touched"), "lastrevid": p.get("lastrevid")}
        return out
    raise RuntimeError("fetch_info exhausted retries")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="rewrite _state.json (a .bak is kept)")
    ap.add_argument("-c", "--concurrency", type=int, default=8)
    ap.add_argument("--report", type=Path, default=OUT_V2 / "_stale_report.json")
    ap.add_argument("--full-rescrape-threshold", type=int, default=30000,
                    help="above this many stale pages, recommend deleting _state.json instead")
    args = ap.parse_args(argv)

    if not STATE_FILE.exists():
        print(f"[fatal] {STATE_FILE} missing - nothing is marked done, so nothing to invalidate")
        return 1
    if not COOKIES_FILE.exists():
        print("[fatal] cookies.json missing - run cookie_warmup_v2.py first")
        return 1

    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    done = set(state.get("done", []))
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    live = {p["pageid"] for p in meta.get("pages", []) if not p.get("is_redirect")}
    cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
    if isinstance(cookies, dict):
        cookies = cookies.get("cookies", [])

    # A page still in `done` but no longer in metadata was deleted or turned into a
    # redirect upstream: it is not stale, it is gone. Drop it so `done` cannot
    # outgrow the target list and mask real coverage.
    gone = sorted(done - live)
    check = sorted(done & live)
    print(f"[plan] done={len(done)} live-nonredirect={len(live)} to-check={len(check)} gone={len(gone)}")

    # captured_at per page, straight from the parsed file it belongs to
    captured = {}
    missing_file = []
    for pid in check:
        path = sha_path(pid)
        if not path.exists():
            missing_file.append(pid)
            continue
        try:
            captured[pid] = json.loads(path.read_text(encoding="utf-8")).get("captured_at") or ""
        except Exception:
            missing_file.append(pid)
    print(f"[plan] parsed files read: {len(captured)}, unreadable/missing: {len(missing_file)}")

    batches = [check[i:i + BATCH] for i in range(0, len(check), BATCH)]
    info = {}
    t0 = time.time()
    threadlocal = threading.local()

    def run(batch):
        if not hasattr(threadlocal, "session"):
            threadlocal.session = make_session(cookies)
        return fetch_info(threadlocal.session, batch)

    n_done = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(run, b): b for b in batches}
        try:
            for fut in as_completed(futures):
                info.update(fut.result())
                n_done += 1
                if n_done % 50 == 0 or n_done == len(batches):
                    rate = n_done / max(1e-9, time.time() - t0)
                    with print_lock:
                        print(f"  [info] {n_done}/{len(batches)} batches  {rate:5.1f}/s  "
                              f"eta {int((len(batches) - n_done) / max(rate, 1e-9))}s")
        except CFExpired as e:
            print(f"[abort] {e}")
            return 2

    stale, unknown, deleted = [], [], []
    for pid in check:
        rec = info.get(pid)
        if rec is None:
            unknown.append(pid)
            continue
        if rec.get("missing"):
            deleted.append(pid)
            continue
        touched, cap = rec.get("touched") or "", captured.get(pid) or ""
        if not cap:
            stale.append(pid)          # no local stamp -> cannot prove freshness
        elif touched > cap:            # both Z-suffixed ISO-8601: lexicographic == chronological
            stale.append(pid)

    drop = sorted(set(stale) | set(missing_file) | set(unknown) | set(deleted) | set(gone))
    print(f"\n[result] edited-since-capture {len(stale)}, parsed-file-missing {len(missing_file)}, "
          f"api-silent {len(unknown)}, deleted-upstream {len(deleted)}, no-longer-listed {len(gone)}")
    print(f"[result] would drop {len(drop)} of {len(done)} done ids -> next dump re-fetches them")
    if len(drop) > args.full_rescrape_threshold:
        print(f"[hint] that is more than --full-rescrape-threshold ({args.full_rescrape_threshold}); "
              "deleting _state.json for a clean full scrape is simpler and about as fast")

    args.report.write_text(json.dumps({
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metadata_captured_at": meta.get("captured_at"),
        "counts": {"done": len(done), "checked": len(check), "stale": len(stale),
                   "missing_file": len(missing_file), "unknown": len(unknown),
                   "deleted": len(deleted), "gone": len(gone), "drop": len(drop)},
        "stale_sample": [{"pageid": p, "captured_at": captured.get(p),
                          "touched": (info.get(p) or {}).get("touched")} for p in stale[:50]],
        "drop": drop,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[result] report -> {args.report}")

    if not args.write:
        print("\n(dry run - pass --write to rewrite _state.json)")
        return 0
    if not drop:
        print("nothing to drop; _state.json untouched")
        return 0

    shutil.copy2(STATE_FILE, STATE_FILE.with_suffix(".json.bak"))
    state["done"] = sorted(done - set(drop))
    state["invalidated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state["invalidated_count"] = len(drop)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)
    print(f"[write] _state.json done {len(done)} -> {len(state['done'])} "
          f"(backup at {STATE_FILE.with_suffix('.json.bak').name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
