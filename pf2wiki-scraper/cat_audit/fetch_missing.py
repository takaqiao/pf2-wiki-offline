"""Fetch the metadata pages missing from the parsed corpus (close the scrape gap).

metadata.json lists ~40k pages; parsed/ has ~37k. The non-redirect pages in
metadata WITHOUT a parsed file are the gap that left ~3.5k stale 'orphan' HTML on
disk and ~1.7% content dead links. This fetches exactly those via the headed
browser (CF-safe), writing parsed JSON byte-compatibly with
dump_parsed_v2_concurrent.py (same payload + sha_path), so a rebuild renders them
fresh.

Usage:
  .venv\\Scripts\\python.exe cat_audit\\fetch_missing.py --dry-run
  .venv\\Scripts\\python.exe cat_audit\\fetch_missing.py [--limit N]
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pfwiki import browser, api_get  # noqa: E402

OUT_V2 = ROOT / "out_v2"
PARSED = OUT_V2 / "parsed"
META_FILE = OUT_V2 / "metadata.json"
STATE_FILE = PARSED / "_state.json"
AUD = OUT_V2 / "_cat_audit"
AUD.mkdir(parents=True, exist_ok=True)
PARSE_PROP = "text|categories|images|links|sections|displaytitle|properties|templates"
# parsed corpus only renders these namespaces (build_v2 NS_TO_DIR)
WANTED_NS = {0, 4, 14, 102, 3500}


def sha_path(pageid: int) -> Path:
    h = hashlib.sha1(str(pageid).encode()).hexdigest()
    return PARSED / h[:2] / f"{h[2:]}.json"


def main() -> int:
    dry = "--dry-run" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    missing = []
    for p in meta.get("pages", []):
        if p.get("is_redirect"):
            continue
        if p.get("ns") not in WANTED_NS:
            continue
        pid = p.get("pageid")
        if pid is None:
            continue
        if not sha_path(pid).exists():
            missing.append(p)
    print(f"[gap] non-redirect pages missing from parsed: {len(missing)}")
    # ns histogram of the gap
    from collections import Counter
    print(f"[gap] by ns: {dict(Counter(p.get('ns') for p in missing))}")
    if limit:
        missing = missing[:limit]
    if dry:
        (AUD / "_missing_pages.json").write_text(
            json.dumps([{"pageid": p["pageid"], "ns": p["ns"], "title": p["title"]} for p in missing[:50]],
                       ensure_ascii=False, indent=1), encoding="utf-8")
        print("[gap] dry-run; wrote first 50 to _missing_pages.json")
        return 0

    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {"done": []}
    done = set(state.get("done", []))
    ok = fail = 0
    with browser(headless=False) as (ctx, page):
        for i, p in enumerate(missing):
            pid, ns, title = p["pageid"], p["ns"], p["title"]
            try:
                res = api_get(page, {
                    "action": "parse", "pageid": str(pid), "prop": PARSE_PROP,
                    "disableeditsection": "1", "disabletoc": "0",
                    "format": "json", "formatversion": "2",
                })
            except Exception as e:
                fail += 1
                print(f"  FAIL pid={pid} {title!r}: {str(e)[:70]}")
                continue
            parse = res.get("parse")
            if not parse:
                fail += 1
                continue
            payload = {"pageid": pid, "ns": ns, "title": title, "parse": parse,
                       "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            dest = sha_path(pid)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, dest)
            done.add(pid)
            ok += 1
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(missing)} ok={ok} fail={fail}")
                state["done"] = sorted(done)
                tmp2 = STATE_FILE.with_suffix(".json.tmp")
                tmp2.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(tmp2, STATE_FILE)
            time.sleep(0.1)
    state["done"] = sorted(done)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[gap] done: ok={ok} fail={fail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
