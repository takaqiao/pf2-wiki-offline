"""Dump LIVE pf2.huijiwiki.com category membership via MediaWiki API.

For each target Category name (read from a UTF-8 file, one per line, WITHOUT the
"Category:" / "分类:" prefix), fetch:
  - categoryinfo (official size/pages/files/subcats)
  - full categorymembers (ids|title|ns|type|sortkey), following continue tokens.

Goes through pfwiki.browser() (headed Chromium, persistent CF-cleared profile) so
Cloudflare sees a real browser. Caches each result to out_v2/_cat_audit/_live/
(gitignored via out_v2/), keyed by sha1(category) so Chinese names are filesystem-safe.

Usage:
  .venv\\Scripts\\python.exe cat_audit\\dump_live_catmembers.py <targets.txt> [--limit N] [--refresh]
    --limit N : only process first N targets (probe mode)
    --refresh : re-fetch even if a cached result exists
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # so `import pfwiki` (scraper root) resolves

from pfwiki import browser, api_get, api_query_continue

OUT = ROOT / "out_v2" / "_cat_audit" / "_live"
OUT.mkdir(parents=True, exist_ok=True)


def safe_key(name: str) -> str:
    return hashlib.sha1(name.encode("utf-8")).hexdigest()[:16]


def fetch_one(page, cat: str) -> dict:
    title = f"Category:{cat}"
    info = api_get(page, {
        "action": "query", "prop": "categoryinfo",
        "titles": title, "format": "json", "formatversion": "2",
    })
    pages = info.get("query", {}).get("pages", [])
    ci = (pages[0].get("categoryinfo", {}) if pages else {}) or {}
    cat_page_missing = bool(pages and pages[0].get("missing", False))

    members = []
    for data in api_query_continue(page, {
        "list": "categorymembers",
        "cmtitle": title,
        "cmlimit": "max",
        "cmprop": "ids|title|ns|type|sortkey",
    }):
        members.extend(data.get("query", {}).get("categorymembers", []) or [])

    return {
        "category": cat,
        "category_page_missing": cat_page_missing,
        "categoryinfo": ci,                 # {size, pages, files, subcats}
        "member_count": len(members),
        "members": members,                 # [{pageid, ns, title, type, sortkey}]
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("usage: dump_live_catmembers.py <targets.txt> [--limit N] [--refresh]")
        return 2
    targets_file = Path(args[0])
    limit = None
    refresh = "--refresh" in args
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    targets = [ln.strip() for ln in targets_file.read_text(encoding="utf-8").splitlines()
               if ln.strip() and not ln.startswith("#")]
    if limit:
        targets = targets[:limit]
    print(f"targets: {len(targets)}")

    index_path = OUT / "_index.json"
    index = {}
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            index = {}

    todo = [c for c in targets if refresh or c not in index or
            not (OUT / f"{safe_key(c)}.json").exists()]
    print(f"to fetch: {len(todo)} (cached: {len(targets) - len(todo)})")
    if not todo:
        print("nothing to fetch; all cached.")
        return 0

    done = 0
    with browser(headless=False) as (ctx, page):
        for i, cat in enumerate(todo):
            try:
                rec = fetch_one(page, cat)
            except Exception as e:
                print(f"  [{i+1}/{len(todo)}] FAIL {cat!r}: {e}")
                continue
            key = safe_key(cat)
            (OUT / f"{key}.json").write_text(
                json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            index[cat] = {
                "key": key,
                "member_count": rec["member_count"],
                "info_size": rec["categoryinfo"].get("size"),
                "info_pages": rec["categoryinfo"].get("pages"),
                "info_subcats": rec["categoryinfo"].get("subcats"),
                "page_missing": rec["category_page_missing"],
            }
            done += 1
            print(f"  [{i+1}/{len(todo)}] {cat}  members={rec['member_count']} "
                  f"info_size={rec['categoryinfo'].get('size')} "
                  f"page_missing={rec['category_page_missing']}")
            # be polite
            time.sleep(0.3)
            if done % 25 == 0:
                index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2),
                                      encoding="utf-8")

    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: fetched {done}, index has {len(index)} entries -> {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
