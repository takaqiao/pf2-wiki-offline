"""Resolve missing redirect targets in metadata.json.

After dump_metadata_v2.py runs, redirect_map[src] often has empty string as
target because `list=allredirects` doesn't include the target field by default.

This script:
  1. Loads out_v2/metadata.json
  2. Collects pages with is_redirect=True
  3. Batches titles=A|B|...&redirects=1 to get redirect chain via `query.redirects`
  4. Updates redirect_map with resolved targets
  5. Saves back to metadata.json

Run AFTER dump_metadata_v2.py, BEFORE build_v2.py --redirects.

Usage:
    .venv\\Scripts\\python.exe resolve_redirect_targets_v2.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from pfwiki import api_get, browser

ROOT = Path(__file__).resolve().parent
META_FILE = ROOT / "out_v2" / "metadata.json"
BATCH = 50  # MW caps titles= at 50 for anonymous


def main() -> int:
    if not META_FILE.exists():
        print(f"ERROR: {META_FILE} missing")
        return 1
    data = json.loads(META_FILE.read_text(encoding="utf-8"))

    # Collect redirect source titles from is_redirect=True pages
    redirect_sources = [p["title"] for p in data.get("pages", []) if p.get("is_redirect")]
    redirect_map = data.get("redirect_map") or {}
    print(f"  redirect pages: {len(redirect_sources)}; existing redirect_map: {len(redirect_map)}")

    # Determine what's missing
    todo = [t for t in redirect_sources if not redirect_map.get(t)]
    # Also include allredirects-source titles that are still empty
    for src, tgt in list(redirect_map.items()):
        if not tgt and src not in todo:
            todo.append(src)
    print(f"  todo: {len(todo)} unresolved")
    if not todo:
        print("  nothing to resolve")
        return 0

    with browser(headless=False) as (_ctx, page):
        t0 = time.time()
        resolved = 0
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            params = {
                "action": "query",
                "titles": "|".join(chunk),
                "redirects": "1",
                "format": "json",
                "formatversion": "2",
            }
            try:
                result = api_get(page, params)
            except Exception as e:
                print(f"  [batch {i//BATCH+1}] FAIL: {e}")
                continue
            redirects = (result.get("query") or {}).get("redirects", []) or []
            normalized = (result.get("query") or {}).get("normalized", []) or []
            # Build normalized title map
            norm_map = {n["from"]: n["to"] for n in normalized}
            for r in redirects:
                src = r.get("from")
                tgt = r.get("to")
                if not src or not tgt:
                    continue
                # If src was normalized, also map back
                for orig, ntitle in norm_map.items():
                    if ntitle == src and orig != src:
                        redirect_map[orig] = tgt
                redirect_map[src] = tgt
                resolved += 1
            if (i // BATCH) % 10 == 0:
                print(f"  [batch {i//BATCH+1}/{(len(todo)+BATCH-1)//BATCH}] resolved so far: {resolved}")
                data["redirect_map"] = redirect_map
                META_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Final flush
        data["redirect_map"] = redirect_map
        META_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  done: resolved {resolved} new targets in {time.time()-t0:.1f}s")
        print(f"  redirect_map final: {len(redirect_map)} entries, "
              f"{sum(1 for v in redirect_map.values() if v)} with targets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
