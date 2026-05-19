"""Dump full wikitext for every page into JSONL, resumable.

Output layout:
  out/wikitext/<nsid>.jsonl       one record per line: {pageid, ns, title, wikitext}
  out/wikitext/_state.json        per-namespace gapcontinue cursor (for resume)

Strategy: `generator=allpages` + `prop=revisions&rvprop=content&rvslots=main`.
Fetches up to 50 pages per API hit. Appends to JSONL as it goes — Ctrl-C safe
as long as you stop between batches. On rerun, skips namespaces marked done
and resumes mid-namespace from the saved continue token.

Run:
    python dump_wikitext.py                  # all content namespaces
    python dump_wikitext.py 0                # only main namespace
    python dump_wikitext.py 0 10 14          # main + Template + Category
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from pfwiki import OUT_DIR, api_get, browser

DUMP_DIR = OUT_DIR / "wikitext"
DUMP_DIR.mkdir(exist_ok=True)
STATE_FILE = DUMP_DIR / "_state.json"

GAPLIMIT = "50"  # max for revisions API

# Namespaces we actually want full wikitext for. Skip noisy/empty ones by default.
DEFAULT_NS = [0, 4, 10, 12, 14, 102, 274, 500, 828, 2300, 2302, 3500]


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def dump_namespace(page, nsid: int, state: dict) -> int:
    """Dump all pages in namespace nsid. Returns number of new pages written."""
    ns_state = state.setdefault(str(nsid), {"done": False, "gapcontinue": None, "count": 0})
    if ns_state.get("done"):
        print(f"    ns={nsid} already done ({ns_state['count']} pages), skipping")
        return 0

    out_file = DUMP_DIR / f"{nsid}.jsonl"
    mode = "a" if ns_state.get("gapcontinue") or out_file.exists() else "w"

    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "allpages",
        "gaplimit": GAPLIMIT,
        "gapnamespace": str(nsid),
        "gapfilterredir": "nonredirects",
        "prop": "revisions",
        "rvprop": "content|ids|timestamp",
        "rvslots": "main",
    }
    if ns_state.get("gapcontinue"):
        params["gapcontinue"] = ns_state["gapcontinue"]

    new_pages = 0
    t0 = time.time()
    with out_file.open(mode, encoding="utf-8", newline="\n") as fout:
        while True:
            data = api_get(page, params)
            pages = (data.get("query") or {}).get("pages", []) or []
            for p in pages:
                revs = p.get("revisions") or []
                wikitext = ""
                rev_id = None
                if revs:
                    slot = (revs[0].get("slots") or {}).get("main") or {}
                    wikitext = slot.get("content", "") or ""
                    rev_id = revs[0].get("revid")
                record = {
                    "pageid": p.get("pageid"),
                    "ns": p.get("ns"),
                    "title": p.get("title"),
                    "revid": rev_id,
                    "wikitext": wikitext,
                }
                fout.write(json.dumps(record, ensure_ascii=False) + "\n")
                new_pages += 1
            ns_state["count"] = ns_state.get("count", 0) + len(pages)

            cont = data.get("continue") or {}
            if "gapcontinue" in cont:
                ns_state["gapcontinue"] = cont["gapcontinue"]
                # Merge any other continue tokens for robustness
                for k, v in cont.items():
                    params[k] = v
                # Persist state each batch so Ctrl-C is safe
                save_state(state)
                # Light pacing — the wiki is small, but be polite
                # (comment out if you need speed)
                # time.sleep(0.1)
            else:
                ns_state["done"] = True
                ns_state["gapcontinue"] = None
                save_state(state)
                break

    dt = time.time() - t0
    print(f"    ns={nsid} done: +{new_pages} pages ({ns_state['count']} total) in {dt:.1f}s -> {out_file.name}")
    return new_pages


def main(argv: list[str]) -> int:
    target_ns = [int(x) for x in argv[1:]] if len(argv) > 1 else DEFAULT_NS
    print(f"Target namespaces: {target_ns}")

    state = load_state()
    with browser(headless=False) as (_ctx, page):
        for nsid in target_ns:
            print(f"[ns {nsid}]")
            dump_namespace(page, nsid, state)

    print("\nAll done.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
