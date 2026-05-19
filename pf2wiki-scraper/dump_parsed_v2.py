"""Phase B: fetch action=parse HTML for every non-redirect page — v2.

Input:  out_v2/metadata.json (from dump_metadata_v2.py)
Output: out_v2/parsed/<sha1[:2]>/<sha1[2:]>.json   (one per pageid)
State:  out_v2/parsed/_state.json
Failures: out_v2/parsed/_failures.jsonl (one line per failed pageid)

Resume behaviour: skip pageid if already in _state.done. _state flushed every 50 pages.
Polite pacing: ~2 req/sec (smoke test showed ~150ms parse latency, server can handle this).

Run:
    .venv\\Scripts\\python.exe dump_parsed_v2.py            # full run
    .venv\\Scripts\\python.exe dump_parsed_v2.py --limit N  # cap at N for testing
    .venv\\Scripts\\python.exe dump_parsed_v2.py --ns 0     # only ns=0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from pfwiki import api_get, browser

ROOT = Path(__file__).resolve().parent
OUT_V2 = ROOT / "out_v2"
PARSED_DIR = OUT_V2 / "parsed"
PARSED_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = PARSED_DIR / "_state.json"
FAIL_FILE = PARSED_DIR / "_failures.jsonl"
META_FILE = OUT_V2 / "metadata.json"


def sha_path(pageid: int) -> Path:
    h = hashlib.sha1(str(pageid).encode()).hexdigest()
    return PARSED_DIR / h[:2] / f"{h[2:]}.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"done": [], "started_at": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def append_fail(pageid: int, title: str, error: str) -> None:
    rec = {"pageid": pageid, "title": title, "error": error[:500], "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with FAIL_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def parse_one(page, pageid: int) -> dict:
    """Single page parse. Returns the JSON. Raises on failure."""
    params = {
        "action": "parse",
        "pageid": str(pageid),
        "prop": "text|categories|images|links|sections|displaytitle|properties|templates",
        "disableeditsection": "1",
        "disabletoc": "0",
        "format": "json",
        "formatversion": "2",
    }
    return api_get(page, params)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="cap N pages (0 = all)")
    ap.add_argument("--ns", type=int, default=-1, help="only this namespace (-1 = all)")
    ap.add_argument("--rate", type=float, default=2.0, help="target req/sec (default 2)")
    args = ap.parse_args(argv[1:])

    if not META_FILE.exists():
        print(f"ERROR: {META_FILE} missing — run dump_metadata_v2.py first")
        return 1
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    pages = meta.get("pages", [])
    # Skip redirects — they'd return target content; we'll handle redirects as stubs in build phase
    targets = [p for p in pages if not p.get("is_redirect")]
    if args.ns >= 0:
        targets = [p for p in targets if p.get("ns") == args.ns]
    if args.limit:
        targets = targets[:args.limit]

    state = load_state()
    done_set = set(state.get("done", []))
    if state.get("started_at") is None:
        state["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    todo = [p for p in targets if p["pageid"] not in done_set]
    print(f"[plan] {len(pages)} total pages, {len(targets)} non-redirect, {len(done_set)} done, {len(todo)} todo")

    if not todo:
        print("[plan] nothing to do")
        return 0

    min_interval = 1.0 / max(args.rate, 0.1)
    t0 = time.time()
    last_req = 0.0
    consecutive_fail = 0

    with browser(headless=False) as (_ctx, page):
        for i, p in enumerate(todo):
            pid = p["pageid"]
            title = p.get("title", "")

            # Polite pacing
            since = time.time() - last_req
            if since < min_interval:
                time.sleep(min_interval - since)

            t1 = time.time()
            try:
                result = parse_one(page, pid)
            except Exception as e:
                last_req = time.time()
                consecutive_fail += 1
                msg = f"{type(e).__name__}: {e}"
                append_fail(pid, title, msg)
                print(f"  [{i+1}/{len(todo)}] pid={pid} FAIL ({consecutive_fail}x): {msg[:120]}")
                if consecutive_fail >= 10:
                    print("  [abort] 10 consecutive failures — saving state and stopping")
                    save_state(state)
                    return 2
                continue

            last_req = time.time()
            consecutive_fail = 0
            # Persist parse result
            payload = {
                "pageid": pid,
                "ns": p.get("ns"),
                "title": title,
                "parse": result.get("parse", {}),
                "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            target_path = sha_path(pid)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            done_set.add(pid)

            # Status line ASCII-only — title may have CJK and PowerShell mojibakes
            title_ascii = title.encode("ascii", "replace").decode()[:40]
            elapsed = time.time() - t0
            rate = (i + 1) / max(elapsed, 0.001)
            eta_s = (len(todo) - i - 1) / max(rate, 0.01)
            eta_h = eta_s / 3600
            print(f"  [{i+1}/{len(todo)}] pid={pid:>6} ns={p.get('ns'):>4} t={t1 - t0:>6.1f}s "
                  f"rate={rate:.2f}/s eta={eta_h:.2f}h  {title_ascii}", flush=True)

            # Flush state every 50 pages
            if (i + 1) % 50 == 0:
                state["done"] = sorted(done_set)
                save_state(state)

        # Final flush
        state["done"] = sorted(done_set)
        save_state(state)

    print(f"\n[done] parsed {len(done_set) - len(state.get('done', [])) + len(todo)} pages in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
