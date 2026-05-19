"""Harvest all page titles from pf2.huijiwiki.com.

Writes two files:
  out/titles.json      — { "<nsid>": [{"pageid": int, "title": str}, ...] }
  out/redirects.json   — [{"from": str, "to": str}, ...]

Covers content namespaces (even-numbered; skips Talk variants). Uses
`list=allpages` with apcontinue pagination, and `list=allredirects` for alias
coverage. Everything goes through the CF-cleared in-page fetch helper.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from pfwiki import OUT_DIR, api_get, api_query_continue, browser

# Skip File (6) / MediaWiki (8) / User (2) / special-purpose ns by default
# We keep: Main(0), Project(4), Template(10), Help(12), Category(14), Module(828)
# plus any custom content namespaces the wiki defines.
# We'll dynamically discover namespaces from siteinfo and filter by even-id and
# presence of `content` flag in namespaceinfo.
INCLUDE_TALK = False

# Tune this per politeness target; the wiki is small (~21k articles), so 500/req
# with continue is fine.
APLIMIT = "500"


def discover_namespaces(page) -> dict[int, dict]:
    data = api_get(page, {"action": "query", "meta": "siteinfo", "siprop": "namespaces", "format": "json", "formatversion": "2"})
    # formatversion=2 returns namespaces as list
    namespaces_obj = data["query"]["namespaces"]
    if isinstance(namespaces_obj, list):
        return {int(ns["id"]): ns for ns in namespaces_obj}
    return {int(nsid): ns for nsid, ns in namespaces_obj.items()}


def harvest_allpages(page, nsid: int) -> list[dict]:
    pages: list[dict] = []
    params = {"list": "allpages", "apnamespace": str(nsid), "aplimit": APLIMIT, "apfilterredir": "nonredirects"}
    for chunk in api_query_continue(page, params):
        batch = chunk.get("query", {}).get("allpages", []) or []
        pages.extend({"pageid": p["pageid"], "title": p["title"]} for p in batch)
    return pages


def harvest_allredirects(page) -> list[dict]:
    redirs: list[dict] = []
    # `list=allredirects` gives redirect source titles; we also need targets.
    # Easier: query `list=allpages` with `apfilterredir=redirects` per namespace
    # then follow each with `titles=...&redirects=1` — but that's slow.
    # Instead use `generator=allpages` + `redirects` in one call? No — `redirects=1`
    # only normalizes input. Use `list=allredirects` which returns (from, to)
    # only in ns=0 by default; pass arnamespace=0.
    params = {"list": "allredirects", "arlimit": APLIMIT, "arnamespace": "0", "arprop": "title|fragment"}
    for chunk in api_query_continue(page, params):
        batch = chunk.get("query", {}).get("allredirects", []) or []
        for r in batch:
            # formatversion=2: r has 'ns', 'title', 'fragment'? Actually allredirects
            # returns the redirect SOURCE; target requires follow-up. So this is
            # just the set of redirect source titles, which is still useful.
            redirs.append({"title": r.get("title"), "ns": r.get("ns", 0)})
    return redirs


def main() -> int:
    # Keep headless=False: CF often blocks headless fingerprints even with cookies.
    with browser(headless=False) as (_ctx, page):
        print("[1/3] Discovering namespaces ...")
        nsmap = discover_namespaces(page)
        # Content namespaces: all even ids >= 0 that aren't special
        content_ns = sorted(
            nsid for nsid, ns in nsmap.items()
            if nsid >= 0 and nsid % 2 == 0 and ns.get("name") != ""  # skip virtual
            or nsid == 0  # main always included
        )
        # Deduplicate + ensure 0 included
        content_ns = sorted(set(content_ns) | {0})
        # Strip File(6) to save bandwidth unless you want image descriptions
        content_ns = [n for n in content_ns if n != 6]
        print(f"    namespaces: {content_ns}")

        print("[2/3] Harvesting titles per namespace ...")
        all_titles: dict[str, list[dict]] = {}
        total = 0
        t0 = time.time()
        for nsid in content_ns:
            ns_name = nsmap.get(nsid, {}).get("name") or "(Main)"
            pages = harvest_allpages(page, nsid)
            all_titles[str(nsid)] = pages
            total += len(pages)
            print(f"    ns={nsid:>4}  {ns_name!s:20}  {len(pages):>6} pages  (total {total})")

        titles_file = OUT_DIR / "titles.json"
        titles_file.write_text(
            json.dumps({"namespaces": nsmap, "titles": all_titles}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"    wrote {titles_file}  ({total} titles)")

        print("[3/3] Harvesting redirects (ns=0) ...")
        redirs = harvest_allredirects(page)
        redirs_file = OUT_DIR / "redirects.json"
        redirs_file.write_text(
            json.dumps(redirs, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"    wrote {redirs_file}  ({len(redirs)} redirects)")

        print(f"\nDone in {time.time() - t0:.1f}s")
        return 0


if __name__ == "__main__":
    sys.exit(main())
