"""Revision/timestamp-aware content refresh (true staleness elimination).

The corpus was scraped ~2026-05-19; dump_parsed tracks done-by-pageid so it never
re-fetches CHANGED pages. This tool uses the wiki's list=recentchanges to find
every page edited/created since the corpus date, then re-fetches exactly those
via the HEADED browser (pfwiki.browser passes Cloudflare via the persistent
profile — no cf_clearance needed, unlike the curl_cffi concurrent path).

Refetched files are written byte-compatibly with dump_parsed_v2_concurrent.py
(same payload + sha_path), so build_v2.py picks them up. New pageids are added to
parsed/_state.json. Output: out_v2/_cat_audit/_refresh_report.json.

Usage:
  .venv\\Scripts\\python.exe cat_audit\\refresh_changed.py --dry-run   # just count
  .venv\\Scripts\\python.exe cat_audit\\refresh_changed.py             # fetch
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pfwiki import browser, api_get, api_query_continue  # noqa: E402

PARSED = ROOT / "out_v2" / "parsed"
STATE_FILE = PARSED / "_state.json"
AUD = ROOT / "out_v2" / "_cat_audit"
AUD.mkdir(parents=True, exist_ok=True)

NAMESPACES = "0|4|14|102|3500"
RC_END = "2026-05-18T00:00:00Z"   # lower bound; corpus scraped ~2026-05-19
PARSE_PROP = "text|categories|images|links|sections|displaytitle|properties|templates"


def sha_path(pid: int) -> Path:
    h = hashlib.sha1(str(pid).encode()).hexdigest()
    return PARSED / h[:2] / f"{h[2:]}.json"


def captured_index() -> dict:
    cap = {}
    for pf in PARSED.rglob("*.json"):
        if pf.name.startswith("_"):
            continue
        try:
            d = json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            continue
        pid = d.get("pageid")
        if pid is not None:
            cap[pid] = d.get("captured_at", "")
    return cap


def main() -> int:
    dry = "--dry-run" in sys.argv
    print(f"[refresh] recentchanges since {RC_END}, ns={NAMESPACES}, dry_run={dry}")
    changes = {}
    with browser(headless=False) as (ctx, page):
        for data in api_query_continue(page, {
            "list": "recentchanges", "rcend": RC_END, "rclimit": "max",
            "rcnamespace": NAMESPACES, "rcprop": "title|ids|timestamp",
            "rctype": "edit|new",
        }):
            for rc in data.get("query", {}).get("recentchanges", []) or []:
                pid = rc.get("pageid")
                if not pid:
                    continue
                ts = rc.get("timestamp", "")
                if pid not in changes or ts > changes[pid]["ts"]:
                    changes[pid] = {"title": rc.get("title", ""), "ns": rc.get("ns", 0),
                                    "ts": ts, "type": rc.get("type", "")}
        print(f"[refresh] {len(changes)} distinct changed/new pages in window")

        cap = captured_index()
        todo = []
        new_cnt = 0
        for pid, info in changes.items():
            c = cap.get(pid)
            if c is None:
                new_cnt += 1
                todo.append((pid, info))
            elif c < info["ts"]:
                todo.append((pid, info))
        print(f"[refresh] to refresh: {len(todo)} ({new_cnt} new pageids, "
              f"{len(todo)-new_cnt} edited-after-capture)")

        report = {"window_since": RC_END, "changed_pages": len(changes),
                  "to_refresh": len(todo), "new": new_cnt}
        if dry:
            (AUD / "_refresh_report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
            print("[refresh] dry-run; no fetch.")
            return 0

        state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {"done": []}
        done = set(state.get("done", []))
        ok = fail = 0
        for i, (pid, info) in enumerate(todo):
            try:
                res = api_get(page, {
                    "action": "parse", "pageid": str(pid), "prop": PARSE_PROP,
                    "disableeditsection": "1", "disabletoc": "0",
                    "format": "json", "formatversion": "2",
                })
            except Exception as e:
                fail += 1
                print(f"  FAIL pid={pid} {info['title']!r}: {str(e)[:80]}")
                continue
            parse = res.get("parse", {})
            if not parse:
                fail += 1
                continue
            payload = {"pageid": pid, "ns": info["ns"], "title": info["title"],
                       "parse": parse, "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            dest = sha_path(pid)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            done.add(pid)
            ok += 1
            if (i + 1) % 25 == 0:
                print(f"  {i+1}/{len(todo)} ok={ok} fail={fail}")
                state["done"] = sorted(done)
                STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(0.12)
        state["done"] = sorted(done)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        report.update({"refreshed_ok": ok, "failed": fail})
        (AUD / "_refresh_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[refresh] done: ok={ok} fail={fail}, state done={len(done)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
