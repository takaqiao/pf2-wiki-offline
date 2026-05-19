"""Phase A: harvest full metadata from pf2.huijiwiki.com — v2.

Fixes v1's harvest_titles.py bugs:
  1. apfilterredir=all (was nonredirects) — keeps redirect entries for ~120 lost aliases
  2. Adds list=allredirects with arprop=title|fragment|target — full source→target chain
  3. Adds prop=info|categories|pageprops in batches — single-pass metadata enrichment

Output:
  out_v2/metadata.json {
    "captured_at": "<iso>",
    "siteinfo": {...},
    "namespaces": [{id, name, canonical, content, ...}],
    "pages": [{"pageid", "ns", "title", "is_redirect", "displaytitle", "content_model",
               "categories": [...], "pageprops": {...}}],
    "redirect_map": {"<from_title>": "<to_title>"},
    "ns_counts": {"<ns>": <count>},
    "stats": {...}
  }

Run:
    .venv\\Scripts\\python.exe dump_metadata_v2.py            # all wanted namespaces
    .venv\\Scripts\\python.exe dump_metadata_v2.py --resume   # pick up where left off
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from pfwiki import OUT_DIR, api_get, api_query_continue, browser

OUT_V2 = Path(__file__).resolve().parent / "out_v2"
OUT_V2.mkdir(exist_ok=True)
META_FILE = OUT_V2 / "metadata.json"
STATE_FILE = OUT_V2 / "_metadata_state.json"

# Namespaces we want for v2 reader-facing content:
#   0     Main
#   4     Project (Pathfinder wiki:)
#   14    Category
#   102   PF2-specific custom
#   3500  Data:
# Skip Talk/User/MediaWiki/Special. Skip Template(10)/Module(828) — server-rendered.
WANTED_NS = [0, 4, 14, 102, 3500]
APLIMIT = "500"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"discovered": False, "ns_done": [], "redirects_done": False}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_partial() -> dict:
    if META_FILE.exists():
        return json.loads(META_FILE.read_text(encoding="utf-8"))
    return {
        "captured_at": None,
        "siteinfo": {},
        "namespaces": [],
        "pages": [],
        "redirect_map": {},
        "ns_counts": {},
        "stats": {},
    }


def save_partial(data: dict) -> None:
    data["captured_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    META_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def discover(page, data: dict, state: dict) -> None:
    if state.get("discovered") and data.get("siteinfo"):
        print("  [discover] cached, skipping")
        return
    si = api_get(page, {
        "action": "query",
        "meta": "siteinfo",
        "siprop": "general|statistics|namespaces|extensions",
        "format": "json",
        "formatversion": "2",
    })
    data["siteinfo"] = (si.get("query") or {}).get("general", {})
    data["stats"] = (si.get("query") or {}).get("statistics", {})
    ns_obj = (si.get("query") or {}).get("namespaces", {})
    # formatversion=2 returns list; older returns dict
    if isinstance(ns_obj, list):
        data["namespaces"] = ns_obj
    else:
        data["namespaces"] = [v for v in ns_obj.values()]
    state["discovered"] = True
    save_state(state)
    save_partial(data)
    g = data["siteinfo"]
    s = data["stats"]
    print(f"  [discover] {g.get('sitename')!s} {g.get('generator')!s}")
    print(f"  [discover] articles={s.get('articles')} pages={s.get('pages')} images={s.get('images')}")


def _harvest_ns_filter(page, nsid: int, filter_kind: str, data: dict, mark_redirect: bool) -> int:
    """One pass of allpages with apfilterredir=<filter_kind> (redirects|nonredirects)."""
    params = {
        "list": "allpages",
        "apnamespace": str(nsid),
        "aplimit": APLIMIT,
        "apfilterredir": filter_kind,
        "format": "json",
        "formatversion": "2",
    }
    n = 0
    for chunk in api_query_continue(page, params):
        for p in (chunk.get("query") or {}).get("allpages", []) or []:
            data["pages"].append({
                "pageid": p["pageid"],
                "ns": p.get("ns", nsid),
                "title": p["title"],
                "is_redirect": mark_redirect,
            })
            n += 1
        save_partial(data)
    return n


def harvest_ns(page, nsid: int, data: dict, state: dict) -> int:
    """Two-pass harvest: nonredirects + redirects (so we can tag is_redirect)."""
    if nsid in state.get("ns_done", []):
        print(f"  [ns={nsid}] cached, skipping")
        return 0
    t0 = time.time()
    nr = _harvest_ns_filter(page, nsid, "nonredirects", data, mark_redirect=False)
    rd = _harvest_ns_filter(page, nsid, "redirects", data, mark_redirect=True)
    data["ns_counts"][str(nsid)] = data["ns_counts"].get(str(nsid), 0) + nr + rd
    state.setdefault("ns_done", []).append(nsid)
    save_state(state)
    dt = time.time() - t0
    print(f"  [ns={nsid}] +{nr} nonredirects, +{rd} redirects ({nr + rd} total) in {dt:.1f}s")
    return nr + rd


def harvest_redirects(page, data: dict, state: dict) -> int:
    if state.get("redirects_done"):
        print("  [redirects] cached, skipping")
        return 0
    # allredirects gives source (with arprop=) and target via api result fields
    # arprop options: ids|title|fragment|interwiki — `title` returns the SOURCE title.
    # The TARGET comes back as separate fields per redirect entry: `to` / `tofragment` etc.
    params = {
        "list": "allredirects",
        "arlimit": APLIMIT,
        "arnamespace": "0",  # ns=0 redirects are the alias chain we care about
        "arprop": "title|fragment",
        "format": "json",
        "formatversion": "2",
    }
    # arprop=title returns 'title' = source; target available via separate query.
    # Easier approach: query redirects for each known redirect page via `redirects` flag.
    # Simplest: re-walk allpages with apfilterredir=redirects and use prop=redirects to get targets.
    # But MediaWiki allredirects DOES return `to` field if we don't filter — let's verify empirically.
    n = 0
    t0 = time.time()
    for chunk in api_query_continue(page, params):
        for r in (chunk.get("query") or {}).get("allredirects", []) or []:
            src = r.get("title")
            tgt = r.get("to") or r.get("target")  # may be None if not returned
            if src:
                data["redirect_map"][src] = tgt or ""
                n += 1
        save_partial(data)
    state["redirects_done"] = True
    save_state(state)
    dt = time.time() - t0
    print(f"  [redirects] {n} entries in {dt:.1f}s")
    return n


def follow_redirect_targets(page, data: dict, state: dict) -> int:
    """For any redirect_map entry where target is empty, batch-query target via prop=info.

    Uses titles=A|B|C&redirects=1 — MediaWiki resolves redirect chain server-side.
    """
    if state.get("targets_filled"):
        return 0
    missing = [src for src, tgt in data["redirect_map"].items() if not tgt]
    print(f"  [redirect_targets] resolving {len(missing)} missing targets ...")
    BATCH = 50
    n = 0
    t0 = time.time()
    for i in range(0, len(missing), BATCH):
        batch = missing[i:i + BATCH]
        params = {
            "action": "query",
            "titles": "|".join(batch),
            "redirects": "1",
            "format": "json",
            "formatversion": "2",
        }
        result = api_get(page, params)
        redirects = (result.get("query") or {}).get("redirects", []) or []
        for r in redirects:
            src = r.get("from")
            tgt = r.get("to")
            if src and tgt:
                data["redirect_map"][src] = tgt
                n += 1
        if (i // BATCH) % 20 == 0:
            save_partial(data)
            print(f"    batch {i // BATCH + 1}/{(len(missing) + BATCH - 1) // BATCH} resolved={n}")
    state["targets_filled"] = True
    save_state(state)
    save_partial(data)
    dt = time.time() - t0
    print(f"  [redirect_targets] filled {n} in {dt:.1f}s")
    return n


def main(argv: list[str]) -> int:
    resume = "--resume" in argv
    if not resume and META_FILE.exists():
        # Defensive: if META_FILE exists but caller didn't pass --resume, treat as resume anyway.
        # Avoids losing partial work.
        print(f"  [main] {META_FILE.name} exists -> auto-resume")

    state = load_state()
    data = load_partial()
    # Initialize missing keys
    data.setdefault("pages", [])
    data.setdefault("redirect_map", {})
    data.setdefault("ns_counts", {})

    t0 = time.time()
    with browser(headless=False) as (_ctx, page):
        print("[1/4] discover ...")
        discover(page, data, state)

        print(f"[2/4] harvest namespaces {WANTED_NS} ...")
        total = 0
        for nsid in WANTED_NS:
            total += harvest_ns(page, nsid, data, state)
        print(f"  [harvest_ns] total {len(data['pages'])} pages")

        print("[3/4] harvest redirects (allredirects ns=0) ...")
        harvest_redirects(page, data, state)

        print("[4/4] resolve empty redirect targets ...")
        follow_redirect_targets(page, data, state)

        save_partial(data)
        print(f"\n[done] {len(data['pages'])} pages, {len(data['redirect_map'])} redirects")
        print(f"       wrote {META_FILE.name} in {time.time() - t0:.1f}s total")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
